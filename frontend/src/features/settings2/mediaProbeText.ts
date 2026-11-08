// 编辑历史: 2026-11-08 小欧 - 新建：实测结论词表与提示文案单源（自 ModelLibraryTab 整块搬出，
//   模型库只读列与②图片实测行共用同一套词，避免两处措辞漂移） — 小欧-2026-11-08
// 2026-11-09 小欧 - 全量重写：副行只留通道事实（能收什么），机制/后果下沉 acceptVerdict 定论行 — 小欧-2026-11-09
// 2026-11-09 小欧 - 行内改三徽标(内联/外链/输出能力)：绿✓通过/红✗失败/灰未测，acceptSub 退役
import type { MediaProbe } from '@/services/api/model.api';

/** 主行：只回答"收得到吗"；通道差别放副行，别让细节压过结论。 */
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

/** 外链能力有没有实测结论：读后端落库的结构化标记，不再解析给人看的 evidence 文本。
 *  url_tested 缺省(旧记录)时用 accept==='both' 反推——外链没通不可能判成 both。 */
export const urlTestedOf = (media?: MediaProbe) =>
  media?.url_tested ?? media?.accept?.image === 'both';

/** 定论行：一句讲清«为什么这样发图»——外链转发与否及理由，判定方法由调用处固定行交代。 */
export const acceptVerdict = (accept?: string, urlTested = false) => {
  if (!accept) return '未实测——暂只随请求发内联图，图片地址一律不转发';
  if (accept === 'none')
    return '不收图：接口拒绝图片内容（HTTP 400/415/422），或返回 200 但图像 token 为 0（静默丢图）；发图会降级为一行文字说明';
  if (accept === 'both') return '内联与外链均实测可用，图片地址可直接转发';
  return urlTested
    ? '只收内联图：测试图片地址被接口拒绝，转发地址会拖垮整轮请求，故不转发'
    : '只收内联图：外链未取证——「媒体 → 外链检测用图片地址」未配置或探测无结论，不转发图片地址';
};
