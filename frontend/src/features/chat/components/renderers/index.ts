/**
 * 统一渲染组件导出
 *
 * 2026-10-04 小欧 文档[8]第六章第7条: 删 5 个零生产引用死文件(SmartContentRenderer /
 *   ToolInfo / WarningBox / NextActions / StatusIcon)——它们仅靠本桶导出"看起来在用",
 *   全仓无任何消费方(违 YAGNI)。现只剩在用的 GenericResultRenderer 一个。
 *   — 小欧-2026-10-04
 */
export { GenericResultRenderer } from './GenericResultRenderer';
