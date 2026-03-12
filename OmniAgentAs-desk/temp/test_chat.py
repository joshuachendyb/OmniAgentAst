from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print('1. 打开聊天页面...')
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    
    print('2. 输入测试消息...')
    textarea = page.locator('textarea').first
    textarea.fill('你好，请介绍一下你自己')
    
    print('3. 点击发送按钮...')
    page.locator('button:has-text("发送")').click()
    
    print('4. 等待回复...')
    page.wait_for_timeout(8000)  # 等待8秒
    
    # 截图保存
    page.screenshot(path='D:/2bktest/MDview/OmniAgentAs-desk/temp/test_chat.png', full_page=True)
    print('聊天截图已保存')
    
    # 检查是否有回复
    messages = page.locator('.message, [class*="message"]').count()
    print(f'消息数量: {messages}')
    
    browser.close()
    print('测试完成!')
