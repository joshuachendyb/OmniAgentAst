import os
import sys
import json
import time
import subprocess
import threading
import platform
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file
import requests
import pyautogui
import pyperclip
import pdfplumber
import pygetwindow as gw
from duckduckgo_search import DDGS

# ================= 配置区域 =================
PROVIDER = "claude" 
CLAUDE_API_KEY = "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" # 替换为你的 Claude Key
CLAUDE_MODEL = "claude-sonnet-4-20250514"

HOST_IP = "0.0.0.0"
PORT = 5000
ACCESS_PASSWORD = "123456"
# ===========================================

app = Flask(__name__)
DATA_DIR = "ai_os_data"
HISTORY_FILE = os.path.join(DATA_DIR, "full_history.json")
os.makedirs(DATA_DIR, exist_ok=True)

# 定义 AI 可以使用的工具
TOOLS_DEFINITION = [
    {
        "name": "run_shell",
        "description": "执行系统命令行指令并获取返回结果",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Windows CMD 或 PowerShell 命令"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "list_windows",
        "description": "获取当前所有打开的窗口标题列表，用于判断软件是否打开或切换",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "switch_window",
        "description": "根据标题关键词切换窗口焦点",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "窗口标题包含的关键词"}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "type_text",
        "description": "在当前聚焦的窗口中输入文字（模拟键盘输入）",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要输入的内容"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "hotkey",
        "description": "发送快捷键组合，如 Ctrl+S 保存, Ctrl+Enter 发送",
        "input_schema": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "快捷键，用逗号分隔，例如 'ctrl,s'"}
            },
            "required": ["keys"]
        }
    },
    {
        "name": "list_desktop_files",
        "description": "列出桌面上的文件，用于查找文件",
        "input_schema": {"type": "object", "properties": {}}
    }
]

