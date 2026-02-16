# AgentationDemo - Agentation 集成演示

## 简介

本项目是 [Agentation](https://agentation.dev/) 可视化反馈工具的演示项目，集成 React + Vite。

用于测试和展示 Agentation 的 UI 标注功能，可与 OpenCode/Claude Code 等 AI Agent 配合使用。

## Agentation 功能

- **点击标注** - 点击 UI 元素生成精确选择器
- **文本选择** - 标注特定文本内容
- **区域选择** - 标注任意区域
- **结构化输出** - Markdown 格式，包含选择器+位置+上下文

## 使用方法

### 1. 安装依赖

```bash
cd AgentationDemo
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
AgentationDemo/
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

## 技术栈

- React 18 + Vite 5
- Agentation 1.0（可视化反馈工具）
- 开发端口：3000

## 常见问题

1. **favicon.ico 404** - 这是正常现象，项目未提供网站图标
2. **React DevTools 提示** - 建议安装浏览器扩展获得更好调试体验
