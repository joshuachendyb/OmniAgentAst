# Desktop工具Schema全面整改设计方案

**版本**: v3.0
**创建时间**: 2026-07-30 21:17:20
**编写人**: 小欧

---

## 版本历史

| 版本 | 时间 | 修改简介 | 编写人 |
|------|------|---------|--------|
| v1.0 | 2026-07-30 21:17:20 | 创建：8个schema问题初步方案 | 小欧 |
| v2.0 | 2026-07-30 21:35:07 | 深度审查补充：发现6类共16个问题，含代码Bug/llm_data错别字/参数名不一致 | 小欧 |
| **v3.0** | **2026-07-30 21:41:10** | **终审修正：合并#16,补#17,修3处文档错误** | **小欧** |
| **v4.0** | **2026-07-30 23:04:29** | **实施补充：原始15项全部落地+三轮复审新增19项整改** | **小欧** |

---

## 一、审查范围

熟读5遍，逐行审查11个工具的全部代码：
- `desktop_schema.py` — 14个Schema类 + model_validator
- `desktop_register.py` — 11个register描述 + 参数模型 + examples
- 11个工具实现文件：全部 `_build_*_llm_data` + 主函数 + helper函数

---

## 二、问题总览（共15个）

### 2.1 分类汇总

| 类型 | 数量 | 说明 |
|------|------|------|
| A. Schema参数描述不清 | 8个 | 原8问题 |
| B. 代码Bug | 1个 | screen_capture summary |
| C. llm_data 错误 | 5处 | 错别字/params key/描述不同步 |
| D. 代码/Register遗漏 | 2处 | 函数签名import + register描述 |

### 2.2 完整清单

| # | 工具 | 问题 | 类型 | 严重度 | 文件(行) |
|---|------|------|------|--------|---------|
| 1 | clipboard_control | `content` default=""与"必填"矛盾 | A | 高 | schema:176 |
| 2 | mouse_scroll | `amount` "滚动单位"太模糊 | A | 高 | schema:114 |
| 3 | mouse_move | `x/y` 没说坐标参考系 | A | 中 | schema:100-104 |
| 4 | window_info/focus/resize/state | "模糊匹配"没说具体方式(4处) | A | 中 | schema:35,41,47,70 |
| 5 | window_resize | `width/height` 默认值说明不全 | A | 中 | schema:49-55 |
| 6 | mouse_click | docstring与Field重复 | A | 低 | schema:78 |
| 7 | screen_capture | `region` Dict键描述不规范 | A | 中 | schema:149-151 |
| 8 | screen_capture | `display` 编号范围没说清 | A | 低 | schema:153-155 |
| 9 | screen_capture | **llm_data summary: "属于第" 后面空** | **B** | **高** | **screen_capture.py:40-42** |
| 10 | window_focus | **llm_data 错别字 "围为"→"为"(2处)** | **C** | **中** | **window_focus.py:23,29** |
| 11 | window_focus | **llm_data params key "title"≠schema "window_title"** | **C** | **中** | **window_focus.py:24** |
| 12 | window_resize | **llm_data params key "title"≠schema "window_title"** | **C** | **中** | **window_resize.py:24** |
| 13 | mouse_scroll | **llm_data 仍说"单位" 应与schema同步改"次"** | **C** | **低** | **mouse_scroll.py:30** |
| 14 | window_resize | **llm_data success summary 标点多 "成功:,"** | **C** | **低** | **window_resize.py:33** |
| 15 | clipboard_control | **函数签名未同步 + import缺Optional** | **D** | **中** | **clipboard_control.py:116,17** |
| 17 | clipboard_control | **llm_data params 缺content** | **B** | **中** | **clipboard_control.py:29** |

> **说明**: #16 已合并到 #4（set_window_state register 描述变更归入 #4）

---

## 三、逐项整改（共15项）

### 3.1 A类 — Schema参数描述（8项）

#### #1 clipboard_control — content 参数矛盾

**问题**: `content: str = Field(default="", description="写入内容(action=write时必填)")`

default="" 给LLM错误暗示有默认值可不传，实际action=write时为空就报错。

**代码行为** `clipboard_control.py:138`:
```python
if not content:  # catches "" and None
```

**整改**:
```python
content: Optional[str] = Field(
    default=None,
    description="action=write时必填的写入内容"
)
```

