# Algorithmic-Art Skill 线条生成技巧总结

**创建时间**: 2026-02-11 00:54:00
**适用场景**: 生成艺术封面、算法美学设计、有机线条图案

---

## 一、核心理念

### 1.1 算法艺术 vs 静态设计

| 维度 | Canvas-Design (静态) | Algorithmic-Art (动态) |
|------|---------------------|----------------------|
| 技术栈 | pycairo 矢量渲染 | p5.js + HTML5 Canvas |
| 风格 | 精确、几何、印刷级 | 有机、流动、生成式 |
| 随机性 | 固定布局 | 种子随机 + 噪声函数 |
| 输出 | PNG/PDF | HTML交互 + PNG截图 |
| 美学 | Blueprint Clarity | Digital Sketch Genesis |

### 1.2 两阶段工作流

```
用户输入 → 算法哲学文档(.md) → 代码实现(.html+.js) → PNG输出
```

**第一阶段**: 创建算法哲学文档
- 定义生成美学运动名称
- 阐述计算过程、涌现行为、数学美感
- 描述噪声函数、粒子动力学、参数变化

**第二阶段**: 编写 p5.js 代码
- 实现代理(agent)系统
- 应用噪声函数驱动运动
- 添加交互式参数控制
- 使用 Puppeteer 生成静态 PNG

---

## 二、关键技术要素

### 2.1 代理系统 (Agent System)

**核心概念**: 多个自主实体在画布上移动并留下轨迹

```javascript
// 代理对象结构
agent = {
    x: random(width),        // 位置 X
    y: random(height),       // 位置 Y
    vx: 0,                   // 速度 X
    vy: 0,                   // 速度 Y
    life: random(100, 400),  // 生命周期
    weight: random(0.5, 2),  // 线条粗细
    color: color(44, 62, 80) // 颜色
}
```

**关键参数**:
- `agentCount`: 代理数量 (20-200)
- `life`: 每个代理的寿命步数
- `weight`: 线条粗细变化

### 2.2 噪声函数 (Noise Functions)

**作用**: 为代理运动添加有机的、非随机的变化

```javascript
// Perlin/Simplex 噪声
let noiseVal = noise(x * scale, y * scale, time);
let angle = noiseVal * TWO_PI * 4;

// 或使用数学近似
noise_val = (Math.sin(x * 3 + time) + Math.sin(y * 2 + time * 1.5)) / 2;
```

**技巧**:
- 多层噪声叠加产生更丰富的纹理
- `noiseScale` 控制变化频率 (0.001-0.02)
- 时间维度让图案动态演化

### 2.3 场动力学 (Field Dynamics)

**原理**: 代理响应虚拟力场而改变运动方向

```javascript
// 计算噪声驱动的角度
let angle = noise(agent.x * params.noiseScale, 
                  agent.y * params.noiseScale, 
                  frameCount * 0.01) * TWO_PI * 4;

// 更新速度
agent.vx += cos(angle) * 0.1 * params.speed;
agent.vy += sin(angle) * 0.1 * params.speed;

// 阻尼衰减
agent.vx *= 0.95;
agent.vy *= 0.95;
```

### 2.4 参数化控制

**可调参数设计**:

| 参数 | 范围 | 效果 |
|------|------|------|
| `agentCount` | 20-200 | 线条密度 |
| `noiseScale` | 0.001-0.02 | 变化平滑度 |
| `speed` | 0.5-5 | 运动快慢 |
| `turbulence` | 0-1 | 混乱程度 |
| `strokeWeight` | 0.5-4 | 线条粗细 |

---

## 三、色彩策略

### 3.1 配色方案

**石墨素描风格**:
```javascript
colors = [
    color(44, 62, 80),     // #2C3E50 深石墨
    color(52, 73, 94),     // #34495E 中石墨
    color(44, 62, 80, 80), // 浅石墨
    color(52, 152, 219)    // #3498DB 蓝色点缀
];
```

**技巧**:
- 使用透明度 (`alpha` 通道) 创造层次感
- 线条颜色基于代理索引循环: `colors[i % colors.length]`
- 线条粗细随生命周期衰减: `weight * (life / maxLife)`

### 3.2 背景与对比

```javascript
// 纸张白色背景
background(250, 250, 250);

// 或使用微暖色调
background(252, 250, 245);
```

---

## 四、从 HTML 到 PNG 的转换

### 4.1 Puppeteer 截图方案

**为什么用 Puppeteer?**
- 从真实浏览器渲染，保留所有细节
- 支持 p5.js 动画完整播放
- 可以精确控制截图时机

**实现步骤**:

