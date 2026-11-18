/**
 * fre2e_24 — 多媒体输入能力域真实浏览器 E2E（粘贴链接 / 非法链接 / 路由模式 / 真实图片附件）
 *
 * opencode 2026-11-18 — 新建：覆盖 2026-11-18 修的输入能力域缺陷的**运行时可观测面**：
 *   C1 纯公网图片链接粘贴 → 正文撤出 + URL chip + 质量徽标（预检 quality 落 chip）
 *   C2 非法链接（本机回环）粘贴 → 拒绝加入且点名原因，**正文不得被吞**（用户输入不可凭空消失）
 *   C3 会话级路由模式切 strict → 刷新后仍为 strict（落库往返）
 *   C4 拖入真实 PNG → 附件 chip + 质量徽标，发送后真实 LLM 回包
 *   C5 拖入真实 PDF → 未声明文档输入的模型走全文注入，正文内容仍进模型上下文
 *
 * 定位口径：输入框用 data-testid（placeholder 文案随功能演进会变，testid 才是稳定锚点）。
 *
 * 真实环境：chromium 真浏览器 + 真后端(:8100) + 真 LLM + 真 SQLite，零 Mock；
 *   截图落 e2e_case/output/（已 gitignore），断言不依赖截图。
 */
import { test, expect, type Page } from '@playwright/test';
import { startNormalUiEnv } from '../e2e_front_lib';

const FRONTEND_DIR = 'D:\\NDOOmniAgent\\frontend';

/** 公网图片链接（预检不下载，只需 URL 形态合法） */
const PUBLIC_IMG = 'https://example.com/media/cat.png';
/** 本机回环：url_reject_reason 必拒（内网/本机地址不得外发） */
const LOCAL_IMG = 'http://127.0.0.1:9/secret.png';

/**
 * 2x2 PNG（左列红 / 右列绿，IHDR+IDAT+IEND 完整、可被 PIL 解析）。
 * 注意：网上流传的 1x1 "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB..." 是**截断的坏图**，
 * 原生投递时上游模型端会报 "broken data stream when reading image file" —— 夹具必须真可解码。
 */
const PNG_B64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEUlEQVR42mP4z8DA8B+MgBgAHfAD/a4/4jgAAAAASUVORK5CYII=';

/**
 * 真实可解析 PDF（ReportLab 生成，内含验证码 OMNI-7731）。
 * 用途：文档输入路由的运行时可观测面 —— 当前模型未声明文档输入时必须走全文注入，
 * 模型仍能答出 PDF 内的原文，证明降级链路不丢正文。
 */
