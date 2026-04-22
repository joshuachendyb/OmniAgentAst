/**
 * 网络检查工具函数
 *
 * 功能：
 * - checkNetworkConnection: 检查网络连接状态
 *
 * 使用场景：
 * - 在发送消息前检查网络连接
 * - 验证服务器是否可达
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-22
 */

/**
 * 检查网络连接状态
 *
 * 通过向服务器发送健康检查请求来验证网络连接是否正常。
 * 如果请求在3秒内返回成功响应，则认为网络连接正常。
 *
 * @param apiBaseUrl - API基础URL
 * @returns Promise<boolean> - 网络连接是否正常
 */
export const checkNetworkConnection = async (apiBaseUrl: string): Promise<boolean> => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 3000);

  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response.ok;
  } catch (error) {
    clearTimeout(timeoutId);
    console.warn("网络连接检查失败:", error);
    return false;
  }
};
