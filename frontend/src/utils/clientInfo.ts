// 编辑历史: 2026-08-27 小欧 - 修复#10: device触屏笔记本误判mobile, 改UA判定(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: device与isMobile共用IS_MOBILE_UA正则, 弃maxTouchPoints防触屏本误判
// 编辑历史: 2026-08-27 小欧 - 修复B4/B5: OS判定移动端(UA含Linux/Mac)优先于Android/iPhone/iPad; B6/B7: 浏览器Edge/Opera先于Chrome判定
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

// 2026-08-27 小欧 三堂会审: 真移动端UA正则, device与isMobile共用, 弃maxTouchPoints(触屏笔记本误判)
const IS_MOBILE_UA = /iPhone|iPad|Android|Mobile/i;

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
    // 2026-08-27 小欧 修复B4/B5: 移动端UA(Android含Linux子串/iPhone含Mac子串)优先判定, 避免误判为Linux/macOS
    if (ua.includes("Windows")) client_os = "Windows";
    else if (ua.includes("iPhone")) client_os = "iOS";
    else if (ua.includes("iPad")) client_os = "iPadOS";
    else if (ua.includes("Android")) client_os = "Android";
    else if (ua.includes("Mac")) client_os = "macOS";
    else if (ua.includes("Linux")) client_os = "Linux";
    else if (navigator.platform) client_os = navigator.platform;
  }

  // 2. 获取浏览器信息
  const ua = navigator.userAgent;
  let browser = "Unknown";
  // 2026-08-27 小欧 修复B6/B7: Edge/Opera的UA亦含Chrome子串, 须先于Chrome判定, 避免误判为Chrome
  // 现代 Edge UA 子串为 "Edg"(Edg/EdgA), 旧版为 "Edge"; 两者均须前置
  if (ua.includes("Edg") || ua.includes("Edge")) browser = "Edge";
  else if (ua.includes("Opera") || ua.includes("OPR")) browser = "Opera";
  else if (ua.includes("Chrome")) browser = "Chrome";
  else if (ua.includes("Firefox")) browser = "Firefox";
  else if (ua.includes("Safari")) browser = "Safari";

  // 3. 获取设备类型（与 isMobile() 统一口径：以 UA 判定真移动端，避免触屏笔记本误判为 mobile）
  const device = IS_MOBILE_UA.test(navigator.userAgent) ? "mobile" : "desktop";

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
// 2026-08-27 小欧 三堂会审: 弃maxTouchPoints(触屏笔记本误判为mobile), 与device共用IS_MOBILE_UA
export function isMobile(): boolean {
  return IS_MOBILE_UA.test(navigator.userAgent);
}

export default getClientInfo;