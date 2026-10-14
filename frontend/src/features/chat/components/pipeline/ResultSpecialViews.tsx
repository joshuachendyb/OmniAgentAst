// 结果视图的两个专用渲染器 —— 目录树 / 文件列表(北京老陈裁定 2026-10-14)
// 编辑历史: 2026-10-14 小欧 - 新建。`tree` / `listdir` 有业务语义(层级/列对齐),
//   通用 JSON 折叠表达不了, 故各写一个专用渲染器; 仅用于「TOOL结果」, 参数视图零影响。
//   数据来源(源码实证, 勿凭记忆改):
//     tree     app/tools/file/tree.py:115-122  {tree:{name,path,type,children[]}, statistics:{file_count,dir_count,total_size}}
//     listdir  app/tools/file/list_directory.py:48-51,127-134  {entries:[{name,type,mtime,[size]}], truncated}
//   注册名依据 app/tools/file/file_register.py:84 的注册清单(AGENTS 铁规指明的单一真源)。
import React, { useState } from 'react';
import { CircleArrow } from '@/components/CircleArrow';
import { Colors, FontFamily, FontSize, Spacing } from '@/utils/stepStyles';
import { formatTimestamp } from '@/utils/time';
import { formatBytes } from '@/utils/format';

/**
 * 2026-10-14 小欧 - mtime 是 **float Unix 时间戳**(list_directory.py:49 `st.st_mtime`),
 *   必须 *1000 才是毫秒 —— 直接交给 `new Date()` 会落到 1970 年。
 *
 * ⚠️ 2026-10-14 自查订正(两轮):
 *   ①初稿在此**自己拼**日期字符串, 属重复造轮子 —— 仓库已有 `src/utils/time.ts`(9 个格式化函数,
 *     AGENTS §1.3「先查后建」), 现复用 `formatTimestamp`。
 *   ②改用 `formatTimeHMS` 后**丢了日期**(只输出 HH:MM:SS), 对「修改时间」列不可用, 由测试抓出。
 *   现取 `formatTimestamp(...)` 并截到分钟精度: 完整输出带毫秒(23 字符)放不进 122px 列,
 *   而文件修改时间精确到秒已足够。故 `slice(0, 16)` 是**有意的精度取舍**, 非偷懒。
 */
const formatMtime = (v: unknown): string =>
  typeof v === 'number' && Number.isFinite(v)
    ? formatTimestamp(v * 1000).slice(0, 16)
    : '—';

/** 2026-10-14 小欧 - 统计数字千分位(tree.file_count 实测最大 26997)。 */
const fmtInt = (v: unknown): string =>
  typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('en-US') : '—';

const mono: React.CSSProperties = {
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.CODE,
  lineHeight: '16px',
};

const rowBase: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: Spacing.XS,
  padding: `1px 0`,
};

// ==================== 目录树 ====================

interface TreeNode {
  name?: unknown;
  path?: unknown;
  children?: unknown;
}

/**
 * 2026-10-14 小欧 - 递归数节点(树里**只含目录**: tree.py:97 过滤 `if item.is_dir()`)。
 *   用于底部统计; **不用 statistics.dir_count** —— 实测两者口径不一致(66 节点 vs 621)。
 *
 * ⚠️ 2026-10-14 探针修正: 原实现 `1 + children.reduce((s,k)=> s+count(k),0)` 在 children 含
 *   null/undefined/数字时把这些元素当 0 丢弃, 但 `DirNode` **照样给它们渲染一行**(key={i}),
 *   导致「底部个目录」与「实际渲染行数」对不上(探针: {children:[null,undefined,1]} 返回 1, 实渲 4 行)。
 *   ⚠️ 同轮第二个坑: 曾误改成 `1 + kids.length`(只数直接子节点), 链式深树从 2726 塌成 3 —— **递归不能丢**。
 *   故最终: 保持递归求和, 且每个数组元素至少算 1 个(与 DirNode 渲染行数一一对应)。
 */
export const countTreeNodes = (node: unknown): number => {
  if (typeof node !== 'object' || node === null) return 0;
  const kids = (node as TreeNode).children;
  // 非数组(含 null/undefined/字符串) → 当前节点自己算 1 个, 与 DirNode 一致(它也渲染本行)
  if (!Array.isArray(kids)) return 1;
  return (
    1 + kids.reduce<number>((sum, k) => sum + Math.max(1, countTreeNodes(k)), 0)
  );
};

/**
 * 2026-10-14 北京老陈裁定: 目录树也裁剪, 与 listdir **同口径**(200 + 裁剪说明)。
 *   探针实测: 2726 节点在 jsdom 渲染 2128ms / 5454 个 DOM —— jsdom 远慢于真实浏览器, 但足以证明
 *   「默认全展开 + 千级以上节点」不可接受。实测节点数中位 66、最大 2726, 故 200 覆盖绝大多数场景。
 *   额度只扣**真正渲染**的行: 节点被折叠时其子树不渲染也不占额度, 展开后自然露出更多。
 */