**逻辑影响**: 无。`if not content` 兼容 None 和 ""。

---

#### #2 mouse_scroll — amount 描述模糊

**问题**: `description="滚动单位"` — 什么单位？像素？行？

**代码行为** `mouse_scroll.py:45`:
```python
scroll_amount = -amount if direction == "down" else amount
pyautogui.scroll(scroll_amount)  # 传滚轮点击次数，每次约3行文本
```

**整改**:
```python
# schema
amount: int = Field(default=3, description="滚动次数(每次约3行文本)")

# register
"amount为滚动次数(每次约3行文本,默认3)"
```

---

#### #3 mouse_move — x/y 没说坐标参考系

**问题**: `description="目标X坐标"` — 相对于什么？

**代码行为** `mouse_move.py:46`:
```python
pyautogui.moveTo(x, y, duration=duration)  # 屏幕绝对坐标，(0,0)=主显示器左上角
```

**整改**:
```python
# schema
x: int = Field(..., description="屏幕绝对X坐标(像素,左上角为原点)")
y: int = Field(..., description="屏幕绝对Y坐标(像素,左上角为原点)")

# register
"x/y为屏幕绝对坐标(像素,左上角为原点)"
```

---

#### #4 四工具统一 — "模糊匹配"→"子串匹配"

**问题**: 4个工具写"大小写不敏感的模糊匹配"，实际是 substring 匹配。

**代码行为** `window_info.py:152`:
```python
filter_title.lower() in w["title"].lower()  # substring匹配
```

**整改**（schema 4处 + register 3处）:
```python
# schema 4处统一:
description="窗口标题(大小写不敏感的子串匹配)"

# register 3处:
"filter_title按标题子串过滤"              # window_info
"window_title支持大小写不敏感的子串匹配"  # window_focus + set_window_state
```

> ✅ #16 合并进 #4，set_window_state register 描述也改"模糊"→"子串"

---

#### #5 window_resize — width/height 默认值说明

**问题**: 没说 width/height=0 时保持原大小。

**代码行为** `window_resize.py:72-73`:
```python
new_width = width if width else curr_width   # 0→保持原宽
new_height = height if height else curr_height # 0→保持原高
```

**整改**:
```python
# schema
width: int = Field(default=800, description="窗口宽度(像素),传0保持原宽度")
height: int = Field(default=600, description="窗口高度(像素),传0保持原高度")

# register
"width/height为目标宽高(像素),传0保持原大小"
```

---

#### #6 mouse_click — docstring 与 Field 重复

**问题**: DocString和Field description重复讲 xy 规则。

**整改**: 删除 docstring，Field + model_validator 已足够。

---

#### #7 screen_capture — region 描述不规范

**问题**: "Dict键:x(默认0)/y(默认0)..." 写法不规范。

**代码行为**: 所有键可选，有默认值。

**整改**:
```python
description="截取区域{x,y,width,height}(像素),不传的键使用默认值(0,0,800,600)。与display互斥"
```

---

#### #8 screen_capture — display 编号范围

**问题**: 没说明3+显示器情况。

**代码行为**: `display < 1 or display >= len(monitors)` → fallback到主显示器。

**整改**:
```python
description="显示器编号(1=主显示器,2~N=扩展显示器)。与region/dest互斥"
```

---

### 3.2 B类 — 代码Bug（2项）

#### #9 screen_capture — llm_data summary Bug

**位置**: `screen_capture.py:40-42`
```python
monitor_text = f"（{monitor_count}个显示器）" if monitor_count > 0 else ""
return {
    "summary": f"截图成功: 已保存到{dest}.属于第{monitor_text}",
    ...
}
```

**问题**: 当 `monitor_count=0`（pyautogui fallback），输出：
```
"截图成功: 已保存到{path}.属于第"  ← "属于第"后面空
```

**整改**:
```python
# 旧
monitor_text = f"（{monitor_count}个显示器）" if monitor_count > 0 else ""
return {
    "summary": f"截图成功: 已保存到{dest}.属于第{monitor_text}",
    ...
}

# 新
if monitor_count > 0:
    summary = f"截图成功: 已保存到{dest}（{monitor_count}个显示器）"
else:
    summary = f"截图成功: 已保存到{dest}"
return {
    "summary": summary,
    ...
}
```

---

#### #17 clipboard_control — llm_data params 缺 content

