from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    print('1. 打开聊天页面...')
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    
    print('2. 点击设置按钮...')
    page.locator('text=设置').click()
    page.wait_for_timeout(1000)
    
    print('3. 截图设置页面...')
    page.screenshot(path='D:/2bktest/MDview/OmniAgentAs-desk/temp/test_settings.png', full_page=True)
    print('设置页面截图已保存')
    
    # 检查设置页面元素
    tabs = page.locator('[class*="tab"], button[class*="tab"]').count()
    print(f'设置标签数量: {tabs}')
    
    browser.close()
    print('测试完成!')
