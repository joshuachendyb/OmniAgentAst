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
      react({
        // 方法10：antd按需导入配置
        babel: {
          plugins: [
            // antd按需导入 - 自动将 import { Button } from 'antd' 转为 import Button from 'antd/es/button'
            ['import', { libraryName: 'antd', libraryDirectory: 'es', style: false }]
          ]
        }
      }),
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
      rollupOptions: {
        output: {
          manualChunks: {},  // 空对象，让Vite自动按node_modules分割
        },
      },
      cssCodeSplit: true,
      chunkSizeWarningLimit: 500,
    },
  };
});