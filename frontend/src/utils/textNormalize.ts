// 编辑历史: 2026-08-30 小欧 - 13.11 实施: 空行规约前端公用函数(与后端 normalize_blank_lines 同一张规则表, 幂等;
//   流式尾随守卫防打字机回缩) - 小欧-2026-08-30
/**
 * normalizeBlankLines - 空行规约（13.11 规则表）
 *
 * 【小欧 2026-08-30】逐行空行折叠 = "至多保留一个段落空行，不能多余空行"：
 * 连续空行(含整行仅空格/制表)折叠为一个空行；streaming 时末尾换行运行只保留一个(尾随守卫，
 * 防打字机逐字单调流被压缩击穿回缩)，终态统一 trim 首尾。幂等（对已规约文本再规约不变）。
 *
 * @author 小欧
 * @date 2026-08-30
 */
export const normalizeBlankLines = (
  text: string,
  options: { streaming?: boolean } = {}
): string => {
  if (!text) return text;
  const out: string[] = [];
  let blank = 0;
  for (const ln of text.split('\n')) {
    if (!ln.trim()) {
      blank += 1;
      if (blank === 1) out.push('');
    } else {
      blank = 0;
      out.push(ln);
    }
  }
  const result = out.join('\n');
  // 流式尾随守卫(段首仍 trim, 段尾换行运行保留一个等下一帧确认); 终态统一 trim 首尾
  return options.streaming ? result.replace(/^\n+/, '') : result.trim();
};