**位置**: `clipboard_control.py:29`
```python
"params": {"action": action}  # 缺少 content!
```

**对比** `keyboard_control.py:22-23`:
```python
_act_params = {"action": action}
if text_or_keys:
    _act_params["text_or_keys"] = text_or_keys
```

**问题**: LLM 看 params 里只有 action，**不知道写了什么内容**。

**整改**:
```python
# 旧
_act_params = {"action": action}

# 新
_act_params = {"action": action}
if content:
    _act_params["content"] = content
```

---

### 3.3 C类 — llm_data 错误（4项）

#### #10 window_focus — 错别字 "围为"→"为"

**位置**: `window_focus.py:23,29`
```python
"summary": f"聚焦窗口失败,其窗口标题围为 {title}"
"summary": f"窗口已聚焦: 其窗口标题围为 {title}"
```

**整改**: "围为" → "为"（2处）

---

#### #11 window_focus — params key 不一致

**位置**: `window_focus.py:24`
```python
"params": {"title": title}  # schema参数叫 window_title
```

**整改**: `"params": {"window_title": title}`

---

#### #12 window_resize — params key 不一致

**位置**: `window_resize.py:23-24`
```python
_act_params = {"width": width, "height": height}
if title:
    _act_params["title"] = title  # 应是 "window_title"
```

**整改**: `_act_params["window_title"] = title`

---

#### #13 mouse_scroll — llm_data 仍说"单位"

**位置**: `mouse_scroll.py:30`
```python
"summary": f"滚动完成: 方向是{direction} ,滚动{amount}单位"
```

**整改**:
```python
"summary": f"滚动完成: 方向{direction},滚动{amount}次"
```

---

#### #14 window_resize — success summary 标点

**位置**: `window_resize.py:33`
```python
"summary": f"调整标题为{title}的窗口成功:,分辨率为 {width}x{height}"
```
"成功:," 多了一个冒号。

**整改**:
```python
"summary": f"调整标题为{title}的窗口成功,分辨率为 {width}x{height}"
```

---

### 3.4 D类 — 代码/Register遗漏（1项）

#### #15 clipboard_control — 函数签名 + import 未同步

**问题**: Schema改`Optional[str]`，函数签名还 `content: str = ""`，且 import 缺 `Optional`。

**位置**: `clipboard_control.py:17,116`

**整改**:
```python
# import 补充
from typing import Dict, Any, Literal, Optional

# 函数签名
def clipboard_control(action: Literal["read", "write"], content: Optional[str] = None) -> Dict[str, Any]:
```

---

## 四、修改文件清单

| 文件 | 涉及问题 | 修改数量 |
|------|---------|---------|
| `desktop_schema.py` | #1,#2,#3,#4,#5,#6,#7,#8 | 14处 |
| `desktop_register.py` | #2,#3,#4,#5 | 6处 |
| `screen_capture.py` | #9(Bug) | 1处(4行改) |
| `window_focus.py` | #10,#11 | 3处 |
| `window_resize.py` | #12,#14 | 2处 |
| `mouse_scroll.py` | #13 | 1处 |
| `clipboard_control.py` | #15,#17 | 3处(import+sig+params) |

**合计**: 7个文件，15个问题，约30处修改点。

---

## 五、功能逻辑影响评估

| # | 修改点 | 是否改代码逻辑 | 风险 |
|---|--------|---------------|------|
| 1-8 | Schema描述 | 仅改描述 | 无风险 |
| 9 | screen_capture summary | 修复输出文本 | 无风险 |
| 10 | window_focus 错别字 | 修复输出文本 | 无风险 |
| 11 | window_focus params key | 修复llm_data key | 无风险 |
| 12 | window_resize params key | 修复llm_data key | 无风险 |
| 13 | mouse_scroll "单位"→"次" | 修复输出文本 | 无风险 |
| 14 | window_resize 标点 | 修复输出文本 | 无风险 |
| 15 | clipboard_control 签名+import | 类型标注同步 | 无风险 |
| 17 | clipboard_control params | 补充llm_data字段 | 无风险 |

**结论**: 15项全部零逻辑风险，只改描述/llm_data/类型标注。

---

## 六、Tool间协作 + LLM理解验证

### 6.1 Tool间协作

