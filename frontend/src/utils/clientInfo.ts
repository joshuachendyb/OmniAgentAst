/**
 * 客户端信息获取工具
 * 
 * 功能：获取客户端的操作系统、浏览器、设备类型等信息
 * 用于：在保存用户消息时传递客户端上下文信息
 * 
 * 创建时间：2026-03-24
 * 作者：小沈
 * 版本：v1.0
 */

interface ClientInfo {
  client_os: string;
  browser: string;
  device: string;
  network?: string;
}

/**
 * 获取客户端系统信息（渐进增强）
 * 
 * 优先级：
 * 1. navigator.userAgentData - 实验性 API，仅 Chrome/Edge/Opera 支持
 * 2. navigator.userAgent - 传统方法，所有浏览器支持
 * 3. navigator.platform - 已废弃但仍可用
 * 
 * @returns 客户端信息对象
 */
export function getClientInfo(): ClientInfo {
  // 类型断言，处理实验性 API
  const nav = navigator as Navigator & { userAgentData?: { platform: string }; connection?: { effectiveType: string } };
  
  // 1. 获取操作系统
  let client_os = "Unknown";
  if (nav.userAgentData && nav.userAgentData.platform) {
    // 实验性 API
    client_os = nav.userAgentData.platform;
  } else {
    const ua = navigator.userAgent;
    if (ua.includes("Windows")) client_os = "Windows";
    else if (ua.includes("Mac")) client_os = "macOS";
    else if (ua.includes("Linux")) client_os = "Linux";
    else if (ua.includes("iPhone")) client_os = "iOS";
    else if (ua.includes("iPad")) client_os = "iPadOS";
    else if (ua.includes("Android")) client_os = "Android";
    else if (navigator.platform) client_os = navigator.platform;
  }

  // 2. 获取浏览器信息
  const ua = navigator.userAgent;
  let browser = "Unknown";
  if (ua.includes("Chrome")) browser = "Chrome";
  else if (ua.includes("Firefox")) browser = "Firefox";
  else if (ua.includes("Safari") && !ua.includes("Chrome")) browser = "Safari";
  else if (ua.includes("Edge")) browser = "Edge";
  else if (ua.includes("Opera") || ua.includes("OPR")) browser = "Opera";

  // 3. 获取设备类型
  const device = navigator.maxTouchPoints > 1 ? "mobile" : "desktop";

  // 4. 获取网络类型（如果支持）
  let network: string | undefined;
  if (nav.connection && nav.connection.effectiveType) {
    network = nav.connection.effectiveType;
  }

  return {
    client_os,
    browser,
    device,
    network
  };
}

/**
 * 获取简化的客户端OS信息
 * 只返回操作系统名称，用于轻量级场景
 * 
 * @returns 操作系统名称（如 "Windows", "macOS", "Linux"）
 */
export function getClientOS(): string {
  const info = getClientInfo();
  return info.client_os;
}

/**
 * 检查是否为移动设备
 * 
 * @returns true 表示移动设备
 */
export function isMobile(): boolean {
  return navigator.maxTouchPoints > 1 || 
    /iPhone|iPad|Android/i.test(navigator.userAgent);
}

export default getClientInfo;