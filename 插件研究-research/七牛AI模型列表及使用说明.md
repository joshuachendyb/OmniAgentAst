# 七牛 AI 模型列表及使用说明

**创建时间**: 2026-03-27  
**版本**: v1.0  
**作者**: 小沈  
**依据**: LLM-Structured-Outputs-支持情况研究报告-小沈-2026-03-20.md

---

## 一、基本信息

| 项目 | 内容 |
|------|------|
| API Base | https://api.qnaigc.com/v1 |
| API Key | sk-ee99b1ccb7495fd4f... |
| 可用模型数 | **52 个** |

---

## 二、快速查看命令

```bash
cd backend
python tools/qiniu_models.py
```

---

## 三、完整模型列表（52个）

### 智谱AI（5个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 1 | z-ai/glm-5 | GLM-5 | - | - | - |
| 22 | z-ai/glm-4.7 | GLM-4.7 | ✅ | ✅ | ❌ |
| 42 | z-ai/glm-4.6 | GLM-4.6 | ✅ | ✅ | ✅ |
| 4 | glm-4.5-air | GLM-4.5 Air | - | - | - |
| 27 | glm-4.5 | GLM-4.5 | - | - | - |

### OpenAI（2个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 2 | openai/gpt-5.4 | GPT-5.4 | - | - | - |
| 3 | openai/gpt-5.4-mini | GPT-5.4 Mini | - | - | - |

### MiniMax（4个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 5 | minimax/minimax-m2.5 | MiniMax M2.5 | ✅ | ✅ | ✅ |
| 21 | minimax/minimax-m2.1 | MiniMax M2.1 | - | - | - |
| 41 | minimax/minimax-m2 | MiniMax M2 | ⚠️ | ✅ | ❌ |
| 28 | MiniMax-M1 | MiniMax M1 | ✅ | ✅ | ❌ |

### 通义千问（16个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 7 | qwen3-235b-a22b-thinking-2507 | Qwen3 思考版 | - | - | - |
| 8 | qwen3-coder-480b-a35b-instruct | Qwen3 Coder | - | - | - |
| 14 | qwen3-32b | Qwen3 32B | - | - | - |
| 24 | qwen3-vl-30b-a3b-thinking | Qwen3 VL 思考版 | - | - | - |
| 25 | qwen3-30b-a3b-thinking-2507 | Qwen3 30B 思考版 | - | - | - |
| 26 | qwen3-30b-a3b-instruct-2507 | Qwen3 30B | - | - | - |
| 29 | qwen3-next-80b-a3b-thinking | Qwen3 Next 思考版 | - | - | - |
| 30 | qwen3-max-preview | Qwen3 Max Preview | - | - | - |
| 31 | qwen3-235b-a22b | Qwen3 235B | - | - | - |
| 33 | qwen-vl-max-2025-01-25 | Qwen VL Max | - | - | - |
| 34 | qwen-max-2025-01-25 | Qwen Max | - | - | - |
| 35 | qwen3-30b-a3b | Qwen3 30B | - | - | - |
| 36 | qwen2.5-vl-72b-instruct | Qwen2.5 VL | - | - | - |
| 37 | qwen2.5-vl-7b-instruct | Qwen2.5 VL 7B | - | - | - |
| 38 | qwen-turbo | Qwen Turbo | ✅ | ✅ | ❌ |
| 43 | qwen3-max | Qwen3 Max | ✅ | ✅ | ❌ |
| 49 | qwen3-235b-a22b-instruct-2507 | Qwen3 235B Instruct | - | - | - |
| 52 | qwen3-next-80b-a3b-instruct | Qwen3 Next Instruct | - | - | - |

### Kimi（4个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 9 | moonshotai/kimi-k2.5 | Kimi K2.5 | ✅ | ✅ | ❌ |
| 23 | moonshotai/kimi-k2-0905 | Kimi K2-0905 | ✅ | ✅ | ❌ |
| 50 | moonshotai/kimi-k2-thinking | Kimi K2 Thinking | ❌ | ❌ | ❌ |
| 51 | kimi-k2 | Kimi K2 (简化) | ✅ | ✅ | ❌ |

### DeepSeek（11个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 15 | deepseek/deepseek-v3.2-exp-thinking | V3.2 Exp Thinking | - | - | - |
| 16 | deepseek/deepseek-v3.2-exp | V3.2 Exp | - | - | - |
| 17 | deepseek-r1 | DeepSeek R1 | ✅ | ✅ | ✅ |
| 18 | deepseek-r1-0528 | DeepSeek R1 0528 | - | - | - |
| 19 | deepseek-v3-0324 | V3.2 0324 | - | - | - |
| 20 | deepseek/deepseek-v3.2-251201 | V3.2 | - | - | - |
| 40 | deepseek/deepseek-v3.1-terminus-thinking | V3.1 Thinking | - | - | - |
| 46 | deepseek-v3 | DeepSeek V3 | ⚠️ | ✅ | ❌ |
| 47 | deepseek/deepseek-v3.1-terminus | V3.1 | - | - | - |
| 48 | deepseek-v3.1 | DeepSeek V3.1 | ✅ | ✅ | ❌ |

