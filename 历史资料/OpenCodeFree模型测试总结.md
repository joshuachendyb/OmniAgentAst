# OpenCode Zen 免费模型测试总结

**测试时间**: 2026-02-15 18:40:00 ~ 18:56:00  
**文档创建**: 2026-02-16 06:20:29  
**测试人员**: AI开发助手  
**测试环境**: OmniAgentAst 项目开发环境  

---

## 一、测试背景

### 1.1 测试目的
在OmniAgentAst项目开发阶段1.2（AI模型接入）中，需要评估OpenCode Zen平台提供的免费模型作为备选方案的可行性。

### 1.2 测试环境
- **API端点**: `https://opencode.ai/zen/v1/chat/completions`
- **认证方式**: Bearer Token
- **测试密钥**: sk-6rMee9Ez89iRCEvDayPq2hdTrMGKyPesy5K88uZKVAqOrc7tg6sVqRI5T1pP2LXb
- **测试工具**: curl + Python httpx

---

## 二、免费模型列表

OpenCode Zen平台共提供**6个免费模型**：

| 序号 | 模型ID | 提供商 | 国家/地区 | 备注 |
|------|--------|--------|-----------|------|
| 1 | **kimi-k2.5-free** | Moonshot AI（月之暗面） | 中国 | 长上下文(256K) |
| 2 | **minimax-m2.1-free** | MiniMax | 中国 | - |
| 3 | **minimax-m2.5-free** | MiniMax | 中国 | - |
| 4 | **glm-4.7-free** | 智谱AI | 中国 | - |
| 5 | **trinity-large-preview-free** | Trinity | 美国 | - |
| 6 | **big-pickle** | 未知 | 未知 | 测试中发现的模型 |

---

## 三、通讯测试结果

### 3.1 首轮测试（18:40:00）

| 模型 | 测试状态 | 说明 |
|------|---------|------|
| trinity-large-preview-free | ✅ 成功 | 响应正常 |
| glm-4.7-free | ✅ 成功 | 响应正常 |
| minimax-m2.1-free | ❌ 失败 | API错误 |
| kimi-k2.5-free | ⚠️ 限速 | 请求被限制 |

### 3.2 次轮测试（18:56:00）

| 模型 | 测试状态 | 说明 |
|------|---------|------|
| trinity-large-preview-free | ✅ 成功 | 稳定可用 |
| big-pickle | ✅ 成功 | 新发现可用模型 |
| minimax-m2.5-free | ✅ 成功 | 次轮可用 |
| glm-4.7-free | ❌ 失败 | 次轮不可用 |
| minimax-m2.1-free | ❌ 失败 | 持续不可用 |
| kimi-k2.5-free | ⚠️ 限速 | 仍然被限速 |

### 3.3 最终可用性评估

| 模型 | 可用性 | 稳定性 | 备注 |
|------|--------|--------|------|
| trinity-large-preview-free | ✅ 可用 | 稳定 | 两次测试均成功 |
| big-pickle | ✅ 可用 | 未知 | 单次测试成功 |
| minimax-m2.5-free | ✅ 可用 | 一般 | 间歇性可用 |
| glm-4.7-free | ⚠️ 不稳定 | 差 | 首次可用，次轮失败 |
| minimax-m2.1-free | ❌ 不可用 | - | 持续失败 |
| kimi-k2.5-free | ⚠️ 限速 | - | API限制访问 |

---

## 四、功能测试结果

### 4.1 中文输入测试

| 模型 | 中文响应 | 问题描述 |
|------|---------|---------|
| trinity-large-preview-free | ❌ 不稳定 | 偶尔返回空内容 |
| big-pickle | ❌ 空content | 返回空响应 |
| minimax-m2.5-free | ❌ 空content | 返回空响应 |
| glm-4.7-free | ❌ 空content | 返回空响应 |
| minimax-m2.1-free | - | API错误，未测试 |
| kimi-k2.5-free | ⚠️ 限速 | 无法测试 |

### 4.2 英文输入测试

| 模型 | 英文响应 | 问题描述 |
|------|---------|---------|
| trinity-large-preview-free | ✅ 正常 | 唯一正常响应的模型 |
| big-pickle | ⚠️ 仅reasoning | 返回reasoning字段，content为空 |
| minimax-m2.5-free | ⚠️ 仅reasoning | 返回reasoning字段，content为空 |
| glm-4.7-free | ⚠️ 仅reasoning | 返回reasoning字段，content为空 |
| minimax-m2.1-free | ❌ API错误 | 持续失败 |
| kimi-k2.5-free | ⚠️ 限速 | 无法测试 |

