// 编辑历史: 2026-10-13 小欧 - 新建: Step 页参数区(文档[29] §2.2/§3.4/DC-04/DC-15/DC-17/DC-19/DC-20)
//   顶层键默认折叠(仅含换行的巨型值) · 长行折行完整显示 · 树头复制(格式化 JSON) — 小欧 2026-10-13
//   其余实现要点: ①nodeKey 只由 entries 下标 idx 构成(不掺参数 key), 参数 key 内含 '/' 也不撞键;
//   ②key 列限宽 96 与浮层 GroupView 同宽(两载体口径一致);③树头复制按钮用 inline + 中间 flex:1 顶到行尾
//   (原默认形态 position:absolute 的包含块是树根而非树头, 会压住第一条节点行的值列);
//   ④行容器 className="params-clickable" 走 CSS hover/focus 反馈(§2.5 V8, 零重渲染);⑤底/框/圆角与 MarkdownText 代码块同款(T32) — 小欧 2026-10-13
// 2026-10-13 小欧 - 十三轮**规则重写**(北京老陈裁定, 违反即打回):
//   【铁律】只有 content 这类**含换行的巨型值**才允许折叠/展开; 其余所有参数一律不许折叠,
//   长行**折行完整显示**, 不截断、不隐藏、不给 title 悬停替代。
//   本次删掉: ①对象/数组的 branch 折叠(树里 `meta ▾ {…} N 项` 即违反, 已改为直接展开 JSON);
//             ②字符阈值方案(曾按 >200 字判可折叠, 已删); ③单行省略号 + 行级 title。
import React, { useCallback, useMemo, useState } from 'react';
import { CircleArrow } from '@/components/CircleArrow';
import { CopyButton } from '@/components/markdown/CopyButton';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  Icon,
  Radius,
  Size,
  Spacing,
} from '@/utils/stepStyles';

/** 节点两态: 单值(恒完整显示, **无折叠**) / 多行巨型值(可折叠, 展开体限高滚动) */
type NodeKind = 'scalar' | 'body';

/** 只有含换行的字符串才是"巨型值", 才配折叠箭头 */
const classify = (v: unknown): NodeKind =>
  typeof v === 'string' && v.includes('\n') ? 'body' : 'scalar';

/**
 * 单值展示文本: 空值给占位、对象直接给格式化 JSON(**不折叠、不显示 `{…} N 项` 摘要**)、
 * 其余原样。配合值列的 pre-wrap + break-word, 长内容与多行 JSON 都折行完整显示。
 */
const displayOf = (v: unknown): string => {
  if (v === undefined || v === null) return '(空)';
  // 2026-10-13 小欧 - 对象用**紧凑单行** JSON: 2 空格缩进会把 3 键对象撑成 8 行,
  //   紧凑后一行读完, 仍不折叠/不截断, 超宽照常折行
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};

/** 空值判定: 用于把「(空)」渲染成更浅的色, 与真实值区分 */
const isEmptyValue = (v: unknown): boolean => v === undefined || v === null;

// ==================== 单节点 ====================

interface ParamNodeProps {
  nodeKey: string;
  label: string;
  value: unknown;
  isExpanded: (key: string) => boolean;
  onToggle: (key: string) => void;
}

