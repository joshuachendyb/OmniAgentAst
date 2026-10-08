/**
 * fre2e_21_interject.spec.ts —— 插话全链路验证（临时验证用例，验证完删除，不入库）
 * 2026-10-08 小欧
 *
 * 真实场景：一条多步任务跑着 → 打开「插话开关」→ 连插 3 条 → 看左侧任务下挂回显。
 * 判据一律取后端唯一读真源（Node 侧直连 8010，不数 DOM 气泡）：
 *   A. 关态执行中输入框锁死（今天行为不变）
 *   B. 开态输入框解锁，3 条插话全部真入库（恰好 +3）
 *   C. 会话真源 allow_interject=true
 *   D. toast 已下线：onMerged 不再弹提示（DOM 计数 = 0）
 *   E. 原任务跑完，答复完整且体现 3 条插话内容
 */
import { test, expect } from '@playwright/test';
import { ChatPage } from '../e2e_front_lib';

const BACKEND = 'http://127.0.0.1:8010';
const N = 3;
const mark = (i: number) => `插话标记${i}`;
const interjectText = (i: number) => `补充第${i}条：请在最终总结里加一句"${mark(i)}"。`;

const LONG_TASK =
  '请分步骤完成下面八件事，每步都要真实调用工具执行并回报结果，一步做完再做下一步：' +
  '第1步：读取 E:/test_dir/test.txt 的全部内容并统计字节数与行数；' +
  '第2步：在 E:/test_dir/ 新建 interject_probe_21.txt，写入一行固定文本 INTERJECT_PROBE_21_OK；' +
  '第3步：再次读取 interject_probe_21.txt，确认写入内容与字节数；' +
  '第4步：列出 E:/test_dir/ 目录下的全部文件；' +
  '第5步：把第1步的统计结果追加写入 interject_probe_21.txt 的第二行；' +
  '第6步：第三次读取 interject_probe_21.txt，确认现在有两行；' +
  '第7步：在 E:/test_dir/ 新建 interject_probe_21_b.txt，写入一行 SECOND_PROBE_OK；' +
  '第8步：分别读取两个 probe 文件做最终比对，确认内容与行数都符合预期。' +
  '最后请用一段话总结八步的结果。';

type MsgResp = { allow_interject?: boolean; messages: Array<{ role: string; content: string }> };
type TaskItem = { task_id: string; merged_inputs?: string[] };