const PDF_B64 =
  'JVBERi0xLjMKJZOMi54gUmVwb3J0TGFiIEdlbmVyYXRlZCBQREYgZG9jdW1lbnQgKG9wZW5zb3VyY2UpCjEgMCBvYmoKPDwKL0YxIDIgMCBSCj4+CmVuZG9iagoyIDAgb2JqCjw8Ci9CYXNlRm9udCAvSGVsdmV0aWNhIC9FbmNvZGluZyAvV2luQW5zaUVuY29kaW5nIC9OYW1lIC9GMSAvU3VidHlwZSAvVHlwZTEgL1R5cGUgL0ZvbnQKPj4KZW5kb2JqCjMgMCBvYmoKPDwKL0NvbnRlbnRzIDcgMCBSIC9NZWRpYUJveCBbIDAgMCA1OTUuMjc1NiA4NDEuODg5OCBdIC9QYXJlbnQgNiAwIFIgL1Jlc291cmNlcyA8PAovRm9udCAxIDAgUiAvUHJvY1NldCBbIC9QREYgL1RleHQgL0ltYWdlQiAvSW1hZ2VDIC9JbWFnZUkgXQo+PiAvUm90YXRlIDAgL1RyYW5zIDw8Cgo+PiAKICAvVHlwZSAvUGFnZQo+PgplbmRvYmoKNCAwIG9iago8PAovUGFnZU1vZGUgL1VzZU5vbmUgL1BhZ2VzIDYgMCBSIC9UeXBlIC9DYXRhbG9nCj4+CmVuZG9iago1IDAgb2JqCjw8Ci9BdXRob3IgKGFub255bW91cykgL0NyZWF0aW9uRGF0ZSAoRDoyMDI2MTExODEwMjk1MyswOCcwMCcpIC9DcmVhdG9yIChhbm9ueW1vdXMpIC9LZXl3b3JkcyAoKSAvTW9kRGF0ZSAoRDoyMDI2MTExODEwMjk1MyswOCcwMCcpIC9Qcm9kdWNlciAoUmVwb3J0TGFiIFBERiBMaWJyYXJ5IC0gXChvcGVuc291cmNlXCkpIAogIC9TdWJqZWN0ICh1bnNwZWNpZmllZCkgL1RpdGxlICh1bnRpdGxlZCkgL1RyYXBwZWQgL0ZhbHNlCj4+CmVuZG9iago2IDAgb2JqCjw8Ci9Db3VudCAxIC9LaWRzIFsgMyAwIFIgXSAvVHlwZSAvUGFnZXMKPj4KZW5kb2JqCjcgMCBvYmoKPDwKL0ZpbHRlciBbIC9BU0NJSTg1RGVjb2RlIC9GbGF0ZURlY29kZSBdIC9MZW5ndGggMjE2Cj4+CnN0cmVhbQpHYXJvOGJtSyVmJ0xxZ1tgT0Rva0YmXFpDUWAxU1glcmxBLDNuPUVwVGQwNClWJiRIZS9wcG42U0FTX3VPN2YhLUo0R3VeJSpTYmZAI2oyckZwTWRSayJhNi5BK0FPRVEvRUZmQ1AjMDtQOjU6ajJGMSUrUFAkKmFTb2dUTF8kImlgOW4udW0rPEVzJyRebVFtPCMlMFJNXj5zY04sdEtlUWQlZ25NZW5MTytpSVlFXHEqby9VPSUlXmVzPCZZT09eSmBXKV1tMEZaLXNbKGQua2YpYV5Wfj5lbmRzdHJlYW0KZW5kb2JqCnhyZWYKMCA4CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDA2MSAwMDAwMCBuIAowMDAwMDAwMDkyIDAwMDAwIG4gCjAwMDAwMDAxOTkgMDAwMDAgbiAKMDAwMDAwMDQwMiAwMDAwMCBuIAowMDAwMDAwNDcwIDAwMDAwIG4gCjAwMDAwMDA3MzEgMDAwMDAgbiAKMDAwMDAwMDc5MCAwMDAwMCBuIAp0cmFpbGVyCjw8Ci9JRCAKWzw5MWZhNGIxMmMwY2NlNDU0MmM3ZTk5YTI4NWU0MDU0Nz48OTFmYTRiMTJjMGNjZTQ1NDJjN2U5OWEyODVlNDA1NDc+XQolIFJlcG9ydExhYiBnZW5lcmF0ZWQgUERGIGRvY3VtZW50IC0tIGRpZ2VzdCAob3BlbnNvdXJjZSkKCi9JbmZvIDUgMCBSCi9Sb290IDQgMCBSCi9TaXplIDgKPj4Kc3RhcnR4cmVmCjEwOTYKJSVFT0YK';

const inputOf = (page: Page) => page.getByTestId('chat-input-textarea');
const sendBtn = (page: Page) => page.getByRole('button', { name: '发送' });
const stopBtn = (page: Page) => page.getByRole('button', { name: '停止' });
/** 引用区（chip 行）—— 文案含「本轮文件 · N 个」 */
const refRow = (page: Page) => page.getByText(/本轮文件\s*·\s*\d+\s*个/);
/** 质量徽标四档文案之一（QualityBadge 单表真源） */
const badge = (page: Page) => page.getByText(/原生投递|全文注入|元信息注入|仅链接/);