const TREE_NODE_LIMIT = 200;

const DirNode: React.FC<{
  node: TreeNode;
  depth: number;
  /** 共享渲染预算(可变计数器); 耗尽后本节点及其子树不再渲染。 */
  budget: { left: number };
}> = ({ node, depth, budget }) => {
  const [open, setOpen] = useState(true);
  const toggle = () => setOpen((p) => !p);
  const kids = Array.isArray(node.children) ? node.children : [];
  const name = typeof node.name === 'string' ? node.name : '';
  const path = typeof node.path === 'string' ? node.path : '';
  if (budget.left <= 0) return null;
  budget.left -= 1;
  return (
    <div>
      <div
        className="params-clickable"
        style={{ ...rowBase, paddingLeft: depth * 14, cursor: 'pointer' }}
        onClick={toggle}
        title={path}
      >
        <CircleArrow
          size={14}
          color={Colors.PRIMARY}
          expanded={open}
          animated={false}
        />
        <span style={{ ...mono, color: Colors.TEXT.STRONG }}>{name}</span>
      </div>
      {open &&
        kids.map((k, i) => (
          <DirNode
            key={i}
            node={k as TreeNode}
            depth={depth + 1}
            budget={budget}
          />
        ))}
    </div>
  );
};

/**
 * 2026-10-14 小欧 - `tree` 工具结果 → 目录树(默认全展开, 可逐层收起)。
 *   数据 `{tree:{name,path,type,children[]}, statistics:{file_count,dir_count,total_size}}`。
 */
export const DirTreeView: React.FC<{ data: Record<string, unknown> }> = ({
  data,
}) => {
  const tree = data.tree as TreeNode | undefined;
  const st = (data.statistics || {}) as Record<string, unknown>;
  if (!tree) return null;
  const total = countTreeNodes(tree);
  const cut = total > TREE_NODE_LIMIT;
  return (
    <div style={{ ...mono, flexBasis: '100%', width: '100%' }}>
      {/* 预算对象每次渲染重建 —— 折叠/展开后重新分配, 展开别的分支即可露出后续节点。
          父组件读不到 budget.left(子组件在父返回后才渲染), 故裁剪提示只按 total 判定。 */}
      <DirNode node={tree} depth={0} budget={{ left: TREE_NODE_LIMIT }} />
      <div
        style={{
          marginTop: Spacing.SM,
          paddingTop: Spacing.XS,
          borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
          color: Colors.TEXT.TERTIARY,
        }}
      >
        {total} 个目录 · {fmtInt(st.file_count)} 文件 ·{' '}
        {formatBytes(st.total_size)}
      </div>
      {cut && (
        <div
          style={{
            ...mono,
            color: Colors.TEXT.TERTIARY,
            paddingTop: Spacing.XS,
          }}
        >
          共 {total.toLocaleString('en-US')} 个目录，最多展示前{' '}
          {TREE_NODE_LIMIT.toLocaleString('en-US')}{' '}
          个；折叠部分节点后再展开其他分支可继续查看
        </div>
      )}
    </div>
  );
};

// ==================== 文件列表 ====================

/** 2026-10-14 北京老陈裁定: 列表只渲染前 200 条 + 截断说明。
 *  实测 entries 中位 20、最大 1410(单次调用), 故 200 覆盖绝大多数场景。 */
const LIST_PREVIEW_LIMIT = 200;

interface FileEntry {
  name?: unknown;
  type?: unknown;
  mtime?: unknown;
  size?: unknown;
}

/**
 * 2026-10-14 小欧 - `listdir` 工具结果 → 文件列表(四列平铺)。
 *   数据 `{entries:[{name,type,mtime,[size]}], truncated}`。
 *   ⚠️ 目录条目**无 size 键**(list_directory.py:50 仅文件有) —— 故用 `'size' in e` 判断,
 *   不可用 `e.size || '—'`, 否则 0 字节文件会被误判成"无大小"。
 */
