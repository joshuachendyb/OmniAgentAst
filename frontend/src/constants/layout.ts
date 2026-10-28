// 编辑历史: 2026-10-27 小欧 - 新建: 会话页 SplitPane 布局常量(唯一定义点)
//   动因: 此前 30% / 180px / 500px 三个数字硬编码在 SplitPane.tsx 内部,
//   改默认宽度必须改组件源码, 违反 SRP(组件只管交互渲染, 不该管调参)
//   与 YAGNI(不该引入抽象, 但也不该把常量散落在实现里)。
//   处置: 常量上移本中立层, 与 settingsEvents.ts 同层同风格(唯一定义点)。
//   消费方: 仅 SplitPane.tsx 一处 import(全仓 grep 验证), 依赖方向单一。
//
//   修改指南: 想改"默认宽度"就改 DEFAULT_RATIO; 想改"拖动范围"就改 MIN_PX / MAX_RATIO。
//   改配置不影响已持久化的用户宽度(localStorage 优先), 想强制回滚默认值见 SplitPane 双击分割线彩蛋。
//
// 编辑历史: 2026-10-28 小欧 - 新增 INPUT_MIN_ROWS(2)/INPUT_MAX_ROWS(3): 输入框 autoSize 行数常量
//   动因: 原 InputCore.tsx 内部字面量上移, 与 SplitPane 常量同层(唯一定义点), 便于统一调参
//
//   @author 小欧
//   @date 2026-10-27

/** 左侧面板默认宽度占容器比例(拖动前的初始值; 用户拖动后由 localStorage 覆盖, 不再回退到本值) */
export const SPLIT_LEFT_DEFAULT_RATIO = 0.3;

/** 左侧面板最小宽度(px); 防止内容被挤压到不可读 */
export const SPLIT_LEFT_MIN_PX = 180;

/** 拖动时左侧最大宽度占容器比例; 保留右侧最小可操作空间 */
export const SPLIT_LEFT_MAX_RATIO = 0.8;

/** localStorage 持久化键; 值格式为像素数值字符串(如 "342")
 *  键名带版本号 v1, 未来结构变更可平滑迁移到 v2 */
export const SPLIT_PREFS_KEY = 'omni.split.v1.leftWidth';

/** 输入框 autoSize 最小行数(空态起步行数) */
export const INPUT_MIN_ROWS = 2;

/** 输入框 autoSize 最大行数(文字增多自动增行, 超过本行数出现内部滚动) */
export const INPUT_MAX_ROWS = 3;
