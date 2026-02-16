# UI UX Pro Max Skill 安装使用指南

**创建时间**: 2026-02-05 00:48:21

## 重要说明：全局安装

本指南采用**全局安装**模式：

| 组件 | 安装位置 | 说明 |
|-----|---------|------|
| **CLI工具** | npm全局目录 | `npm install -g uipro-cli` |
| **Skill资源** | `%APPDATA%\.opencode\skills\` | 全局目录，所有项目共享 |

**全局安装优势**：
- 一次安装，所有项目可用
- 资源集中管理，易于维护
- 卸载简单，不留残留

---

## 一、文档概述

### 1.1 文档目的

本文档为UI UX Pro Max Skill的完整安装、使用和卸载指南。UI UX Pro Max是一个AI驱动的UI/UX设计智能技能库，提供10条推理规则、30种UI风格、10种配色方案、10组字体搭配，帮助开发者快速生成专业的UI/UX设计系统和代码。

**注**：完整版包含100条推理规则、57种UI风格、96种配色、56组字体搭配及8种技术栈模板。如需安装完整版，请参阅本文档第五章"新增资源安装方法"。

### 1.2 适用范围

本指南适用于以下技术栈：
- Vue / Nuxt.js
- React / Next.js
- Flutter

### 1.3 版本信息

| 项目 | 版本 | 说明 |
|-----|------|------|
| UI UX Pro Max | v1.1 | 当前版本 |
| uipro-cli | 最新版本 | CLI工具版本 |
| Python | 3.x | 搜索脚本依赖 |

---

## 二、功能介绍

### 2.1 核心功能

UI UX Pro Max Skill提供以下核心功能：

| 功能类别 | 当前数量 | 完整版数量 | 说明 |
|---------|---------|-----------|------|
| **行业推理规则** | 10条 | 100条 | 科技、金融、医疗、电商等行业设计规则 |
| **UI风格** | 30种 | 57种 | Glassmorphism、Neumorphism、Brutalism等 |
| **配色方案** | 10种 | 96种 | Modern SaaS、Dark Tech、Healthcare等 |
| **字体搭配** | 10组 | 56组 | Google Fonts最佳搭配 |
| **技术栈** | 3种 | 8种 | React、Vue、Flutter等 |

### 2.2 支持的技术栈

| 类别 | 技术栈 |
|-----|-------|
| **当前支持** | React、Next.js、Vue、Nuxt.js、Flutter |
| **完整版支持** | + Svelte、SwiftUI、React Native、HTML+Tailwind |

### 2.3 应用场景

| 场景 | 示例 |
|-----|------|
| 落地页设计 | SaaS产品页、创业公司官网 |
| 仪表板开发 | 数据分析后台、监控系统 |
| 移动应用 | 电商App、健康管理App |
| 组件设计 | 按钮、卡片、导航栏等 |

---

## 三、安装方法

### 3.1 前置条件

#### 3.1.1 必需软件

| 软件 | 版本要求 | 说明 |
|-----|---------|------|
| Node.js | 14.0+ | npm包管理器 |
| npm | 6.0+ | Node包管理器 |
| Python | 3.x | 搜索脚本依赖 |

#### 3.1.2 检查环境

安装前请确认环境已准备就绪：

```bash
# 检查Node.js版本
node --version

# 检查npm版本
npm --version

# 检查Python版本
python --version
```

### 3.2 安装步骤

#### 步骤1：全局安装CLI工具

```bash
# 全局安装uipro-cli
npm install -g uipro-cli

# 验证安装成功
uipro --version
```

**安装位置**：
- Windows: `%APPDATA%\npm\node_modules\uipro-cli`
- 命令行: 直接使用 `uipro` 命令

#### 步骤2：创建全局目录结构

```bash
# 确定全局目录位置（Windows）
OPENCODE_GLOBAL="$APPDATA/.opencode/skills/ui-ux-pro-max"

# 创建全局OpenCode技能目录
mkdir -p "$OPENCODE_GLOBAL"

