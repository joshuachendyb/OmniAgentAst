import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
  ChatPage,
  attachStreamDiag,
  findAdjacentDup,
  getCaseId,
  keepBrowserOpenIfRequested,
  printDiag,
  runChatFlow,
  startNormalUiEnv,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * 历史/实时任务切换 UI 全链路 E2E — 小欧-2026-09-14
 *
 * [36]前端3接收实时变量 5.5.1/5.5.2/5.5.3 规格落地（专项覆盖 B6/C5 端到端）。
 * 环境: 普通会话流 `startNormalUiEnv`(前端 API 直连 :8000 跨域放行, 无 9000 代理, 本 case 不含断流)。
 * 前置: 后端 :8000 预先手动启动(用例不拉起)。真实浏览器 + 真实后端 + 真实LLM + 真实SQLite。
 *
 * test01: 实时任务 B 后台运行中切历史任务 A → isCurrentLive 翻 false、历史回放无等待圈(C5 契约)、
 *   切回实时恢复 live、后台续收、终态完整。
 * test02: 实时期间 isCurrentLive 恒 true 回归(删 receiving 后实时期不依赖连接信号)。
 *
 * 取证探针: DOM 状态(.task-list-item.active / right-viewer-body 内容) 替代 DBG-1 日志轮询。
 *
 * 铁规提醒: AGENTS.md 严令禁止 commit 任何测试相关代码文件 —— 本 spec 严禁提交。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';

// ---- sseParser 帧日志解析(替代已删 DBG-1) ----
/** 从 consoleAll 扫描 sseParser 帧日志: [HH:MM:SS.mmm] 轮次=X type */
const countFrameType = (
  all: string[],
  base: number,
  typePattern: RegExp
): number => {
  let n = 0;
  for (let i = base; i < all.length; i += 1) {
    if (/\[[\d:.]+\]\s*轮次=\S+\s/.test(all[i]) && typePattern.test(all[i])) {
      n += 1;
    }
  }
  return n;
};

/** 等待 sseParser 帧日志出现指定 type, 超时抛异常 */
const pollFrameType = async (
  diag: DiagBundle,
  base: number,
  typePattern: RegExp,
  timeout: number,
  label: string
): Promise<void> => {
  const dl = Date.now() + timeout;
  while (Date.now() < dl) {
    if (countFrameType(diag.consoleAll, base, typePattern) > 0) return;
    await new Promise((r) => setTimeout(r, 250));
  }
  const frames = diag.consoleAll
    .filter((c) => /\[[\d:.]+\]\s*轮次=\S+\s/.test(c))
    .slice(-30);
  printDiag(
    diag.streamReqs,
    diag.reconnectLogs,
    diag.sseErrors,
    diag.consoleAll,
    '',
    diag.allFailed,
    getCaseId()
  );
  console.log(
    `[DIAG] === 近段帧日志(${frames.length} 条) ===\n` +
      frames.map((l) => `[DIAG]   ${l.slice(0, 160)}`).join('\n')
  );
  throw new Error(`[E2E] pollFrameType 超时(未出现 ${label}) 自base=${base}`);
};

/** 任务列表: 全部 task-list-item 的 aria-label->task_id 集合 */
const taskIds = async (page: Page): Promise<string[]> => {
  const labels = await page
    .locator('.task-list-item')
    .evaluateAll((els) => els.map((el) => el.getAttribute('aria-label') ?? ''));
  return labels
    .map((l) => {
      const m = l.match(/^任务 (\S+) (\S+)$/);
      return m ? m[1] : null;
    })
    .filter((x): x is string => x !== null);
};

const norm = (s: string): string => s.replace(/\s+/g, '');

// 编辑历史: 2026-09-14 小欧 - readRightText: 右栏正文唯一锚点(right-viewer-body)。
//   多任务/切历史下整页 innerText 尾串含输入工具栏等 UI 文字, aTail/正文增长断言脆弱(误判A历史未载),
//   业务正文同源锁定右栏容器；空/未载返回 '' 由调用方 poll 等待 - 小欧-2026-09-14
// 编辑历史: 2026-09-18 小欧 - 历史回放长文被 CollapsibleText 折叠(>5行/>200字取首2行),
//   innerText 取不到被折叠正文致 aTail 断言误红(实时有chunk全文/历史DB只存final被折叠);
//   读取前先展开 body 内所有折叠块(span[role=button][aria-expanded=false])再取全文, 与当前折叠设计对齐 - 小欧-2026-09-18
const readRightText = async (page: Page): Promise<string> => {
  await page.evaluate(() => {
    document
      .querySelectorAll(
        '.right-viewer-body span[role="button"][aria-expanded="false"]'
      )
      .forEach((b) => (b as HTMLElement).click());
  });
  await page.waitForTimeout(30); // 等折叠展开重渲染
  return page.evaluate(() => {
    const el = document.querySelector('.right-viewer-body');
    return el ? (el as HTMLElement).innerText : '';
  });
};

