import requests
import json

# 测试后端返回的模型列表数据
def test_model_list():
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/config/models")
        response.raise_for_status()  # 检查HTTP错误
        
        data = response.json()
        print("后端返回的模型列表数据：")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        print("\n模型详情：")
        for model in data.get("models", []):
            print(f"ID: {model['id']}")
            print(f"Provider: {model['provider']}")
            print(f"Model: {model['model']}")
            print(f"Display Name: {model['display_name']}")
            print(f"Current Model: {model['current_model']}")
            print("-" * 50)
            
    except Exception as e:
        print(f"测试失败：{e}")

if __name__ == "__main__":
    test_model_list()