| 链路 | 数据映射 | 正确性 |
|------|---------|--------|
| window_info → screen_capture(region) | {left,top,width,height} → {x,y,width,height} | ✅ |
| window_info → window_focus | windows[].title → window_title | ✅ |
| window_info → window_resize | windows[].title → window_title | ✅ |
| window_info → set_window_state | windows[].title → window_title | ✅ |
| mouse_position → mouse_click | {x,y} → {x,y} | ✅ |
| mouse_move → mouse_click | (x,y) → 直接点 | ✅ |

### 6.2 LLM能看懂吗

**Schema改后**:
- ✅ "滚动次数(每次约3行文本)" — LLM 知道 amount 是次数
- ✅ "屏幕绝对X坐标(像素,左上角为原点)" — LLM 知道坐标系
- ✅ "子串匹配" — LLM 知道是 contains 匹配
- ✅ "传0保持原宽度" — LLM 知道 0 的含义
- ✅ "显示器编号(1=主显示器,2~N=扩展显示器)" — LLM 知道编号规则

**llm_data改后**:
- ✅ params key 与 schema 参数名一致 (window_focus, window_resize)
- ✅ clipboard_control params 补上 content (LLM 知道写了什么)
- ✅ 错别字修复 (window_focus "围为"→"为")
- ✅ mouse_scroll summary 改"单位"→"次"
- ✅ screen_capture summary 不再"属于第"空洞

### 6.3 Tool 内部功能 & 输出正确性审查

| 工具 | 内部功能 | result data | llm_data | 状态 |
|------|---------|-------------|----------|------|
| window_info | ✅ EnumWindows+过滤 | ✅ {"windows": [...]} | ✅ | OK |
| window_focus | ✅ EnumWindows+SetForeground | ✅ {} | ❌→✅ #10,#11 | 修复 |
| window_resize | ✅ GetWindowRect+MoveWindow | ✅ {width,height} | ❌→✅ #12,#14 | 修复 |
| set_window_state | ✅ ShowWindow/SetWindowPos | ✅ {} | ✅ | OK |
| mouse_click | ✅ pyautogui.click | ✅ {} | ✅ | OK |
| mouse_move | ✅ pyautogui.moveTo | ✅ {} | ✅ | OK |
| mouse_scroll | ✅ pyautogui.scroll | ✅ {} | ❌→✅ #13 | 修复 |
| mouse_position | ✅ GetCursorPos | ✅ {x,y} | ✅ | OK |
| keyboard_control | ✅ typewrite/hotkey | ✅ {text_length}/{keys} | ✅ | OK |
| screen_capture | ✅ screenshot/mss | ✅ {image_path,display} | ❌→✅ #9 | 修复 |
| clipboard_control | ✅ pyperclip/ctypes | ✅ {text} | ❌→✅ #15,#17 | 修复 |

---

## 七、验证方案

1. **语法检查**: `python -c "from app.tools.desktop.desktop_schema import *"`
2. **Pydantic验证**: 所有Input模型边界值测试
3. **llm_data结构一致性**: 确认 params key 与 schema 参数名匹配
4. **LLM实调验证**: 真实调用确认描述理解正确

---

## 八、原始15项实施状态（v4.0确认）

> 更新人: 小欧 | 更新时间: 2026-07-30 23:04:29

### 8.1 逐项实施确认

| # | 问题 | 状态 | 实施文件 | 验证方式 |
|---|------|------|---------|---------|
| 1 | clipboard_control content Optional | ✅ 已实施 | schema.py:172-175, clipboard_control.py:123 | AST+语法 |
| 2 | mouse_scroll amount描述"次数" | ✅ 已实施 | schema.py:115-118, register.py:98, mouse_scroll.py:34 | AST+语法 |
| 3 | mouse_move x/y绝对坐标 | ✅ 已实施 | schema.py:101-107, register.py:96 | AST+语法 |
| 4 | 四工具"子串匹配"统一 | ✅ 已实施 | schema.py:38,44,50,73 + register.py:86,88,92 | AST+语法 |
| 5 | window_resize width/height传0保持原大小 | ✅ 已实施 | schema.py:52-59, register.py:90 | AST+语法 |
| 6 | mouse_click删docstring | ✅ 已实施 | schema.py:80-98(model_validator已足够) | AST+语法 |
| 7 | screen_capture region描述规范 | ✅ 已实施 | schema.py:151-153 | AST+语法 |
| 8 | screen_capture display编号范围 | ✅ 已实施 | schema.py:155-158 | AST+语法 |
| 9 | screen_capture summary"属于第"空洞Bug | ✅ 已实施 | screen_capture.py:48-53 | AST+语法 |
| 10 | window_focus错别字"围为"→"为" | ✅ 已实施 | window_focus.py:27,33 | AST+语法 |
| 11 | window_focus params key title→window_title | ✅ 已实施 | window_focus.py:28,34 | AST+语法 |
| 12 | window_resize params key title→window_title | ✅ 已实施 | window_resize.py:26-28 | AST+语法 |
| 13 | mouse_scroll "单位"→"次" | ✅ 已实施 | mouse_scroll.py:34 | AST+语法 |
| 14 | window_resize success summary标点 | ✅ 已实施 | window_resize.py:37 | AST+语法 |
| 15 | clipboard_control函数签名+import | ✅ 已实施 | clipboard_control.py:19,123 | AST+语法 |
| 17 | clipboard_control llm_data params补content | ✅ 已实施 | clipboard_control.py:31-33 | AST+语法 |

