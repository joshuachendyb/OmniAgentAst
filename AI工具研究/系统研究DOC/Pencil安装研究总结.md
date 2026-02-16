# Pencil 安装研究总结

**研究时间**: 2026-02-06 至 2026-02-07
**文档创建时间**: 2026-02-07 05:06:29
**版本**: v1.0
**存放位置**: D:\2bktest\MDview\AI工具研究\

---

## 一、研究背景

### 1.1 什么是 Pencil

Pencil（官网：https://www.pencil.dev/）是一款 **AI 驱动的 UI 设计画布工具**，核心创新在于打破了传统的"设计→交接→开发"工作流程。

**主要特点**：
- 直接嵌入代码编辑器（VS Code 或 Cursor）
- 基于 MCP（Model Context Protocol）与 AI 编程工具协作
- 支持 Claude Code、Cursor、Windsurf 等
- 设计文件（.pen）直接存储在代码仓库中

### 1.2 为什么要研究

在 Windows 环境下，Pencil 的安装方式较为复杂，存在多种安装途径，需要确定最适合与 OpenCode 集成的方案。

---

## 二、Pencil 的安装方式调研

### 2.1 方式一：桌面应用（Desktop Application）

**官方下载地址**：https://www.pencil.dev/downloads

**各平台支持情况**：

| 平台 | 状态 | 说明 |
|------|------|------|
| **macOS** | ✅ 可用 | Apple Silicon 和 Intel 版本均有 |
| **Linux** | ✅ 可用 | AppImage 和 Tarball 格式 |
| **Windows** | ❌ 暂不支持 | 官网显示 "coming very soon" |

**macOS 下载链接**：
- Apple Silicon: https://5ykymftd1soethh5.public.blob.vercel-storage.com/Pencil-mac-arm64.dmg
- Intel: https://5ykymftd1soethh5.public.blob.vercel-storage.com/Pencil-mac-x64.dmg

**Linux 下载链接**：
- AppImage x64: https://5ykymftd1soethh5.public.blob.vercel-storage.com/Pencil-linux-x86_64.AppImage
- AppImage ARM: https://5ykymftd1soethh5.public.blob.vercel-storage.com/Pencil-linux-arm64.AppImage

**我们的测试**：
- 下载了错误的 Pencil 版本（evolus/pencil，原型设计工具）
- 正确的 Pencil.dev 桌面版 Windows 尚未发布
- **结论**：Windows 用户目前无法使用桌面版

### 2.2 方式二：VS Code 扩展（推荐）

**官方文档**：https://docs.pencil.dev/getting-started/installation

**安装步骤**：
1. 打开 VS Code
2. 进入 Extensions（Ctrl + Shift + X）
3. 搜索 "Pencil"
4. 点击安装（作者是 highagency）

**验证安装**：
1. 创建新文件，扩展名改为 `.pen`
2. 打开文件，查看右上角是否出现 Pencil 图标
3. 如果没有，打开命令面板（Ctrl + Shift + P），搜索 "Pencil"

**Windows 命令行安装**：
```bash
code --install-extension highagency.pencildev
```

**VS Code 市场地址**：
- https://marketplace.visualstudio.com/items?itemName=highagency.pencildev

### 2.3 方式三：Cursor 扩展

**安装步骤**：
1. 打开 Cursor IDE
2. 进入 Extensions
3. 搜索 "Pencil"
4. 点击安装

**验证方式**：与 VS Code 相同

### 2.4 方式四：其他 IDE 支持

**支持的 IDE**：
- ✅ VS Code
- ✅ Cursor
- ✅ Google Antigravity
- ✅ Windsurf

**Open VSX 地址**（用于 VSCodium 等）：
- https://open-vsx.org/extension/highagency/pencildev

---

## 三、错误尝试记录

### 3.1 错误 1：安装了错误的 Pencil

**错误版本**：evolus/pencil（GitHub: https://github.com/evolus/pencil）

**特征**：
- 这是一个传统的 GUI 原型设计工具
- 不是 AI 驱动的设计工具
- 不支持 MCP 协议

**发现问题**：
- 配置文件位置：`C:\Users\40968\.pencil\config.json`
- 配置内容与 Pencil.dev 完全不同
- 没有 MCP 相关配置

**解决方法**：
```bash
# 卸载步骤
1. 停止 Pencil 进程
2. 运行卸载程序 "E:\0APPsoftware\Pencil\Uninstall Pencil.exe"
3. 删除残留文件：
   - E:\0APPsoftware\Pencil\
   - C:\Users\40968\.pencil
   - C:\Users\40968\AppData\Roaming\Pencil
   - C:\Users\Public\Desktop\Pencil.lnk
```

### 3.2 错误 2：尝试桌面版与 OpenCode 直接通信

**测试过程**：
1. 启动 Pencil 桌面应用（错误版本）
2. 检查进程：`tasklist | findstr pencil`
3. 尝试 OpenCode MCP 命令：`opencode mcp list`
4. 结果：未检测到 MCP 服务器

