import requests

print('=== 小健Python测试中文指令 ===')
print()

test_cases = [
    ('删除文件 tests/11.txt', '7-8分'),
    ('查看文件 readme.txt', '0-3分'),
    ('创建目录 temp', '0-3分'),
]

for cmd, expected in test_cases:
    print(f'Test: {cmd}')
    try:
        r = requests.post('http://localhost:8000/api/v1/security/check', 
                         json={'command': cmd})
        data = r.json()
        if data.get('success'):
            score = data["data"]["score"]
            msg = data["data"]["message"]
            print(f'  Score: {score}')
            print(f'  Message: {msg}')
            print('  [OK]')
        else:
            print(f'  [ERROR]: {data.get("error")}')
    except Exception as e:
        print(f'  [EXCEPTION]: {e}')
    print()