**结论**: 原始15项全部实施完毕，7个文件约30处修改点全部落地。

---

## 九、三轮深度复审新增整改（v4.0）

> 更新人: 小欧 | 更新时间: 2026-07-30 23:04:29

在原始15项基础上，进行三轮深度复审（熟读3遍+三堂会审），发现并修复以下问题：

### 9.1 代码Bug修复（13项）

| # | 级别 | 文件 | 问题 | 修复 |
|---|------|------|------|------|
| 1 | CRITICAL | clipboard_control.py | `GMEM_MOVEABLE`未定义→ctypes fallback路径NameError崩溃 | 补`GMEM_MOVEABLE=0x0002` |
| 2 | HIGH | screen_capture.py | 所有error用同一dependency hint，非依赖错误也提示安装库 | hint区分依赖错误vs运行时错误 |
| 4 | HIGH | mouse_click.py | x/y=None时summary显示"点击(None,None)" | 改为"点击(当前位置,当前位置)" |
| 5 | HIGH | mouse_position.py | `if x or y`跳过(0,0)合法坐标 | 改为`if x is not None or y is not None` |
| 6 | HIGH | set_window_state.py | 非Windows平台也提示"需要安装pywin32" | hint区分平台不支持vs缺库 |
| 7 | MEDIUM | screen_capture.py | region/dest类型hint不规范(Optional) | 统一Optional类型标注 |
| 8 | MEDIUM | screen_capture.py | PIL import无ImportError处理 | 补try/except ImportError |
| 9 | MEDIUM | keyboard_control.py | hint格式不统一(依赖/运行时混合) | 统一is_dep_error判断 |
| 12 | MEDIUM | desktop_register.py | screen_capture描述未提display/region/dest互斥 | 补充互斥说明 |
| 17 | MEDIUM | window_info.py | get_window_rect返回None时前端可能报错 | 补默认值`{left:0,top:0,...}` |
| 10 | LOW | desktop_schema.py | 编辑历史超120字符 | 折行处理 |
| 14 | LOW | window_info.py | check_win32_platform()重复日志 | 删除调用时重复日志 |
| 16 | LOW | set_window_state.py | `msg_fmt`死代码(解构未使用) | 改为`_` |

### 9.2 LLM输出格式修复（2项）

| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| A | keyboard_control.py | error时status.message写"无效的键盘操作"但action实际有效 | 改为"键盘操作{action}失败" |
| B | desktop_schema.py | `from typing import List`未使用(lint warning) | 删除List |

### 9.3 失败路径Hint精确化（5项）

| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| C | mouse_click.py | 运行时异常hint说"或pyautogui库是否可用"但pyautogui已通过检查 | 去掉多余提示 |
| D | mouse_move.py | 同上 | 同上 |
| E | mouse_position.py | error_detail说"win32api/pyautogui均未安装"——win32api不是pip包，实际用ctypes | 改为"无可用依赖(ctypes获取失败,pyautogui未安装)" |
| F | mouse_position.py | hint说"需要安装pywin32库"——mouse_position不依赖pywin32 | 改为"鼠标位置获取不可用,请检查系统环境或安装pyautogui库" |
| G | window_info.py | 非Windows平台hint说"需要安装pywin32"——平台不支持安装无用 | 区分：非Windows→"此功能仅支持Windows系统" |

