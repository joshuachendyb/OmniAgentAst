# 测试配置文件替换逻辑
test_content = '''# OmniAgentAst 配置文件
ai:
  provider: "zhipuai"

  zhipuai:
    model: "glm-4.7-flash"
    api_key: "xxx"

  opencode:
    model: "kimi-k2.5-free"
    api_key: "yyy"
'''

import re

# 测试从 zhipuai 切换到 opencode
pattern = r'(provider:\s*["\']?)(\w+)(["\']?)'
replacement = rf'\g<1>opencode\g<3>'
new_content = re.sub(pattern, replacement, test_content, count=1)

print("原始内容:")
print(test_content)
print("\n替换后内容:")
print(new_content)
print("\n验证是否包含 opencode:", 'provider: "opencode"' in new_content or "provider: opencode" in new_content)

# 再测试切换回来
new_content2 = re.sub(pattern, replacement.replace('opencode', 'zhipuai'), new_content, count=1)
print("\n再次切换回智谱:")
print(new_content2)
print("\n验证是否包含 zhipuai:", 'provider: "zhipuai"' in new_content2 or "provider: zhipuai" in new_content2)
