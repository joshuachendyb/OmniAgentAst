# AI Agent OS

AI Agent操作系统 - 企业级、安全、可扩展的智能体平台

## 项目结构

```
ai-agent-os/
├── ai_os_shell_v2.py       # 当前原型版本
├── doc/                     # 文档目录
│   ├── AI_OS_Agent_技术深度分析报告.md
│   ├── AI_OS_Agent_代码解析说明文档.md
│   └── AI_Agent_OS_2.0_系统设计方案.md
└── README.md
```

## 文档说明

1. **AI_OS_Agent_技术深度分析报告.md** - 原版代码的全面技术分析
2. **AI_OS_Agent_代码解析说明文档.md** - 逐行代码详解
3. **AI_Agent_OS_2.0_系统设计方案.md** - 新版系统完整设计方案

## 快速开始

### 安装依赖
```bash
pip install flask requests pyautogui pyperclip pygetwindow
```

### 运行程序
```bash
python AI_OSShell_v2.py
```

然后访问 http://127.0.0.1:5000

## 安全警告

⚠️ 当前版本存在安全风险，仅用于本地测试：
- 硬编码API密钥
- 任意命令执行
- 弱密码保护

生产环境请使用 2.0 设计方案重构

## 许可证

MIT License