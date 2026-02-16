# 贡献指南

**创建时间**: 2026-02-16 17:26:13

---

## 欢迎贡献

感谢您对 OmniAgentAst 项目的兴趣！我们欢迎任何形式的贡献，包括但不限于：

- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 完善文档
- 💻 提交代码改进
- 🌍 翻译文档

---

## 开发环境要求

### 后端
- Python 3.13+
- FastAPI
- 智谱 AI API Key

### 前端
- Node.js 18+
- React
- Vite

### 工具
- Git
- GitHub 账户

---

## 开发流程

### 1. Fork 项目

点击 GitHub 页面右上角的 "Fork" 按钮。

### 2. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/OmniAgentAst.git
cd OmniAgentAst
```

### 3. 创建功能分支

```bash
# 从 master 创建新分支
git checkout -b feature/your-feature-name
# 或
git checkout -b bugfix/issue-description
```

### 4. 开发与测试

```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖
cd ../frontend
npm install

# 运行开发服务器
# 后端
cd backend
uvicorn app.main:app --reload

# 前端
cd frontend
npm run dev
```

### 5. 提交代码

```bash
# 添加修改的文件
git add .

# 提交（遵循提交规范）
git commit -m "feat: 添加新功能描述"

# 推送到你的 Fork
git push origin feature/your-feature-name
```

### 6. 创建 Pull Request

在 GitHub 上点击 "New Pull Request"，描述您的修改内容。

---

## 提交信息规范

请使用以下前缀：

| 前缀 | 说明 | 示例 |
|------|------|------|
| `feat:` | 新功能 | `feat: 添加用户登录功能` |
| `fix:` | Bug 修复 | `fix: 修复登录页面样式问题` |
| `docs:` | 文档更新 | `docs: 更新 README 安装说明` |
| `refactor:` | 代码重构 | `refactor: 优化用户认证逻辑` |
| `test:` | 测试相关 | `test: 添加登录单元测试` |
| `chore:` | 维护任务 | `chore: 更新依赖版本` |

---

## 代码规范

### Python
- 遵循 PEP 8
- 使用类型注解
- 编写单元测试

### 前端
- 遵循 ESLint 规则
- 使用 TypeScript
- 组件保持单一职责

---

## 问题反馈

如果您发现 Bug 或有新功能建议，请通过 [GitHub Issues](https://github.com/joshuachendyb/OmniAgentAst/issues) 反馈。

---

## 许可证

通过贡献代码，您同意您的贡献将遵循 [MIT 许可证](LICENSE)。

---

**更新时间**: 2026-02-16 17:26:13
