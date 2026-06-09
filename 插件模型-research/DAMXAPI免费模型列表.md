# DAMXAPI 免费模型列表

**创建时间**: 2026-03-31 23:30:00
**版本**: v1.0
**作者**: 小沈

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-31 23:30:00 | 初始版本 | 小沈 |

---
https://www.dmxapi.cn/panel
账号 chendyg@qq.com  MM ：cdy199571
Base URL	https://www.dmxapi.cn
对话	https://www.dmxapi.cn/v1/chat/completions
对话（新）	https://www.dmxapi.cn/v1/responses
嵌入（Embedding）	https://www.dmxapi.cn/v1/embeddings
图片生成	https://www.dmxapi.cn/v1/images/generations
图片编辑	https://www.dmxapi.cn/v1/images/edits
语音转文字 STT	https://www.dmxapi.cn/v1/audio/transcriptions
文字转语音 TTS	https://www.dmxapi.cn/v1/audio/speech
base_url="https://www.dmxapi.cn/v1"
API-key=sk-N2cFYdEXiCRQ2gKUCBTwnP3arxfwesLHBGntk1tk8X3m2gS1

## API 配置信息

| 项目 | 值 |
|------|-----|
| Base URL | https://www.dmxapi.cn/v1 |
| API Key | sk-N2cFYdEXiCRQ2gKUCBTwnP3arxfwesLHBGntk1tk8X3m2gS1 |

---

## 免费模型列表

**统计信息**：
- 总模型数：766
- 免费模型数：20

### 免费模型清单

| 序号 | 模型ID | 说明 |
|------|--------|------|
| 1 | Baichuan-M3-Plus-free | 百川M3增强版免费 |
| 2 | DMXAPI-Code-Free | DMXAPI代码助手 |
| 3 | DMXAPI-CodeX-Free | DMXAPI代码增强版 |
| 4 | MiniMax-M2.5-free | MiniMax 2.5免费 |
| 5 | MiniMax-M2.7-free | MiniMax 2.7免费 |
| 6 | bge-reranker-v2-m3-free | BGE重排序模型 |
| 7 | doubao-seed-2.0-code-free | 豆包代码助手 |
| 8 | doubao-seed-2.0-lite-free | 豆包轻量版 |
| 9 | doubao-seed-2.0-pro-free | 豆包专业版 |
| 10 | glm-4.7-free | 智谱4.7免费 |
| 11 | glm-5-free | 智谱5免费 |
| 12 | glm-5-turbo-free | 智谱5Turbo免费 |
| 13 | glm-5.1-free | 智谱5.1免费 |
| 14 | kimi-k2.5-free | Kimi 2.5免费 |
| 15 | qwen-flash-free | 通义闪思 |
| 16 | qwen3-8b-free | 通义3 8B免费 |
| 17 | qwen3-coder-next-free | 通义3代码Next |
| 18 | qwen3-coder-plus-free | 通义3代码Plus |
| 19 | qwen3-max-2026-01-23-free | 通义3 Max |
| 20 | qwen3.5-plus-free | 通义3.5 Plus |

---

## 使用方法

在配置文件中使用免费模型：

```yaml
model:
  provider: dmxapi
  model: glm-5-turbo-free
  api_base: https://www.dmxapi.cn/v1
  api_key: sk-N2cFYdEXiCRQ2gKUCBTwnP3arxfwesLHBGntk1tk8X3m2gS1
```

---

## 查询方法

可以通过以下命令查询免费模型：

```bash
curl -s -H "Authorization: Bearer sk-N2cFYdEXiCRQ2gKUCBTwnP3arxfwesLHBGntk1tk8X3m2gS1" \
  "https://www.dmxapi.cn/v1/models"
```

或使用Python：

```python
import requests

r = requests.get(
    'https://www.dmxapi.cn/v1/models',
    headers={'Authorization': 'Bearer sk-N2cFYdEXiCRQ2gKUCBTwnP3arxfwesLHBGntk1tk8X3m2gS1'}
)
data = r.json()

# 筛选免费模型
free_models = [m for m in data.get('data', []) if 'free' in m['id'].lower()]
```