# 创建子目录结构
cd "$OPENCODE_GLOBAL"
mkdir -p data scripts templates/react templates/vue templates/flutter
```

**目录结构**：
```
C:\Users\你的用户名\AppData\Roaming\.opencode\skills\ui-ux-pro-max\
├── data/                   # 资源文件目录
│   ├── styles.csv         # 30种UI风格数据（完整版57种）
│   ├── colors.csv         # 10种配色方案（完整版96种）
│   ├── typography.csv     # 10组字体搭配（完整版56组）
│   └── rules.csv          # 10条推理规则（完整版100条）
├── scripts/               # 脚本目录
│   ├── search.py          # 搜索脚本
│   └── design_system.py   # 设计系统生成器
├── templates/             # 代码模板目录
│   ├── react/             # React/Next.js模板
│   ├── vue/              # Vue/Nuxt.js模板
│   └── flutter/           # Flutter模板
└── skill.json             # 技能配置文件
```

**说明**：全局安装后，所有项目都可以使用此Skill，无需在每个项目中重复安装。

#### 步骤3：下载资源文件

从GitHub仓库下载核心资源文件：

```bash
# 确定全局目录
OPENCODE_GLOBAL="$APPDATA/.opencode/skills/ui-ux-pro-max"

# 方法1：使用git克隆（推荐）
cd "$OPENCODE_GLOBAL"
git clone https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git temp