**失败原因**：
- 安装的是错误的 Pencil 版本
- 正确的 Pencil.dev Windows 桌面版尚未发布

---

## 四、正确的集成方案

### 4.1 方案一：VS Code + OpenCode + Pencil（推荐）

**适用场景**：Windows 用户，需要立即使用

**架构**：
```
VS Code (IDE)
├── OpenCode 扩展（AI 编程助手）
├── Pencil 扩展（AI 设计画布）
└── 两者通过 MCP 协议协作
```

**安装步骤**：

**步骤 1：安装 OpenCode VS Code 扩展**
```bash
code --install-extension sst-dev.opencode
# 或搜索：OpenCode by SST
```

**步骤 2：安装 Pencil VS Code 扩展**
```bash
code --install-extension highagency.pencildev
# 或搜索：Pencil by High Agency
```

**步骤 3：验证安装**
1. 重启 VS Code
2. 查看左侧边栏是否有 Pencil 铅笔图标
3. 查看状态栏是否有 OpenCode 图标
4. 创建 `.pen` 文件测试

**步骤 4：配置 Claude Code**
```bash
# 安装 Claude Code CLI
npm install -g @anthropic-ai/claude-code-cli

# 登录
claude

# 验证
claude --version
```

**步骤 5：验证 MCP 连接**
- 在 VS Code 中打开 Pencil
- 在 Cursor/VS Code 设置中查看 Tools & MCP
- 确认 Pencil 出现在 MCP 服务器列表

### 4.2 方案二：等待 Windows 桌面版

**适用场景**：不急于使用，希望独立应用

**状态**：官网显示 "coming very soon"

**预期功能**：
- 独立的桌面应用程序
- OpenCode 可直接通过 MCP 连接
- 无需 VS Code

### 4.3 方案三：手动配置 MCP（待测试）

**理论上可行**：
- Pencil VS Code 扩展启动时会启动 MCP Server
- 如果能找到 MCP Server 的可执行文件和端口
- 可以在 OpenCode 中手动配置 MCP

**待解决问题**：
- MCP Server 路径不确定
- 需要随 VS Code 扩展一起启动
- 配置复杂度较高

---

## 五、参考资源汇总

### 5.1 官方资源

| 资源 | 链接 | 说明 |
|------|------|------|
| **官网** | https://www.pencil.dev/ | 产品介绍和下载 |
| **文档** | https://docs.pencil.dev/ | 完整使用文档 |
| **安装文档** | https://docs.pencil.dev/getting-started/installation | 安装指南 |
| **AI 集成** | https://docs.pencil.dev/getting-started/ai-integration | AI 工具集成 |
| **下载页面** | https://www.pencil.dev/downloads | 各平台下载 |

### 5.2 扩展市场

| 平台 | 链接 |
|------|------|
| **VS Code** | https://marketplace.visualstudio.com/items?itemName=highagency.pencildev |
| **Cursor** | cursor:extension/highagency.pencildev |
| **Antigravity** | antigravity:extension/highagency.pencildev |
| **Windsurf** | windsurf:extension/highagency.pencildev |
| **Open VSX** | https://open-vsx.org/extension/highagency/pencildev |

### 5.3 教程和学习资源

| 资源 | 链接 | 说明 |
|------|------|------|
| **CSDN 深度指南** | https://blog.csdn.net/u013134676/article/details/157392400 | Pencil.dev 深度使用指南（中文） |
| **GitHub Skills** | https://github.com/anthropics/skills/tree/main/skills | Claude Code Skills |
| **pencil-ui-design** | https://github.com/AllenAI2014/pencil-ui-design | UI 设计规范 Skill |

### 5.4 我们之前的研究

| 文档 | 位置 | 说明 |
|------|------|------|
| **Skill-MCP-plugin安装日志** | D:\50RuleTool\Skill-MCP-plugin安装日志.md | Skills 安装记录 |
| **AI助手安装程序铁规** | D:\50RuleTool\规范与规则\AI助手安装程序铁规.md | 环境变量配置规范 |

---

## 六、关键概念说明

### 6.1 MCP（Model Context Protocol）

**定义**：模型上下文协议，标准化 AI 助手与外部工具通信的接口。

**工作原理**：
```
AI 助手 (Claude Code/Cursor/OpenCode)
    ↓ MCP 协议
MCP Server (Pencil/文件系统/数据库等)
    ↓ 读写
设计文件/代码/数据
```

**配置位置**：
- VS Code/Cursor: 设置 → Tools & MCP
- Claude Code: `~/.claude/config.json`
- OpenCode: `opencode.json` 或 `opencode.jsonc`

### 6.2 .pen 文件

**定义**：Pencil 的设计文件格式，纯文本 JSON。

**特点**：
- 可直接用 Git 版本控制
- 支持分支、合并、历史追踪
- 人类可读，AI 可编辑

