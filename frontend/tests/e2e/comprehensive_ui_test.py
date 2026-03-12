"""
OmniAgentAs-desk Frontend E2E Comprehensive Testing Script
@description Test frontend UI including Chat page, Settings page, responsive design
@author 小新
"""

from playwright.sync_api import sync_playwright
import time

def test_chat_page_ui(page):
    """Test Chat page UI"""
    print("\n=== Testing Chat Page UI ===")
    
    # Navigate to Chat page
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    
    # Check 1: Page title
    try:
        title = page.get_by_text('AI助手对话')
        if title.is_visible():
            print("✅ Chat page title is visible")
        else:
            print("❌ Chat page title not visible")
    except:
        print("❌ Chat page title not found")
    
    # Check 2: Input box
    try:
        input_box = page.get_by_placeholder('输入消息')
        if input_box.is_visible():
            print("✅ Input box is visible")
        else:
            print("❌ Input box not visible")
    except:
        print("❌ Input box not found")
    
    # Check 3: Send button
    try:
        send_button = page.get_by_role('button', name='发送消息')
        if send_button.is_visible():
            print("✅ Send button is visible")
        else:
            print("❌ Send button not visible")
    except:
        print("❌ Send button not found")
    
    # Check 4: Check service button
    try:
        check_service = page.get_by_role('button', name='检查服务')
        if check_service.is_visible():
            print("✅ Check service button is visible")
        else:
            print("❌ Check service button not visible")
    except:
        print("❌ Check service button not found")
    
    # Screenshot
    page.screenshot(path='frontend/playwright-report/screenshots/chat-page-ui.png', full_page=True)

def test_settings_page_ui(page):
    """Test Settings page UI"""
    print("\n=== Testing Settings Page UI ===")
    
    # Navigate to Settings page
    page.goto('http://localhost:3000/settings')
    page.wait_for_load_state('networkidle')
    time.sleep(1)  # Wait for page to fully load
    
    # Check 1: Settings tabs
    try:
        tabs = ['模型配置', '安全配置', '会话历史']
        for tab_name in tabs:
            try:
                tab = page.get_by_text(tab_name)
                if tab.is_visible():
                    print(f"✅ {tab_name} tab is visible")
                else:
                    print(f"❌ {tab_name} tab not visible")
            except:
                print(f"❌ {tab_name} tab not found")
    except:
        print("❌ Settings tabs check failed")
    
    # Check 2: Form elements
    try:
        has_form = page.locator('form').count() > 0
        has_inputs = page.locator('input').count() > 0
        has_buttons = page.locator('button').count() > 0
        
        if has_form:
            print("✅ Settings page has form elements")
        if has_inputs:
            print(f"✅ Settings page has input boxes ({page.locator('input').count()}个)")
        if has_buttons:
            print(f"✅ Settings page has buttons ({page.locator('button').count()}个)")
    except:
        print("❌ Settings page form elements check failed")
    
    # Screenshot
    page.screenshot(path='frontend/playwright-report/screenshots/settings-page-ui.png', full_page=True)

def test_responsive_design(page):
    """Test responsive design"""
    print("\n=== Testing Responsive Design ===")
    
    # Test mobile device viewport
    print("Testing mobile device viewport (375x667)...")
    page.set_viewport_size({'width': 375, 'height': 667})
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    
    try:
        input_box = page.get_by_placeholder('输入消息')
        send_button = page.get_by_role('button', name='发送消息')
        
        if input_box.is_visible() and send_button.is_visible():
            print("✅ Mobile device viewport layout is normal")
        else:
            print("❌ Mobile device viewport layout is abnormal")
    except:
        print("❌ Mobile device viewport check failed")
    
    page.screenshot(path='frontend/playwright-report/screenshots/mobile-viewport.png', full_page=True)
    
    # Test tablet device viewport
    print("Testing tablet device viewport (768x1024)...")
    page.set_viewport_size({'width': 768, 'height': 1024})
    page.goto('http://localhost:3000')
    page.wait_for_load_state('networkidle')
    
    try:
        title = page.get_by_text('AI助手对话')
        if title.is_visible():
            print("✅ Tablet device viewport layout is normal")
        else:
            print("❌ Tablet device viewport layout is abnormal")
    except:
        print("❌ Tablet device viewport check failed")
    
    page.screenshot(path='frontend/playwright-report/screenshots/tablet-viewport.png', full_page=True)
    
    # Restore desktop viewport
    page.set_viewport_size({'width': 1920, 'height': 1080})

def main():
    """Main test function"""
    print("=== OmniAgentAs-desk Frontend E2E Comprehensive Testing ===")
    print("Test time:", time.strftime("%Y-%m-%d %H:%M:%S"))
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Use non-headless mode for easy observation
        page = browser.new_page()
        
        try:
            # Test 1: Chat page UI
            test_chat_page_ui(page)
            
            # Test 2: Settings page UI
            test_settings_page_ui(page)
            
            # Test 3: Responsive design
            test_responsive_design(page)
            
            print("\n=== All Tests Completed ===")
            print("✅ All UI interface checks completed")
            print("📸 Screenshots saved to frontend/playwright-report/screenshots/")
            
            # Keep browser open for manual inspection
            input("\nPress Enter to close browser...")
            
        except Exception as e:
            print(f"\n❌ Error occurred during testing: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == '__main__':
    main()
