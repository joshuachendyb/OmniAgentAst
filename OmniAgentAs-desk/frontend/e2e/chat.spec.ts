/**
 * Chat E2E Tests
 * 
 * @author 小新
 * @description End-to-end tests for chat functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Chat Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display chat interface', async ({ page }) => {
    // Check if chat title is visible
    await expect(page.getByText('AI助手对话')).toBeVisible();
    
    // Check if input area is present
    await expect(page.getByPlaceholder(/输入消息/)).toBeVisible();
    
    // Check if send button is present
    await expect(page.getByRole('button', { name: /发送消息/ })).toBeVisible();
  });

  test('should send message and receive response', async ({ page }) => {
    // Type a message
    const messageInput = page.getByPlaceholder(/输入消息/);
    await messageInput.fill('Hello, AI!');
    
    // Click send button
    await page.getByRole('button', { name: /发送消息/ }).click();
    
    // Check if user message appears
    await expect(page.getByText('Hello, AI!')).toBeVisible();
    
    // Wait for AI response (with timeout)
    await expect(page.getByText(/AI助手/)).toBeVisible({ timeout: 10000 });
  });

  test('should switch between providers', async ({ page }) => {
    // Open provider selector
    await page.getByRole('combobox').click();
    
    // Select OpenCode
    await page.getByText(/OpenCode/).click();
    
    // Check if system message appears
    await expect(page.getByText(/已切换到/)).toBeVisible();
  });

  test('should clear chat history', async ({ page }) => {
    // Send a message first
    await page.getByPlaceholder(/输入消息/).fill('Test message');
    await page.getByRole('button', { name: /发送消息/ }).click();
    
    // Wait for message to appear
    await expect(page.getByText('Test message')).toBeVisible();
    
    // Click clear button
    await page.getByRole('button', { name: /清空对话/ }).click();
    
    // Check if chat is cleared
    await expect(page.getByText(/开始与AI助手对话/)).toBeVisible();
  });

  test('should show service status', async ({ page }) => {
    // Click check service button
    await page.getByRole('button', { name: /检查服务/ }).click();
    
    // Check if status alert appears
    await expect(page.getByText(/AI服务/)).toBeVisible({ timeout: 5000 });
  });

  test('should disable send button when input is empty', async ({ page }) => {
    const sendButton = page.getByRole('button', { name: /发送消息/ });
    await expect(sendButton).toBeDisabled();
  });

  test('should handle Enter key to send message', async ({ page }) => {
    const messageInput = page.getByPlaceholder(/输入消息/);
    await messageInput.fill('Test with Enter');
    await messageInput.press('Enter');
    
    // Check if message was sent
    await expect(page.getByText('Test with Enter')).toBeVisible();
  });

  test('should allow Shift+Enter for new line', async ({ page }) => {
    const messageInput = page.getByPlaceholder(/输入消息/);
    await messageInput.fill('Line 1');
    await messageInput.press('Shift+Enter');
    await messageInput.fill('Line 1\nLine 2');
    
    // Content should have newline
    await expect(messageInput).toHaveValue('Line 1\nLine 2');
  });
});

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings');
  });

  test('should display settings tabs', async ({ page }) => {
    await expect(page.getByText(/模型配置/)).toBeVisible();
    await expect(page.getByText(/安全配置/)).toBeVisible();
    await expect(page.getByText(/会话历史/)).toBeVisible();
  });

  test('should save model configuration', async ({ page }) => {
    // Switch to model config tab
    await page.getByText(/模型配置/).click();
    
    // Fill in API key
    await page.getByPlaceholder(/输入API密钥/).fill('test-api-key');
    
    // Click save button
    await page.getByRole('button', { name: /保存模型配置/ }).click();
    
    // Check for success message
    await expect(page.getByText(/已保存/)).toBeVisible();
  });

  test('should display session history', async ({ page }) => {
    // Switch to session history tab
    await page.getByText(/会话历史/).click();
    
    // Check if refresh button is present
    await expect(page.getByRole('button', { name: /刷新列表/ })).toBeVisible();
  });
});

test.describe('Responsive Design', () => {
  test('should adapt to mobile viewport', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    
    await page.goto('/');
    
    // Check if chat interface is still usable
    await expect(page.getByPlaceholder(/输入消息/)).toBeVisible();
    await expect(page.getByRole('button', { name: /发送消息/ })).toBeVisible();
  });

  test('should adapt to tablet viewport', async ({ page }) => {
    // Set tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });
    
    await page.goto('/');
    
    // Check if layout is responsive
    await expect(page.getByText('AI助手对话')).toBeVisible();
  });
});