async function readSession(
  page: import('@playwright/test').Page
): Promise<{ sid: string; data: MsgResp }> {
  const sid = await page.evaluate(() => {
    const m = window.location.search.match(/session_id=([^&]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  });
  expect(sid, 'URL 上应有 session_id').not.toBe('');
  const res = await fetch(`${BACKEND}/api/v1/sessions/${sid}/messages`);
  expect(res.ok).toBe(true);
  const data = (await res.json()) as MsgResp;
  expect(Array.isArray(data.messages)).toBe(true);
  return { sid, data };
}

async function readTasks(sid: string): Promise<TaskItem[]> {
  const res = await fetch(`${BACKEND}/api/v1/sessions/${sid}/tasks`);
  expect(res.ok).toBe(true);
  const d = (await res.json()) as { tasks: TaskItem[] };
  return d.tasks;
}

async function waitMark(sid: string, m: string, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${BACKEND}/api/v1/sessions/${sid}/messages`);
      if (res.ok) {
        const d = (await res.json()) as MsgResp;
        if ((d.messages ?? []).some((x) => x.content.includes(m))) return true;
      }
    } catch {
      /* 瞬时不可用继续等 */
    }
    await new Promise((r) => setTimeout(r, 800));
  }
  return false;
}

const userCount = (d: MsgResp) => d.messages.filter((m) => m.role === 'user').length;

test('插话全链路: 关态锁输入 / 开态连插3条真入库 / 左栏下挂回显 / toast已下线', async ({ page }) => {
  const chat = new ChatPage(page);
  const errors: string[] = [];
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(m.text());
  });

  await chat.gotoChat();
  await chat.newSession();

  const sw = page.locator('label:has-text("插话开关") input[type="checkbox"]');
  const input = page.locator('textarea').first();
  const stopBtn = page.getByRole('button', { name: /停止/ });

  await expect(sw, '插话开关应渲染').toHaveCount(1);
  expect(await sw.isChecked(), '新会话默认关').toBe(false);
  console.log('[验证] 插话开关已渲染，默认关态');

  // D. toast 已下线 → 探针预挂，统计「已并入正在运行的任务」文本节点新增次数
  await page.evaluate(() => {
    const w = window as unknown as { __toastMount: number };
    w.__toastMount = 0;
    const hasText = (n: Node): boolean => {
      if (n.nodeType === 3) return (n.textContent || '').includes('已并入正在运行的任务');
      if (n.nodeType !== 1) return false;
      const el = n as Element;
      return el.children.length === 0 && (el.textContent || '').includes('已并入正在运行的任务');
    };
    new MutationObserver((records) => {
      for (const r of records) r.addedNodes.forEach((n) => hasText(n) && (w.__toastMount += 1));
    }).observe(document.body, { childList: true, subtree: true });
  });

  // A. 关态执行中 → 输入框锁死
  await sw.click(); // 先勾开关，让值随首条消息落库（关态判定仍走首条消息）
  await expect(sw).toBeChecked();
  await sw.click(); // 关回，验证关态锁输入
  await expect(sw).not.toBeChecked();
  await chat.sendPrompt(LONG_TASK);
  await expect(stopBtn, '第一条任务应执行中').toHaveCount(1);
  await expect(input, '关态执行中应锁输入').toBeDisabled();
  console.log('[验证] 关态执行中：输入框已锁');

  const sid = (await readSession(page)).sid;
  const baseUsers = userCount((await readSession(page)).data);

  // B. 开态 → 解锁并连插 3 条
  await sw.click();
  await expect(sw).toBeChecked();
  await expect(input, '开态执行中应可插话').toBeEnabled();
  console.log('[验证] 开关已打开 → 输入框解锁，开始连插 3 条');

  for (let i = 1; i <= N; i += 1) {
    await input.fill(interjectText(i));
    await input.press('Enter');
    expect(await waitMark(sid, mark(i), 30_000), `第${i}条插话必须真入库`).toBe(true);
    await expect(stopBtn, `第${i}条插话后任务必须仍在跑`).toHaveCount(1);
    console.log(`[验证] 第${i}条插话已入库（任务未中断）`);
    if (i < N) {
      // 间隔 20 秒: 模拟真实用户逐条插话节奏, 也让 Agent 有轮次真正吸收前一条插话
      console.log(`[验证] 等待 20 秒后发第${i + 1}条插话`);
      await chat.waitMs(20_000);
    }
  }

  const after = (await readSession(page)).data;
  expect(userCount(after), '3 条插话应恰好多 3 条 user').toBe(baseUsers + N);
  expect(after.allow_interject, '会话真源应为开').toBe(true);
  console.log('[验证] 3 条插话全部入库、无重复无丢失；会话真源 allow_interject=true');

  // 左栏下挂回显（历史+实时同一真源 merged_inputs）
  const tasks = await readTasks(sid);
  const merged = tasks.flatMap((t) => t.merged_inputs ?? []);
  expect(merged.length, '左栏下挂的「追加N条」应恰有 3 条').toBe(N);
  for (let i = 1; i <= N; i += 1) {
    expect(merged.some((m) => m.includes(mark(i))), `下挂回显应含第${i}条`).toBe(true);
  }
  await expect(
    page.locator('text=/追加 \\d+ 条/').first(),
    '左栏应可见「追加 3 条」折叠块'
  ).toBeVisible();
  console.log('[验证] 左栏任务下挂「追加 3 条」已渲染');

  // D. toast 应为 0（onMerged 已删提示条）
  const toastMount = await page.evaluate(
    () => (window as unknown as { __toastMount: number }).__toastMount
  );
  expect(toastMount, 'toast 已下线，不应再弹「已并入正在运行的任务」').toBe(0);
  console.log('[验证] toast 计数 = 0（已下线，只留左栏高亮）');

  // E. 原任务跑完 → 答复完整且体现 3 条插话
  await chat.waitDone(480_000);
  await chat.waitMs(2000);
  const finalText = await chat.getFinalText();
  expect(finalText.length, '原任务答复应完整落地').toBeGreaterThan(20);
  for (let i = 1; i <= N; i += 1) {
    expect(finalText, `最终答复应体现第${i}条插话`).toContain(mark(i));
  }
  console.log('[验证] 原任务答复完整，且 3 条插话都已在答复中体现');

  const realErrors = errors.filter((e) => !/favicon|ResizeObserver/i.test(e));
  expect(realErrors, '控制台不应有真错误').toEqual([]);

  console.log('[验证] 停留 20 秒供人工观察，随后结束');
  await chat.waitMs(20_000);
});