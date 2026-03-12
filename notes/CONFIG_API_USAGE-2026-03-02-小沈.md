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
  provider: opencode        # 当前选中的provider（必须放在ai块最前面）
  model: kimi-k2.5-free    # 当前选中的model（必须放在provider后面）
  opencode:                # provider名称（不能有model字段！）
    api_base: https://opencode.ai/zen/v1    # ✅ 必填：API地址
    api_key: sk-xxx                      # ✅ 必填：API密钥
    models:                              # ✅ 必填：可用模型列表
      - minimax-m2.5-free
      - glm-5-free
      - kimi-k2.5-free
    timeout: 150                          # 可选：超时时间（秒）
    max_retries: 3                       # 可选：最大重试次数
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
3. **每个provider必须配置以下子字段**：

| 子字段 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `api_base` | string | ✅ 必填 | AI服务的API地址（如 https://opencode.ai/zen/v1） |
| `api_key` | string | ✅ 必填 | API密钥 |
| `models` | array | ✅ 必填 | 可用模型列表（如 ["minimax-m2.5-free", "glm-5-free"]） |
| `timeout` | number | 可选 | 请求超时时间（秒），默认120 |
| `max_retries` | number | 可选 | 最大重试次数，默认3 |

**注意**：❌ provider下面**不能**有 `model` 字段（已废弃）

---

## 接口概览

### 模型配置相关API