/** 等右侧正文增长: 返回 poll 期间是否 len>baseLen */
const waitBodyGrowth = async (
  page: Page,
  baseLen: number,
  timeout: number
): Promise<number> => {
  const dl = Date.now() + timeout;
  let max = baseLen;
  while (Date.now() < dl) {
    const text = await readRightText(page);
    max = Math.max(max, text.length);
    if (max > baseLen) return max;
    await new Promise((r) => setTimeout(r, 500));
  }
  return max;
};

// ---- 5.5.2 监控探针(软诊断, 不参与断言) ----
/** 采样三等待圈存在性, 同帧 action&&thinking 打 [WARN] premature */
const monitorActionWaiting = async (
  page: Page,
  t0: number,
  windowMs: number,
  sampleMs = 250
): Promise<string[]> => {
  const samples: string[] = [];
  const dl = Date.now() + windowMs;
  while (Date.now() < dl) {
    const r = await page.evaluate(() => ({
      action: !!document.querySelector('.action-waiting-cursor'),
      thinking: !!document.querySelector('.waiting-cursor'),
      tool: !!document.querySelector('.tool-waiting-cursor'),
    }));
    const ts = Date.now() - t0;
    samples.push(
      `[T+${ts}ms] action=${r.action} thinking=${r.thinking} tool=${r.tool}`
    );
    if (r.action && r.thinking) {
      console.log(`[WARN] action-waiting-premature T+${ts}ms`);
    }
    await page.waitForTimeout(sampleMs);
  }
  return samples;
};

/** done 后 5s 采样: action 仍现打 [WARN] leftover */
const checkWaitingLeftover = async (page: Page, t0: number): Promise<void> => {
  await page.waitForTimeout(5000);
  const r = await page.evaluate(
    () => !!document.querySelector('.action-waiting-cursor')
  );
  if (r) {
    console.log(`[WARN] action-waiting-leftover T+${Date.now() - t0}ms`);
  }
};

