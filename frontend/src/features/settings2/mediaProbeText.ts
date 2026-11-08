// 编辑历史: 2026-11-08 小欧 - 新建：实测结论词表与提示文案单源（自 ModelLibraryTab 整块搬出，
//   模型库只读列与②图片实测行共用同一套词，避免两处措辞漂移） — 小欧-2026-11-08
import type { MediaProbe } from '@/services/api/model.api';

/** 实测结论主行：只回答"收得到吗"；通道差别放副行，别让细节压过结论。 */
const ACCEPT_MAIN: Record<string, string> = {
  inline: '能接收',
  both: '能接收',
  none: '不能接收',
};

/** 主行文案：未测就说未测——把"没测"讲成"不行"会让用户白换模型。 */
export const acceptMain = (accept?: string) => {
  if (!accept) return '未测';
  return ACCEPT_MAIN[accept] ?? accept;
};

/** 副行：内联 = 图片字节 base64 随请求体发送；外链 = 只传地址，由厂商抓取。 */
export const acceptSub = (accept?: string, urlTested = false) => {
  if (accept === 'none') return '厂商拒绝或静默丢图';
  if (accept === 'both') return '内联＋外链';
  if (accept === 'inline') return urlTested ? '仅内联' : '仅内联·外链未测';
  return '按仅内联处理';
};

/** 外链能力有没有实测结论：读后端落库的结构化标记，不再解析给人看的 evidence 文本。
 *  url_tested 缺省(旧记录)时用 accept==='both' 反推——外链没通不可能判成 both。 */
export const urlTestedOf = (media?: MediaProbe) =>
  media?.url_tested ?? media?.accept?.image === 'both';

/** 行内提示：术语就地定义，按「实测值 × 外链是否取证」查表——未测≠不支持，内联≠外链可用。 */
export const acceptTip = (accept?: string, urlTested = false) => {
  if (!accept)
    return '尚未实测。未实测按"仅内联"处理：图片字节随请求体发送，公网图片地址不转发。点「实测」可验证';
  if (accept === 'none')
    return '实测收不到图片：厂商拒绝该内容类型（HTTP 400/415/422），或返回 200 但图像 token 为 0（网关静默丢图）。发图会降级成一行说明文字';
  if (accept === 'both')
    return '实测内联与外链都可用：内联 = 图片字节 base64 随请求体发送；外链 = 只传图片地址，由厂商自己抓取，不下载、不转码';
  return urlTested
    ? '实测仅内联可用：外链探测被厂商拒绝（该地址取不到或不认），转发地址会导致整轮请求失败，故不转发'
    : '实测内联可用。外链未取证——「媒体 → 外链检测用图片地址」为空，或本次外链探测未取得确定结论；未取证一律按外链不可用处理';
};