```javascript
const puppeteer = require('puppeteer');

// 1. 启动浏览器
const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox']
});

// 2. 设置视口
await page.setViewport({ width: 800, height: 600 });

// 3. 加载 HTML
await page.goto('file://' + htmlPath);

// 4. 等待动画完成
await new Promise(resolve => setTimeout(resolve, 5000));

// 5. 截图
await element.screenshot({ path: 'output.png', type: 'png' });
```

### 4.2 替代方案: Python PIL

**适用场景**: 无需浏览器环境，快速生成

```python
from PIL import Image, ImageDraw
import random
import math

# 创建画布
img = Image.new('RGB', (800, 600), (250, 250, 250))
draw = ImageDraw.Draw(img)

# 模拟代理系统
for agent in agents:
    # 计算噪声角度
    angle = (math.sin(x * scale) + math.sin(y * scale)) / 2
    # 绘制线条
    draw.line([(x1, y1), (x2, y2)], fill=color, width=weight)

img.save('output.png')
```

---

## 五、最佳实践

### 5.1 项目结构

```
doc/ProjectCover/
├── Algorithmic_Philosophy.md     # 设计理念文档
├── Sketch_Genesis.html           # 交互式网页
├── generate_cover.py/js          # PNG生成脚本
└── Cover_Final_800x600.png       # 最终封面
```

### 5.2 调试技巧

**1. 种子可复现性**
```javascript
let seed = 12345;
randomSeed(seed);
noiseSeed(seed);
// 相同种子 = 相同图案
```

**2. 参数实时调节**
- 在 HTML 中添加滑块控件
- 实时预览不同参数效果
- 找到最佳组合后固定值

**3. 动画暂停检查**
```javascript
if (agents.length === 0) {
    noLoop(); // 所有代理死亡后停止
}
```

### 5.3 性能优化

- 限制代理数量 (< 200)
- 使用 `noLoop()` 避免无效重绘
- 减少噪声计算频率
- Puppeteer 截图时关闭动画

---

## 六、常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 线条太乱 | agentCount 太高或 turbulence 太大 | 减少数量，降低混乱度 |
| 线条太平滑 | noiseScale 太小 | 增大 scale 值 (0.01-0.02) |
| 图案太简单 | 代理寿命太短 | 增加 life 值 |
| 颜色单调 | 缺少透明度变化 | 添加 alpha 通道变化 |
| PNG 模糊 | 截图时机太早 | 等待动画完成后再截图 |

---

## 七、进阶技巧

### 7.1 多层叠加

```javascript
// 第一层: 粗线条骨架
// 第二层: 中等细节
// 第三层: 细线条纹理
for (let layer = 0; layer < 3; layer++) {
    strokeWeight(3 - layer);
    // ...
}
```

### 7.2 响应式边界

```javascript
// 边界反弹而非截断
if (x < 0 || x > width) vx *= -1;
if (y < 0 || y > height) vy *= -1;
```

### 7.3 力场叠加

```javascript
// 多个噪声场叠加
let angle1 = noise(x * scale1, y * scale1) * PI;
let angle2 = noise(x * scale2 + 100, y * scale2) * PI;
let angle = (angle1 + angle2) / 2;
```

---

## 八、案例复盘: Pencil 封面

**项目**: Pencil 安装研究文章封面
**风格**: Digital Sketch Genesis (数字素描创世纪)

**关键决策**:
1. **代理数量**: 80 个 (平衡密度与清晰度)
2. **噪声尺度**: 0.008 (中等变化频率)
3. **配色**: 石墨灰 + 蓝色点缀 (专业感)
4. **背景**: 纯白 (突出线条)
5. **尺寸**: 800x600 (文章封面标准)

**生成流程**:
1. 编写算法哲学文档 → 定义美学方向
2. 创建 p5.js HTML → 实现交互式生成
3. Puppeteer 截图 → 获得高质量 PNG

---

## 九、工具链对比

| 工具 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **p5.js + Puppeteer** | 真实渲染，可交互 | 需要浏览器 | 高质量最终输出 |
| **Python PIL** | 快速，无需浏览器 | 无法运行 JS | 快速原型，批量生成 |
| **Canvas-Design** | 矢量精度，印刷级 | 静态设计 | 几何风格封面 |

---

## 十、核心口诀

```
算法艺术两阶段
先写文档后代码

代理系统画线条
噪声函数添变化

参数控制可调节
种子固定可复现

Puppeteer 截高清
PIL快速做原型

有机流动是风格
蓝灰配色显专业
```

---

**文档创建**: 2026-02-11 00:54:00
**适用项目**: 技术文章封面、算法艺术展示、生成式设计

