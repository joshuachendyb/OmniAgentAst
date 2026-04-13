import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import eslint from "vite-plugin-eslint";
import prettier from "vite-plugin-prettier";
import { visualizer } from "rollup-plugin-visualizer";

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
      // 方法9：使用 visualizer 分析 bundle（仅构建时）
      isBuild && visualizer({
        filename: "dist/stats.html",
        open: false,
        gzipSize: true,
        brotliSize: true,
      }),
    ].filter(Boolean),
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:8000",
          changeOrigin: true,
        },
      },
    },
    build: {
      // 方法2：使用Vite自动分割
      // 方法8：Tree-shaking - 改成 'recommended' 而非 'smallest'
      rollupOptions: {
        // treeshake: 'smallest' 太aggressive，会删掉所有代码
        // 改用 'recommended' 或直接删除（默认就是recommended）
        output: {
          manualChunks: {},  // 空对象，让Vite自动按node_modules分割
        },
      },
      cssCodeSplit: true,
      chunkSizeWarningLimit: 500,
    },
  };
});