/** 进页并显式新建会话（裸 URL 会命中"加载最近会话"，残留会污染断言） */
const enterNewSession = async (page: Page): Promise<void> => {
  await page.goto('/');
  await expect(inputOf(page)).toBeVisible({ timeout: 60_000 });
  await page.getByRole('button', { name: /新建会话/ }).click();
  await page.waitForURL(/[?&]session_id=/, { timeout: 30_000 });
  await expect(inputOf(page)).toBeVisible({ timeout: 60_000 });
};

/**
 * 真粘贴：Chromium 允许写系统剪贴板后按 Ctrl+V，走浏览器原生 paste 链路
 * （不是直接 dispatchEvent —— 原生粘贴才会把正文真正落进 textarea，撤出逻辑才有意义）。
 */
const pasteText = async (page: Page, text: string): Promise<void> => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.evaluate(async (t) => {
    await navigator.clipboard.writeText(t);
  }, text);
  await inputOf(page).click();
  await page.keyboard.press('Control+V');
};

/** 用 DataTransfer 构造真实 File 并派发 drop（浏览器真实拖拽链路，文件经真实 multipart 上传） */
const dropFile = async (
  page: Page,
  name: string,
  b64: string,
  mime: string
): Promise<void> => {
  const box = await inputOf(page).boundingBox();
  if (!box) throw new Error('输入框不可见，无法投递 drop 事件');
  await page.evaluate(
    ({ data, fname, ftype, cx, cy }) => {
      const bin = atob(data);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const dt = new DataTransfer();
      dt.items.add(new File([bytes], fname, { type: ftype }));
      // 拖拽落点悬在输入框上（onDrop 挂在 ChatInput 根节点，事件冒泡可达）
      const target = document.elementFromPoint(cx, cy) as HTMLElement | null;
      if (!target) throw new Error('drop 落点为空');
      for (const type of ['dragenter', 'dragover', 'drop']) {
        target.dispatchEvent(
          new DragEvent(type, {
            dataTransfer: dt,
            bubbles: true,
            cancelable: true,
          })
        );
      }
    },
    {
      data: b64,
      fname: name,
      ftype: mime,
      cx: box.x + box.width / 2,
      cy: box.y + box.height / 2,
    }
  );
};

