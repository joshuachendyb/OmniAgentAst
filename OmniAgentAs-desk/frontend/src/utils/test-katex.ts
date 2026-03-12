import katex from "katex";
import "katex/dist/katex.min.css";

// 测试用例
const testCases = [
  "$$x^2$$",
  "**粗体** $$x^2$$",
  "**最终答案：**  \n$$\\boxed{22}$$",
  "**最终答案：**\n$$\\boxed{22}$$",
];

testCases.forEach((test, i) => {
  console.log(`\n=== 测试 ${i + 1} ===`);
  console.log("输入:", JSON.stringify(test));
  
  // 简单测试：只匹配块公式
  const blockRegex = /\$\$[\s\S]*?\$\$/g;
  const matches = test.match(blockRegex);
  console.log("块公式匹配:", matches);
  
  // 测试 KaTeX 渲染
  if (matches) {
    matches.forEach((m, j) => {
      try {
        const formula = m.slice(2, -2).trim();
        const html = katex.renderToString(formula, { displayMode: true, throwOnError: false });
        console.log(`  公式${j + 1}: ${formula}`);
        console.log(`  HTML: ${html.substring(0, 50)}...`);
      } catch (e) {
        console.log(`  公式${j + 1} 错误:`, e);
      }
    });
  }
});