# ================= HTML 界面 =================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI OS Agent v2.0</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; margin: 0; padding: 0; color: #333; }
        .container { max-width: 800px; margin: 0 auto; padding: 10px; height: 100vh; display: flex; flex-direction: column; }
        .header { background: #ff5722; color: white; padding: 15px; border-radius: 10px; margin-bottom: 10px; text-align: center; }
        .mode-selector { display: flex; gap: 5px; margin-bottom: 10px; }
        .mode-btn { flex: 1; padding: 10px; border: none; background: #ddd; border-radius: 5px; cursor: pointer; font-weight: bold;}
        .mode-btn.active { background: #ff5722; color: white; }
        .chat-box { flex: 1; overflow-y: auto; background: white; border-radius: 10px; padding: 15px; border: 1px solid #ddd; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px; border-radius: 10px; max-width: 85%; word-wrap: break-word; white-space: pre-wrap; font-size: 14px; }
        .msg-user { align-self: flex-end; background: #DCF8C6; }
        .msg-ai { align-self: flex-start; background: #E8E8E8; }
        .msg-action { align-self: flex-start; background: #e3f2fd; font-size: 12px; color: #0d47a1; border: 1px dashed #90caf9; font-family: monospace; }
        .input-area { background: white; padding: 10px; border-radius: 10px; margin-top: 10px; border: 1px solid #ddd; }
        .text-input { width: 100%; height: 60px; border: 1px solid #ccc; border-radius: 5px; padding: 5px; box-sizing: border-box; resize: none; }
        .controls { display: flex; gap: 5px; margin-top: 5px; }
        .btn { flex: 1; padding: 10px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .btn-send { background: #ff5722; color: white; }
        .login-screen { position: fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); display:flex; justify-content:center; align-items:center; z-index: 999; }
        .login-box { background: white; padding: 20px; border-radius: 10px; text-align: center; }
    </style>
</head>
<body>
    <div id="login-screen" class="login-screen">
        <div class="login-box">
            <h3>安全验证</h3>
            <input type="password" id="pwd-input" placeholder="输入访问密码">
            <button onclick="login()">解锁</button>
            <p id="err-msg" style="color:red; display:none;">密码错误</p>
        </div>
    </div>

    <div class="container">
        <div class="header"><h3>AI OS Agent (ReAct Loop)</h3></div>
        <div class="mode-selector">
            <button class="mode-btn active" onclick="setMode('agent')">智能体模式</button>
            <button class="mode-btn" onclick="setMode('chat')">纯聊天</button>
        </div>
        <div class="chat-box" id="chat-box"></div>
        <div class="input-area">
            <textarea class="text-input" id="user-input" placeholder="输入指令..."></textarea>
            <div class="controls">
                <button class="btn btn-send" onclick="sendMessage()">执行</button>
            </div>
        </div>
    </div>
    <script>
        let currentMode = 'agent';
        
        function login() {
            const pwd = document.getElementById('pwd-input').value;
            fetch('/check_auth', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({password: pwd})
            }).then(r => r.json()).then(d => {
                if(d.success) document.getElementById('login-screen').style.display = 'none';
                else document.getElementById('err-msg').style.display = 'block';
            });
        }

        function addMsg(type, text) {
            const box = document.getElementById('chat-box');
            const div = document.createElement('div');
            div.className = `msg msg-${type}`;
            div.innerText = text;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }
        
        function setMode(m){ 
            currentMode = m; 
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
        }

        async function sendMessage() {
            const input = document.getElementById('user-input');
            const text = input.value.trim();
            if(!text) return;
            addMsg('user', text);
            input.value = '';
            
            try {
                const resp = await fetch('/chat', { 
                    method: 'POST', 
                    body: JSON.stringify({text, mode: currentMode}), 
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await resp.json();
                
                addMsg('ai', data.response);
                
                if(data.logs && data.logs.length > 0){
                    data.logs.forEach(log => {
                        addMsg('action', `⚙️ ${log.action}\n📄 ${log.result}`);
                    });
                }
            } catch (e) {
                addMsg('ai', "连接服务器失败，请检查控制台报错");
            }
        }
    </script>
</body>
</html>
"""

class AIAgent:
    def __init__(self):
        self.history = []

    # --- 工具函数实现 ---
    def tool_run_shell(self, command):
        try:
            # 使用 utf-8 编码捕获输出
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, encoding='utf-8', errors='ignore')
            return result.stdout + result.stderr
        except Exception as e:
            return str(e)

    def tool_list_windows(self):
        try:
            windows = gw.getAllTitles()
            return json.dumps([w for w in windows if w])
        except Exception as e:
            return f"Error: {str(e)}"

    def tool_switch_window(self, keyword):
        try:
            wins = gw.getWindowsWithTitle(keyword)
            if wins:
                wins[0].activate()
                time.sleep(0.5)
                return f"已切换到窗口: {wins[0].title}"
            return "未找到包含该关键词的窗口"
        except Exception as e:
            return f"切换失败: {str(e)}"

    def tool_type_text(self, text):
        time.sleep(0.5)
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        # 修复点：修正了这里的语法错误 text[:20]
        return f"已输入内容: {text[:20]}..."

    def tool_hotkey(self, keys):
        key_list = [k.strip() for k in keys.split(',')]
        pyautogui.hotkey(*key_list)
        return f"已发送快捷键: {keys}"

    def tool_list_desktop_files(self):
        desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
        files = os.listdir(desktop)
        return json.dumps(files)

    # --- 核心循环逻辑 ---
    def run_agent_loop(self, user_goal):
        messages = [
            {"role": "user", "content": f"用户目标: {user_goal}\n\n请利用工具一步步完成任务。每一步都要先思考，然后调用工具，最后根据工具返回结果决定下一步。"}
        ]
        
        logs = []
        max_steps = 10 # 防止死循环
        
        for step in range(max_steps):
            print(f"[Agent Loop] Step {step+1}...")
            # 1. 调用 Claude (带上工具定义)
            try:
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": CLAUDE_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json"
                    },
                    json={
                        "model": CLAUDE_MODEL,
                        "max_tokens": 1024,
                        "system": "你是一个电脑操作智能体。请使用提供的工具操作电脑。如果任务完成，请直接回复用户'任务完成'并总结结果。",
                        "messages": messages,
                        "tools": TOOLS_DEFINITION
                    },
                    timeout=30
                )
            except Exception as e:
                return f"网络连接错误: {str(e)}", logs
            
            if resp.status_code != 200:
                return f"API Error ({resp.status_code}): {resp.text}", logs
                
            data = resp.json()
            
            # 将 assistant 的回复加入历史 (包含思考过程和工具调用请求)
            messages.append({"role": "assistant", "content": data['content']})
            
            # 2. 检查是否需要调用工具
            tool_calls = [block for block in data['content'] if block['type'] == 'tool_use']
            
            if not tool_calls:
                # 没有工具调用，说明任务结束
                final_text = "".join([b['text'] for b in data['content'] if b['type'] == 'text'])
                return final_text, logs
            
            # 3. 执行工具并反馈结果
            tool_results = []
            for tool in tool_calls:
                func_name = tool['name']
                params = tool['input']
                tool_id = tool['id']
                
                print(f"Executing: {func_name} with {params}")
                
                # 执行函数
                result = "Unknown tool"
                if func_name == "run_shell": result = self.tool_run_shell(params['command'])
                elif func_name == "list_windows": result = self.tool_list_windows()
                elif func_name == "switch_window": result = self.tool_switch_window(params['keyword'])
                elif func_name == "type_text": result = self.tool_type_text(params['text'])
                elif func_name == "hotkey": result = self.tool_hotkey(params['keys'])
                elif func_name == "list_desktop_files": result = self.tool_list_desktop_files()
                
                # 记录日志
                logs.append({"action": f"{func_name}({params})", "result": str(result)[:200]})
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": str(result)
                })
            
            # 4. 将工具结果塞回消息历史，准备下一轮
            messages.append({"role": "user", "content": tool_results})

        return "达到最大步数限制，任务暂停。", logs

# Flask 路由
agent = AIAgent()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/check_auth', methods=['POST'])
def check_auth():
    data = request.json
    if data.get('password') == ACCESS_PASSWORD:
        return jsonify(success=True)
    return jsonify(success=False)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    text = data.get('text')
    mode = data.get('mode')
    
    if mode == 'chat':
        return jsonify(response="纯聊天模式暂未配置API", logs=[])
    
    # 进入 Agent 循环
    final_response, logs = agent.run_agent_loop(text)
    
    return jsonify(response=final_response, logs=logs)

if __name__ == '__main__':
    print("-" * 30)
    print("AI OS Agent v2.0 (Fixed)")
    print(f"Provider: {PROVIDER}")
    print(f"Please visit: http://{HOST_IP}:{PORT}")
    print("-" * 30)
    # 增加异常捕获，防止双击闪退看不到错误
    try:
        app.run(host=HOST_IP, port=PORT, debug=False)
    except Exception as e:
        print(f"\n[!] 启动失败: {e}")
        input("按回车键退出...") 