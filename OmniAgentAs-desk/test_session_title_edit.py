from playwright.sync_api import sync_playwright
import time
import subprocess
import threading
import sys
import os

def start_servers():
    """启动后端和前端服务器"""
    # 启动后端服务器
    backend_process = subprocess.Popen([
        sys.executable, "-m", "app.main"
    ], cwd=r"D:\2bktest\MDview\OmniAgentAs-desk\backend", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 启动前端服务器
    frontend_process = subprocess.Popen([
        "npm", "run", "dev"
    ], cwd=r"D:\2bktest\MDview\OmniAgentAs-desk\frontend", stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    
    # 等待一段时间让服务器启动
    time.sleep(10)
    
    return backend_process, frontend_process

def test_session_title_edit():
    """测试会话标题编辑功能"""
    # 启动服务器
    print("启动后端和前端服务器...")
    backend_proc, frontend_proc = start_servers()
    
    try:
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(headless=False)  # 设为False以便观察
            page = browser.new_page()
            
            # 访问应用
            print("访问应用...")
            page.goto("http://localhost:3001")
            
            # 等待页面加载
            page.wait_for_load_state('networkidle')
            print("页面已加载")
            
            # 等待会话标题元素出现
            print("等待会话标题元素...")
            session_title = page.locator("text='AI对话助手'")
            session_title.wait_for()
            
            # 点击会话标题以进入编辑模式
            print("点击会话标题...")
            title_element = page.locator("span:has-text('新会话')")
            if title_element.count() > 0:
                title_element.click()
                print("点击了现有标题")
            else:
                # 尝试点击标题周围的区域或"未命名会话"
                title_element = page.locator("text='未命名会话'")
                if title_element.count() > 0:
                    title_element.click()
                    print("点击了'未命名会话'")
                else:
                    # 尝试找到任何可点击的标题区域
                    title_selectors = [
                        "span[style*='cursor: pointer']",
                        "div[style*='cursor: pointer']",
                        "[data-testid='session-title']",
                        ".ant-card-head-title span"
                    ]
                    
                    clicked = False
                    for selector in title_selectors:
                        try:
                            element = page.locator(selector)
                            if element.count() > 0:
                                element.first.click()
                                print(f"点击了选择器 {selector}")
                                clicked = True
                                break
                        except:
                            continue
                    
                    if not clicked:
                        print("尝试直接点击标题区域...")
                        # 直接尝试点击标题区域
                        page.locator(".ant-card-head-title").click()
            
            # 等待输入框出现
            print("等待输入框出现...")
            try:
                input_field = page.locator("input")
                input_field.wait_for(timeout=10000)
                
                # 清空输入框并输入新标题
                new_title = "测试标题 - " + str(int(time.time()))
                print(f"输入新标题: {new_title}")
                input_field.fill(new_title)
                
                # 按Enter键保存
                input_field.press("Enter")
                
                # 或者尝试点击页面其他地方来保存
                # page.locator("body").click(position={"x": 0, "y": 0})
                
                print("等待标题更新...")
                time.sleep(3)
                
                # 检查标题是否已更新
                if page.locator(f"text='{new_title}'").count() > 0:
                    print(f"✅ 成功更新标题为: {new_title}")
                else:
                    print("⚠️ 标题可能未更新，检查页面内容")
                    # 截图以便检查
                    page.screenshot(path="title_edit_result.png")
                    
            except Exception as e:
                print(f"编辑标题时出错: {e}")
                # 截图以便检查
                page.screenshot(path="title_edit_error.png")
                
                # 尝试另一种保存方式
                try:
                    # 查找保存按钮或其他交互元素
                    save_button = page.locator("button:has-text('保存')")
                    if save_button.count() > 0:
                        save_button.click()
                        print("点击了保存按钮")
                except:
                    print("未找到保存按钮")
            
            # 创建新会话测试
            print("测试创建新会话...")
            new_session_btn = page.locator("button:has-text('新建会话')")
            if new_session_btn.count() > 0:
                new_session_btn.click()
                time.sleep(3)
                print("已创建新会话")
            
            # 等待一段时间以便观察
            time.sleep(5)
            
            # 关闭浏览器
            browser.close()
            
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭服务器进程
        print("关闭服务器进程...")
        try:
            backend_proc.terminate()
            frontend_proc.terminate()
        except:
            print("无法终止进程")

if __name__ == "__main__":
    test_session_title_edit()