# DCP prune 错误曲折时间线

## 事件1（初始阶段）：错误认知
- **我最初声称**：prune/distill 是 OpenCode 内置工具
- **用户质疑**：记得是安装插件后才有的这些工具
- **我的错误**：没有查证就凭记忆下结论

## 事件2（第一次查证）：官方文档核验
- **用户要求**：查看官方文档证明
- **我查证结果**：OpenCode 官方文档工具列表不包含 prune/distill
- **结论**：承认错误，prune/distill 不是内置工具

## 事件3（转向DCP）：npm信息误导
- **转向讨论**：prune/distill 来自 DCP 插件
- **我的错误**：查看 npm 页面时看到 discard/extract 信息
- **错误结论**：声称存在"版本混乱"（GitHub版用prune/distill，npm版用discard/extract）

## 事件4（第二次查证）：源码验证
- **用户要求**：查看实际源代码确认
- **我查证结果**：tarquinen/opencode-dcp v2.0.2 的 dist/index.js 暴露 prune/distill/compress
- **最终结论**：不存在版本混乱，npm 页面信息是错误的

## 关键发现点
1. **工具实际来源**：prune/distill/compress 确实由 DCP 插件提供
2. **版本一致性**：GitHub 官方版和 npm 版实际工具名一致
3. **信息差异来源**：npm 页面文档滞后或错误
4. **默认配置问题**：自动策略过于激进，导致频繁清理

## 改进建议
1. **统一来源**：以源码为准，文档要同步更新
2. **调整策略**：考虑将 prune 权限设为 "ask"，减少自动清理
3. **配置模板**：提供可直接使用的配置示例

## 证据链
- OpenCode 官方文档：https://opencode.ai/docs/tools/
- DCP 源码：tarquinen/opencode-dcp v2.0.2/dist/index.js
- 本地配置：dcp.jsonc（仅包含 schema 引用）

---

**创建时间**: 2026-02-10 06:36:14  
**更新时间**: 2026-02-10 当前时间