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
      // 只在构建时启用可视化分析
      isBuild && visualizer({ gzipSize: true, open: false }),
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
      // 生产环境压缩优化
      minify: 'esbuild',
      // 使用函数方式配置 manualChunks，避免循环依赖
      rollupOptions: {
        output: {
          // 按node_modules路径关键字分割，避免循环依赖
          manualChunks(id) {
            if (id.includes('node_modules')) {
              // React 核心库 - 最稳定，单独一个大chunk
              if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
                return 'vendor-react';
              }
              // antd UI库 - 较大，单独分割
              if (id.includes('antd') || id.includes('@ant-design')) {
                return 'vendor-antd';
              }
              // 其他第三方库
              return 'vendor-other';
            }
            // 应用代码放到主chunk
            return 'app';
          },
        },
      },
      cssCodeSplit: true,
      chunkSizeWarningLimit: 500,
      sourcemap: false,
    },
  };
});
