# 模型配置API使用文档

**文档版本**：v1.0
**创建时间**：2026-03-02 15:00:00
**编写者**：小沈
**适用范围**：OmniAgentAs-desk前端模型配置功能

---

## 📋 目录

1. [数据存储说明](#数据存储说明)
2. [接口概览](#接口概览)
3. [核心流程说明](#核心流程说明)
4. [接口详情](#接口详情)
5. [错误避免说明](#错误避免说明)
6. [API汇总表](#api汇总表)
7. [核心要点汇总](#核心要点汇总)

---

## 数据存储说明

### 配置文件位置

| 项目 | 路径 |
|------|------|
| 配置文件 | `D:\2bktest\MDview\OmniAgentAs-desk\config\config.yaml` |
| 版本文件 | `D:\2bktest\MDview\OmniAgentAs-desk\version.txt` |

### 配置文件结构 (config.yaml)

```yaml
ai:
  provider: opencode        # 当前选中的provider（必须在前）
  model: kimi-k2.5-free   # 当前选中的model（必须在后）
  opencode:
    api_base: https://opencode.ai/zen/v1
    api_key: sk-xxx
    max_retries: 3
    models:
    - minimax-m2.5-free
    - glm-5-free
    - kimi-k2.5-free
    timeout: 150
  zhipuai:
    api_base: https://open.bigmodel.cn/api/paas/v4/
    api_key: xxx
    models:
    - glm-4.7-flash
    timeout: 90
  longcat:
    api_base: https://api.longcat.chat/openai/v1
    api_key: xxx
    models:
    - LongCat-Flash-Thinking-2601
    timeout: 120

app:
  theme: light
  language: zh-CN

security:
  contentFilterEnabled: false
  contentFilterLevel: medium

logging:
  level: INFO
```

### 重要规则

1. **ai.provider 和 ai.model 必须放在最前面**（第1、2行）
2. **provider配置顺序**：先provider/model，再各个provider详情
3. **每个provider必须配置**：api_key、api_base、models、timeout

---

## 接口概览

### 模型配置相关API

| 类别 | API | 方法 | 说明 |
|------|-----|------|------|
| 健康检查 | `/api/v1/health` | GET | 获取后端健康状态和版本号 |
| 配置读取 | `/api/v1/config` | GET | 获取当前配置 |
| 配置更新 | `/api/v1/config` | PUT | 更新配置 |
| 模型验证 | `/api/v1/config/validate` | POST | 验证API Key是否有效 |
| 模型列表 | `/api/v1/config/models` | GET | 获取可用模型列表 |
| 完整验证 | `/api/v1/config/validate-full` | GET | 完整配置验证 |
| 完整配置 | `/api/v1/config/full` | GET | 获取完整配置 |
| AI服务验证 | `/api/v1/chat/validate` | GET | 验证AI服务可用性 |

---

## 核心流程说明

### 流程一：启动阶段 - 模型配置验证流程

**触发时机**：前端页面加载时

**前端代码位置**：`frontend/src/pages/Settings/index.tsx` useEffect

```
前端页面加载
   ↓
【第1步】useEffect 初始化
   ↓
【第2步】调用 validateFullConfig 验证配置（只读）
   ↓
【第3步】根据验证结果决定是否继续
   ├─ 失败 → 设置空列表，返回
   └─ 成功 → 继续
   ↓
【第4步】调用 getModelList 获取模型列表（只读）
   ↓
【第5步】后端读取配置文件确定 current_model
   ↓
【第6步】前端设置模型列表和当前选中的模型
   ↓
【第7步】调用 validateService 验证服务可用性（只读）
   ↓
【第8步】后端验证服务
   ├─ 检查是否有遗留备份（由之前的模型切换产生）
   ├─ 有备份且验证成功 → 删除备份
   ├─ 有备份且验证失败 → 恢复备份
   └─ 无备份 → 跳过备份处理
   ↓
【第9步】前端显示验证结果
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/config/validate-full` | GET | 完整配置验证 |
| `/api/v1/config/models` | GET | 获取模型列表 |
| `/api/v1/chat/validate` | GET | 验证AI服务可用性 |

---

### 流程二：用户切换模型流程

**触发时机**：用户在下拉框选择新模型

**前端代码位置**：`frontend/src/pages/Settings/index.tsx` onProviderChange / onModelChange

```
用户点击下拉框选择模型
   ↓
【第1步】前端 Select onChange 触发
   value = "${provider}-${model}" (如："opencode-kimi-k2.5-free")
   ↓
【第2步】从 modelList 查找 selectedModel
   const selectedModel = modelList.find(m => `${m.provider}-${m.model}` === value)
   ↓
【第3步】调用 API 切换模型
   configApi.updateConfig({
     ai_provider: selectedModel.provider,
     ai_model: selectedModel.model
   })
   ↓
【第4步】后端处理配置更新
   4.1 备份配置文件 → backup_path
   4.2 更新 ai.provider
   4.3 更新 ai.model
   4.4 清空缓存（AIServiceFactory._instance + _config）
   4.5 设置全局备份路径（AIServiceFactory.set_backup_paths）
   4.6 写入配置文件（保持provider/model在最前面）
   4.7 返回成功（包含 backup_path）
   ↓
【第5步】前端更新选中状态
   setCurrentProvider(value)
   ↓
【第6步】前端自动调用 handleCheckService
   ↓
【第7步】handleCheckService 刷新配置验证
   configApi.validateFullConfig()
   ↓
【第8步】handleCheckService 刷新模型列表
   configApi.getModelList()
   ↓
【第9步】后端 getModelList 确定 current_model
   9.1 读取配置文件 ai.provider 和 ai.model
   9.2 验证配置是否有效
   9.3 设置 final_provider 和 final_model
   9.4 构建模型列表，标记 current_model
   9.5 返回模型列表
   ↓
【第10步】前端更新当前选中的模型
   const currentModel = modelData.models.find(m => m.current_model === true)
   setCurrentProvider(`${currentModel.provider}-${currentModel.model}`)
   ↓
【第11步】handleCheckService 验证服务可用性
   chatApi.validateService()
   ↓
【第12步】后端 validate_ai_service 验证
   12.1 获取 AI 服务（加载配置）
   12.2 获取 provider 和 model
   12.3 获取 backup_path（从全局状态）
   12.4 检查 API Key
   12.5 调用 ai_service.validate()
   12.6 验证成功 → 删除备份
   12.7 验证失败 → 恢复备份
   12.8 清除全局状态
   12.9 返回验证结果
   ↓
【第13步】前端显示验证结果
   setServiceStatus(status)
   显示绿色（成功）或红色（失败）
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/config` | PUT | 更新配置（provider、model） |
| `/api/v1/config/validate-full` | GET | 刷新配置验证 |
| `/api/v1/config/models` | GET | 刷新模型列表 |
| `/api/v1/chat/validate` | GET | 验证AI服务 |

**备份机制说明**：
- 更新配置时创建备份文件
- 验证成功则删除备份
- 验证失败则恢复备份
- 启动时检查清理遗留备份（防御性）

---

### 流程三：验证API Key流程

**触发时机**：用户在设置页面点击"验证"按钮

**前端代码位置**：`frontend/src/pages/Settings/index.tsx` handleValidate

```
用户点击验证按钮
   ↓
【第1步】前端调用验证API
   configApi.validateConfig({
     provider: "opencode"
   })
   ↓
【第2步】后端处理
   2.1 读取配置文件
   2.2 创建临时AI服务
   2.3 调用validate()测试API Key
   2.4 返回验证结果
   ↓
【第3步】前端显示验证结果
   ↓
完成
```

**涉及的后端API**：
| API | 方法 | 说明 |
|-----|------|------|
| `/api/v1/config/validate` | POST | 验证指定provider的API Key |

---

## 接口详情

### 1. 健康检查
- **URL**: `GET /api/v1/health`
- **描述**: 获取后端健康状态和版本号
- **响应**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-03-02T10:00:00Z",
    "version": "0.4.14"
  }
  ```

---

### 2. 获取当前配置
- **URL**: `GET /api/v1/config`
- **描述**: 获取当前系统配置（脱敏，不返回真实API Key）
- **响应**:
  ```json
  {
    "ai_provider": "opencode",
    "ai_model": "kimi-k2.5-free",
    "api_key_configured": true,
    "theme": "light",
    "language": "zh-CN",
    "security": {
      "contentFilterEnabled": false,
      "contentFilterLevel": "medium",
      "whitelistEnabled": false,
      "commandWhitelist": "",
      "commandBlacklist": "",
      "confirmDangerousOps": true,
      "maxFileSize": 100
    }
  }
  ```

---

### 3. 更新配置
- **URL**: `PUT /api/v1/config`
- **描述**: 更新系统配置
- **请求体**:
  ```json
  {
    "ai_provider": "opencode",
    "ai_model": "kimi-k2.5-free",
    "theme": "light",
    "language": "zh-CN",
    "provider_api_keys": {
      "opencode": "sk-xxx",
      "zhipuai": "xxx"
    }
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "配置更新成功，请验证服务可用性",
    "updated_fields": {...},
    "backup_path": "D:\\...\\config.yaml.backup.20260302_150000"
  }
  ```
- **重要**: 更新后会创建备份文件，等待验证成功后删除

---

### 4. 验证API Key
- **URL**: `POST /api/v1/config/validate`
- **描述**: 验证指定provider的API Key是否有效
- **请求体**:
  ```json
  {
    "provider": "opencode"
  }
  ```
- **响应**:
  ```json
  {
    "valid": true,
    "message": "API Key验证成功，当前使用 opencode",
    "model": "kimi-k2.5-free"
  }
  ```

---

### 5. 获取模型列表
- **URL**: `GET /api/v1/config/models`
- **描述**: 获取所有可用的模型列表
- **响应**:
  ```json
  {
    "models": [
      {
        "id": 1,
        "provider": "opencode",
        "model": "minimax-m2.5-free",
        "display_name": "MiniMax Free",
        "current_model": false
      },
      {
        "id": 2,
        "provider": "opencode",
        "model": "kimi-k2.5-free",
        "display_name": "Kimi Free",
        "current_model": true
      }
    ],
    "default_provider": "opencode"
  }
  ```

---

### 6. 完整配置验证
- **URL**: `GET /api/v1/config/validate-full`
- **描述**: 完整验证所有配置
- **响应**:
  ```json
  {
    "success": true,
    "provider": "opencode",
    "model": "kimi-k2.5-free",
    "message": "配置验证通过: provider=opencode, model=kimi-k2.5-free",
    "errors": [],
    "warnings": []
  }
  ```

---

### 7. 获取完整配置
- **URL**: `GET /api/v1/config/full`
- **描述**: 获取完整配置（包含所有provider详情）
- **响应**:
  ```json
  {
    "ai": {
      "provider": "opencode",
      "model": "kimi-k2.5-free",
      "opencode": {...},
      "zhipuai": {...}
    },
    "app": {...},
    "security": {...}
  }
  ```

---

### 8. 验证AI服务
- **URL**: `GET /api/v1/chat/validate`
- **描述**: 验证当前配置的AI服务是否可用
- **响应**:
  ```json
  {
    "success": true,
    "provider": "opencode",
    "model": "kimi-k2.5-free",
    "message": "AI 服务验证成功，当前使用 opencode (kimi-k2.5-free)"
  }
  ```
- **重要**: 
  - 验证成功会删除备份文件
  - 验证失败会恢复备份文件

---

## 错误避免说明

### 1. 配置更新后必须验证

**错误做法**：只调用updateConfig，不调用validateService

**正确做法**：
```
updateConfig → validateService → 根据结果处理
```

---

### 2. 验证失败会自动恢复配置

**重要**：如果在updateConfig后没有调用validateService，配置可能处于不一致状态。

**防御措施**：
- 启动时检查清理遗留备份文件
- 确保每次updateConfig后都调用validateService

---

### 3. provider和model必须匹配

**错误做法**：
- provider配置了，但model不在该provider的models列表中
- api_key为空

**正确做法**：
- 确保model在provider的models列表中
- 确保api_key已配置

---

### 4. 配置文件格式要求

**必须遵守**：
- ai.provider 在第1行
- ai.model 在第2行
- 其他provider按字母顺序排列

---

## API汇总表

### 读取类API

| 序号 | API | 方法 | 说明 |
|------|-----|------|------|
| 1 | `/api/v1/health` | GET | 健康检查，返回版本号 |
| 2 | `/api/v1/config` | GET | 获取当前配置（脱敏） |
| 3 | `/api/v1/config/models` | GET | 获取模型列表 |
| 4 | `/api/v1/config/validate-full` | GET | 完整配置验证 |
| 5 | `/api/v1/config/full` | GET | 获取完整配置 |
| 6 | `/api/v1/chat/validate` | GET | 验证AI服务可用性 |

### 写入类API

| 序号 | API | 方法 | 说明 |
|------|-----|------|------|
| 1 | `/api/v1/config` | PUT | 更新配置 |
| 2 | `/api/v1/config/validate` | POST | 验证API Key |

---

## 核心要点汇总

### 1. 统一Fallback逻辑

**规则**：
1. 只有当 ai.provider 存在 且 ai.model 存在 且 ai.model 在 ai.provider 的 models 列表中时，才使用 ai.provider + ai.model
2. 否则统一fallback到：第一个有models的provider + 第一个model

### 2. 备份恢复机制

- updateConfig → 创建备份
- validateService成功 → 删除备份
- validateService失败 → 恢复备份

### 3. 配置验证流程

启动流程：validateFullConfig → getModelList → validateService

切换模型流程：updateConfig → validateFullConfig → getModelList → validateService

### 4. 重要禁止事项

- 禁止硬编码provider名称（opencode、zhipuai、longcat等）
- 必须动态遍历配置文件中的provider

---

**更新时间**: 2026-03-02 15:00:00
**版本**: v1.0
**编写者**: 小沈