---

## 五、核心问题分析

### 5.1 空content问题
**现象**: 多个模型（MiniMax、GLM）返回JSON结构正常，但content字段为空

**可能原因**:
1. 免费模型限制返回内容
2. 模型实际生成了内容但被过滤
3. API网关截断了响应
4. 模型本身输出异常

### 5.2 速率限制问题
**现象**: kimi-k2.5-free 触发速率限制

**错误信息**:
```json
{
  "type": "error",
  "error": {
    "type": "FreeUsageLimitError",
    "message": "Rate limit exceeded. Please try again later."
  }
}
```

**建议**: 免费模型有访问频率限制，需要控制请求频率

### 5.3 模型不稳定问题
**现象**: 同一模型在不同时间测试结果不同

**案例**: glm-4.7-free 首次成功，次轮失败

**可能原因**:
1. 免费模型负载均衡导致分配到不同实例
2. 部分实例故障或维护
3. 免费额度耗尽

---

## 六、测试结论

### 6.1 可用性结论

| 结论 | 说明 |
|------|------|
| **trinity-large-preview-free** | ✅ 推荐作为备选方案（英文场景） |
| **MiniMax系列** | ❌ 不推荐，返回空内容 |
| **GLM-4.7-free** | ⚠️ 不稳定，不推荐 |
| **kimi-k2.5-free** | ⚠️ 限速严重，暂时不可用 |

### 6.2 使用建议

1. **短期方案**: 使用 trinity-large-preview-free 作为英文对话备选
2. **中文场景**: 当前免费模型均无法稳定支持中文
3. **生产环境**: 建议购买付费API或继续使用智谱GLM
4. **开发测试**: 可以集成但需做好容错处理

### 6.3 技术实现建议

```python
# 建议的容错处理逻辑
async def chat_with_fallback(message):
    providers = ["zhipuai", "opencode"]
    
    for provider in providers:
        try:
            service = AIServiceFactory.get_service(provider)
            response = await service.chat(message)
            
            if response.success and response.content:
                return response
            
            # 记录失败原因
            print(f"{provider} 失败: {response.error}")
            
        except Exception as e:
            print(f"{provider} 异常: {e}")
    
    return ChatResponse(
        content="所有AI服务暂时不可用，请稍后重试",
        model="fallback",
        error="all_providers_failed"
    )
```

---

## 七、相关API端点

### 7.1 OpenCode Zen API

| 端点 | 功能 | 方法 |
|------|------|------|
| `https://opencode.ai/zen/v1/models` | 获取模型列表 | GET |
| `https://opencode.ai/zen/v1/chat/completions` | 对话生成 | POST |
| `https://opencode.ai/zen/v1/credits` | 查询积分 | GET |

### 7.2 调用示例

**获取模型列表**:
```bash
curl -s https://opencode.ai/zen/v1/models
```

**测试模型**:
```bash
curl -s -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -X POST https://opencode.ai/zen/v1/chat/completions \
  -d '{
    "model": "trinity-large-preview-free",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

---

## 八、后续建议

### 8.1 短期行动
- [ ] 集成 trinity-large-preview-free 作为备选（仅英文）
- [ ] 实现自动切换逻辑（主服务失败时切换到备选）
- [ ] 添加详细的错误日志和监控

### 8.2 中长期规划
- [ ] 评估购买OpenCode付费API
- [ ] 寻找其他免费/低成本AI API
- [ ] 实现本地模型部署方案（如Ollama）

---

## 九、参考文档

- **来源文档**: `D:\2bktest\MDview\历史资料\网络查询记录-2026-02-15.md`
- **项目设计**: `D:\2bktest\MDview\OmniAgentAs-desk\doc\阶段1.2-设计文档-2026-02-15.md`
- **API文档**: https://opencode.ai/docs

---

**总结**: OpenCode Zen免费模型可用性较差，仅有 trinity-large-preview-free 在英文场景下可用。建议作为临时备选方案，生产环境仍需依赖付费API或主服务（智谱GLM）。

**文档状态**: 已完成  
**审核人**: 待审核