| 类别 | API | 方法 | 用途 |
|------|-----|------|------|
| 健康检查 | `/api/v1/health` | GET | 检查后端是否正常，获取版本号 |
| 配置路径 | `/api/v1/config/path` | GET | 获取配置文件完整路径（新增） |
| 配置读取 | `/api/v1/config` | GET | 获取当前系统配置（脱敏） |
| 配置更新 | `/api/v1/config` | PUT | 切换模型、修改主题等保存配置 |
| 模型验证 | `/api/v1/config/validate` | POST | 验证API Key是否有效（需provider+api_key） |
| 模型列表 | `/api/v1/config/models` | GET | 获取可用模型列表供选择 |
| 完整验证 | `/api/v1/config/validate-full` | GET | 验证config.yaml配置完整性（新增逻辑有效性检查） |
| 完整配置 | `/api/v1/config/full` | GET | 获取完整配置（调试用） |
| AI服务验证 | `/api/v1/chat/validate` | GET | 测试AI服务是否可用（触发备份删除/恢复） |
| **配置修复** | `/api/v1/config/fix` | **POST** | **自动修复配置问题** |
| 添加Provider | `/api/v1/config/provider` | POST | 添加新Provider |
| 更新Provider | `/api/v1/config/provider/{name}` | PUT | 修改Provider配置 |
| 删除Provider | `/api/v1/config/provider/{name}` | DELETE | 删除Provider |
| 添加模型 | `/api/v1/config/provider/{name}/model` | POST | 添加模型到Provider |
| 删除模型 | `/api/v1/config/provider/{name}/model/{model_name}` | DELETE | 删除Provider下的模型 |

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
- **用途**: 检查后端服务是否正常运行，获取版本号用于前端显示
- **响应**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-03-02T10:00:00Z",
    "version": "0.4.14"
  }
  ```

---

### 2. 获取配置文件路径（新增）
- **URL**: `GET /api/v1/config/path`
- **用途**: 获取配置文件的完整路径和所在目录（新增接口）
- **响应**:
  ```json
  {
    "config_path": "D:\\2bktest\\MDview\\OmniAgentAs-desk\\config\\config.yaml",
    "config_dir": "D:\\2bktest\\MDview\\OmniAgentAs-desk\\config",
    "exists": true
  }
  ```

---

### 3. 获取当前配置
- **URL**: `GET /api/v1/config`
- **用途**: 获取当前系统配置（用于前端显示当前设置，不包含真实API Key）
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
- **用途**: 用户在设置页面切换模型、修改主题等配置时调用此接口保存配置
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
- **用途**: 用户在设置页面点击"验证"按钮时，测试输入的API Key是否有效
- **请求体**:
  ```json
  {
    "provider": "opencode",
    "api_key": "sk-xxx"
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
- **用途**: 启动时或刷新下拉框时，获取所有可用的模型列表供用户选择
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

### 7. 完整配置验证（新增逻辑有效性检查）
- **URL**: `GET /api/v1/config/validate-full`
- **用途**: 对配置文件本身进行完整性验证（不是测试AI服务），检查config.yaml是否有错误或警告
- **新增验证项**：
  1. 检查 ai.provider 是否存在
  2. 检查 ai.provider 的值是否在配置中
  3. 检查 ai.provider 的配置是否是有效的字典
  4. 检查 ai.model 是否存在
  5. 检查 ai.model 是否在 ai.provider 的 models 列表中
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

### 8. 获取完整配置
- **URL**: `GET /api/v1/config/full`
- **用途**: 获取完整配置信息（包含所有provider的详细配置，用于高级设置或调试）
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

### 9. 验证AI服务
- **URL**: `GET /api/v1/chat/validate`
- **用途**: 切换模型后或启动时，实际调用AI服务测试是否可用（会触发备份删除/恢复）
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

| 序号 | API | 方法 | 用途 |
|------|-----|------|------|
| 1 | `/api/v1/health` | GET | 检查后端健康，获取版本号 |
| 2 | `/api/v1/config/path` | GET | 获取配置文件路径（新增） |
| 3 | `/api/v1/config` | GET | 获取当前配置（脱敏） |
| 4 | `/api/v1/config/models` | GET | 获取模型列表 |
| 5 | `/api/v1/config/validate-full` | GET | 验证配置文件完整性（新增逻辑有效性检查） |
| 6 | `/api/v1/config/full` | GET | 获取完整配置 |
| 7 | `/api/v1/chat/validate` | GET | 验证AI服务可用性 |

### 写入类API

| 序号 | API | 方法 | 用途 |
|------|-----|------|------|
| 1 | `/api/v1/config` | PUT | 更新配置（切换模型等） |
| 2 | `/api/v1/config/validate` | POST | 验证API Key |
| 3 | `/api/v1/config/fix` | POST | 自动修复配置 |
| 4 | `/api/v1/config/provider` | POST | 添加Provider |
| 5 | `/api/v1/config/provider/{name}` | PUT | 更新Provider |
| 6 | `/api/v1/config/provider/{name}` | DELETE | 删除Provider |
| 7 | `/api/v1/config/provider/{name}/model` | POST | 添加模型 |
| 8 | `/api/v1/config/provider/{name}/model/{model_name}` | DELETE | 删除模型 |

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

## 附录：Provider管理API

### 1. 自动修复配置

- **URL**: `POST /api/v1/config/fix`
- **用途**: 当 validate-full 返回警告提示"provider下有废弃的model字段"时，调用此接口自动修复
- **响应**:
  ```json
  {
    "success": true,
    "fixed_issues": [
      "删除 provider 'zhipuai' 下废弃的 model 字段"
    ],
    "warnings": [],
    "backup_path": "D:\\...\\config.yaml.backup.20260302_150000"
  }
  ```

**触发场景**：
- 当 `/api/v1/config/validate-full` 返回警告 `"provider 'xxx' 下有废弃的 model 字段，建议调用 /config/fix 接口修复"`

---

### 2. 添加Provider

- **URL**: `POST /api/v1/config/provider`
- **用途**: 在配置文件中添加一个新的AI Provider（前端"设置页面"新增Provider按钮）
- **请求体**:
  ```json
  {
    "name": "newprovider",
    "api_base": "https://api.newprovider.com/v1",
    "api_key": "sk-xxx",
    "models": ["model-1", "model-2"],
    "timeout": 120,
    "max_retries": 3
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "Provider newprovider 已添加",
    "warnings": []
  }
  ```

---

### 3. 更新Provider

- **URL**: `PUT /api/v1/config/provider/{provider_name}`
- **用途**: 修改现有Provider的配置（前端"设置页面"修改Provider配置）
- **请求体**:
  ```json
  {
    "api_base": "https://api.newprovider.com/v1",
    "api_key": "sk-xxx",
    "model": "model-2",
    "timeout": 120,
    "max_retries": 3
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "Provider opencode 已更新",
    "warnings": [],
    "backup_path": "D:\\...\\config.yaml.backup.20260302_150000"
  }
  ```

---

### 4. 删除Provider

- **URL**: `DELETE /api/v1/config/provider/{provider_name}`
- **用途**: 删除指定的AI Provider（前端"设置页面"删除Provider按钮）
- **响应**:
  ```json
  {
    "success": true,
    "message": "Provider longcat 已删除"
  }
  ```

**注意**：
- 至少需要保留一个Provider
- 如果删除当前使用的Provider，会自动切换到第一个Provider

---

### 5. 添加模型

- **URL**: `POST /api/v1/config/provider/{provider_name}/model`
- **用途**: 向指定Provider添加新模型（前端"设置页面"添加模型按钮）
- **请求体**:
  ```json
  {
    "model": "new-model-1"
  }
  ```
- **响应**:
  ```json
  {
    "success": true,
    "message": "模型 new-model-1 已添加"
  }
  ```

---

### 6. 删除模型

- **URL**: `DELETE /api/v1/config/provider/{provider_name}/model/{model_name}`
- **用途**: 从指定Provider删除模型（前端"设置页面"删除模型按钮）
- **响应**:
  ```json
  {
    "success": true,
    "message": "模型 old-model 已删除"
  }
  ```

**注意**：
- 每个Provider至少需要保留一个模型
- 如果删除当前使用的模型，会自动切换到该Provider的第一个模型

---

## 已废弃接口（仅保留兼容）

### /chat/switch/{provider}

- **状态**: ⚠️ **已废弃**，不再推荐使用
- **原因**: 功能已被 `/api/v1/config` PUT 接口替代
- **URL**: `POST /api/v1/chat/switch/{provider}`
- **说明**: 已被 `PUT /api/v1/config` 替代，仅保留以防后续需要

---

## 附录：配置文件规范

### 正确格式

```yaml
ai:
  provider: opencode        # 顶层：当前使用的provider
  model: kimi-k2.5-free    # 顶层：当前使用的model
  opencode:
    api_base: https://opencode.ai/zen/v1
    api_key: sk-xxx
    models:
      - minimax-m2.5-free
      - glm-5-free
    timeout: 120
    max_retries: 3
  zhipuai:
    api_base: https://open.bigmodel.cn/api/paas/v4/
    api_key: xxx
    models:
      - glm-4.7-flash
```

### 禁止事项

| 禁止项 | 说明 |
|--------|------|
| ❌ provider下不能有model字段 | 只能有api_base, api_key, models, timeout, max_retries |
| ❌ 不能硬编码provider名称 | 必须从配置文件动态读取 |

---

**更新时间**: 2026-03-03 02:56:59
**版本**: v1.5
**编写者**: 小沈
**更新内容**: 2026-03-03 新增 /api/v1/config/path 接口，更新 /api/v1/config/validate-full 接口说明（新增逻辑有效性检查）
**测试说明**: 2026-03-02 18:30 所有API已通过实际测试验证，每个接口已添加"用途"说明
