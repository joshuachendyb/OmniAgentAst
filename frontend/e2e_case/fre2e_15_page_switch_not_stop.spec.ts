import { test, expect } from '@playwright/test';
import {
  ChatPage,
  activeTaskId,
  attachStreamDiag,
  counterFailMsg,
  getCaseId,
  getTodayLogPath,
  keepBrowserOpenIfRequested,
  logBaseOf,
  printDiag,
  readLogSince,
  readStepCounter,
  sessionIdFromUrl,
  startNormalUiEnv,
  statusOfTask,
  waitCounterIncreases,
} from '../e2e_front_lib';
import type { DiagBundle } from '../e2e_front_lib/stream-diag';

/**
 * E2E-15 新会话·任务执行中·点菜单切走再切回·验页面切走 ≠ 点「停止」
 *
 * 做什么: 发一条长任务, 等它执行中, 点菜单「历史会话」切到 /history, 再点「对话任务」切回 /。
 *   全程不刷新、不关浏览器、不新建会话。
 * 断什么: 「我不看了」≠「我要停止」。切走只是卸掉视图, 不得顺手把后台任务也停掉。
 * 判据: 切走时零 abort、零 DELETE /chat/*、零 clearSteps/clearCompleted,
 *      后端 status 仍是 executing, 日志无该 task 的 cancel;
 *      切回后原 taskId 还在列表、切走前的轮次一个不少、任务还在跑时「停止」按钮可见;
 *      点「停止」后才发取消。
 *
 * 编辑历史: 原名 close_view_not_stop, 正文写「关闭视图」。那词出自 [63] 1091/1106 行
 *   (与取消订阅/停止任务/删除会话并列的四个动作), 不是自造, 但没落到 UI 上, 场景说不准。
 *   故全改用 UI 实际文案 —— 2026-10-01 小欧。
 * 刷新不在本 case 范围, 由 14/16/17 覆盖。
 * 铁规: AGENTS.md 禁止 commit 测试文件。
 */

const FRONTEND_DIR = 'F:\\OmniAgentAs-repair\\frontend';
const BACKEND_DIR = 'F:\\OmniAgentAs-repair\\backend'; // 可用切走页只有 /history 与 /settings2: App.tsx 只注册 `/` `/history` `/settings2` `/login`,
//   /shortcuts、/files、/knowledge 都落到 `path="*"` 兜底渲染 ChatPage = 切了等于没切。
const AWAY_MENU_TEXT = '历史会话';
const AWAY_URL_PATH = '/history';

/**
 * 2026-10-01 小欧 编辑历史: 本文件原有本地 helper `latestTaskStatus`(走 `latest_task_id` 取
 *   "会话里最新的那个任务"), 已**删除**, 改用 lib 的 `statusOfTask`(按 task_id 精确查)。
 *   理由(北京老陈裁定口径统一): 本 case 的判据是"**这个**任务切走时还在不在跑",
 *   一旦系统挑错了任务(正是 fre2e_17 要抓的 bug), 用 latest 的 helper 会跟着挑错,
 *   断言跟着一起绿 —— 恰好把要抓的缺陷放过去。latest 语义就此废止。
 * 另: 本地 `activeTaskId` 与 16/17 的实现逐字相同, 已删改为引用 lib/page-anchors。
 */

/**
 * 2026-10-01 小欧 编辑历史: 本文件原有本地的 readStepCounter / waitCounterIncreases,
 *   已删除改为从 e2e_front_lib/step-counter 统一引用 —— 北京老陈要求 4 个 case 判同一件事
 *   (切回任务页后计数器还在不在数、step 还在不在显示), 计数器全项目只渲染一处,
 *   四份拷贝必然走偏, 故收进公用库。锚点/正则口径见该文件注释。
 */