### 9.4 标点修正（1项）

| # | 文件 | 问题 | 修复 |
|---|------|------|------|
| H | set_window_state.py | summary `"窗口标题为:{title}"` 多余冒号 | 改为 `"窗口标题为{title}"` |

---

## 十、全量修改文件清单（v4.0）

| 文件 | 原始15项 | 新增整改 | 合计修改点 |
|------|---------|---------|-----------|
| `desktop_schema.py` | #1-#8,#10-#14,#15,#17 | 编辑历史折行+删List | ~18处 |
| `desktop_register.py` | #2-#5 | #12 screen_capture互斥 | ~7处 |
| `clipboard_control.py` | #15,#17 | #1 GMEM_MOVEABLE | ~5处 |
| `screen_capture.py` | #9 | #2hint/#7类型/#8 PIL | ~8处 |
| `window_focus.py` | #10,#11 | — | ~3处 |
| `window_resize.py` | #12,#14 | — | ~2处 |
| `mouse_scroll.py` | #13 | — | ~1处 |
| `mouse_click.py` | — | #4坐标显示+hint | ~4处 |
| `mouse_move.py` | — | hint精确化 | ~2处 |
| `mouse_position.py` | — | #5(0,0)+error_detail+hint | ~5处 |
| `keyboard_control.py` | — | #9hint+A status.message | ~4处 |
| `window_info.py` | — | #17rect+重复日志+hint | ~5处 |
| `set_window_state.py` | — | #6hint+#16死代码+H标点 | ~5处 |

**合计**: 13个文件，原始15项+新增19项=**34项整改**，约70处修改点。

---

## 十一、验证结果

| 验证项 | 结果 |
|--------|------|
| 9个核心文件AST解析 | ✅ 全部通过 |
| 4个补充文件AST解析 | ✅ 全部通过 |
| 语法检查(py_compile) | ✅ 13个文件全部通过 |
| 关键修改点grep验证 | ✅ 旧代码已清除，新代码就位 |
| 原始15项逐项确认 | ✅ 全部实施 |
| 成功路径llm_data审计 | ✅ 11个tool全部正确 |
| 失败路径hint精确化审计 | ✅ 5处错误hint已修正 |

---

**编写人**: 小欧
**更新人**: 小欧
**完成时间**: 2026-07-30 23:04:29

---

## 附四：2026-08-05 落实复核说明

**编写人**: 小欧
**时间**: 2026-08-05 17:44:47
**复核方法**: 逐一对照本方案原始15项+九章新增19项与本地 `F:\OmniAgentAs-repair\backend\app\tools\desktop` 实际源码（13个文件熟读3遍+AST语法检查+Pydantic边界值验证+llm_data结构一致性验证）。

### 一、复核总体结论

| 类别 | 数量 | 说明 |
|------|------|------|
| 原始15项全部实施 | 15 | schema/register/9个实现文件 |
| 九章新增19项全部实施 | 19 | 代码Bug13+LLM输出2+hint精确化5（含标点H归入代码Bug） |
| 未落地项 | 0 | — |
| 文档未记录但代码已增强 | 若干 | 三堂会审增强（见下） |

**核心结论**：本方案34项整改在本地代码**全部落地，无任何"声明已修但代码未修"的遗漏**。且代码存在文档未记录的后续三堂会审增强，实际比文档更完善。

### 二、原始15项逐项落地证据

| # | 整改 | 本地证据（文件:行号） |
|---|------|----------------------|
| 1 | clipboard content Optional+write必填 | `desktop_schema.py:187-196`(content Optional+validator) / `clipboard_control.py:140`(签名) |
| 2 | mouse_scroll amount描述"次数" | `desktop_schema.py:125-129`(含ge=1) / `desktop_register.py:101` |
| 3 | mouse_move x/y绝对坐标 | `desktop_schema.py:112-117` / `desktop_register.py:99` |
| 4 | 四工具"子串匹配"统一 | `desktop_schema.py:44,50,56,79` / `desktop_register.py:89-95` |
| 5 | window_resize传0保持原大小 | `desktop_schema.py:58-65` / `desktop_register.py:93` |
| 6 | mouse_click删docstring+xy同传 | `desktop_schema.py:86-108`(model_validator) |
| 7 | screen_capture region描述规范 | `desktop_schema.py:166-169` |
| 8 | screen_capture display编号范围 | `desktop_schema.py:170-173` |
| 9 | screen_capture summary"属于第"空洞Bug | `screen_capture.py:51-55`(monitor_count=0独立分支) |
| 10 | window_focus错别字"围为"→"为" | `window_focus.py:31,37` |
| 11 | window_focus params key title→window_title | `window_focus.py:32,38` |
| 12 | window_resize params key title→window_title | `window_resize.py:30-31` |
| 13 | mouse_scroll "单位"→"次" | `mouse_scroll.py:37` |
| 14 | window_resize success summary标点 | `window_resize.py:40`("成功,分辨率为") |
| 15 | clipboard函数签名+import | `clipboard_control.py:24`(Optional)/`:140`(签名) |
| 17 | clipboard llm_data params补content | `clipboard_control.py:36-37`(成功/失败路径均含) |

