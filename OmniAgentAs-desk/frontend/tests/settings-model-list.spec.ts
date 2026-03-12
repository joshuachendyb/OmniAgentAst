import { test, expect } from '@playwright/test';

test('检查模型列表星号显示', async ({ page }) => {
  // 访问 Settings 页面
  await page.goto('http://localhost:3013/settings');
  
  // 等待页面加载完成
  await page.waitForSelector('text=当前模型');
  
  // 获取下拉框的所有选项
  const options = page.locator('.ant-select-dropdown-menu-item');
  
  // 检查选项数量
  const count = await options.count();
  console.log(`模型选项数量: ${count}`);
  
  // 遍历所有选项，检查星号显示
  for (let i = 0; i < count; i++) {
    const option = options.nth(i);
    const text = await option.innerText();
    
    // 检查是否包含星号
    if (text.includes('*')) {
      console.log(`包含星号的选项: ${text}`);
      
      // 检查是否是当前模型
      expect(text).toBe('zhipuai (cogview-3-flash) *');
    }
  }
});