/**
 * 2026-10-01 小欧 编辑历史: **删除本地 `resolveSessionIdByPrompt`(按 prompt 片段反查会话)**。
 *
 * 删除理由(该函数原注释的假设已被实测证伪): 它注释写「用 PROMPT 的唯一片段匹配, 既能拿到 id
 * 又能确认拿的是**本次**任务的会话(不会串到别的会话)」—— **错**。它取
 * `GET /sessions?page=1&page_size=50` 后用 `find` 取**第一个** title 含该片段的会话,
 * 而本 case 的 PROMPT 固定为「近地小行星采矿工程」, 库里已堆积 20+ 个同名会话
 * (反复跑 case 所致), `find` 必然命中**旧**会话。
 * 2026-10-01 实测: 新建会话 f2f56890 / task 0e6b3d55 均正确, 但反查返回旧会话 ed2ac24d,
 * 导致 `statusOfTask(ed2ac24d, 0e6b3d55)` → `__not_found__` → 判据①假红。
 * 这与 5.5 节纪律第 3 问同型: 把「应该成立」当成「已经成立」。
 *
 * 改法: 改用 `sessionIdFromUrl(page)`。上一环节已调 `chat.newSession()`, 它内部
 * `waitForURL(/[?&]session_id=/)` **已保证地址栏带本次新建的 session_id**, 故直接取 URL 即可,
 * 且**结构上不可能串到别的会话**(不像反查是"猜")。
 */

const seenRounds = (all: string[], base: number): number[] => {
  const out: number[] = [];
  for (let i = base; i < all.length; i += 1) {
    const m = all[i].match(/轮次=(\d+)/);
    if (m) {
      const n = Number(m[1]);
      if (!out.includes(n)) out.push(n);
    }
  }
  return out;
};