### 三、九章新增19项逐项落地证据

**9.1 代码Bug修复（13项）**：

| # | 文件 | 本地证据（文件:行号） |
|---|------|----------------------|
| 1 | clipboard GMEM_MOVEABLE | `clipboard_control.py:103`(`GMEM_MOVEABLE=0x0002`) |
| 2 | screen_capture hint区分依赖/运行时 | `screen_capture.py:165-171` |
| 4 | mouse_click x/y=None当前位置 | `mouse_click.py:28-29` |
| 5 | mouse_position (0,0)不被跳过 | `mouse_position.py:26`(`if x is not None or y is not None`) |
| 6 | set_window_state hint平台/缺库区分 | `set_window_state.py:79-80` |
| 7 | screen_capture region/dest类型hint | `screen_capture.py:29-30`(Optional) |
| 8 | screen_capture PIL import保护 | `screen_capture.py:122-126` |
| 9 | keyboard hint统一 | `keyboard_control.py:98-99`(is_dep_error) |
| 12 | register screen_capture互斥说明 | `desktop_register.py:107` |
| 17 | window_info get_window_rect默认值 | `window_info.py:110-111` |
| 10 | schema编辑历史折行+删List | `desktop_schema.py:11` |
| 14 | window_info重复日志删除 | `window_info.py:27-39`(模块加载单次) |
| 16 | set_window_state msg_fmt死代码→_ | `set_window_state.py:100`(`func, args =`) |

**9.2 LLM输出格式（2项）**：keyboard status.message改"键盘操作{action}失败"(`keyboard_control.py:33`)；desktop_schema删List import(`desktop_schema.py:33`)。

**9.3 失败路径hint精确化（5项）**：C(`mouse_click.py:70`)、D(`mouse_move.py:62`)、E(`mouse_position.py:58`)、F(`mouse_position.py:69`)、G(`window_info.py:149`) 全部修正。

**9.4 标点修正（1项）**：set_window_state summary冒号(`set_window_state.py:53`)。

### 四、文档未记录但代码已增强（代码超预期）

| 文件 | 增强内容 |
|------|---------|
| desktop_schema.py | 2026-07-31 三堂会审：Clipboard write必填validator、MouseScroll ge=1、Keyboard min_length=1、MouseClick clicks双击参数、Window title非空提示 |
| window_focus.py | B9(SetForegroundWindow返回值检查)、ERR_NO_WIN32GUI补导入 |
| window_resize.py | B24(MoveWindow返回值检查)、width显式判0 |
| mouse_scroll.py | B25(amount<=0拦截)、amount非int类型守卫 |
| clipboard_control.py | B4(owned防double-free)、B10(char_count原始长度)、B15/B26(OpenClipboard检查+read warning) |
| mouse_position.py | B19(补import ctypes.wintypes) |
| desktop_register.py | B17(注册循环异常隔离) |

### 五、验证结果

| 验证项 | 结果 |
|--------|------|
| 13个文件AST语法检查 | ✅ 全部通过 |
| Pydantic边界值（write无content/amount=0/xy同传/display互斥） | ✅ 全部正确拦截 |
| llm_data params key与schema参数名一致性 | ✅ 完全对齐（window_focus/window_resize/mouse_scroll/clipboard实测） |
| 34项整改逐项落地 | ✅ 全部实施 |

**结论**：本方案（原始15项+九章19项）已在本地代码完整落地，无遗漏，且代码含文档未记录的后续增强，符合并超出方案预期。
