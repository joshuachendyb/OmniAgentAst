from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print('正在打开前端页面...')
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    
    page.screenshot(path='D:/2bktest/MDview/OmniAgentAs-desk/temp/test_homepage.png', full_page=True)
    print('首页截图已保存')
    
    title = page.title()
    print(f'页面标题: {title}')
    
    chat_input = page.locator('textarea').count()
    print(f'聊天输入框数量: {chat_input}')
    
    browser.close()
    print('测试完成!')