export const FileListView: React.FC<{ data: Record<string, unknown> }> = ({
  data,
}) => {
  const entries = Array.isArray(data.entries)
    ? (data.entries as FileEntry[])
    : [];
  const shown = entries.slice(0, LIST_PREVIEW_LIMIT);
  const rest = entries.length - shown.length;

  // 2026-10-14 小欧 - 超时提示**先于**空态判断渲染: 「扫描超时且一个条目都没扫到」
  //   (entries=[] && truncated=true) 是真实存在的组合, 若先 return 空态就会丢掉提示,
  //   用户会误以为目录本来就是空的(2026-10-14 自查发现)。
  const timeoutNotice =
    data.truncated === true ? (
      <div
        style={{ ...mono, color: Colors.WARNING, padding: `${Spacing.XS}px 0` }}
      >
        已达扫描时限，结果可能不完整
      </div>
    ) : null;

  if (entries.length === 0) {
    return (
      <div style={{ flexBasis: '100%', width: '100%' }}>
        {timeoutNotice}
        <div style={{ ...mono, color: Colors.TEXT.TERTIARY }}>目录为空</div>
      </div>
    );
  }

  const colType: React.CSSProperties = {
    ...mono,
    width: 56,
    flexShrink: 0,
    color: Colors.TEXT.SECONDARY,
  };
  const colSize: React.CSSProperties = {
    ...mono,
    width: 76,
    flexShrink: 0,
    textAlign: 'right',
    color: Colors.TEXT.SECONDARY,
  };
  const colTime: React.CSSProperties = {
    ...mono,
    width: 122,
    flexShrink: 0,
    textAlign: 'right',
    color: Colors.TEXT.SECONDARY,
  };

  return (
    <div style={{ flexBasis: '100%', width: '100%' }}>
      <div
        style={{
          ...rowBase,
          color: Colors.TEXT.TERTIARY,
          borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
          paddingBottom: 2,
        }}
      >
        <span style={{ flex: 1, minWidth: 0 }}>名称</span>
        <span style={colType}>类型</span>
        <span style={colSize}>大小</span>
        <span style={colTime}>修改时间</span>
      </div>

      {timeoutNotice}

      {shown.map((e, i) => {
        const isDir = e.type === 'directory';
        return (
          <div
            key={i}
            className="params-clickable"
            style={{
              ...rowBase,
              color: isDir ? Colors.TEXT.SECONDARY : Colors.TEXT.PRIMARY,
            }}
            title={typeof e.name === 'string' ? e.name : undefined}
          >
            <span
              style={{
                ...mono,
                flex: 1,
                minWidth: 0,
                wordBreak: 'break-all',
                paddingLeft: 8,
              }}
            >
              {typeof e.name === 'string' ? e.name : ''}
            </span>
            <span style={colType}>{isDir ? '目录' : '文件'}</span>
            {/* 目录无 size 键; 0 字节文件 size=0 必须显示 "0 B" */}
            <span style={colSize}>
              {'size' in e ? formatBytes(e.size) : '—'}
            </span>
            <span style={colTime}>{formatMtime(e.mtime)}</span>
          </div>
        );
      })}

      {rest > 0 && (
        <div
          style={{
            ...mono,
            marginTop: Spacing.XS,
            paddingTop: Spacing.XS,
            borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
            color: Colors.TEXT.TERTIARY,
          }}
        >
          共 {entries.length.toLocaleString('en-US')} 项，已展示前{' '}
          {LIST_PREVIEW_LIMIT} 项，剩余 {rest.toLocaleString('en-US')} 项未展示
        </div>
      )}
    </div>
  );
};

// ==================== 派发 ====================

/**
 * 2026-10-14 小欧 - 结果视图的**专用渲染派发**。
 *   判据顺序: ① 工具名(注册清单 `app/tools/file/file_register.py:84` 的
 *   `"listdir", "tree", "find", "grep"` —— 这是 AGENTS 铁规指明的单一真源);
 *   ② 结构兜底(防注册名将来变动而静默退化)。
 *
 * ⚠️ 2026-10-14 实证删除了 `list_directory` 别名: 真库 4648 个 observation 步的
 *   `action.tools[].tool`(前端 toolName 的来源)统计 —— `listdir` **269 次**,
 *   `list_directory` **0 次**。别名只存在于 `app/tools/tools_alias_mapper.py:356`,
 *   **不在该产出链上**, 加它属 YAGNI(我一度被 `registry.py:363` 那行误导加过, 已删)。
 */
export const pickResultView = (
  toolName: string,
  data: Record<string, unknown>
): React.ReactNode => {
  const byName =
    toolName === 'tree' ? 'tree' : toolName === 'listdir' ? 'listdir' : null;
  /**
   * 2026-10-14 小欧 - 结构兜底判据必须是 `typeof === 'object' && !== null`, **不能用 `!== undefined`**:
   *   `null !== undefined` 为 true, 故 `{tree: null, statistics: {...}}` 会被误派发到 DirTreeView,
   *   而其内部 `if (!tree) return null` → **整个结果区空白**, 比落回通用视图更糟(探针实测证实)。
   */
  const byShape =
    typeof data.tree === 'object' &&
    data.tree !== null &&
    data.statistics !== undefined
      ? 'tree'
      : Array.isArray(data.entries)
        ? 'listdir'
        : null;
  const kind = byName ?? byShape;
  if (kind === 'tree') return <DirTreeView data={data} />;
  if (kind === 'listdir') return <FileListView data={data} />;
  return null;
};
