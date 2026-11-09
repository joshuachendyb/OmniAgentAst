// 编辑历史: 2026-11-08 小欧 - 新建：实测结论词表与提示文案单源（自 ModelLibraryTab 整块搬出，
//   模型库只读列与②图片实测行共用同一套词，避免两处措辞漂移） — 小欧-2026-11-08
// 2026-11-09 小欧 - 全量重写：副行只留通道事实（能收什么），机制/后果下沉 acceptVerdict 定论行 — 小欧-2026-11-09
// 2026-11-09 小欧 - 行内改三徽标(内联/外链/输出能力)：绿✓通过/红✗失败/灰未测，acceptSub 退役
// 2026-11-09 小欧 - 主词改输入Y/输入X/未验证（北京老陈定版：测的是图片输入；勾选只管按钮可用性，结论 3 态）
// 2026-11-09 小欧 - 主词定稿：Y/X 落成符号（绿对勾/红叉叉，同内联徽标），词只留「输入/未验证」
// 2026-11-09 小欧 - 外链未取证分叉归因：补 urlErr(厂商抓图失败)第三态, 不再一律说「地址为空」（2.5-flash 实测取证）
// 2026-11-09 小欧 - urlErr 归因措辞精确化：网络不可达→超时或不可达(会审: 与实测定性一致)
// 2026-11-09 小欧 - 行名词改「输入图片能力验证」/按钮改「验证」；补 probeMsText 探测腿耗时格式化(tip 按腿显示用)
import type { MediaProbe } from '@/services/api/model.api';

/** 主词=整体定论，词只说「输入」；Y/X 落符号不落字母（绿对勾/红叉叉，同内联徽标款），未验证=灰字。
 *  措辞由北京老陈定版（勾选只管按钮可用性，结论 3 态）。 */
const ACCEPT_MAIN: Record<string, string> = {
  inline: '输入',
  both: '输入',
  none: '输入',
};

/** 主行文案：未测就说未验证——把"没测"讲成"不行"会让用户白换模型。 */
export const acceptMain = (accept?: string) => {
  if (!accept) return '未验证';
  return ACCEPT_MAIN[accept] ?? accept;
};

/** 外链能力有没有实测结论：读后端落库的结构化标记，不再解析给人看的 evidence 文本。
 *  url_tested 缺省(旧记录)时用 accept==='both' 反推——外链没通不可能判成 both。 */
export const urlTestedOf = (media?: MediaProbe) =>
  media?.url_tested ?? media?.accept?.image === 'both';

/** 外链腿发了请求但厂商抓图失败(非确定结论)：提示要归因「网络不可达」而非「地址为空」— 小欧-2026-11-09 */
export const urlErrOf = (media?: MediaProbe) => !!media?.url_err;

/** 定论行：一句讲清«为什么这样发图»——外链转发与否及理由，判定方法由调用处固定行交代。 */
export const acceptVerdict = (
  accept?: string,
  urlTested = false,
  urlErr = false
) => {
  if (!accept) return '未实测——暂只随请求发内联图，图片地址一律不转发';
  if (accept === 'none')
    return '不收图：接口拒绝图片内容（HTTP 400/415/422），或返回 200 但图像 token 为 0（静默丢图）；发图会降级为一行文字说明';
  if (accept === 'both') return '内联与外链均实测可用，图片地址可直接转发';
  return urlTested
    ? '只收内联图：测试图片地址被接口拒绝，转发地址会拖垮整轮请求，故不转发'
    : urlErr
      ? '只收内联图：外链腿已请求，厂商侧抓图失败（网络超时或不可达）——不判对错，可再点「验证」重试'
      : '只收内联图：外链未取证——上方「Image_URL」为空，外链腿未发起请求；填好地址再点「验证」即出对/错';
};

/** 探测腿耗时(ms→人话)：485 ms / 33.2 s / 3 分 35 秒；null/undefined = 该腿未发起，返回空串
 *  视频腿是异步任务，排队可上探到分钟级，故 60s 起换分秒 — 小欧-2026-11-09 */
export const probeMsText = (ms?: number | null): string => {
  if (ms == null) return '';
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const total = Math.round(ms / 1000);
  return `${Math.floor(total / 60)} 分 ${total % 60} 秒`;
};
