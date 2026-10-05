// 编辑历史: 2026-08-26 小欧 - 8.4.10 实施: 思考流灰斜体同列展开, 尾随呼吸光标(4.9.1②)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距修复: 段距margin4px0→8px0统一流水线节奏(8点网格主节奏)
// 编辑历史: 2026-08-30 小欧 - 设计稿实施(北京老陈 2026-08-30 批准): 段距落 Spacing.MD 常量(数值不变8px, 去魔法数字); 新增 normalizeBlankLines 显示入口(reasoning 段规约, 光标态即流式走尾随守卫防打字机回缩) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈定案纠正(step间8/内部6/折叠4): 加 compact prop, 同 step 内部(reasoning 与后置 thought 相邻)段距 SM(6), 默认仍是 MD(8)=step 间 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距走 stepMargin → 默认=(MD)-2=6, compact=(SM)-2=4, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(斜体视觉平衡): thought 斜体 14→12(secondary), 行高16(12+4), step间6/内4 层次不变 - 小欧-2026-08-30
// 编辑历史: 2026-09-14 小欧 - 思考光标不显示问题修复(北京老陈驱动): thinking 光圈本无需改动
//   (bind cursor 无打字机进度门槛); CURSOR T 打点下放本组件反转检测(false→true 才打, ref 去重) — 小欧-2026-09-14
//   2026-09-14 小欧 - DRY: 反转检测打点抽取公用 hook useRiseLog(本组件与 TextStream 同款逻辑去重) — 小欧-2026-09-14
// 编辑历史: 2026-10-05 小欧 - 思考图标行 + 每次可折叠展开(文档[9] §5.5):
//   ①每次 reasoning 一行([思考点图标 24px] + "推理内容..." + >); ②图标=绿色光圈 ReasoningIcon(替换原 🤖 AI emoji)
//   ③`>` 每次折叠是独立 state, 初值=reasoningVisible; ④收起态只显思考行(不显正文, 防刷屏挤掉后续 step)
//   ⑤折叠切换交公用 hook useDisclosure(同 CollapsibleText, 零逻辑复写) — 小欧-2026-10-05
// 编辑历史: 2026-10-05 小欧 - 三堂会审修复3处: ①useRiseLog 打点补 expanded 条件(收起态不渲染
//   thinking-cursor, 打点在折叠分支外会让诊断日志报"光标亮"而屏幕上无光标, 诊断说谎)
//   ②图标按 expanded 传 dim(收起=亮+动画 / 展开=暗+静止, CSS 侧两态)
//   ③defaultExpanded 改为"设置变化即跟随"(此前仅挂载读一次, 设为关对已渲染段无反应) — 小欧-2026-10-05
/**
 * ThinkingStream - 思考流（思考图标行 + 尾随光标）
 *
 * 【小欧 2026-08-26 8.4.10】4.9.1② 思考块灰斜体且不再"单独折叠"——与正文同列
 * 顺序展开；实时思考末段尾随呼吸光标(.thinking-cursor)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Colors, FontSize, Spacing, getStreamStyle } from '@/utils/stepStyles';
import { normalizeBlankLines } from '@/utils/textNormalize'; // 13.11 显示兜底 — 小欧 2026-08-30
import { useRiseLog } from '@/features/chat/hooks/useRiseLog'; // 2026-09-14 小欧: CURSOR T 翻转打点(抽公用 hook) — 小欧-2026-09-14
import { CircleArrow } from '@/components/CircleArrow'; // 2026-10-05 小欧: 折叠箭头(同 CollapsibleText) — 小欧-2026-10-05
import { ReasoningIcon } from '@/components/WaitingIcons'; // 2026-10-05 小欧: 思考点图标(文档[9] §5.3) — 小欧-2026-10-05
import { useDisclosure } from '@/features/chat/hooks/useDisclosure'; // 2026-10-05 小欧: 折叠切换公用 hook(§5.6) — 小欧-2026-10-05

interface ThinkingStreamProps {
  text: string;
  cursor?: boolean; // 实时思考末段光标
  compact?: boolean; // 同 step 内部(13.6 拆出的 reasoning 与后置 thought 相邻): 段距 SM(6)
  /**
   * 2026-10-05 小欧 - 折叠态初值(文档[9] §5.5): 取自 appearance.step_render.reasoningVisible,
   *   仅决定**每段初态**; 用户点击后是纯文本 state(每次思考独立可折叠)。
   *   未传时默认 true(展开), 保证渲染不分化(无此 prop 行为同旧版)。 — 小欧-2026-10-05
   */
  defaultExpanded?: boolean;
}

