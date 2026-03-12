import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import eslint from "vite-plugin-eslint";
import prettier from "vite-plugin-prettier";

// https://vitejs.dev/config/
// ⭐ 老杨完美方案：根据环境决定是否运行检查
// - 用户运行(npm run dev): 不检查，启动快
// - 构建(npm run build): 运行检查，保证质量
// - E2E测试: 通过npm scripts单独运行检查
export default defineConfig(({ command }) => {
  const isBuild = command === "build";
  
  // 只在构建时运行ESLint和Prettier，用户开发时不运行
  const shouldCheck = isBuild;
  
  return {
    plugins: [
      react(),
      shouldCheck && eslint(),
      shouldCheck && prettier({
        parser: "typescript",
      }),
    ].filter(Boolean),
    server: {
      port: 3000,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