# 复制资源文件
cp temp/src/ui-ux-pro-max/data/* data/
cp temp/src/ui-ux-pro-max/scripts/* scripts/
cp -r temp/src/ui-ux-pro-max/templates/* templates/

# 清理临时文件
rm -rf temp
```

**资源文件说明**：

| 文件 | 来源 | 说明 |
|-----|------|------|
| styles.csv | ui-ux-pro-max/data/ | 30种UI风格定义（完整版57种） |
| colors.csv | ui-ux-pro-max/data/ | 10种配色方案（完整版96种） |
| typography.csv | ui-ux-pro-max/data/ | 10组字体搭配（完整版56组） |
| rules.csv | ui-ux-pro-max/data/ | 10条推理规则（完整版100条） |
| search.py | ui-ux-pro-max/scripts/ | 搜索脚本 |
| design_system.py | ui-ux-pro-max/scripts/ | 设计系统生成器 |

#### 步骤4：配置技能文件

创建技能配置文件 `skill.json`：

```json
{
  "name": "ui-ux-pro-max",
  "version": "2.0",
  "description": "AI驱动的UI/UX设计智能技能",
  "author": "nextlevelbuilder",
  "license": "MIT",
  "triggers": [
    "build", "create", "design", "implement", "fix", "improve",
    "UI", "UX", "界面", "设计", "组件", "样式"
  ],
  "templates": {
    "web": ["react", "nextjs", "vue", "nuxt", "html-tailwind"],
    "mobile": ["flutter", "swiftui", "react-native"]
  },
  "default_stack": "react",
  "features": {
    "design_system": true,
    "code_generation": true,
    "style_recommendation": true,
    "color_palette": true,
    "typography_pairing": true
  },
  "installation": {
    "method": "cli",
    "global_cli": true
  }
}
```

#### 步骤5：创建使用说明文档

创建 `README.md` 文件：

```markdown
# UI UX Pro Max Skill

## 简介

AI驱动的UI/UX设计智能技能，提供10条推理规则、30种UI风格、10种配色、10组字体搭配和3种技术栈模板，帮助开发者快速生成专业的UI/UX设计系统和代码。

**注**：完整版包含100条推理规则、57种UI风格、96种配色、56组字体搭配及8种技术栈模板。

## 功能

- 自动生成设计系统
- 多技术栈代码生成（React、Vue、Flutter）
- 行业特定的设计规则
- 配色和字体搭配建议

## 使用方法

在OpenCode中直接用自然语言描述需求即可自动触发。

## 详细指南

请参阅主安装文档。
```

### 3.3 验证安装

#### 3.3.1 验证CLI工具

```bash
# 查看CLI版本
uipro --version

# 查看可用命令
uipro --help
```

#### 3.3.2 验证资源文件

```bash
# 检查data目录
ls -la "$APPDATA/.opencode/skills/ui-ux-pro-max/data/"

# 检查scripts目录
ls -la "$APPDATA/.opencode/skills/ui-ux-pro-max/scripts/"
```

#### 3.3.3 验证模板文件

```bash
# 检查React模板
ls -la "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/react/"

# 检查Vue模板
ls -la "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/vue/"

# 检查Flutter模板
ls -la "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/flutter/"
```

---

## 四、使用方法

### 4.1 自然语言触发

在OpenCode中直接用自然语言描述需求，技能会自动识别并触发：

#### 4.1.1 创建页面

```
用户输入: "创建一个红色的登录页面"
系统输出: 配色方案 + 登录组件代码

用户输入: "设计一个深色系的仪表板"
系统输出: 深色配色 + 仪表板布局 + 图表组件

用户输入: "Build a landing page for my SaaS product"
系统输出: Landing page design system + React/Vue/Flutter code
```

#### 4.1.2 创建组件

```
用户输入: "帮我设计一个按钮组件"
系统输出: 按钮设计系统 + 多风格代码

用户输入: "创建一个卡片布局"
系统输出: 卡片设计 + 响应式代码

用户输入: "设计导航栏"
系统输出: 导航栏设计 + 多框架代码
```

### 4.2 指定技术栈

在描述中明确指定技术栈：

```
"用Vue创建一个导航栏组件"
"用Next.js实现深色主题"
"用Flutter做个卡片布局"
"用React设计一个登录表单"
"用Nuxt.js创建产品展示页面"
```

### 4.3 支持的UI风格（30种）

本技能目前支持以下30种UI风格：

| 编号 | 风格名称 | 适用场景 | 关键词 |
|:---:|---------|---------|--------|
| 1 | Minimalism & Swiss Style | 企业应用、仪表板、文档 | clean,typography,whitespace |
| 2 | Neumorphism | 健康类APP、冥想平台 | soft,shadows,subtle |
| 3 | Glassmorphism | 现代SaaS、金融仪表板 | transparent,blur,glass |
| 4 | Brutalism | 作品集、艺术项目 | bold,raw,minimal |
| 5 | 3D & Hyperrealism | 游戏、产品展示 | 3d,realistic |
| 6 | Vibrant & Block-based | 创业公司、创意机构 | colorful,blocks |
| 7 | Dark Mode (OLED) | 夜间模式APP、编程平台 | dark,oled,night |
| 8 | Accessible & Ethical | 政府、医疗、教育 | a11y,inclusive |
| 9 | Claymorphism | 教育APP、儿童APP、SaaS | 3d,soft,rounded |
| 10 | Aurora UI | 现代SaaS、创意机构 | gradient,animated |
| 11 | Retro-Futurism | 游戏、娱乐、音乐平台 | vintage,future |
| 12 | Flat Design | WebAPP、移动APP、创业MVP | flat,simple,clean |
| 13 | Skeuomorphism | 遗留系统、游戏、 premium产品 | realistic,textures |
| 14 | Liquid Glass | 高级SaaS、高端电商 | fluid,glass |
| 15 | Motion-Driven | 作品集、叙事平台 | animation,motion |
| 16 | Micro-interactions | 移动APP、触摸屏UI | gestures,touch |
| 17 | Inclusive Design | 公共服务、教育、医疗 | accessible |
| 18 | Zero Interface | 语音助手、AI平台 | minimal,invisible |
| 19 | Soft UI Evolution | 现代企业APP、SaaS | soft,gentle |
| 20 | Neubrutalism | Gen Z品牌、创业公司、Figma风格 | bold,borders |
| 21 | Bento Box Grid | 仪表板、产品页、作品集 | grids,cards |
| 22 | Y2K Aesthetic | 时尚品牌、音乐、Gen Z | retro,gradient |
| 23 | Cyberpunk UI | 游戏、科技产品、加密货币 | neon,cyber |
| 24 | Organic Biophilic | 健康APP、可持续品牌 | nature,organic |
| 25 | AI-Native UI | AI产品、聊天机器人、copilot | smart,clean |
| 26 | Memphis Design | 创意机构、音乐、年轻品牌 | patterns,colorful |
| 27 | Vaporwave | 音乐平台、游戏、作品集 | retro,gradient |
| 28 | Dimensional Layering | 仪表板、卡片布局、弹窗 | layers,depth |
| 29 | Exaggerated Minimalism | 时尚、建筑、作品集 | minimal,bold |
| 30 | Kinetic Typography | 首屏、营销网站 | typography,motion |

#### 4.3.1 使用示例

```bash
# 指定具体风格
"用Glassmorphism风格设计卡片"
"用Neumorphism做个按钮"
"Brutalist风格的落地页"
"Dark Mode的仪表板"
"Soft UI的移动APP"

# 混合风格需求
"Minimalism + Dark Mode的仪表板"
"Glassmorphism + Neumorphism的按钮组件"
```

### 4.4 支持的配色方案（10种）

本技能目前支持以下10种行业配色方案：

| 编号 | 配色名称 | 主色 | 副色 | 背景色 | 文字色 | 强调色 | 适用行业 |
|:---:|---------|------|------|--------|-------|-------|---------|
| 1 | Modern SaaS | #6366F1 | #8B5CF6 | #F8FAFC | #1E293B | #F59E0B | 科技 |
| 2 | Dark Tech | #0F172A | #1E293B | #020617 | #F8FAFC | #22D3EE | 科技 |
| 3 | Healthcare | #10B981 | #059669 | #ECFDF5 | #064E3B | #F59E0B | 医疗 |
| 4 | Finance | #0F766E | #115E59 | #F0FDF4 | #134E4A | #F59E0B | 金融 |
| 5 | E-commerce | #EC4899 | #DB2777 | #FDF2F8 | #831843 | #F59E0B | 电商 |
| 6 | Beauty Spa | #F472B6 | #EC4899 | #FDF2F8 | #831843 | #D4AF37 | 美容 |
| 7 | Corporate | #2563EB | #1D4ED8 | #EFF6FF | #1E3A8A | #F59E0B | 企业 |
| 8 | Gaming | #7C3AED | #5B21B6 | #EDE9FE | #4C1D95 | #22D3EE | 游戏 |
| 9 | Nature | #65A30D | #4D7C0F | #F7FEE7 | #365314 | #D4AF37 | 自然 |
| 10 | Dark Finance | #1F2937 | #374151 | #111827 | #F9FAFB | #10B981 | 金融 |

#### 4.4.1 使用示例

```bash
# 指定配色方案
"用Healthcare配色做健康APP"
"Beauty Spa配色风格的美容网站"
"Dark Finance的深色金融仪表板"

# 与风格组合
"Glassmorphism + Healthcare配色的卡片"
"Neumorphism + Nature配色的按钮"
```

### 4.5 支持的字体搭配（10种）

本技能目前支持以下10种字体搭配：

#### 4.5.1 字体加载说明

**字体使用方案**：

| 应用类型 | 字体加载方式 | 断网影响 |
|---------|-------------|---------|
| **网页应用** | Google Fonts CDN | 需要网络 |
| **独立桌面APP** | 系统字体回退 | **无影响，完全离线可用** |

**网页应用**：
生成的网页代码会自动包含Google Fonts引用：
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```

**独立桌面APP（如MermaidReader）**：
采用系统字体回退方案，代码示例：
```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 
             'Microsoft YaHei', 'PingFang SC', sans-serif;
```

**特点**：
- ✅ 在线时：使用Google Fonts（如Inter）
- ✅ 断网时：自动切换到系统字体（微软雅黑，思源黑体等）
- ✅ 无需额外配置
- ✅ **完全离线可用**
- ✅ 无需打包字体文件

| 编号 | 搭配名称 | 标题字体 | 正文字体 | Google Fonts | 风格特点 |
|:---:|---------|---------|---------|--------------|---------|
| 1 | Modern Sans | Inter | Open Sans | Inter\|Open Sans | clean,professional |
| 2 | Elegant Serif | Playfair Display | Source Sans Pro | Playfair Display\|Source Sans Pro | elegant,sophisticated |
| 3 | Tech Modern | Roboto Mono | Roboto | Roboto Mono\|Roboto | tech,modern |
| 4 | Creative | Montserrat | Lato | Montserrat\|Lato | creative,friendly |
| 5 | Premium | Playfair Display | Lato | Playfair Display\|Lato | luxury,premium |
| 6 | Minimal | Space Grotesk | Inter | Space Grotesk\|Inter | minimal,contemporary |
| 7 | Editorial | Merriweather | Open Sans | Merriweather\|Open Sans | editorial,readable |
| 8 | Startup | DM Sans | Inter | DM Sans\|Inter | startup,friendly |
| 9 | Corporate | IBM Plex Sans | IBM Plex Sans | IBM Plex Sans | corporate,professional |
| 10 | Friendly | Nunito | Nunito | Nunito | friendly,rounded |

#### 4.5.2 使用示例

```bash
# 指定字体搭配
"用Elegant Serif字体做高档品牌网站"
"Tech Modern字体的技术文档"
"Startup字体的创业公司落地页"

# 与风格组合
"Glassmorphism + Modern Sans字体的现代APP"
"Neumorphism + Friendly字体的儿童教育APP"
```

### 4.6 支持的技术栈（3种）

本技能目前支持以下3种技术栈的代码生成：

| 技术栈 | 说明 | 模板类型 | 适用场景 |
|-------|------|---------|---------|
| **React / Next.js** | 前端主流框架 | 组件、页面、Hooks | Web应用、SaaS产品 |
| **Vue / Nuxt.js** | 渐进式框架 | 组件、页面、Composables | 企业应用、内容网站 |
| **Flutter** | 跨平台移动开发 | Widget、页面、主题 | 移动APP、跨平台应用 |

#### 4.6.1 使用示例

```bash
# 指定技术栈
"用React创建登录组件"
"用Next.js实现深色主题"
"用Vue设计导航栏"
"用Nuxt.js创建产品展示页"
"用Flutter做个按钮组件"
```

#### 4.6.2 模板列表

当前已安装的模板：

| 技术栈 | 模板类型 | 文件 |
|-------|---------|------|
| React | button.tsx | 按钮组件 |
| Vue | card.vue | 卡片组件 |
| Flutter | button.dart | 按钮组件 |

### 4.7 使用命令行工具

#### 4.7.1 生成设计系统

```bash
# 生成设计系统（ASCII输出）
uipro design-system "beauty spa wellness" -p "Serenity Spa"

# 生成设计系统（Markdown输出）
uipro design-system "fintech banking" -f markdown

# 生成设计系统（保存到文件）
uipro design-system "SaaS dashboard" --persist -p "MyApp"
```

#### 4.7.2 搜索资源

```bash
# 搜索UI风格
uipro search --style glassmorphism

# 搜索配色方案
uipro search --colors dark

# 搜索字体搭配
uipro search --typography elegant

# 搜索行业规则
uipro search --rules healthcare
```

#### 4.7.3 技术栈相关

```bash
# 查看React模板
uipro templates react

# 查看Vue模板
uipro templates vue

# 查看Flutter模板
uipro templates flutter

# 导出特定模板
uipro export react button -o ./components/
```

---

## 五、新增资源安装方法

本章节说明如何安装文档中提到的完整资源（57种UI风格、96种配色、24种图标、56种字体搭配）。

### 5.1 前置条件

确保已安装Git和Python 3.x：

```bash
# 检查Git
git --version

# 检查Python
python --version

# 如果未安装，使用以下命令安装：
# Windows: winget install Git.Git -s winget
# Windows: winget install Python.Python.3.12 -s winget
```

### 5.2 安装完整资源包

#### 5.2.1 克隆完整GitHub仓库

```bash
# 确定全局目录
OPENCODE_GLOBAL="$APPDATA/.opencode/skills/ui-ux-pro-max"

# 进入目录
cd "$OPENCODE_GLOBAL"

# 克隆完整仓库（如果网络正常）
git clone https://github.com/nextlevelbuilder/ui-ux-pro-max-skill.git temp

# 复制所有资源文件
cp temp/src/ui-ux-pro-max/data/* data/
cp temp/src/ui-ux-pro-max/scripts/* scripts/
cp -r temp/src/ui-ux-pro-max/templates/* templates/

# 清理临时文件
rm -rf temp
```

#### 5.2.2 使用国内镜像（推荐）

如果GitHub访问缓慢，可使用Gitee镜像：

```bash
# 克隆Gitee镜像（如果存在）
cd "$OPENCODE_GLOBAL"
git clone https://gitee.com/nextlevelbuilder/ui-ux-pro-max-skill.git temp

# 复制资源文件（同上）
cp temp/src/ui-ux-pro-max/data/* data/
cp temp/src/ui-ux-pro-max/scripts/* scripts/
cp -r temp/src/ui-ux-pro-max/templates/* templates/

rm -rf temp
```

### 5.3 新增其他技术栈模板

#### 5.3.1 支持的完整技术栈列表

| 技术栈 | 模板目录 | 说明 |
|-------|---------|------|
| **React** | templates/react/ | 前端组件库 |
| **Next.js** | templates/nextjs/ | 全栈React框架 |
| **Vue** | templates/vue/ | 渐进式框架 |
| **Nuxt.js** | templates/nuxt/ | Vue全栈框架 |
| **Svelte** | templates/svelte/ | 编译型框架 |
| **SwiftUI** | templates/swiftui/ | iOS原生框架 |
| **React Native** | templates/react-native/ | 跨平台移动 |
| **Flutter** | templates/flutter/ | 跨平台开发 |

#### 5.3.2 手动添加技术栈模板

如果需要添加未安装的技术栈模板，可以手动创建：

```bash
# 创建模板目录
mkdir -p "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/nextjs"
mkdir -p "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/svelte"
mkdir -p "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/swiftui"
mkdir -p "$APPDATA/.opencode/skills/ui-ux-pro-max/templates/react-native"

# 创建模板文件示例（Next.js页面）
cat > "$OPENCODE_GLOBAL/templates/nextjs/page.tsx" << 'EOF'
// Next.js Page Component
// Generated by UI UX Pro Max

import React from 'react';

interface PageProps {
  title?: string;
  children?: React.ReactNode;
}

export const Page = ({ title = 'Page', children }: PageProps) => {
  return (
    <div className="page">
      {title && <h1>{title}</h1>}
      {children}
    </div>
  );
};

export default Page;
EOF
```

#### 5.3.3 使用社区模板

从社区获取更多模板：

```bash
# 克隆社区模板仓库
cd "$OPENCODE_GLOBAL/templates"
git clone https://github.com/nextlevelbuilder/ui-ux-templates.git community

# 复制需要的模板
cp community/nextjs/* nextjs/
cp community/svelte/* svelte/
```

### 5.4 新增图标资源

#### 5.4.1 图标目录结构

```
templates/
├── icons/                    # 图标资源目录
│   ├── heroicons/          # Heroicons图标
│   ├── lucide/             # Lucide图标
│   ├── fontawesome/         # Font Awesome图标
│   └── material/           # Material Icons
```

#### 5.4.2 安装图标依赖

```bash
# 安装图标库（如果需要）
npm install lucide-react      # React图标
npm install @heroicons/react # Heroicons
```

### 5.5 验证新增资源

#### 5.5.1 验证安装结果

```bash
# 查看已安装的风格数量
ls "$OPENCODE_GLOBAL/data/styles.csv"
wc -l "$OPENCODE_GLOBAL/data/styles.csv"
# 当前显示31行（1行标题 + 30行数据）

# 查看已安装的配色数量
ls "$OPENCODE_GLOBAL/data/colors.csv"
wc -l "$OPENCODE_GLOBAL/data/colors.csv"
# 当前显示11行（1行标题 + 10行数据）

# 查看已安装的字体数量
ls "$OPENCODE_GLOBAL/data/typography.csv"
wc -l "$OPENCODE_GLOBAL/data/typography.csv"
# 当前显示11行（1行标题 + 10行数据）

# 查看已安装的模板目录
ls -la "$OPENCODE_GLOBAL/templates/"
```

#### 5.5.2 测试搜索功能

```bash
# 搜索完整风格列表
cd "$OPENCODE_GLOBAL/scripts"
python search.py "" --style | head -20

# 搜索完整配色列表
python search.py "" --colors | head -20

# 搜索完整字体列表
python search.py "" --typography | head -20
```

### 5.6 完整资源包包含内容

安装完整资源包后，将获得：

| 资源类型 | 完整数量 | 说明 |
|---------|---------|------|
| UI风格 | 57种 | 包含通用、落地页、仪表板三大类 |
| 配色方案 | 96种 | 覆盖科技、金融、医疗等10+行业 |
| 字体搭配 | 56组 | Google Fonts最佳搭配 |
| 图标资源 | 24组 | Heroicons、Lucide、FontAwesome等 |
| 推理规则 | 100条 | 行业特定设计规则 |
| 搜索脚本 | 2个 | 风格搜索、设计系统生成 |
| 技术栈模板 | 8种 | React、Vue、Flutter、Svelte等 |

---

## 六、卸载删除方法

### 6.1 两种安装方式的卸载差异

| 安装方式 | Skill目录位置 | CLI工具 | 复杂度 |
|---------|--------------|---------|--------|
| **全局安装**（本指南） | `%APPDATA%\.opencode\skills\` | 需单独卸载 | 简单 |
| **项目级安装** | `项目\.opencode\skills\` | 视情况而定 | 极简 |

#### 6.1.1 全局安装的卸载（本指南采用）

```bash
# 步骤1：删除全局Skill目录
rm -rf "$APPDATA/.opencode/skills/ui-ux-pro-max"

# 步骤2：卸载全局CLI工具
npm uninstall -g uipro-cli

# 步骤3：清理缓存（可选）
rm -rf ~/.uipro
npm cache clean --force
```

#### 6.1.2 项目级安装的卸载（备选方案）

```bash
# 只需删除项目内的Skill目录
rm -rf D:\你的项目\.opencode\skills\ui-ux-pro-max

# CLI工具如果也是项目级安装，通常不需要单独卸载
```

### 6.2 全局安装的完整卸载步骤

#### 6.2.1 删除全局Skill目录

```bash
# 方法1：使用rm命令（Git Bash或WSL）
rm -rf "$APPDATA/.opencode/skills/ui-ux-pro-max"

# 方法2：使用PowerShell
Remove-Item -Recurse -Force "$APPDATA/.opencode/skills/ui-ux-pro-max"

# 方法3：使用CMD
rd /s /q "%APPDATA%\.opencode\skills\ui-ux-pro-max"
```

#### 6.2.2 卸载CLI工具

```bash
# 全局卸载uipro-cli
npm uninstall -g uipro-cli

# 验证卸载成功
uipro --version
# 应该显示"command not found"或类似错误
```

#### 6.2.3 清理缓存（可选）

```bash
# 清理npm缓存
npm cache clean --force

# 清理Python缓存（如果有）
# 删除用户目录下的.uipro目录（如果存在）
rm -rf ~/.uipro
```

### 6.3 完整卸载清单（全局安装）

| 删除项 | 命令 | 优先级 | 说明 |
|-------|------|-------|------|
| **全局Skill目录** | `rm -rf "$APPDATA/.opencode/skills/ui-ux-pro-max"` | **必须** | 核心资源文件 |
| **全局CLI工具** | `npm uninstall -g uipro-cli` | **必须** | CLI命令工具 |
| **用户缓存** | `rm -rf ~/.uipro` | 可选 | 临时文件 |
| **npm缓存** | `npm cache clean --force` | 可选 | 清理空间 |

### 6.4 卸载后验证

```bash
# 1. 确认Skill目录已删除
if [ -d "$APPDATA/.opencode/skills/ui-ux-pro-max" ]; then
  echo "全局Skill目录仍存在，需手动删除"
else
  echo "全局Skill目录已成功删除"
fi

# 2. 确认CLI工具已卸载
if command -v uipro &> /dev/null; then
  echo "CLI工具仍存在，需运行 npm uninstall -g uipro-cli"
else
  echo "CLI工具已成功卸载"
fi

# 3. 确认命令不再可用
uipro --version
# 应该显示错误信息
```

---

## 七、常见问题

### 7.1 安装问题

#### Q1: npm安装失败，提示权限不足

**问题**：安装时提示"Permission denied"或"access denied"

**解决方法**：
```bash
# 方法1：使用管理员权限运行终端
# 右键点击终端图标，选择"以管理员身份运行"

# 方法2：修改npm全局目录权限
npm config set prefix "C:\Users\你的用户名\AppData\Roaming\npm"
```

#### Q2: git克隆失败，网络超时

**问题**：克隆仓库时连接超时或速度慢

**解决方法**：
```bash
# 方法1：使用国内镜像
git clone https://gitee.com/nextlevelbuilder/ui-ux-pro-max-skill.git temp

# 方法2：手动下载ZIP文件
# 访问 https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
# 点击"Code"按钮，选择"Download ZIP"
```

#### Q3: Python脚本无法运行

**问题**：运行search.py或design_system.py时出错

**解决方法**：
```bash
# 检查Python版本
python --version

# 确保Python在系统PATH中
where python

# 如果没有Python，下载安装
# Windows: winget install Python.Python.3.12
```

### 7.2 使用问题

#### Q4: 技能无法自动触发

**问题**：在OpenCode中输入需求，但没有响应

**解决方法**：
1. 确认Skill目录存在且路径正确
2. 检查skill.json配置文件格式正确
3. 重启OpenCode
4. 尝试使用命令行工具验证安装

#### Q5: 生成的代码不符合预期

**问题**：输出代码风格或技术与需求不符

**解决方法**：
1. 在需求中明确指定技术栈，如"用React创建"
2. 在需求中明确指定风格，如"Glassmorphism风格"
3. 检查是否使用了正确的触发词

#### Q6: 找不到特定风格或组件

**问题**：想要某种风格，但搜索不到

**解决方法**：
```bash
# 使用命令行搜索
uipro search --style "你的关键词"

# 或查看完整风格列表
uipro search --list-styles
```

### 7.3 卸载问题

#### Q7: Skill目录删除不掉

**问题**：使用rm或Remove-Item命令失败

**解决方法**：
1. 关闭所有使用该目录的程序
2. 重启电脑后再次删除
3. 使用文件粉碎工具强制删除

#### Q8: CLI卸载后命令仍可用

**问题**：运行npm uninstall后，uipro命令仍能使用

**解决方法**：
```bash
# 检查npm全局安装位置
npm root -g

# 手动删除uipro-cli目录
rm -rf "C:\Users\你的用户名\AppData\Roaming\npm\node_modules\uipro-cli"

# 从PATH中移除（如果需要）
# 检查环境变量PATH，移除npm全局目录
```

---

## 八、参考资源

### 8.1 官方资源

| 资源 | 链接 |
|-----|------|
| GitHub仓库 | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill |
| npm包 | https://www.npmjs.com/package/uipro-cli |

### 8.2 相关文档

| 文档 | 位置 |
|-----|------|
| OpenCode配置 | C:\Users\40968\.config\opencode\AGENTS.md |
| 项目文档 | D:\2bktest\MDview\docs\ |
| 代码风险分析 | D:\2bktest\MDview\docs\代码风险分析方法.md |
| UI UX Pro Max演示 | D:\2bktest\MDview\AI工具研究\ui-ux-demo\ |

---

## 九、版本历史

| 版本 | 日期 | 更新内容 |
|-----|------|---------|
| v1.0 | 2026-02-05 00:48:21 | 初始版本，包含完整安装、使用和卸载指南 |
| v1.1 | 2026-02-05 02:20:00 | 更新：列出实际安装的30种UI风格、10种配色、10组字体；添加第五章"新增资源安装方法"，说明如何安装完整版资源包；更新字体加载说明，独立APP完全离线可用 |

---

**文档类型**: 安装指南
**更新时间**: 2026-02-05 02:20:00
**维护人**: 技术团队
**适用范围**: Vue/Nuxt.js + React/Next.js + Flutter 多技术栈项目