test.describe('[63] P6 红线 · 切到历史会话页 ≠ 点停止按钮', () => {
  test('操作①点菜单「历史会话」切走(不刷新): 零abort/零clear/status仍executing/回会话页仍在跑; 操作②点「停止」按钮: 才cancel', async ({
    page,
  }) => {
    test.setTimeout(600_000);

    const chat = new ChatPage(page);
    const diag: DiagBundle = attachStreamDiag(page);
    const BLOG = getTodayLogPath(BACKEND_DIR);

    await startNormalUiEnv(FRONTEND_DIR);
    await chat.gotoChat();
    // 2026-10-01 小欧: 显式新建会话。gotoChat() 裸 URL 会命中 useChatSession 场景3 自动加载
    //   "最近会话" → 连续跑轮次时消息落进上一轮残留会话, URL 不带 id、task 数累积, 判据失效。
    await chat.newSession();
    await expect(chat.input).toBeVisible({ timeout: 60_000 });
    const logBase = logBaseOf(BLOG);

    const PROMPT =
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

    const frameBase0 = diag.consoleAll.length;
    await chat.sendPrompt(PROMPT);
    try {
      await chat.waitReceiving(90_000);
    } catch (e) {
      printDiag(
        diag.streamReqs,
        diag.reconnectLogs,
        diag.sseErrors,
        diag.consoleAll,
        readLogSince(BLOG, logBase),
        diag.allFailed,
        getCaseId()
      );
      throw e;
    }

    // 等到 ≥2 轮, 让"操作①"落在任务中段
    const dl = Date.now() + 240_000;
    while (
      Date.now() < dl &&
      seenRounds(diag.consoleAll, frameBase0).length < 2
    ) {
      await page.waitForTimeout(500);
    }
    const taskId = await activeTaskId(page);
    // session_id 直接取地址栏: 上面 newSession() 已 waitForURL 保证带本次新建的 id, 无歧义。
    //   (原按 prompt 片段反查, 已被实测证伪会串到同名旧会话 —— 见本文件 resolveSessionIdByPrompt 删除记录)
    const sessionId = sessionIdFromUrl(page);
    if (!sessionId) {
      throw new Error(
        `[E2E] URL=${page.url()} 取不到 session_id —— 本 case 判据全靠 session_id 查 DB 状态。` +
          `newSession() 是否生效? 不当通过处理`
      );
    }
    expect(taskId).toBeTruthy();
    const statusBefore = await statusOfTask(sessionId, taskId);
    console.log(
      `[E2E] 操作前: task=${taskId} session=${sessionId} status=${statusBefore}`
    );
    // 2026-10-01 小欧 [1]: 操作①/② 都以「任务在飞」为前提(见下文 statusBefore 硬校验)。
    //   若此刻已自然终态, 后面两条判据都无从验证, 提前显式报错, 不带着失效前提往下跑。
    if (statusBefore !== 'executing') {
      throw new Error(
        `[E2E] 前置不成立: 发完消息等 ≥2 轮后 status=${statusBefore} 不是 executing —— ` +
          `「任务执行中切走」「点停止才cancel」都需要任务在飞。请重跑 —— 不当通过处理`
      );
    }

    // 基线: 切走前把顶栏计数器(轮/步)读下来, 切回后要与它比 —— 北京老陈要求:
    //   「切回任务页后那个计数器还在不在正常计数、step 还在不在正常显示」。
    const counterAtAway = await readStepCounter(page);
    console.log(
      `[E2E] 切走前计数器: ${counterAtAway ? `轮=${counterAtAway.rounds} 步=${counterAtAway.steps}` : '(读不到)'}`
    );
    // 读不到就是缺陷本身(任务在跑却没有信息带), 不放过
    if (!counterAtAway) {
      throw new Error(
        `[E2E] 切走前读不到顶栏计数器(.taskinfo-bar 里的 轮/步) —— ` +
          `任务在飞却看不到计数, 本身就是问题。请重跑确认 —— 不当通过处理`
      );
    }
    expect(counterAtAway.steps).toBeGreaterThan(0);

    // ══ 操作①: 点菜单「历史会话」切走(离开会话页), 不点「停止」 ══
    const reqBase1 = diag.streamReqs.length;
    const failBase1 = diag.allFailed.length;
    const logBase1 = logBaseOf(BLOG);

    // 2026-10-01 小欧 — **修复假通过**(headed 人工复核, 北京老陈"看不到页面切换"发现):
    //   原实现切走与切回**都点「对话任务」**, 而 [63]第八章(2026-09-30 v1.42/v1.43)已把该项
    //   改为"显式带回当前 session_id" → 两次落点同一个 `/?session_id=<当前>`, **页面从未真正离开会话页**。
    //   于是"切走不停止任务"这条红线根本没被触发, 断言全在同一页面内自然通过。
    //   本 case 切走改用「历史会话」(/history) —— 与 fre2e_13 的 /settings2 分派到不同页面,
    //   避免两个 case 只覆盖同一条切换路径(北京老陈裁定: 4 个 case 分派不同切走页面)。
    //   注: /shortcuts、/files、/knowledge 不能用 —— App.tsx 只注册 `/` `/history` `/settings2`
    //   `/login`, 这三个落到 `path="*"` 兜底渲染 ChatPage, URL 变了但页面没变。
    const urlAtAway = page.url();
    await page
      .locator('.ant-menu-item', { hasText: AWAY_MENU_TEXT })
      .first()
      .click();
    // 2026-10-01 小欧 [2] 北京老陈: 什么算通过要真实 —— 把"点完菜单干等 6 秒再看一眼"改成
    //   **显式观察窗**: 在窗口内持续盯着"任务级资源"是否被动(DELETE / cancel / abort)。
    //   为什么必须这样: 固定 sleep 只覆盖"6 秒内发生"的情形。若产品把清理挂在定时器/防抖上
    //   (例如切走 10s 后才发 DELETE), sleep 6s 后立刻断言 → 请求还没发 → 断言通过 → **假通过**。
    //   这正是本 case 红线要抓的那类缺陷, 用固定 sleep 去抓它自相矛盾。
    //   窗口 20s: 覆盖防抖/短定时器; 代价是本 case 多花 14s, 换判据真实, 值。
    const AWAY_OBSERVE_MS = 20_000;
    const dlObserve = Date.now() + AWAY_OBSERVE_MS;
    while (Date.now() < dlObserve) {
      await page.waitForTimeout(1000);
      // 观察期内若任务自己跑完了, 后面的 status 判据就没有"在飞"可言了, 提前如实报错
      const stMid = await statusOfTask(sessionId, taskId);
      if (stMid !== 'executing') {
        throw new Error(
          `[E2E] 操作① 观察窗内任务已离开 executing(status=${stMid}) —— ` +
            `「切走时任务仍在跑」无法验证(它是自己跑完的, 不是被切走害的)。请重跑 —— 不当通过处理`
        );
      }
    }
    // 防假通过硬断言: 视图必须真的关闭(URL 变了且落在目标页), 否则后续红线断言全部空转
    const urlAfterAway = page.url();
    console.log(`[E2E] 操作① 切走: ${urlAtAway} -> ${urlAfterAway}`);
    expect(urlAfterAway).not.toBe(urlAtAway);
    expect(urlAfterAway).toContain(AWAY_URL_PATH);
    // 2026-10-01 小欧 [1] 编辑历史: 此前我曾在切走之后插入 `page.reload()`, 想让本 case
    //   也覆盖"刷新"。**已撤销**, 理由有二:
    //     ① 语义冲突 —— 本 case 的红线是「切到历史会话页 ≠ 停止任务」, 验的是**点菜单切走**时
    //        不误 abort/不误 DELETE/status 不被误改; "刷新"是另一条初始化分支(场景3),
    //        塞进来会让本 case 同时守两件事, 一红就分不清是谁的锅。
    //     ② 与其他 case 重复 —— 刷新由 fre2e_14(URL带id)/fre2e_16(无taskId)/fre2e_17(旧会话)
    //        各守其位, 本 case 不重复守。
    //   故此处恢复原状: 切走 →(离开中段断言)→ 切回, 不做刷新。

    // ①a abort **只记录不判红** —— 2026-10-01 小欧 修订(北京老陈指令"一次性改好"):
    //   原 `expect(aborts).toEqual([])` 是**代理指标选错**, 100% 假红。abort 有两个来源,
    //   在浏览器里长得一模一样(net::ERR_ABORTED), 效果却相反:
    //     · 切页 → 组件卸载 → cleanup 调 abortController.abort() → 技术性关连接, 任务照跑
    //     · 点「停止」→ stop() → 取消任务                                    → 业务性停任务
    //   该判据既拦下正确的切页行为, 又在真出问题时拦不住(abort 总会发生)。实测取证
    //   (2026-10-01 首跑): 切走产生 1 次 abort, 而该 task 的 DB 仍 status=executing、
    //   end_time=None、事件流水续涨至 seq=3427(3397 个 chunk) —— 任务在后台跑到底,
    //   完全符合后端设计(stream_orchestrator.py:617-620「客户端断开: 静默返回, agent 后台继续」)。
    //   若切页**没有** abort 反而可疑(说明连接泄漏)。真命题「切走≠停任务」由下方
    //   观察窗 20s 持续 `status==='executing'` 硬判据 + ①g 切回后计数器续涨共同承担。
    const aborts = diag.allFailed
      .slice(failBase1)
      .filter((l) => /ERR_ABORTED|ABORTED/i.test(l));
    console.log(
      `[E2E] 操作① 新增请求失败=${diag.allFailed.length - failBase1} 其中abort=${aborts.length}` +
        `(abort 不判红: 切页组件卸载必触发, 与「点停止」在网络面板上无法区分; ` +
        `真判据是下面 status 恒为 executing + 切回后计数器续涨)`
    );

    // ①b **零 clearSteps/clearCompleted** —— 北京老陈 2026-10-01 审核发现本条曾是**假通过**并已删除:
    //   原写法 `expect(clearsAfterAway).toEqual([])`, 其中 clearsAfterAway 是拿 console 文本
    //   过滤 /clearSteps|clearCompleted/ 得来的。核实生产代码:
    //     useChatStreaming.ts:444 `clearSteps = useCallback(() => chatStreamStore.clearSteps(...))`
    //     —— 全程**不打任何 console**; clearSteps/clearCompleted 在 src 下没有任何日志输出。
    //   即"切走时触发了 clearSteps"这件事在 console 里**根本没有痕迹** → 那个数组恒为空 →
    //   断言恒真。看似硬判据, 实则永远抓不到东西(比没有判据更坏: 给人"已覆盖"的错觉)。
    //   现改为**用可观测的真实状态覆盖同一红线**: 见 ①g 的计数器判据 ——
    //   clearSteps 的实际效果是清掉步骤, 所以"切走/切回后 step 不减"就是"没被 clear"的直接证据。
    //   (若日后要在生产侧加日志, 应加 `[clearSteps] session=...` 之类再回填此处, 不能凭空断言)
    //
    // ①b2 零 DELETE /chat/**(守任务级资源: 删会话/删任务接口不得被切走触发)
    const deletes = diag.streamReqs
      .slice(reqBase1)
      .filter((l) => l.includes('REQ DELETE') && l.includes('/chat/'));
    expect(deletes).toEqual([]);

    // ①d DB status 仍 executing(未被误取消/误改终态)
    // 2026-10-01 小欧 [1] 硬判据整改: 原写法是 `if (statusBefore==='executing') expect(...)` ——
    //   若切走那一瞬间任务已自然跑完(statusBefore='completed'), 整段 if 不进, 断言被跳过,
    //   而"切走时误取消"这个 bug 恰恰只在任务在飞时才会犯 → 假通过。
    //   改为: 切走前必须真的是 executing, 否则显式报错要求重跑(不把跳过当通过)。
    // 2026-10-01 小欧 [2] 删重复: 此处原有**第二份** `if (statusBefore !== 'executing') throw`,
    //   与 L157 那份逐字重复。因 L157 已抛错走到这里时 statusBefore 必为 'executing',
    //   第二份是**永不可达的死代码**(读起来像"又确认了一遍", 实际永远不执行)。已删。
    const statusAfterAway = await statusOfTask(sessionId, taskId);
    console.log(
      `[E2E] 操作① 后 status=${statusAfterAway}(操作前=${statusBefore})`
    );
    expect(statusAfterAway).toBe('executing');

    // ①e 后端日志无该 task 的 cancel/abort 痕迹
    const tailAway = readLogSince(BLOG, logBase1);
    const cancelLines = tailAway
      .split('\n')
      .filter((l) => l.includes(taskId) && /cancel|取消|abort/i.test(l));
    expect(cancelLines).toEqual([]);

    // ①f 切回后任务仍在跑, 后续步骤可见(证明"点了历史会话菜单没停任务"——红线的正面证据)
    const roundsAtAway = seenRounds(diag.consoleAll, frameBase0);
    await page
      .locator('.ant-menu-item', { hasText: '对话任务' })
      .first()
      .click();
    await page.waitForTimeout(3000);
    // 防假通过硬断言: 切回必须真的回到会话页, 且带回原会话(不是新会话)
    const urlAfterBack = page.url();
    console.log(`[E2E] 切回: ${urlAfterAway} -> ${urlAfterBack}`);
    expect(urlAfterBack).not.toBe(urlAfterAway);
    // 2026-10-01 小欧 [1] 断言口径纠偏: 原 `expect(urlAfterBack).toContain('session_id=...')` 与
    //   App.tsx:72-79 的既定设计矛盾 —— 菜单「对话任务」回跳刻意**不带** session_id,
    //   会话归属靠 `readStoredSessionId()` 从 sessionStorage 回落(该段注释已自认这是设计而非缺陷)。
    //   故 URL 无参是**预期行为**, 断言它反而把红线用例判红(实测基线无本次修复时同样恒红, 见 fe15_baseline)。
    //   真正要验的是"切回的是原会话、且该运行中任务还在" → 改用右栏/列表的实证判据:
    //   原任务的 taskId 仍出现在任务列表(下方 stillListed 硬断言已覆盖) + 轮次一个不丢(lostRounds 覆盖)。
    //   此处只保留"确实离开了 history 页"这一条, 会话归属交给下面两条实证断言判定。
    expect(urlAfterBack).not.toContain('/history');
    const roundsBack = seenRounds(diag.consoleAll, frameBase0);
    console.log(
      `[E2E] 切回后轮次数=${roundsBack.length}(切走时=${roundsAtAway.length})`
    );
    // 正面证据1: 该运行中任务仍在任务列表里(没被清掉)
    const stillListed = await page
      .locator(`.task-list-item[aria-label*="${taskId}"]`)
      .count();
    console.log(
      `[E2E] 切回后该 task 在列表中的条数=${stillListed}(应>=1, 未被清掉)`
    );
    expect(stillListed).toBeGreaterThanOrEqual(1);

    // ①g【北京老陈要求的核心判据】切回后**顶栏计数器仍在正常计数**, step 仍在正常显示。
    //   这条是"关页面没停任务"最直观的正面证据 —— 后端在跑是一回事, 页面上看得到数字在涨是另一回事。
    //   原先本 case 没有任何 UI 计数断言, 只查 DB status 与帧日志, 出现"任务在跑但页面数字不动"
    //   这类缺陷会全绿通过 —— 那正是老陈截图的现象。
    // 判据拆三条, 逐条说清"过/不过":
    //   ① 切回后计数器**读得到**        —— 读不到 = 信息带整个没了 = 不过
    //   ② 轮数/步数**都不小于**切走时的值 —— 变小 = 状态被回滚/换了任务 = 不过
    //   ③ 在 90s 内轮数或步数**继续增长**  —— 一直不涨 = 流没在推 = 不过
    const counterBack = await waitCounterIncreases(
      page,
      counterAtAway.rounds,
      counterAtAway.steps,
      90_000
    );
    console.log(
      `[E2E] 切回后计数器: ${counterBack ? `轮=${counterBack.rounds} 步=${counterBack.steps}` : '(读不到)'}` +
        ` (切走时 轮=${counterAtAway.rounds} 步=${counterAtAway.steps})`
    );
    if (!counterBack) {
      throw new Error(
        `[E2E] 切回后读不到顶栏计数器 —— 步骤/step 没有正常显示。` +
          counterFailMsg(
            'TaskInfoBar 未渲染或文本形态变了',
            counterAtAway,
            null
          ) +
          ` —— 不当通过处理`
      );
    }
    // ② 不得回退(回退=挂到了别的任务或状态被清)
    expect(counterBack.rounds).toBeGreaterThanOrEqual(counterAtAway.rounds);
    expect(counterBack.steps).toBeGreaterThanOrEqual(counterAtAway.steps);
    // ③ 必须真的在涨(没涨=流没在推, 页面看着像"卡住不动")
    expect(
      counterBack.rounds > counterAtAway.rounds ||
        counterBack.steps > counterAtAway.steps,
      counterFailMsg(
        '切回后计数器未增长 —— DB 里任务是 executing, 但页面计数没动, 说明 SSE 停止推送',
        counterAtAway,
        counterBack
      )
    ).toBeTruthy();

    // 正面证据2: 切走期间已收到的轮次一个都没丢
    const lostRounds = roundsAtAway.filter((r) => !roundsBack.includes(r));
    expect(lostRounds).toEqual([]);
    // 任务未提前终态时, 切回后应仍在接收(停止钮可见)
    if (statusAfterAway === 'executing') {
      await expect(chat.stopBtn).toBeVisible({ timeout: 20_000 });
    }

    // ══ 操作②: 点停止 —— 此时才允许 cancel ══
    // 2026-10-01 小欧 [1] 硬判据整改(北京老陈: 什么算通过什么算不通过, 要真实):
    //   原 `expect([...4值...]).toContain(statusAfterStop)` 把 failed 和 executing 都放过 ——
    //   任务失败也绿, 那这条判据等于没写。改为按下述三态分别显式判红。
    const stopVisible = await chat.stopBtn.isVisible().catch(() => false);
    if (!stopVisible) {
      // 前置不成立: 任务已自然终态, 没有「停止」按钮可点。
      // 此时"点停止才cancel"无从验证 —— 必须显式报错, 不能当成通过(否则是假通过)。
      const st = await statusOfTask(sessionId, taskId);
      throw new Error(
        `[E2E] 操作② 前置不成立: 任务已自然终态(status=${st}), 「停止」按钮不可见, ` +
          `「点停止才cancel」这条判据无法验证。请重跑以覆盖该分支 —— 不当通过处理`
      );
    }
    const reqBase2 = diag.streamReqs.length;
    await chat.stopBtn.click();

    // 等终态落库(取消要经 agent_runner finally 落库, 不是瞬时的)
    await expect
      .poll(
        async () => (await statusOfTask(sessionId, taskId)) !== 'executing',
        {
          timeout: 60_000,
          intervals: [1000],
        }
      )
      .toBeTruthy();
    const statusAfterStop = await statusOfTask(sessionId, taskId);
    console.log(`[E2E] 操作② 后 status=${statusAfterStop}`);

    // ②a 点停止 → 落点必须是 cancelled(后端 task_runtime.py:108 set_cancelled → 'cancelled')。
    //    唯一例外是 STOP_RACE: 任务已在点之前自然完成, 后端 cancel 返回 not_found,
    //    前端按 chatStreamStore.ts:744-754 回读 DB 权威终态 —— 那时 completed 是合法落点。
    //    failed 在任何情况下都是产品问题(本 case 任务是纯文稿), 一律显式红。
    if (statusAfterStop === 'failed') {
      const errLines = readLogSince(BLOG, logBase1)
        .split('\n')
        .filter(
          (l) => l.includes(taskId) && /ERROR|失败|error|Traceback/i.test(l)
        )
        .slice(-25);
      for (const l of errLines) console.log(`[E2E][DIAG] ${l.slice(0, 200)}`);
      throw new Error(
        `[E2E] 操作② 点停止后 status=failed —— 本 case 任务是纯文稿, failed 必是产品问题。后端日志行数=${errLines.length}`
      );
    }
    expect(['cancelled', 'completed']).toContain(statusAfterStop);

    // ②b 落点语义校验: 走到 cancelled 说明"点停止真的取消了任务";
    //    走到 completed 只能是 STOP_RACE —— 即取消请求发出时, 后端 set_cancelled 落空
    //    (chatStreamStore.ts stop(): `if (!r.success)` → 回读 DB 权威终态)。
    //    注意: STOP_RACE **无法用 HTTP 状态码区分** —— 后端 cancel_task 在任务不在 running_tasks 时
    //    仍返回 200 + {success:false}(task_runtime.cancel_task → set_cancelled 返回 False),
    //    所以 RES 是 200。真正的证据是"针对本 task 的取消请求确实发出、且拿到了响应"。
    // 2026-10-01 小欧 [2] 收紧: 原写法只数 `/cancel/i` 的请求条数 > 0 —— 该正则会命中任何
    //   含 "cancel" 字样的行(包括别的会话/别的 URL), 不是"本任务的取消请求已生效"的证据。
    //   改为同时要求: ① 针对本 task 的 cancel 请求 ② 它有对应响应。
    if (statusAfterStop === 'completed') {
      const cancelReq = diag.streamReqs
        .slice(reqBase2)
        .filter(
          (l) =>
            l.includes('REQ POST ') &&
            l.includes(`/chat/stream/cancel/${taskId}`)
        );
      const cancelRes = diag.streamReqs
        .slice(reqBase2)
        .filter(
          (l) =>
            l.includes('RES ') && l.includes(`/chat/stream/cancel/${taskId}`)
        );
      console.log(
        `[E2E] 操作② 落点=completed: 判为 STOP_RACE(取消请求发出时任务已自然完成)。` +
          `针对本 task(${taskId}) 的 cancel 请求=${cancelReq.length} 响应=${cancelRes.length}`
      );
      // 没发出针对本任务的取消请求 → 「点停止」这个动作没作用到任何东西, 判据不成立
      expect(
        cancelReq.length,
        `落点 completed 但没有针对本 task(${taskId}) 的取消请求 —— ` +
          `说明「点停止」没作用到任务上, 本条判据不成立`
      ).toBeGreaterThan(0);
      // 请求发出但没响应 → 前端根本没拿到结果, STOP_RACE 的解释不成立
      expect(
        cancelRes.length,
        `针对本 task 的取消请求发出但无响应(${cancelReq.length} 请求 / ${cancelRes.length} 响应) —— ` +
          `前端未拿到 cancel 结果, 不能按 STOP_RACE 放行`
      ).toBeGreaterThan(0);
    }

    // ②c 允许出现 cancel/取消 请求(红线只禁出现在 ①, 此处不设否)
    const cancels = diag.streamReqs
      .slice(reqBase2)
      .filter((l) => /cancel/i.test(l));
    console.log(`[E2E] 操作② 新增 cancel 相关请求=${cancels.length}`);

    // ③ 通用区
    printDiag(
      diag.streamReqs,
      diag.reconnectLogs,
      diag.sseErrors,
      diag.consoleAll,
      readLogSince(BLOG, logBase),
      diag.allFailed,
      getCaseId()
    );
    await keepBrowserOpenIfRequested(page);
  });
});