### 字节豆包（6个）

| 序号 | 模型ID | 名称 | rf | tools | reason |
|------|--------|------|-----|-------|--------|
| 11 | doubao-1.5-thinking-pro | 豆包思考版 | - | - | - |
| 12 | doubao-1.5-vision-pro | 豆包视觉版 | - | - | - |
| 13 | doubao-seed-1.6-thinking | Seed 思考版 | - | - | - |
| 38 | doubao-seed-1.6-flash | Seed Flash | - | - | - |
| 39 | doubao-seed-1.6 | Seed | - | - | - |
| 45 | doubao-1.5-pro-32k | 豆包 Pro 32K | - | - | - |

### 其他（4个）

| 序号 | 模型ID | 名称 | 提供商 | rf | tools | reason |
|------|--------|------|--------|-----|-------|--------|
| 6 | nvidia/nemotron-3-super-120b-a12b | Nemotron | NVIDIA | - | - | - |
| 10 | meituan/longcat-flash-lite | LongCat Lite | 美团 | - | - | - |
| 44 | xiaomi/mimo-v2-flash | Mimo Flash | 小米 | - | - | - |

**图例**: ✅=支持，❌=不支持，⚠️=部分支持/非标准JSON

---

## 四、功能支持汇总

### 完整支持（rf + tools + reasoning）

| 模型ID | 名称 |
|--------|------|
| z-ai/glm-4.6 | 智谱GLM-4.6 |
| minimax/minimax-m2.5 | MiniMax M2.5 |
| deepseek-r1 | DeepSeek R1 |

### 支持 rf + tools

| 模型ID | 名称 |
|--------|------|
| z-ai/glm-4.7 | 智谱GLM-4.7 |
| moonshotai/kimi-k2 | Kimi K2 |
| moonshotai/kimi-k2-0905 | Kimi K2-0905 |
| moonshotai/kimi-k2.5 | Kimi K2.5 |
| deepseek-v3.1 | DeepSeek V3.1 |
| MiniMax-M1 | MiniMax M1 |
| qwen-turbo | 通义千问 Turbo |
| qwen3-max | 通义千问3 Max |

### 支持 basic + tools

| 模型ID | 名称 |
|--------|------|
| deepseek-v3 | DeepSeek V3 |
| minimax/minimax-m2 | MiniMax M2 |

---

## 五、推荐使用

### 用于 Function Calling

- **z-ai/glm-4.6** - 智谱GLM-4.6（推荐）
- **minimax/minimax-m2.5** - MiniMax M2.5（推荐）

### 用于意图分类

- **z-ai/glm-4.7** - 便宜快速
- **moonshotai/kimi-k2.5** - 理解力强

---

## 六、代码使用

### Python 导入

```python
# 文件位置: backend/tools/qiniu_models.py

from tools.qiniu_models import (
    QINIU_CONFIG,
    ALL_MODELS,
    TEST_RESULTS,
    RECOMMENDED_FOR_TOOLS,
    RECOMMENDED_FOR_INTENT,
    get_model_info,
    is_full_support,
    is_tools_support,
)

# 七牛 API 配置
api_base = QINIU_CONFIG["api_base"]  # https://api.qnaigc.com/v1
api_key = QINIU_CONFIG["api_key"]

# 获取模型信息
info = get_model_info("z-ai/glm-4.6")

# 检查功能支持
if is_full_support("z-ai/glm-4.6"):
    print("完整支持")
```

### API 调用示例

```python
import requests

url = "https://api.qnaigc.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

response = requests.post(
    url,
    headers=headers,
    json={
        "model": "z-ai/glm-4.7",
        "messages": [{"role": "user", "content": "判断意图：查看D盘目录 是 file 还是 chat？只回答 file 或 chat"}]
    }
)

print(response.json()["choices"][0]["message"]["content"])
```

### 用 LLM 做意图分类

```python
from app.services.llm_core import BaseAIService

# 创建服务
service = BaseAIService(
    api_key="YOUR_API_KEY",
    model="z-ai/glm-4.7",
    api_base="https://api.qnaigc.com/v1",
    provider="qiniu"
)

import asyncio

async def classify_intent(text):
    prompt = f'判断意图："{text}" 是 file 还是 chat？只回答 file 或 chat'
    response = await service.chat(prompt)
    return response.content

result = asyncio.run(classify_intent("查看D盘目录"))
print(result)
```

---

**更新时间**: 2026-03-27
