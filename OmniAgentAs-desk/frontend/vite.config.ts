import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    // ⭐ 老杨修复：移除vite-plugin-eslint和vite-plugin-prettier
    // 原因：这两个插件在开发时每次启动都会运行，导致启动特别慢
    // 建议：使用 npm run lint 和 npm run format 手动检查，或配置IDE自动检查
  ],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
