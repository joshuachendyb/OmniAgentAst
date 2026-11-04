// 编辑历史: 2026-10-29 小欧 - 新建：前端唯一读盘点(自 quote.ts:34-36 与 refresh.ts:35 分叉收口) — 小欧-2026-10-29

// 编辑历史: 2026-10-30 小欧 - probeRef 改走 stat 轻端点(删整份读与自设 60s 上限/truncated/
//   loaded_lines, 只取 size/mtime): 探引用只需存在性与时间戳, 读正文纯浪费 — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 三堂会审整改(A4/A5/A6): ①precheckRefs 回写 mtime, 同一变更不再每次都报
//   "内容已更新"; ②checked 保留失效条目(invalid:true)供 chip 标红, 不再被 setAll 抹掉;
//   ③预检改并行且不吞错(异常交调用方转成可见提示) — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 批3: 抽 statRef(端点唯一调用口, 业务失败归 reason/传输异常上抛) 供
//   probeRef 与 precheckRefs 共用; 超时码补 ETIMEDOUT, 文案匹配改大小写不敏感 — 小欧-2026-10-30

/**
 * probe —— 前端对引用的唯一读盘点
 *
 * 为什么收口(DRY)：重构前有 3 处自读盘(quote.ts:34-36 有外部/根内分流、refresh.ts:35 没有、
 *   pages/Files:784-792 又一份)，"选哪个接口"的知识也是两份。本文件是唯一实现。
 *
 * 职责边界：
 * - probeRef(path)：走 stat 轻端点(存在性/size/mtime, 不读正文)；读失败仍允许入队
 *   (chip 标"未校验")。
 * - precheckRefs(refs)：发送前走 stat 轻端点(GET /files/stat, 真源 browse_service, 落点 5.2.13;
 *   前端入口 fileApi.statFile 见 F12), 只取存在性/mtime, 不读正文(R3: 消掉点引用+发送前
 *   两次全读的 IO); mtime 与点引用时本地比对, 变化条目进 updated → 调用方(precheckOrBlock)
 *   点名提示"内容已更新"——mtime 仅本地比对, 不进 wire(4.5)。
 * - 不切片、不裁决：行区间由后端按 lineRange 直接读(前端不再切片, sliceByLineRange 已删)；体积裁决归后端。
 */
import { fileApi } from '@/services/api/file.api';

export interface ProbeResult {
  ok: boolean;
  size?: number;
  mtime?: string; // 内部字段: 仅两次预检间本地比对, 不上行(4.5)
  reason?: 'missing' | 'unsupported' | 'timeout';
}

/**
 * stat 端点唯一调用口(2026-10-30 小欧): 业务失败(ok:false)归一成 reason, 传输异常**原样抛出**。
 *
 * 为何这样切: probeRef 与 precheckRefs 对传输异常的策略相反 —— 前者"失败仍允许入队", 要把异常
 *   转成 reason; 后者"预检失败必须可见"(A6), 要上抛给调用方提示。策略归各自, 只有"调端点 +
 *   把 ok:false 归一成 reason"这段是共用的, 收在这里(原先两处各写一遍, 后端加一个 reason 要改两处)。
 */
export const statRef = async (path: string): Promise<ProbeResult> => {
  const st = await fileApi.statFile(path); // 传输异常自然上抛, 由调用方决定处置
  if (!st.ok) {
    // 后端 reason 只有 missing/unsupported；其余过渡值一律按 missing(从严, 允许入队"未校验")
    return {
      ok: false,
      reason: st.reason === 'unsupported' ? 'unsupported' : 'missing',
    };
  }
  return { ok: true, size: st.size, mtime: st.mtime };
};

/** 传输层异常 → reason(唯一分类实现): 415→unsupported, 超时→timeout, 其余→missing。 */
const reasonOfError = (e: unknown): 'missing' | 'unsupported' | 'timeout' => {
  const status = (e as { response?: { status?: number } })?.response?.status;
  const code = (e as { code?: string })?.code;
  const msg = (e as { message?: string })?.message ?? '';
  if (status === 415) return 'unsupported';
  // ETIMEDOUT 是 Node/socket 层超时码, ECONNABORTED 是 axios 自设超时码, 两者都要认 — 小欧 2026-10-30
  if (code === 'ECONNABORTED' || code === 'ETIMEDOUT' || /timeout/i.test(msg))
    return 'timeout';
  return 'missing';
};

/** 探一条引用：stat 轻端点取 size/mtime；失败给 reason 供 chip 标"未校验"。 */
export const probeRef = async (path: string): Promise<ProbeResult> => {
  try {
    return await statRef(path);
  } catch (e) {
    // 失败仍允许入队"未校验", reason 供 chip 文案分支。
    return { ok: false, reason: reasonOfError(e) };
  }
};

/** 发送前预检(轻, R3)：走 stat 端点(存在性/mtime, 不读正文);
 *  失败条目标 invalid(红底+点名)并阻断。mtime 与入队时(probeRef)比对, 变化条目进 updated,
 *  由调用方(precheckOrBlock)发送前点名提示"内容已更新"——mtime 仅请求链本地留存, 不进 wire。
 *  2026-10-30 小欧 A6: 并行发起(20 条串行会叠成 20 个 RTT), 且**不吞错** —— statFile 抛错
 *  原样上抛, 由调用方转成"校验失败"可见提示(原实现一路 void 到底, 点发送看着没反应)。
 */
export const precheckRefs = async <
  T extends { path: string; mtime?: string; invalid?: boolean },
>(
  refs: T[]
): Promise<{ checked: T[]; invalid: T[]; updated: T[] }> => {
  // 2026-10-30 小欧 A5: checked 保留全部条目 —— 失效条目带 invalid:true 一起回写,
  //   调用方 setAll 后 chip 仍在(红底+「已失效」), 用户才可能按提示移除;
  //   原实现只回有效条目, 失效 chip 被抹掉, 红底/「已失效」/阻断派生值全成死分支。
  const results = await Promise.all(
    refs.map(async (r) => {
      const st = await statRef(r.path); // 唯一调用口: 传输异常上抛, 业务失败给 reason
      if (!st.ok) {
        return {
          ref: { ...r, invalid: true } as T,
          invalid: true,
          updated: false,
        };
      }
      const updated = Boolean(r.mtime && st.mtime && st.mtime !== r.mtime);
      // 2026-10-30 小欧 A4: 回写 mtime —— 只回写 size 时, 同一处变更会在 30s 去重窗之后的
      //   每次发送重复提示"内容已更新"(盘面不会再匹配到入队时的旧时间戳)。
      return {
        ref: { ...r, size: st.size, mtime: st.mtime, invalid: false } as T,
        invalid: false,
        updated,
      };
    })
  );
  return {
    checked: results.map((x) => x.ref),
    invalid: results.filter((x) => x.invalid).map((x) => x.ref),
    updated: results.filter((x) => x.updated).map((x) => x.ref),
  };
};
