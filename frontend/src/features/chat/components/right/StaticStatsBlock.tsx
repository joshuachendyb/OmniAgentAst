// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 任务结束静态统计块7项+token终值, 历史C1/当前final_stats(4.5.1)
// 编辑历史: 2026-08-27 小欧 - 修复#8: 工具汇总空对象{}时显'-'而非空白(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 修复: 8.4.2 抽STATUS_COLOR_MAP查表替嵌套三元
// 编辑历史: 2026-08-27 小欧 - 去框/边距: 去卡片双框留上分割线(borderTop#f0f0f0,去#fafafa+radius+padding覆盖), marginTop8→12 paddingTop8→padding12, 仅留终止语义锚点
// 编辑历史: 2026-08-27 小欧 - 修复chat-H: accumulated_usage 空对象{}时 token 字段缺失显'-'而非 undefined
// 编辑历史: 2026-08-28 小强 - 修复: token字段缺失显undefined, 用?? '-'兜底 - 小强-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 修复工具汇总null×4: 工具汇总过滤tool_name为null的条目(根因: SQL取错key致全归null); 删除步骤/轮次行(TaskInfoBar已展示)
// 编辑历史: 2026-08-30 小欧 - 布局调整: column 2→3, 第一行放最终状态/总耗时/token终值, 第二行工具汇总横跨3列; 删除重试行(TaskInfoBar已展示)
// 编辑历史: 2026-09-01 小欧 - 修复token终值行折行: 加contentStyle whiteSpace:nowrap强制单行 + 格式紧凑化P/C/T去/两侧空格省宽度; 不折行不剪切(北京老陈要求) - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 任务统计增强 v0.8: 重构为极简六节(状态Tag同行/基本信息无框/Token行内/工具汇总+单折叠链/产出物极简列表/错误弱提示)，去重总耗时/tokenTag/产出Tag - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复工具调用链折叠三角移至(*步)后 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 规范全页折叠方法与符号位置/大小统一：三角统一置于(*步)后、复用TrustPanel可访问方法与FontSize/Spacing/Colors常量，符号大小统一FontSize.SECONDARY - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 整个板块可折叠(北京老陈定案): 默认折叠只显标题行(任务统计+Tag+运行时间+▼), 点击展开显示完整统计内容; 与内层工具调用链折叠独立互不影响
// 编辑历史: 2026-09-11 小欧 - DB滞后兜底: detail.status为executing但有duration(>0)或updated_at时覆盖为completed, 防SSE final后DB未及时更新致状态残留 - 小欧-2026-09-11
// 编辑历史: 2026-09-11 小欧 - M3c(标题行析出+折叠状态提升): 标题行(title 段)析出至 TitleBlock, 折叠状态提升父级受控; finalStats 帧复合兜底(tool_stats/artifacts/llm/步数), DB 失败也渲染折叠区 — 小欧-2026-09-11
// 编辑历史: 2026-09-11 小欧 - 修复: fmtTime块体补return(原缺return恒返undefined TS2322×2); props复用TokenLayer消重复私有形状(DRY), import TokenLayer — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - 修复: 抽sectionStyle/sectionTitleStyle模块级常量消4处容器+4处标题重复(DRY); 全部硬编码灰阶收敛至Colors.TEXT三档, fontSize:12收敛至FontSize.SECONDARY(复用优先) — 小欧-2026-09-12
// 编辑历史: 2026-09-15 小欧 - 第一阶段: S6错误警示条#fff1f0/#ffa39e→Colors.ERROR_BG/ERROR_BORDER;
//   S7二级折叠▲▼→CircleArrow(20px 静止animated=false, 复用组件); A1/A2参数slice(0,80)硬截→省略号+复用EllipsisTip悬停全文 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 历史补记(工作区已落地改动核查补齐): 全板块间距/字号令牌化收敛——
//   sectionStyle marginTop10→Spacing.MD/paddingTop8→MD; 标题 paddingLeft6→SM; 网格 columnGap12→LG/rowGap4→XS/marginTop6→SM;
//   fontSize11→FontSize.CAPTION×2 处; lineHeight 18/22px→字号+Spacing派生; gap8→MD; marginTop 6/4/2→SM/XS/XS/2 — 小欧-2026-09-15
// 编辑历史: 2026-09-17 小欧 - 修改: 错误项英文枚举经 formatErrorType 转中文标签(方括号去掉)+图标换 CloseCircleFilled — 小欧-2026-09-17
// 编辑历史: 2026-10-22 小欧 - 2 处硬编码 'monospace' 收敛到 FontFamily.MONO 令牌(DRY) — 小欧-2026-10-22
// 2026-10-22 小欧 - 产出物路径改 FilePathLink 可点深链（原死文本须手抄路径）— 小欧-2026-10-22
// 2026-10-27 小欧 - doc[48] N6 配套([40] H3 同批决策): sectionTitleStyle 色条 PRIMARY→BORDER.STRONG——
//   TitleBlock 主标题「任务统计」加 PRIMARY 蓝色条后, 五节子标题若同色即层级倒挂(子标题视觉权重 ≥ 主标题)。
//   降级浅灰条后主标题(蓝条+14px+600) > 子标题(灰条+12px+500); 顺带 fontWeight 500 裸写→FontWeight.MEDIUM(DRY) — 小欧-2026-10-27
// 2026-10-28 小欧 - 展开区域优化(用户定案): ①修数据重复——"事件"与"步数"同显 total_steps 删"事件"行,
//   Token 任务级重复(accumulated_usage 与 task_accumulated_tokens)合并——主值用 accumulated_usage(K/M 单位
//   对齐 TitleBlock), task_accumulated_tokens 已由 adaptTaskDetail 兜底并入 usage 不再单独显; ②布局分组
//   5 碎片节→2 大语义组(任务元信息=基本信息+Token / 执行结果=工具汇总+产出物), 错误低频独立贴边保留;
//   ③截断一致——工具调用链参数 slice(0,80) 硬截改 EllipsisTip+CSS 宽度省略(对齐 TaskInfoBar 位2 做法);
//   ④基本信息去"开始/结束"(用户令), grid 4列→2列; 工具汇总单行·连接改 flex 换行 chip — 小欧-2026-10-28
// 2026-10-28 小欧 - 去魔法数字(三堂会审): 展开区遗留数字字面量全部令牌化/常量化——
//   复用现有令牌: 12px→Spacing.LG(容器padding), 1px→BorderWidth.THIN(section/chip/错误条边框),
//   2px→BorderWidth.THICK(sectionTitle色条), 4→Radius.SM(错误条圆角);
//   无现成令牌提模块级局部常量(命名沿用 ParamsPanel NESTED_INDENT_PX 先例):
//   LABEL_COL_W=72(基本信息标签列宽)/ARROW_SIZE=20(链折叠箭头直径)/CHIP_RADIUS=2(chip圆角,Radius.SM=4偏大)/
//   CHAIN_ROW_GAP=Spacing.XS/2(链行间距)/SEQ_COL_W=20(链序号列宽)/PARAM_MAX_W=320(参数省略最大宽)/
//   ART_INDEX_W=16(产出物序号列宽)/ERR_PAD_Y=2(错误条纵向内边距,横向用Spacing.SM)。
//   纯样式令牌化零逻辑改动, 视觉零变化; 三堂会审通过(合规/合理/关联) — 小欧-2026-10-28
/**
 * StaticStatsBlock - 任务结束静态统计块（右侧查看区底部）
 *
 * 【小欧 2026-08-26 8.5】7 项：最终状态/总耗时/总步骤轮次/工具汇总/错误/重试/产出物
 * + 单任务 token 终值（4.5.1 行7/14）。历史=C1 TaskDetail；当前任务终态经
 * final_stats/FinalStep 下发后由外层把 ExecutionStep 映射为 TaskDetail 传入。
 * 动态/静态分工：本组件只在任务结束后出现，切换锚定任务随之切换（4.5.1 联动规则）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Typography } from 'antd'; // Tag 已移至 TitleBlock，此处删除
import { CloseCircleFilled } from '@ant-design/icons'; // 2026-09-17 小欧 修改: 错误项 emoji 改 antd SVG 内联图标 — 小欧-2026-09-17
import { formatErrorType } from '@/features/chat/components/ErrorDetail'; // 2026-09-17 小欧 修改: 中文标签映射复用 — 小欧-2026-09-17
import type { TaskDetail } from '../../../../services/api/task.api';
import type { ExecutionStep } from '../../../../types/execution';
import type { FinalStatsFrame } from '@/types/sse'; // 2026-09-11 小欧 M3c(final_stats帧复合兜底): 折叠区复合兜底数据源 — 小欧-2026-09-11
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontWeight,
  FontSize,
  Radius,
  Spacing,
  formatTokenFull,
  type TokenLayer,
} from '@/utils/stepStyles'; // 2026-09-11 小欧 修复: 复用公用 TokenLayer 消重复私有形状(DRY) — 小欧-2026-10-22(补 FontFamily 收敛字体栈)
import { EllipsisTip } from '../taskinfo/EllipsisTip'; // 2026-09-15 小欧 复用省略+Tooltip全文封装 — 小欧-2026-09-15
import { formatTokenK } from '../taskinfo/infoMaps'; // 2026-10-28 小欧 - 展开区域 Token 主值用 K/M 单位(对齐 TitleBlock) — 小欧-2026-10-28
import { CircleArrow } from '@/components/CircleArrow'; // 2026-09-15 小欧 复用折叠箭头组件 — 小欧-2026-09-15
// 2026-10-22 小欧 - 产出物路径改可点深链（原先是死文本，必须手抄路径）
import { FilePathLink } from '@/components/FilePathLink';

// ==================== 展开区局部尺寸常量 ====================
// 2026-10-28 小欧 - 去魔法数字: 本组件专属尺寸(无现成令牌)提模块级常量;
//   能复用现有令牌(Spacing/Radius/BorderWidth/FontSize)一律用令牌, 不重造(DRY/复用优先)。
//   命名沿用项目先例(ParamsPanel NESTED_INDENT_PX / InputHistoryPanel PANEL_W 等局部常量) — 小欧-2026-10-28
const LABEL_COL_W = 72; // 基本信息 grid 标签列宽(标签左值右)
const ARROW_SIZE = 20; // 工具调用链折叠箭头直径(标题行 CircleArrow 24 属另一组件, 各自局部)
const CHIP_RADIUS = 2; // 工具汇总 chip 圆角(Radius.SM=4 偏大, chip 用更小)
const CHAIN_ROW_GAP = Spacing.XS / 2; // 工具调用链行间距(Spacing.XS 半档)
const SEQ_COL_W = 20; // 工具调用链序号列宽
const PARAM_MAX_W = 320; // 工具调用链参数省略最大宽(对齐 TaskInfoBar 位2 收窄口径)
const ART_INDEX_W = 16; // 产出物序号列宽
const ERR_PAD_Y = 2; // 错误警示条纵向内边距

// 2026-09-12 小欧 修复: 模块级样式常量, 消四处section容器+四处标题完全重复(DRY) — 小欧-2026-09-12
const sectionStyle: React.CSSProperties = {
  marginTop: Spacing.MD,
  borderTop: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
  paddingTop: Spacing.MD,
};
const sectionTitleStyle: React.CSSProperties = {
  fontSize: FontSize.SECONDARY,
  fontWeight: FontWeight.MEDIUM,
  color: Colors.TEXT.PRIMARY,
  // 2026-10-27 小欧 - 色条 PRIMARY→BORDER.STRONG(doc[48] N6 + [40] H3 同批决策): 主标题「任务统计」
  //   已加 PRIMARY 蓝色条, 五节子标题若同色则层级倒挂(蓝条子标题 ≥ 蓝条主标题)。降级浅灰条后:
  //   主标题(蓝条+14px+600) > 子标题(灰条+12px+500), 层级清晰。BORDER.STRONG 是既有令牌, 不新增(DC-19);
  //   fontWeight 500 裸写→FontWeight.MEDIUM(DRY) — 小欧-2026-10-27
  borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.STRONG}`,
  paddingLeft: Spacing.SM,
};

interface StaticStatsProps {
  detail: TaskDetail | null;
  chainSteps?: ExecutionStep[];
  // 小欧 2026-09-11 M3c(final_stats帧复合兜底): final_stats 帧复合兜底——DB 缺失/失败时折叠区字段不空(三者复合) — 小欧-2026-09-11
  finalStats?: FinalStatsFrame | null;
  // 2026-09-11 小欧 修复: TokenLayer 复用(stepStyles.ts 公用), 与 RightViewer props 同契约, 消除必选/可选形状不一致(TS2322) — 小欧-2026-09-11
  sessionTokens?: TokenLayer;
  chainTokens?: TokenLayer;
}

const StaticStatsBlock: React.FC<StaticStatsProps> = ({
  detail,
  chainSteps,
  finalStats, // 小欧 2026-09-11 M3c(final_stats帧复合兜底): 折叠区复合兜底 — 小欧-2026-09-11
  sessionTokens,
  chainTokens,
}) => {
  const [chainOpen, setChainOpen] = React.useState(false);
  // 小欧 2026-09-11 M3c(final_stats帧复合兜底): DB 全缺失时 final_stats 帧兜底，两者都无才隐藏
  // 小欧 2026-09-11 M3c(final_stats帧复合兜底): effectiveStatus/statusColor 已移至 TitleBlock（final 帧 outcome 驱动，不读 DB）— 小欧-2026-09-11
  if (!detail && !finalStats) return null;
  // 小欧 2026-09-11 M3c(final_stats帧复合兜底): DB 读到的字段优先, final_stats 帧兜底(DB 失败/缺失时折叠区不空) — 小欧-2026-09-11
  const toolStats: Record<string, number> =
    detail?.tool_stats && Object.keys(detail.tool_stats).length > 0
      ? detail.tool_stats
      : (finalStats?.tool_stats ?? detail?.tool_stats ?? {});
  const artifacts =
    detail?.artifacts && detail.artifacts.length > 0
      ? detail.artifacts
      : (finalStats?.artifacts ?? detail?.artifacts ?? []);
  const llmCallCount = detail?.llm_call_count ?? finalStats?.llm_call_count;
  const stepCount = detail?.total_steps ?? finalStats?.step_count;
  const chain = (chainSteps ?? []).filter((s) => s.type === 'action');
  const chainSeq =
    chain.flatMap((s) => (s.tools ?? []).map((t) => t.tool)).join(' -> ') ||
    '-';
  return (
    <div
      style={{
        marginTop: 0, // 2026-09-11 小欧 M3c: title 段已移至 TitleBlock，此 div 仅承载折叠区内容，去掉标题行 margin — 小欧-2026-09-11
        padding: `0 ${Spacing.LG}px ${Spacing.LG}px`, // 2026-09-11 小欧 M3c: 上方 padding 清零，与 TitleBlock 下边缘自然衔接 — 小欧-2026-09-11
        background: 'transparent',
        border: 'none',
        borderRadius: 0,
        // borderTop 已移至 TitleBlock（L71 附近），此处删除防双线 — 小欧-2026-09-11
      }}
    >
      {/* 展开内容（title 段已由父级 TitleBlock 渲染，此处从"基本信息"开始）— 小欧 2026-09-11 第七章 M3c */}
      <>
        {/* 2026-10-28 小欧 - 布局分组: 5 碎片节→2 大语义组。组1「任务元信息」= 基本信息(去开始/结束/事件)
            + Token(主值 K/M 对齐 TitleBlock, 任务级重复已并入 usage 不再单显) — 小欧-2026-10-28 */}
        <div style={sectionStyle}>
          <Typography.Text style={sectionTitleStyle}>任务元信息</Typography.Text>
          {/* 基本信息: 去"开始/结束"(用户令)/"事件"(与步数重复), grid 4列→2列(标签左值右) — 小欧-2026-10-28 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `${LABEL_COL_W}px 1fr`,
              columnGap: Spacing.LG,
              rowGap: Spacing.XS,
              marginTop: Spacing.SM,
              fontSize: FontSize.SECONDARY,
            }}
          >
            <span style={{ color: Colors.TEXT.SECONDARY }}>步数</span>
            <span style={{ color: Colors.TEXT.STRONG }}>
              {stepCount ?? '-'}
            </span>
            <span style={{ color: Colors.TEXT.SECONDARY }}>LLM</span>
            <span style={{ color: Colors.TEXT.STRONG }}>
              {llmCallCount ?? '-'}
            </span>
            <span style={{ color: Colors.TEXT.SECONDARY }}>模型</span>
            <span
              style={{
                color: Colors.TEXT.STRONG,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {detail?.provider ?? '-'} / {detail?.model ?? '-'}
            </span>
          </div>
          {/* Token 主值: 任务级 P/C/T, K/M 单位对齐 TitleBlock; task_accumulated_tokens 已由 adaptTaskDetail
              兜底并入 accumulated_usage, 不再单显(修任务级重复) — 小欧-2026-10-28 */}
          <div
            style={{
              marginTop: Spacing.SM,
              fontSize: FontSize.SECONDARY,
            }}
          >
            <Typography.Text style={{ color: Colors.TEXT.SECONDARY }}>
              Token{' '}
            </Typography.Text>
            <Typography.Text
              style={{
                color: Colors.TEXT.PRIMARY,
                fontWeight: FontWeight.MEDIUM,
              }}
            >
              {detail?.accumulated_usage
                ? `P ${formatTokenK(detail.accumulated_usage.prompt_tokens)} / C ${formatTokenK(detail.accumulated_usage.completion_tokens)} / T ${formatTokenK(detail.accumulated_usage.total_tokens)} [tok]`
                : '-'}
            </Typography.Text>
          </div>
          {/* 会话级/链级 次要行(任务级已并入主值) — 小欧-2026-10-28 */}
          {(() => {
            const s = sessionTokens;
            const c = chainTokens;
            if (!s && !c) return null;
            return (
              <div
                style={{
                  marginTop: Spacing.XS,
                  fontSize: FontSize.CAPTION,
                  color: Colors.TEXT.SECONDARY,
                  lineHeight: `${FontSize.CAPTION + Spacing.XS}px`,
                }}
              >
                {s && <div>会话级: {formatTokenFull(s)}</div>}
                {c && <div>链级: {formatTokenFull(c)}</div>}
              </div>
            );
          })()}
        </div>
        {/* 2026-10-28 小欧 - 布局分组: 组2「执行结果」= 工具汇总+产出物 — 小欧-2026-10-28 */}
        <div style={sectionStyle}>
          <Typography.Text style={sectionTitleStyle}>执行结果</Typography.Text>
          {/* 工具汇总: 单行·连接改 flex 换行 chip — 小欧-2026-10-28 */}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: Spacing.SM,
              marginTop: Spacing.XS,
              fontSize: FontSize.SECONDARY,
            }}
          >
            {toolStats && Object.keys(toolStats).length > 0
              ? Object.entries(toolStats)
                  .filter(([k]) => k !== 'null')
                  .map(([k, v]) => (
                    <span
                      key={k}
                      style={{
                        color: Colors.TEXT.PRIMARY,
                        background: Colors.BG.LIGHT,
                        border: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
                        borderRadius: CHIP_RADIUS,
                        padding: `0 ${Spacing.XS}px`,
                        lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
                      }}
                    >
                      {k}×{v}
                    </span>
                  ))
              : '-'}
          </div>
          {/* 折叠规范(小欧 2026-09-01): 三角统一▲▼、大小14(PRIMARY)、颜色PRIMARY#595959、位置数量后、方法role=button/aria-expanded/tabIndex/onKeyDown - 北京老陈定案，全页统一 */}
          <div
            role="button"
            tabIndex={0}
            aria-expanded={chainOpen}
            onClick={() => setChainOpen(!chainOpen)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                setChainOpen(!chainOpen);
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              cursor: 'pointer',
              lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
              marginTop: Spacing.XS,
            }}
          >
            <span
              style={{
                fontSize: FontSize.SECONDARY,
                color: Colors.TEXT.PRIMARY,
              }}
            >
              工具调用链{chain.length ? ` (${chain.length}步)` : ''}
            </span>
            {/* 2026-09-15 小欧: ▲▼→CircleArrow(20px/PRIMARY#595959/静止animated=false), 复用组件消双三角符号 — 小欧-2026-09-15 */}
            <CircleArrow
              size={ARROW_SIZE}
              color={Colors.TEXT.PRIMARY}
              expandedColor={Colors.TEXT.PRIMARY}
              expanded={chainOpen}
              animated={false}
              style={{ marginLeft: Spacing.XS }}
            />
          </div>
          {chainOpen && (
            <div style={{ marginTop: Spacing.XS }}>
              <Typography.Text style={{ fontSize: FontSize.SECONDARY }}>
                {chainSeq}
              </Typography.Text>
              {chain.flatMap((s, sIdx) =>
                (s.tools ?? []).map((t, tIdx) => {
                  // 2026-10-28 小欧: slice(0,80) 硬截改 EllipsisTip+CSS 宽度省略(对齐 TaskInfoBar 位2 做法) — 小欧-2026-10-28
                  const paramText = JSON.stringify(t.params ?? {});
                  return (
                    <div
                      key={`${sIdx}-${tIdx}`}
                      style={{
                        fontSize: FontSize.SECONDARY,
                        display: 'flex',
                        gap: Spacing.MD,
                        marginTop: CHAIN_ROW_GAP,
                      }}
                    >
                      <span
                        style={{ color: Colors.TEXT.SECONDARY, minWidth: SEQ_COL_W }}
                      >
                        {sIdx + 1}.{tIdx + 1}
                      </span>
                      <span style={{ color: Colors.TEXT.PRIMARY }}>
                        {t.tool}
                      </span>
                      <EllipsisTip
                        text={paramText}
                        tooltip={paramText}
                        maxWidth={PARAM_MAX_W}
                      >
                        <span
                          style={{
                            color: Colors.TEXT.SECONDARY,
                            fontFamily: FontFamily.MONO,
                          }}
                        >
                          {paramText}
                        </span>
                      </EllipsisTip>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
        {/* 2026-09-12 修复: 产出物 section 复用常量; 序号/类型#8c8c8c→SECONDARY, 工具名#595959→PRIMARY, 名称#262626→STRONG — 小欧-2026-09-12 */}
        <div style={sectionStyle}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.MD,
              marginTop: Spacing.XS,
            }}
          >
            <Typography.Text style={sectionTitleStyle}>产出物</Typography.Text>
            <Typography.Text
              type="secondary"
              style={{ fontSize: FontSize.SECONDARY }}
            >
              {(artifacts ?? []).length} 个{' '}
              {/* 小欧 2026-09-11 M3c: DB 优先 final_stats 兜底 — 小欧-2026-09-11 */}
            </Typography.Text>
          </div>
          {(artifacts ?? []).length > 0 ? (
            (artifacts ?? []).map((a, i) => (
              <div
                key={a.path}
                style={{
                  display: 'flex',
                  gap: Spacing.MD,
                  fontSize: FontSize.SECONDARY,
                  lineHeight: `${FontSize.SECONDARY + Spacing.SM}px`,
                }}
              >
                <span style={{ color: Colors.TEXT.SECONDARY, minWidth: ART_INDEX_W }}>
                  {i + 1}
                </span>
                <span style={{ color: Colors.TEXT.PRIMARY }}>
                  {a.tool_name || '-'}
                </span>
                <span style={{ color: Colors.TEXT.STRONG }}>{a.name}</span>
                <span
                  style={{
                    color: Colors.TEXT.SECONDARY,
                    fontSize: FontSize.CAPTION,
                  }}
                >
                  {a.type}
                </span>
                {/* 2026-10-22 小欧 - 路径 → 可点深链
                    判界（根内/形态）在 FilePathLink 内统一处理，根外路径退化为纯文本 */}
                <FilePathLink rawPath={a.path} text={a.path} />
              </div>
            ))
          ) : (
            <Typography.Text
              type="secondary"
              style={{ fontSize: FontSize.SECONDARY }}
            >
              0 个 — 无产出物
            </Typography.Text>
          )}
        </div>
        {detail?.error_message && (
          /* 2026-09-15 小欧: 错误(低频)脱离统一sectionStyle(去borderTop分隔), 弱化为贴边警示，与高频四节分主次 — 小欧-2026-09-15 */
          <div style={{ marginTop: Spacing.MD }}>
            {/* 2026-09-15 小欧: 警示条#fff1f0/#ffa39e→Colors.ERROR_BG/ERROR_BORDER 令牌化 — 小欧-2026-09-15 */}
            <Typography.Text
              style={{
                fontSize: FontSize.SECONDARY,
                background: Colors.ERROR_BG,
                border: `${BorderWidth.THIN}px solid ${Colors.ERROR_BORDER}`,
                borderRadius: Radius.SM,
                padding: `${ERR_PAD_Y}px ${Spacing.SM}px`,
                display: 'inline-block',
              }}
            >
              <CloseCircleFilled style={{ color: Colors.ERROR }} />{' '}
              {formatErrorType(detail.error_type || '')}：{detail.error_message}
            </Typography.Text>
          </div>
        )}
      </>
    </div>
  );
};

export { StaticStatsBlock };