**示例结构**：
```json
{
  "type": "frame",
  "name": "Page",
  "children": [
    {
      "type": "frame",
      "name": "Button",
      "fill": "#18181B",
      "cornerRadius": 8
    }
  ]
}
```

### 6.3 Skills 和 Design System

**Skills**：Claude Code/OpenCode 的扩展功能模块。

**我们安装的 Skills**：
- `docx` - Word 文档处理
- `ui-ux-pro-max` - UI/UX 设计
- `pencil-ui-design` - Pencil 设计规范

**Design Tokens**：设计系统的变量定义（颜色、字体、间距等）。

---

## 七、Windows 环境特殊说明

### 7.1 当前限制

- ❌ Pencil 桌面应用暂不支持 Windows
- ✅ 只能通过 VS Code 扩展使用
- ✅ 功能和 macOS/Linux 版本一致

### 7.2 环境变量配置

**PATH 中需要包含**：
```
E:\0APPsoftware\Microsoft VS Code\bin
E:\0APPsoftware\nodejs
```

**配置方法**：
使用我们验证过的 Python + winreg 方法（见 AI助手安装程序铁规）。

### 7.3 推荐工作流

```
1. 在 VS Code 中打开项目
2. 创建或打开 .pen 文件（Pencil 画布）
3. 在 Pencil 中设计 UI（自然语言或手动）
4. 使用 OpenCode/Claude Code 生成代码
5. 迭代修改，设计即代码
```

---

## 八、常见问题（FAQ）

### Q1: Pencil 可以替代 Figma 吗？

**A**: 对于快速原型和小型项目可以。但对于大规模设计系统，Figma 仍然更成熟。可以搭配使用：Figma 设计 → 导入 Pencil → 生成代码。

### Q2: 生成的代码质量如何？

**A**: 取决于 AI 工具和提示。通常可直接用于生产，但复杂逻辑可能需要微调。使用 Skills 定义设计规范可提高代码质量。

### Q3: Windows 桌面版什么时候发布？

**A**: 官网显示 "coming very soon"，但无具体日期。建议使用 VS Code 扩展版。

### Q4: OpenCode 能直接使用 Pencil 吗？

**A**: 目前需要通过 VS Code 扩展间接使用。等 Windows 桌面版发布后，可直接通过 MCP 集成。

### Q5: 需要付费吗？

**A**: Pencil 插件本身免费。但可能需要付费的 AI 工具（如 Claude 订阅）。

---

## 九、结论和建议

### 9.1 当前最佳方案

**Windows 用户**（推荐）：
1. 在 VS Code 中安装 OpenCode 扩展
2. 在 VS Code 中安装 Pencil 扩展
3. 两者在 VS Code 内协作使用

**macOS/Linux 用户**：
- 可选桌面应用或 VS Code 扩展
- 桌面应用可与 OpenCode 直接通过 MCP 集成

### 9.2 我们的下一步

**短期**（现在就能做）：
- [ ] 在 VS Code 中安装 OpenCode 扩展
- [ ] 在 VS Code 中安装 Pencil 扩展
- [ ] 测试完整工作流：设计 → 生成代码

**中期**（等发布）：
- [ ] 等待 Pencil Windows 桌面版
- [ ] 测试桌面版与 OpenCode 直接集成

**长期**：
- [ ] 建立完整的 Design System（使用 pencil-ui-design Skill）
- [ ] 创建项目特定的组件库

### 9.3 重要提醒

⚠️ **不要安装错误的 Pencil**：
- ❌ evolus/pencil（传统原型工具）
- ✅ highagency.pencildev（AI 设计工具）

⚠️ **安装前确认**：
- 查看扩展作者是 "High Agency"
- 官网确认：https://www.pencil.dev/

---

## 十、附录

### 10.1 相关 GitHub 仓库

| 仓库 | 链接 | 用途 |
|------|------|------|
| **Pencil** | https://github.com/pencildev/pencil | 官方仓库 |
| **pencil-ui-design** | https://github.com/AllenAI2014/pencil-ui-design | 设计规范 Skill |
| **Anthropic Skills** | https://github.com/anthropics/skills | Claude Code Skills |

### 10.2 相关 npm 包

```bash
# Claude Code CLI
npm install -g @anthropic-ai/claude-code-cli

# Skills 安装工具
npx skills add <skill-name>

# 旧版（已弃用）
npx add-skill <skill-name>
```

### 10.3 配置文件位置

**Windows**：
- VS Code 扩展：`C:\Users\40968\.vscode\extensions\`
- OpenCode 配置：`C:\Users\40968\AppData\Roaming\.opencode\`
- Skills：`C:\Users\40968\AppData\Roaming\.opencode\skills\`
- Claude Code：`C:\Users\40968\.claude\`

---

**文档更新时间**: 2026-02-07 05:06:29
**研究者**: OpenCode AI Assistant
**状态**: 已完成初步研究，待实施安装
