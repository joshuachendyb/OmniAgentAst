# React 项目模板 - Agentation 集成

## 简介

本模板集成了 [Agentation](https://agentation.dev/) 可视化反馈工具。

## Agentation 功能

- **点击标注** - 点击 UI 元素生成精确选择器
- **文本选择** - 标注特定文本内容
- **区域选择** - 标注任意区域
- **结构化输出** - Markdown 格式，包含选择器+位置+上下文

## 使用方法

### 1. 安装依赖

```bash
cd react-template
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

### 3. 使用 Agentation

1. 打开浏览器访问 `http://localhost:3000`
2. 点击右下角 Agentation 工具栏图标
3. 点击任意 UI 元素进行标注
4. 复制标注内容，发送给 AI Agent

### 4. AI Agent 集成示例

```javascript
// Agentation 标注输出示例
{
  "element": "Button",
  "elementPath": "body > div.app > main > button.btn-primary",
  "boundingBox": { "x": 100, "y": 200, "width": 120, "height": 40 },
  "annotation": "主要操作按钮，需要修改颜色"
}
```

## 目录结构

```
react-template/
├── index.html          # HTML 入口
├── package.json        # 项目配置
├── vite.config.js      # Vite 配置
└── src/
    ├── main.jsx        # React 入口
    └── App.jsx         # 主应用组件（集成 Agentation）
```

## 与 OpenCode/Claude Code 结合

```
用户反馈 → Agentation 标注 → 复制标注 → OpenCode → AI 修改代码
```

## 后续项目使用

1. 复制 `react-template` 目录
2. 重命名为项目名称
3. 修改 `package.json` 中的项目名
4. 安装依赖并启动开发
