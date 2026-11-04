// 编辑历史: 2026-10-22 小欧 - 新建：改写类文件操作判定（单一真源，树✎与足迹ops同源）— 小欧-2026-10-22
/**
 * 改写类文件操作（写入/修改/移动/删除/改名/打包…）
 *
 * 取值域 = 后端工具注册名（backend/app/tools/tool_constants.py FILE_OPERATION_TOOLS，18 个），
 *   本表只收**会改变盘面**的那 12 个；读类（read/read_xlsx/read_docx/read_pdf/read_pptx）不在此表。
 *
 * 为什么收口成一处：树的 ✎ 标记与足迹面板的 ops 徽标都要判"这次操作
 *   改没改文件"，两处各列一份 → 加新写工具时必漏一处（DRY）。
 */
export const MUTATING_FILE_OPS: ReadonlySet<string> = new Set([
  'write',
  'edit',
  'move',
  'copy',
  'delete',
  'rename',
  'compress',
  'extract',
  'write_xlsx',
  'write_docx',
  'write_pdf',
  'write_pptx',
]);

/** 该文件是否被改写过（ops 里有改写类操作即算） */
export const isMutatedByOps = (ops?: string[] | null): boolean =>
  (ops ?? []).some((op) => MUTATING_FILE_OPS.has(op));