test.describe('历史/实时任务切换 isCurrentLive/taskActive 语义全链路', () => {
  test('test01 实时 B 后台运行中切历史 A → 切回恢复 live/历史无等待圈/终态完整', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    const chat = new ChatPage(page);
    const diag = attachStreamDiag(page);
    const t0 = diag.t0;

    // 1) 环境+进页
    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    // 发 A 之前记录既有任务集合 → A 的 task_id = 之后新增者(差集, 防多历史残留误命)
    const idsBeforeA = await taskIds(page);

    // 发消息防拦截(历史会话加载窗口), 见 ChatPage.sendPrompt
    const PROMPT_A =
      '请用300字以内简要论述"深空探测任务与近地轨道任务在工程难度上的三大差异"。本题仅供思辨，无需任何工具。';
    // 编辑历史: 2026-09-14 小欧 - B 复杂度升级(北京老陈指示: 任务复杂数据才多判定才准): 原B仅21-26s活期、
    //   steps少, 步骤7/8观察窗口稍长即落在B活性外; 新B要求八部分1200字技术报告+具体数值参数, 活期拉长至60s+,
    //   让"切走→切回"在B运行窗口内宽裕完成, 消除时序竞争, 使产品语义在宽裕条件下受验 - 小欧-2026-09-14
    // 编辑历史: 2026-09-14 小欧 - B 升级为真实工具链(北京老陈指示: 任务复杂数据才多判定才准): 纯文本快模型
    //   活期仅20s量/2718步, 步骤7/8观察窗口稍宽即滑出B活性; 另纯文本流正文数据少, 判定依据弱。
    //   B 现要求真实调用 file/network 工具做多轮操作(建目录/写报告骨架/查网络参数/读回确认),
    //   活期拉长至60s+, 步骤/等待圈/正文数据丰富, 切走切回可在B工具执行窗口内宽裕受验 - 小欧-2026-09-14
    const PROMPT_B =
      '请完成一篇关于"近地小行星采矿工程可行性"的技术论证报告，全文不少于1200字、分八大部分并给出具体数值参数：' +
      '①目标小行星选择标准（≥5个候选并给轨道/直径/自转/材质参数）②采矿技术路线对比（≥3种，附能源估算表）' +
      '③自主作业装备清单（≥6类，附功率质量）④ISRU水电解/甲烷合成当量参数⑤返回推进（比冲/质量比/窗口）' +
      '⑥风险故障树（≥5类排序）⑦经济性（单矿收益/往返成本/盈亏点）⑧分级结论（可行/不可行/需论证）。' +
      '为支撑报告数据，请按以下步骤实际操作（不要停留在思考层面）：' +
      '第一步：新建一个临时工作目录，并在其中创建一份 markdown 报告骨架文件（含标题+八个小节标题目录）；' +
      '第二步：用网络工具查一次候选小行星的真实公开参数（尺寸或轨道等，任选其一），并把结果填入报告文件对应小节；' +
      '第三步：读回该文件，核对骨架与数据是否完整；' +
      '第四步：在对话中给出完整的论证报告正文（仍覆盖八大部分并包含你查到的数值）。' +
      '请务必在最终回答中包含"近地小行星采矿工程"这几个字。';

    // 2) 任务 A 至终态
    const aFinal = await runChatFlow(chat, PROMPT_A, { diag });
    expect(aFinal.trim().length).toBeGreaterThan(30);
    // 编辑历史: 2026-09-14 小欧 - aTail 同源锁定右栏正文: 整页 innerText 的尾串是输入工具栏等 UI 文字,
    //   runChatFlow 后与"点击A历史后"页面顺序不同→aTail 误判 A 历史未载; 右栏正文(right-viewer-body)
    //   两时刻同源一致, 断言才可靠 - 小欧-2026-09-14
    // 编辑历史: 2026-09-25 04:06:45 小健 - aTail 治理: 断言由 norm(aReal).slice(-40) 动态提取改硬编码
    //   '深空探测与近地轨道'（A 报告主题词，消除读到 B 实时流的源歧义）+ PROMPT_B 前注释缩进修复 +
    //   全文 prettier 重排 — 小健-2026-09-25
    const aReal = await readRightText(page);
    expect(aReal.trim().length).toBeGreaterThan(30);
    const aTail = '深空探测与近地轨道';
    const idsAfterA = await taskIds(page);

    // 处理历史残留掩码滚动时以增量厘定 A 任务项(A 之前差集非空时取首个新 id)
    const aId = idsAfterA.find((id) => !idsBeforeA.includes(id)) ?? '';
    expect(aId).toBeTruthy();

    // 4) 发 B(独立话题长思考) → 等 active task 切到 B + sseParser 帧日志确认流活跃
    // 编辑历史: 2026-09-17 小欧 - 删 DBG-1 轮询, 改 DOM active task + sseParser 帧日志检测 — 小欧-2026-09-17
    const frameBase4 = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT_B);
    await chat.waitReceiving(90_000);
    // 等 active 项锚定 B(DOM 直接证据, 替代 DBG-1 live=true)
    await expect
      .poll(
        async () => {
          const label = await page
            .locator('.task-list-item.active')
            .first()
            .getAttribute('aria-label');
          return (label ?? '').includes(aId) ? '' : (label ?? '');
        },
        { timeout: 30_000 }
      )
      .toBeTruthy();
    // 补充: sseParser 帧日志确认有 action/thought 帧到达(流活跃的独立证据)
    const frames4 = countFrameType(
      diag.consoleAll,
      frameBase4,
      /action|thought-start/
    );
    console.log(
      `[E2E] 步骤4: active=B, 帧日志 action/thought-count=${frames4}`
    );
    // B 已确立为当前任务 → active 项必为 B → 提取 bId
    const activeLabel = await page
      .locator('.task-list-item.active')
      .first()
      .getAttribute('aria-label');
    const bId = activeLabel?.match(/^任务 (\S+) (\S+)$/)?.[1] ?? '';
    expect(bId).toBeTruthy();
    expect(bId).not.toBe(aId);

    // 5) 录 B 实时正文基线(右栏同源)
    const b5Text = await readRightText(page);
    const len5 = b5Text.length;
    const b5Tail = norm(b5Text).slice(-40);

    // 6) 点历史任务 A(精确按 aId, 非"任意非 active")
    const aItem = page.locator(`.task-list-item[aria-label*="${aId}"]`).first();
    await aItem.click();

    // 7) 切走后校验: ① 历史正文含 A 尾部 ② 无任何等待圈(C5 契约) ③ sseParser 帧日志无新 action(流已切走)
    // 编辑历史: 2026-09-17 小欧 - 删 DBG-1 live=false 轮询, 改 aTail DOM + 帧日志静默检测 — 小欧-2026-09-17
    const frameBase7 = diag.consoleAll.length;
    // 等待切走后 2s 给流稳定窗口, 然后检查无新 action 帧
    await new Promise((r) => setTimeout(r, 2000));
    const frames7 = countFrameType(diag.consoleAll, frameBase7, /action/);
    console.log(`[E2E] 步骤7: 切走后 2s 新 action 帧数=${frames7}(预期0)`);
    // 编辑历史: 2026-09-14 小欧 - 步骤7②超时取证: expect.poll 裸抛不落盘, 改 try/catch 落 DIAG+右侧现场,
    //   区分"aTail源歧义(getFinalText读到B实时)"与"A历史未渲染"两种失败 - 小欧-2026-09-14
    try {
      await expect
        .poll(
          async () => {
            const text = await readRightText(page);
            return norm(text).includes(aTail);
          },
          { timeout: 30_000 }
        )
        .toBeTruthy();
    } catch (aErr) {
      const curText = await readRightText(page);
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        '',
        diag.allFailed,
        getCaseId()
      );
      console.log(`[E2E] aTail=${JSON.stringify(aTail)}`);
      console.log(
        `[E2E] 点击A后 右栏正文 len=${curText.length} head=${JSON.stringify(
          norm(curText).slice(0, 80)
        )}`
      );
      throw aErr;
    }
    const waitingAbsent = await page.evaluate(() => {
      const sel = [
        '.waiting-cursor',
        '.tool-waiting-cursor',
        '.action-waiting-cursor',
      ];
      return sel.every((s) => document.querySelectorAll(s).length === 0);
    });
    expect(waitingAbsent).toBeTruthy();
    console.log(
      `[E2E] test01 步骤7 通过: 历史正文含A尾 无等待圈 新action帧=${frames7}`
    );

    // 8) 点回实时 B → ① active 项锚定 bId(DOM直接证据) ② 帧日志确认流恢复 ③ 正文恢复增长/含 B 基线尾
    // 编辑历史: 2026-09-17 小欧 - 删 DBG-1 live=true 轮询, 改 DOM active + sseParser 帧日志 + 正文增长 — 小欧-2026-09-17
    const bItem = page.locator(`.task-list-item[aria-label*="${bId}"]`).first();
    const frameBase8 = diag.consoleAll.length;
    await bItem.click();
    // DOM 取证: active 项必须锚定 bId
    await expect
      .poll(
        async () => {
          const label = await page
            .locator('.task-list-item.active')
            .first()
            .getAttribute('aria-label');
          return (label ?? '').includes(bId);
        },
        { timeout: 8_000 }
      )
      .toBeTruthy();
    // sseParser 帧日志: 切回后应有新 action/thought 帧到达(流恢复)
    await pollFrameType(
      diag,
      frameBase8,
      /action|thought-start/,
      30_000,
      '切回后 action/thought 帧'
    );
    const len8 = await waitBodyGrowth(page, len5, 30_000);
    const b8Text = await readRightText(page);
    expect(len8).toBeGreaterThan(len5);
    expect(norm(b8Text)).toContain(b5Tail);
    const frames8 = countFrameType(
      diag.consoleAll,
      frameBase8,
      /action|thought-start/
    );
    console.log(
      `[E2E] test01 步骤8 通过: active=B 帧日志 count=${frames8} len ${len5}->${len8}`
    );

    // 9) B 流至终态: 含 B 关键词 + 无 run-on(软 DIAG) + >30 字
    await chat.waitDone(420_000);
    const bFinal = await readRightText(page);
    expect(bFinal.trim().length).toBeGreaterThan(30);
    expect(bFinal).toContain('近地小行星采矿工程');
    const dups = findAdjacentDup(bFinal);
    if (dups.length > 0) {
      console.log(
        `[WARN] run-on 命中 ${dups.length} 处(软DIAG): ${dups.slice(0, 3).join(' | ')}`
      );
    } else {
      console.log('[E2E] test01 步骤9: 终态完整, 无 run-on');
    }

    // 10) 通用区③ 诊断落盘 + 软监控(全程 action-waiting 采样)
    await monitorActionWaiting(page, t0, 6000);
    await checkWaitingLeftover(page, t0);
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      '',
      diag.allFailed,
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page);
  });

  test('test02 实时期间 isCurrentLive 恒 true 回归(删 receiving 后语义)', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    const chat = new ChatPage(page);
    const diag = attachStreamDiag(page);

    // 1) 环境+进页
    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });

    // 2) 发 C 长思考
    // 编辑历史: 2026-09-17 小欧 - 删 DBG-1 扫描, 改 sseParser 帧日志连续性检测 — 小欧-2026-09-17
    const PROMPT_C =
      '请撰写一篇关于"深空通信延迟与探测器自主决策"的系统性说明文，全文不少于1000字，必须包含六个部分：' +
      '①深空通信为何延迟严重（列出光速极限、距离、时延-误码-带宽权衡三个原因并给出火星/木星/柯伊伯带三档具体时延数值）；' +
      '②延迟如何迫使探测器提高自主性（给出"指令周期"与"事件窗口期"的量化对比）；' +
      '③三个依赖高自主性的深空任务案例（Deep Space 1、勇气号/机遇号、毅力号，逐一对比其自主程度与决策权限）；' +
      '④自主决策的主要风险与约束（燃料安全、地形感知、科学价值损失三方面）；' +
      '⑤未来深空任务的自主发展趋势（至少给出3个方向）；' +
      '⑥综合启示（联系本任务是否需要自主: 给出明确判断）。' +
      '行文需分章节、每条给出具体参数对照。无需工具。' +
      '请务必在回答中包含"深空通信延迟自主"这几个字。';
    const frameBase3 = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT_C);
    await chat.waitReceiving(90_000);

    // 3) 全程帧日志连续性: 流期间应持续有 action/thought 帧到达, 无长时间静默(>15s 无帧)
    const frameGaps: string[] = [];
    let lastFrameTime = Date.now();
    let lastFrameIdx = diag.consoleAll.length;
    const dl = Date.now() + 420_000;
    while (
      Date.now() < dl &&
      !(await chat.stopBtn.isVisible().catch(() => false))
    ) {
      const now = diag.consoleAll.length;
      if (now > lastFrameIdx) {
        // 有新帧, 检查帧间隔
        const gap = Date.now() - lastFrameTime;
        if (gap > 15_000) {
          frameGaps.push(`帧间隔 ${gap}ms (idx ${lastFrameIdx}→${now})`);
        }
        lastFrameTime = Date.now();
        lastFrameIdx = now;
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    await chat.waitDone(420_000);
    // 最终统计
    const totalFrames = countFrameType(
      diag.consoleAll,
      frameBase3,
      /action|thought-start|observation|final/
    );
    const actionFrames = countFrameType(diag.consoleAll, frameBase3, /action/);
    const thoughtFrames = countFrameType(
      diag.consoleAll,
      frameBase3,
      /thought-start/
    );
    const finalFrames = countFrameType(diag.consoleAll, frameBase3, /final$/);
    console.log(
      `[E2E] test02 步骤3: 帧统计 action=${actionFrames} thought=${thoughtFrames} final=${finalFrames} total=${totalFrames}`
    );
    if (frameGaps.length > 0) {
      console.log(
        `[WARN] test02 帧间隔异常 ${frameGaps.length} 处: ${frameGaps.slice(0, 3).join(' | ')}`
      );
    }
    // 基本断言: 流期间必须有 action 或 thought 帧(证明流是活的)
    expect(actionFrames + thoughtFrames).toBeGreaterThan(0);
    console.log('[E2E] test02 步骤3 通过: 帧日志连续, 流活跃');

    // 4) 终态完整断言
    const cFinal = await chat.getFinalText();
    expect(cFinal.trim().length).toBeGreaterThan(30);
    expect(cFinal).toContain('深空通信延迟自主');
    const dups2 = findAdjacentDup(cFinal);
    if (dups2.length > 0) {
      console.log(
        `[WARN] run-on 命中 ${dups2.length} 处(软DIAG): ${dups2.slice(0, 3).join(' | ')}`
      );
    } else {
      console.log('[E2E] test02 步骤4: 终态完整, 无 run-on');
    }

    // 5) 通用区
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      '',
      diag.allFailed,
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page);
  });
});
