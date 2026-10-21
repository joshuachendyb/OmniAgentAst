// 编辑历史: 2026-10-13 小欧 - 新建: Step 页参数区
//   顶层键默认折叠(仅含换行的巨型值) · 长行折行完整显示 · 树头复制(格式化 JSON) — 小欧 2026-10-13
//   其余实现要点: ①nodeKey 只由 entries 下标 idx 构成(不掺参数 key), 参数 key 内含 '/' 也不撞键;
//   ②key 列限宽 96 与浮层 GroupView 同宽(两载体口径一致);③树头复制按钮用 inline + 中间 flex:1 顶到行尾
// 编辑历史: 2026-10-21 小杨 - 路径判定抽到 paramCategories（单一真源，ParamsPanel/ParamsTree 双入口共用）、
//   路径类值渲染成可点击链接（直达文件页） — 小杨-2026-10-21
//   (原默认形态 position:absolute 的包含块是树根而非树头, 会压住第一条节点行的值列);
//   ④行容器 className="params-clickable" 走 CSS hover/focus 反馈(零重渲染);⑤底/框/圆角与 MarkdownText 代码块同款;
//   ⑥**补底部闭合 `}`**(结构图均有, 初稿代码漏渲染);⑦树根 CircleArrow 显式给 expandedColor=PRIMARY,
//     否则恒展开态会用默认 FOLD_EXPANDED 粉(#ff4d94)—— 粉色在本系统是"可折叠且当前展开"的语义色,
//     树根不可折叠(no onClick), 用该色属误导, 与「装饰图标不用蓝」同一逻辑 — 小欧 2026-10-13
// 2026-10-13 小欧 - 十三轮**规则重写**(北京老陈裁定, 违反即打回):
//   【铁律】只有 content 这类**含换行的巨型值**才允许折叠/展开; 其余所有参数一律不许折叠,
//   长行**折行完整显示**, 不截断、不隐藏、不给 title 悬停替代。
//   本次删掉: ①对象/数组的 branch 折叠(树里 `meta ▾ {…} N 项` 即违反, 已改为直接展开 JSON);
//             ②字符阈值方案(曾按 >200 字判可折叠, 已删); ③单行省略号 + 行级 title。
import React, { useCallback, useMemo, useState } from 'react';
import { CircleArrow } from '@/components/CircleArrow';
import { CopyButton } from '@/components/markdown/CopyButton';
// 2026-10-21 小杨 - 路径判定单一真源 + 路径可点击 + 项目根取数
import { isPathParam } from './paramCategories';
import { PathAwareJson } from './PathAwareJson';
import { PathLink } from './PathLink';
import { useProjectRoot } from '@/hooks/useProjectRoot';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  Icon,
  Radius,
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
  // 2026-10-21 小杨 - 路径链接需要项目根（绝对路径→相对路径）
  const projectRoot = useProjectRoot();
  const kind = classify(value);
  const foldable = kind === 'body';
  const open = foldable && isExpanded(nodeKey);
  const summary = foldable
    ? `共 ${String(value).split('\n').length} 行`
    : // 对象值由 PathAwareJson 渲染，这里不再预先 JSON.stringify 一份（大对象白跑一遍）
      typeof value === 'object' && value !== null
      ? ''
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
          {/* 2026-10-21 小杨 - 路径值接链接；对象/数组递归渲染，嵌套 path 也可点。
              多行值走折叠体（原文完整展示），不做成整段链接文本 */}
          {!foldable &&
          typeof value === 'string' &&
          isPathParam(label, value) ? (
            <>
              {': '}
              <PathLink value={value} projectRoot={projectRoot} />
            </>
          ) : typeof value === 'object' && value !== null ? (
            <>
              {': '}
              <PathAwareJson value={value} projectRoot={projectRoot} />
            </>
          ) : (
            `: ${summary}`
          )}
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
          // 2026-10-13 小欧 - 补 expandedColor: 树根**恒展开且不可折叠**(无 onClick), 若用默认的
          //   FOLD_EXPANDED(#ff4d94 粉)会永远显示粉色 —— 而粉色在本系统是"可折叠且当前展开"的语义色,
          //   用在不可交互元素上属误导(同「装饰图标不用蓝」一条逻辑)。显式给 PRIMARY 保持恒蓝。
          expandedColor={Colors.PRIMARY}
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
      {/* 2026-10-13 小欧 - 补底部闭合括号: 设计 §2.2/§3.4.1 结构图都有 `}`, 而初稿代码只渲染了
          开头 `{` 属漏实现(与「示意图左对齐 vs 文字右对齐」同类的示意图-代码脱节)。
          marginLeft = 箭头宽 14 + gap 6 = Icon.BOX + Spacing.XS, 使 `}` 与 `{` 同一 x 起手 */}
      <div
        style={{
          marginLeft: Icon.BOX + Spacing.XS,
          color: Colors.TEXT.STRONG,
        }}
      >
        {'}'}
      </div>
    </div>
  );
};

export { ParamsTree };
export default ParamsTree;