const ThinkingStream: React.FC<ThinkingStreamProps> = ({
  text,
  cursor = false,
  compact = false,
  defaultExpanded = true,
}) => {
  const clean = normalizeBlankLines(text, { streaming: cursor }); // 13.11: 思考段规约, 光标态(实时末段)走尾随守卫
  // 2026-10-05 小欧 - 设置跟随(北京老陈: 开关设为关后 reasoning 必须收着):
  //   defaultExpanded 此前只在挂载读一次(设置异步到达, 数据回来时标题行已把旧值吃进
  //   useState), 改成关对已渲染段完全无反应、切页面也无效。现改为:
  //   设置值**变化**时立即跟随(用户手动折过的也重置) —— 设置是"默认值", 用户手动折叠是临时
  //   覆盖; 设置一改即视为新基线, 否则该段会对该开关永久失效且无任何提示(原实现)。
  //   设置值不变时不动, 故流式过程中用户手动折叠不会被自动弹回。
  const { expanded, setExpanded, onToggleClick, onToggleKeyDown } =
    useDisclosure(defaultExpanded);
  const touched = React.useRef(false);
  const prevDefault = React.useRef(defaultExpanded);
  React.useEffect(() => {
    if (prevDefault.current !== defaultExpanded) {
      prevDefault.current = defaultExpanded;
      touched.current = false; // 新基线: 清掉临时覆盖标记
    }
    if (!touched.current) setExpanded(defaultExpanded);
  }, [defaultExpanded, setExpanded]);
  // 2026-09-14 小欧: thinking 光标本就 bind cursor(无打字机进度门槛), 翻转打点(CURSOR T)
  //   2026-10-05 小欧: 补 expanded —— 收起态正文与光标均不渲染, 打点须与实际渲染一致 — 小欧-2026-10-05
  useRiseLog('CURSOR T', cursor && expanded);
  if (!text && !cursor) return null;
  return (
    <div
      className="thinking-stream"
      style={{
        color: Colors.TEXT.SECONDARY,
        fontSize: FontSize.SECONDARY,
        lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
        fontStyle: 'italic',
        ...getStreamStyle(compact),
      }}
    >
      {/* 2026-10-05 小欧 - 思考图标行 + 每次可折叠(文档[9] §5.5, 北京老陈裁定):
          思考段每一行一个; 图标=绿色光圈 ReasoningIcon(§5.3) 替换原 🤖 AI emoji,
          后文只留"推理内容..."; 折叠层只有文本 state(每次独立), 不写回设置(见 §5.11) — 小欧-2026-10-05 */}
      <span
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-label={expanded ? '收起思考' : '展开思考'}
        onClick={(e) => {
          touched.current = true; // 用户手动折过 → 后续设置变化不再覆盖(设置是默认值, 用户选择优先)
          onToggleClick(e);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') touched.current = true;
          onToggleKeyDown(e);
        }}
        style={{
          // 2026-10-05 小欧 修正: 必须块级(flex), 不能用文档原写的 inline-flex ——
          //   inline-flex 是行内盒, 其后紧跟的正文会**接在同一行**(图标行+正文串行, 破版);
          //   块级后正文另起一行 = 保持 2026-10-05 之前"reasoning 正文独占一行"的原样 — 小欧-2026-10-05
          display: 'flex',
          width: 'fit-content', // 块级但宽度只占内容, 避免整行被 point 事件铺满
          alignItems: 'center',
          gap: Spacing.XS,
          fontStyle: 'normal', // 图标行不斜体(斜体是思考正文的视觉语言)
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        <ReasoningIcon size={24} dim={expanded} />
        {'推理内容...'}
        <CircleArrow
          size={14}
          color={Colors.PRIMARY}
          expanded={expanded}
          animated={false}
        />
      </span>
      {/* 正文: 折叠态不显全文(防刷屏挤掉后续 step) 展开态显示完整内容 */}
      {expanded && (
        <>
          {clean}
          {cursor && <span className="thinking-cursor">▍</span>}
        </>
      )}
    </div>
  );
};

export { ThinkingStream };
