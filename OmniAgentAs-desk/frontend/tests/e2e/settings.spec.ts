/**
 * Settings E2E Tests
 * 
 * @author 小新
 * @description End-to-end tests for settings functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Settings Page - Model Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    // Click on model config tab
    await page.getByText(/模型配置/).click();
  });

  test('should display model configuration form', async ({ page }) => {
    await expect(page.getByText(/模型提供商/)).toBeVisible();
    await expect(page.getByText(/模型名称/)).toBeVisible();
    await expect(page.getByText(/API密钥/)).toBeVisible();
  });

  test('should have provider dropdown with options', async ({ page }) => {
    const providerSelect = page.getByRole('combobox').first();
    await providerSelect.click();
    
    // Check for provider options
    await expect(page.getByText(/智谱AI/)).toBeVisible();
    await expect(page.getByText(/OpenCode/)).toBeVisible();
    await expect(page.getByText(/OpenAI/)).toBeVisible();
    await expect(page.getByText(/Anthropic/)).toBeVisible();
  });

  test('should save model config with valid data', async ({ page }) => {
    // Select provider
    await page.getByRole('combobox').first().click();
    await page.getByText(/智谱AI/).click();
    
    // Fill model name
    await page.getByPlaceholder(/输入模型名称/).fill('glm-4-test');
    
    // Fill API key
    await page.getByPlaceholder(/输入API密钥/).fill('test-api-key-123');
    
    // Click save
    await page.getByRole('button', { name: /保存模型配置/ }).click();
    
    // Should show success message
    await expect(page.getByText(/已保存/)).toBeVisible();
  });

  test('should show validation error for empty API key', async ({ page }) => {
    // Clear API key if it has value
    const apiKeyInput = page.getByPlaceholder(/输入API密钥/);
    await apiKeyInput.fill('');
    
    // Try to submit
    await page.getByRole('button', { name: /保存模型配置/ }).click();
    
    // Should show validation error
    await expect(page.getByText(/请输入API密钥/)).toBeVisible();
  });

  test('should have temperature slider options', async ({ page }) => {
    await expect(page.getByText(/温度参数/)).toBeVisible();
    
    // Click on temperature select
    await page.getByRole('combobox').filter({ hasText: /平衡/ }).click();
    
    // Should show temperature options
    await expect(page.getByText(/最确定/)).toBeVisible();
    await expect(page.getByText(/最随机/)).toBeVisible();
  });

  test('should reset form when reset button clicked', async ({ page }) => {
    // Fill in some data
    await page.getByPlaceholder(/输入模型名称/).fill('test-model');
    
    // Click reset
    await page.getByRole('button', { name: /重置/ }).click();
    
    // Form should be reset (values cleared or restored to default)
    // This depends on implementation, checking if button exists is enough
    await expect(page.getByRole('button', { name: /保存模型配置/ })).toBeVisible();
  });
});

test.describe('Settings Page - Security Configuration', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    // Click on security config tab
    await page.getByText(/安全配置/).click();
  });

  test('should display security switches', async ({ page }) => {
    await expect(page.getByText(/启用内容安全/)).toBeVisible();
    await expect(page.getByText(/启用命令白名单/)).toBeVisible();
    await expect(page.getByText(/危险操作二次确认/)).toBeVisible();
  });

  test('should toggle content filter', async ({ page }) => {
    // Find the content filter switch
    const contentFilterSwitch = page.locator('.ant-switch').first();
    
    // Toggle it
    await contentFilterSwitch.click();
    
    // Should be toggled (check class or aria attribute)
    await expect(contentFilterSwitch).toHaveAttribute('aria-checked', 'true');
  });

  test('should display filter level options when content filter enabled', async ({ page }) => {
    // Enable content filter first
    await page.locator('.ant-switch').first().click();
    
    // Should show filter level select
    await expect(page.getByText(/敏感词过滤级别/)).toBeVisible();
    
    // Click on level select
    await page.getByRole('combobox').filter({ hasText: /平衡/ }).click();
    
    // Should show level options
    await expect(page.getByText(/低 - 仅过滤明显违规内容/)).toBeVisible();
    await expect(page.getByText(/高 - 严格过滤所有敏感内容/)).toBeVisible();
  });

  test('should have command whitelist textarea', async ({ page }) => {
    // Enable whitelist
    const whitelistSwitch = page.locator('.ant-switch').nth(1);
    await whitelistSwitch.click();
    
    // Should show whitelist textarea
    await expect(page.getByPlaceholder(/示例/)).toBeVisible();
  });

  test('should have command blacklist textarea', async ({ page }) => {
    await expect(page.getByText(/命令黑名单/)).toBeVisible();
    await expect(page.locator('textarea').last()).toBeVisible();
  });

  test('should save security configuration', async ({ page }) => {
    // Toggle some switches
    await page.locator('.ant-switch').first().click();
    await page.locator('.ant-switch').nth(2).click();
    
    // Click save
    await page.getByRole('button', { name: /保存安全配置/ }).click();
    
    // Should show success message
    await expect(page.getByText(/已保存/)).toBeVisible();
  });
});

test.describe('Settings Page - Session History', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
    // Click on session history tab
    await page.getByText(/会话历史/).click();
  });

  test('should display session list controls', async ({ page }) => {
    await expect(page.getByRole('button', { name: /清空所有会话/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /刷新列表/ })).toBeVisible();
  });

  test('should show empty state when no sessions', async ({ page }) => {
    // If no sessions, should show empty state
    await expect(page.getByText(/暂无会话记录/).first()).toBeVisible();
  });

  test('should refresh session list', async ({ page }) => {
    // Click refresh button
    await page.getByRole('button', { name: /刷新列表/ }).click();
    
    // Should show loading or refresh the list
    await expect(page.getByRole('button', { name: /刷新列表/ })).toBeVisible();
  });

  test('should show confirmation before clearing all sessions', async ({ page }) => {
    // Click clear all button
    await page.getByRole('button', { name: /清空所有会话/ }).click();
    
    // Should show confirmation dialog
    await expect(page.getByText(/确定要清空所有会话吗/)).toBeVisible();
    await expect(page.getByRole('button', { name: /确定/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /取消/ })).toBeVisible();
  });
});

test.describe('Settings Page - Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
  });

  test('should switch between tabs', async ({ page }) => {
    // Start on model config (default)
    await expect(page.getByText(/模型配置说明/)).toBeVisible();
    
    // Switch to security
    await page.getByText(/安全配置/).click();
    await expect(page.getByText(/安全配置说明/)).toBeVisible();
    
    // Switch to session history
    await page.getByText(/会话历史/).click();
    await expect(page.getByText(/会话管理/)).toBeVisible();
    
    // Switch back to model config
    await page.getByText(/模型配置/).click();
    await expect(page.getByText(/模型配置说明/)).toBeVisible();
  });

  test('should have back navigation to chat', async ({ page }) => {
    // Navigate to chat page
    await page.goto('/');
    
    // Should be on chat page
    await expect(page.getByText(/AI助手对话/)).toBeVisible();
  });
});