/** 2026-10-13 小欧 - 单节点: 只有巨型值可折叠; 单值恒完整折行显示 */
const ParamNode: React.FC<ParamNodeProps> = ({
  nodeKey,
  label,
  value,
  isExpanded,
  onToggle,
}) => {
  const kind = classify(value);
  const foldable = kind === 'body';
  const open = foldable && isExpanded(nodeKey);
  const summary = foldable
    ? `共 ${String(value).split('\n').length} 行`
    : displayOf(value);

  // 2026-10-13 小欧 - 文档[29]§3.4.2/D-1: 此处**不加** e.stopPropagation()。
  //   展开区已移出 role="button" 容器(父级不再是按钮, 无冒泡可阻);
  //   加了反而使点选/复制节点文字失效, 正是 D-1 要根治的病。
  const toggle = () => onToggle(nodeKey);
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggle();
    }
  };

  return (
    <div>
      <div
        // 2026-10-13 小欧 - §2.5 V8(解决 B3): 节点 hover / 键盘焦点反馈走 CSS 类
        //   (.params-clickable, index.css; 与面板内折叠行/✕ 共用一套规则)
        className="params-clickable"
        role={foldable ? 'button' : undefined}
        tabIndex={foldable ? 0 : undefined}
        aria-expanded={foldable ? open : undefined}
        onClick={foldable ? toggle : undefined}
        onKeyDown={foldable ? onKeyDown : undefined}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: Spacing.SM,
          fontFamily: FontFamily.MONO,
          fontSize: FontSize.CODE,
          lineHeight: `${FontSize.CODE + Spacing.XS}px`,
          color: Colors.TEXT.SECONDARY,
          cursor: foldable ? 'pointer' : 'default',
        }}
      >
        {foldable && (
          <CircleArrow
            size={14}
            color={Colors.PRIMARY}
            expanded={open}
            animated={false}
          />
        )}
        <span
          style={{
            color: Colors.TEXT.SECONDARY,
            // key 列限宽 96 与浮层 GroupView 同宽(两载体口径一致, 布局常量已就地标注);
            //   key 与值同一口径折行, 不省略
            maxWidth: 96,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {label}
        </span>
        <span
          style={{
            // 空值(「(空)」)用更浅的 TERTIARY, 与真实值(STRONG)区分, 避免和 false/0 混淆
            color: isEmptyValue(value)
              ? Colors.TEXT.TERTIARY
              : Colors.TEXT.STRONG,
            // 【铁律】长行折行完整显示: 有多少行显示多少行, 不截断、不隐藏、不靠 title 兜底。
            //   flex:1 + minWidth:0 保证在本 flex 行内正确折行而不撑破容器
            flex: 1,
            minWidth: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          : {summary}
        </span>
      </div>
      {/* 巨型值展开体: <pre> 显示**全部行数**; 底/框/圆角与 MarkdownText 代码块同款(T32) */}
      {open && (
        <div
          style={{
            marginLeft: Icon.BOX,
            // 2026-10-13 小欧 - 展开体与上一行拉开间距: 原 Spacing.XS-2(2px) 代码块几乎贴着
            //   「共 N 行」那行, 视觉糊在一起; 改 Spacing.SM(6px) 分层清楚
            marginTop: Spacing.SM,
          }}
        >
          <pre
            style={{
              margin: 0,
              padding: Spacing.SM,
              background: Colors.BG.SECONDARY,
              border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
              borderRadius: Radius.SM,
              fontFamily: FontFamily.MONO,
              fontSize: FontSize.CODE,
              lineHeight: `${FontSize.CODE + Spacing.XS}px`,
              color: Colors.TEXT.STRONG,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {String(value)}
          </pre>
        </div>
      )}
    </div>
  );
};

// ==================== 树根 ====================

interface ParamsTreeProps {
  entries: Array<[string, unknown]>;
}

/**
 * ParamsTree - 参数区(展开区)
 *
 * 2026-10-13 小欧: 顶层键默认折叠(仅含换行的巨型值), 折叠态高度与参数值体量无关;
 * 单值(含对象)一律折行完整显示, 不折叠、不限高 —— 这是 §1.4 C1/C2 的根治点。
 *
 * @author 小欧
 * @since 2026-10-13
 */
const ParamsTree: React.FC<ParamsTreeProps> = ({ entries }) => {
  const [expandedKeys, setExpandedKeys] = useState<ReadonlySet<string>>(
    () => new Set()
  );
  // 2026-10-13 小欧 - 用 Set 承载展开态而非布尔数组: key 是路径字符串, 新增/删除无需考虑下标对齐
  const isExpanded = useCallback(
    (key: string) => expandedKeys.has(key),
    [expandedKeys]
  );
  const onToggle = useCallback((key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);
  const copyText = useMemo(
    () => JSON.stringify(Object.fromEntries(entries), null, 2),
    [entries]
  );

  return (
    <div
      style={{
        marginTop: Spacing.XS,
        padding: Spacing.XS,
        background: Colors.BG.SECONDARY,
        // 2026-10-13 小欧 - 与 §3.4.3 复用表对齐: 底/框/圆角与 MarkdownText 代码块同款(T32)
        border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: Radius.SM,
        fontFamily: FontFamily.MONO,
        fontSize: FontSize.CODE,
        lineHeight: `${FontSize.CODE + Spacing.XS}px`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          color: Colors.TEXT.STRONG,
        }}
      >
        <CircleArrow
          size={14}
          color={Colors.PRIMARY}
          expanded
          animated={false}
        />
        <span>{'{'}</span>
        {/* 2026-10-13 小欧 - B1/D-9 决策: 复制按钮改 inline + 中间 flex:1 占位顶到行尾。
            原默认形态(absolute)的包含块是树根而非树头, 会压住第一条节点行的值列 */}
        <span style={{ flex: 1 }} />
        <CopyButton text={copyText} inline />
      </div>
      {entries.map(([k, v], idx) => {
        // 2026-10-13 小欧 - nodeKey 只由 idx 构成(不掺 key), 参数 key 仅作显示 label
        const nodeKey = String(idx);
        return (
          <ParamNode
            key={nodeKey}
            nodeKey={nodeKey}
            label={k}
            value={v}
            isExpanded={isExpanded}
            onToggle={onToggle}
          />
        );
      })}
    </div>
  );
};

export { ParamsTree };
export default ParamsTree;