test.describe('多媒体输入能力域（真后端 + 真 LLM）', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(900_000);
    await startNormalUiEnv(FRONTEND_DIR);
    await enterNewSession(page);
  });

  test('C1 粘贴纯公网图片链接：正文撤出 + URL chip + 质量徽标', async ({ page }) => {
    await pasteText(page, PUBLIC_IMG);

    // 后端 text_url_only=true → 前端把正文撤出改挂 chip
    await expect(refRow(page)).toBeVisible({ timeout: 30_000 });
    await expect(inputOf(page)).toHaveValue('', { timeout: 30_000 });
    await expect(page.getByText(PUBLIC_IMG, { exact: false }).first()).toBeVisible();
    // 质量徽标（后端 quality 落 chip，不是前端猜的）
    await expect(badge(page).first()).toBeVisible({ timeout: 30_000 });
    await page.screenshot({
      path: 'e2e_case/output/media_c1_url_chip.png',
      fullPage: false,
    });
  });

  test('C2 粘贴本机回环链接：拒绝加入并点名原因，正文不得被吞', async ({ page }) => {
    await pasteText(page, LOCAL_IMG);

    // 拒绝提示：toast 点名 URL 与原因
    await expect(page.getByText(/链接未加入/)).toBeVisible({ timeout: 30_000 });
    // 未生成任何 chip
    await expect(refRow(page)).toHaveCount(0);
    // 关键断言：全被拒时正文必须留着 —— 没有 chip 顶替，撤出等于吞掉用户输入
    await expect(inputOf(page)).toHaveValue(LOCAL_IMG, { timeout: 30_000 });
  });

  test('C3 路由模式切 strict 后刷新仍持久化', async ({ page }) => {
    // 三档文案: 提示(suggest 缺省) / 自动 / 严格
    const current = page.locator('.ant-select-selection-item', { hasText: '提示' });
    await expect(current).toBeVisible({ timeout: 30_000 });
    await current.click();
    await page.locator('.ant-select-item-option', { hasText: '严格' }).click();

    await page.waitForTimeout(2000); // 等写库往返
    await page.reload();
    await expect(inputOf(page)).toBeVisible({ timeout: 60_000 });
    // 刷新后仍是严格档 = 落库往返成功(不是前端本地态)
    await expect(
      page.locator('.ant-select-selection-item', { hasText: '严格' })
    ).toBeVisible({ timeout: 30_000 });
  });

  test('C4 拖入真实 PNG：附件 chip + 徽标，发送后真实回复', async ({ page }) => {
    const prompt = '这张图里是什么颜色？一句话回答。';
    await dropFile(page, 'dot-2x2.png', PNG_B64, 'image/png');

    await expect(refRow(page)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/dot-2x2\.png/).first()).toBeVisible();
    await expect(badge(page).first()).toBeVisible({ timeout: 60_000 });
    await page.screenshot({
      path: 'e2e_case/output/media_c4_attachment_chip.png',
      fullPage: false,
    });

    await inputOf(page).fill(prompt);
    // 上行契约校验：前端只发标识(attachment_id/mime), 媒体载荷由后端按 refs 展开(厚后端)
    const streamReq = page.waitForRequest(
      (r) => r.url().includes('/chat/stream') && r.method() === 'POST',
      { timeout: 120_000 }
    );
    await sendBtn(page).click();
    const body = (await streamReq).postData() ?? '';
    expect(body).toContain('"kind":"attachment"');
    expect(body).toContain('"attachment_id"');
    expect(body).toContain('"mime":"image/png"');

    // 「发起了」= 停止钮出现; 「结束了」= 停止钮消失(发送钮常驻渲染, 不能当终态判据)
    await expect(stopBtn(page)).toBeVisible({ timeout: 90_000 });
    await expect(stopBtn(page)).toHaveCount(0, { timeout: 300_000 });

    // 真实往返落屏: 用户消息 + 助手回答
    await expect(page.getByText(prompt).first()).toBeVisible({ timeout: 60_000 });
    const answer = page.locator('[class*="message"]').filter({ hasNotText: prompt });
    await expect(answer.first()).toBeVisible({ timeout: 60_000 });
  });

  test('C5 拖入真实 PDF：未声明文档输入的模型走全文注入，正文内容仍进模型', async ({ page }) => {
    const prompt = '这份 PDF 里的验证码是什么？只回答验证码本身。';
    await dropFile(page, 'doc_probe.pdf', PDF_B64, 'application/pdf');

    await expect(refRow(page)).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText(/doc_probe\.pdf/).first()).toBeVisible();
    // 当前配置模型未声明文档输入 → 徽标必须是「全文注入」；虚报「原生投递」即为契约造假
    await expect(page.getByText('全文注入').first()).toBeVisible({ timeout: 30_000 });

    await inputOf(page).fill(prompt);
    await sendBtn(page).click();
    await expect(stopBtn(page)).toBeVisible({ timeout: 90_000 });
    await expect(stopBtn(page)).toHaveCount(0, { timeout: 300_000 });

    // 关键断言：回答里出现 PDF 内的验证码 → 文档正文确实经文本抽取进入了模型上下文
    await expect(page.getByText('OMNI-7731').first()).toBeVisible({ timeout: 120_000 });
    await page.screenshot({
      path: 'e2e_case/output/media_c5_pdf_text_injection.png',
      fullPage: false,
    });
  });
});
