# Python 函数注册方法汇总

**创建时间**: 2026-06-17 12:49:01  
**编写人**: 小沈  
**用途**: 记录Python函数注册的8种常见方法及适用场景

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-17 12:49:01 | 初始版本，8种注册方法 | 小沈 |

---

## 一、装饰器注册

**原理**: 定义函数时通过装饰器自动放入注册表

```python
# 定义注册表
registry = {}

# 定义装饰器
def register(name):
    def wrapper(func):
        registry[name] = func
        return func
    return wrapper

# 使用装饰器注册
@register("hello")
def say_hello():
    return "你好"

# 调用
result = registry["hello"]()  # "你好"
```

| 优点 | 缺点 |
|------|------|
| 声明式，直观 | 注册时机不可控（导入即触发）|
| 定义与注册在一起 | 条件注册需要额外 if 包裹 |

**适合场景**: 数量固定的工具/命令/处理器注册

---

## 二、显式调用注册

**原理**: 定义函数后手动调用注册函数

```python
registry = {}

def register(name, func):
    registry[name] = func

def say_hello():
    return "你好"

# 手动注册，放最后统一执行
register("hello", say_hello)
```

| 优点 | 缺点 |
|------|------|
| 注册时机完全可控 | 多写一行调用代码 |
| 适合条件注册 | 容易漏掉（忘了写 register 调用） |

**适合场景**: 需要根据配置/条件决定是否注册时

---

## 三、类继承注册（自动收子类）

**原理**: 利用 `__init_subclass__` 或元类自动收集子类

```python
class PluginBase:
    plugins = {}  # 注册表

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        PluginBase.plugins[cls.__name__] = cls

# 子类自动注册到 PluginBase.plugins
class PdfPlugin(PluginBase):
    def run(self):
        return "处理PDF"

class DocxPlugin(PluginBase):
    def run(self):
        return "处理DOCX"

# 使用
for name, cls in PluginBase.plugins.items():
    instance = cls()
    print(instance.run())
```

| 优点 | 缺点 |
|------|------|
| 写新类自动注册，零手工操作 | 依赖继承，不够灵活 |
| 适合插件体系 | 单继承限制 |

**适合场景**: 插件系统、策略模式、格式处理器

---

## 四、导入即注册（有副作用，不推荐）

**原理**: 模块被 import 时，模块顶层的注册代码自动执行

```python
# register.py
registry = {}

# tools.py
from register import registry

def do_register(func):
    registry[func.__name__] = func
    return func

@do_register
def read_pdf():
    pass

@do_register
def write_pdf():
    pass
```

```python
# main.py
import tools  # 这一行就触发了注册！
```

| 优点 | 缺点 |
|------|------|
| 写模块时省心 | 副作用不易发现 |
| 代码少 | 测试困难（import就会注册） |

**适合场景**: **不推荐使用**，除非是极其简单的场景

---

## 五、入口点注册（标准插件机制）

**原理**: Python 包安装时通过 `entry_points` 声明，运行时按接口名发现

```python
# pyproject.toml 或 setup.py
[project.entry-points."myapp.plugins"]
pdf = "myapp.plugins.pdf:register"
docx = "myapp.plugins.docx:register"
```

```python
# 运行时发现所有插件
from importlib.metadata import entry_points

plugins = entry_points(group="myapp.plugins")
for ep in plugins:
    func = ep.load()  # 加载插件
    func()
```

| 优点 | 缺点 |
|------|------|
| 标准做法，生态兼容 | 需要安装包才能注册 |
| 第三方插件直接可用 | 不适合动态增减 |

**适合场景**: 第三方插件系统、框架扩展点

---

## 六、自发现注册

**原理**: 扫描指定包目录，按命名约定自动找到并注册

```python
import importlib
import pkgutil

registry = {}

def discover_plugins(package_name):
    """扫描指定包下所有模块，按命名约定注册"""
    package = importlib.import_module(package_name)
    for mod_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        mod = importlib.import_module(mod_info.name)
        for name in dir(mod):
            if name.startswith("tool_"):  # 命名约定
                registry[name] = getattr(mod, name)

discover_plugins("my_plugins")
```

| 优点 | 缺点 |
|------|------|
| 零配置，加文件即可 | 依赖命名约定，改名就漏 |
| 适合按目录组织 | 无法排除不需要的 |

**适合场景**: 约定大于配置的框架、按目录组织的工具集

---

## 七、配置文件注册

**原理**: 读 YAML/JSON 配置文件，动态加载指定函数

```python
import yaml
import importlib

registry = {}

def load_from_config(config_path):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    for item in config.get("plugins", []):
        mod = importlib.import_module(item["module"])
        func = getattr(mod, item["func"])
        registry[item["name"]] = func

# 使用
# config.yaml:
# plugins:
#   - name: pdf
#     module: myapp.plugins.pdf
#     func: parse

load_from_config("config.yaml")
```

| 优点 | 缺点 |
|------|------|
| 改配置文件即可加减 | 需要用户懂配置格式 |
| 无需改代码 | 路径写错了就加载失败 |

**适合场景**: 用户可配置的插件列表、按需加载的工具

---

## 八、抽象基类注册（带类型检查）

**原理**: 抽象基类 + `__init_subclass__`，注册同时做类型约束

```python
from abc import ABC, abstractmethod

class Shape(ABC):
    _registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Shape._registry[cls.__name__] = cls

    @abstractmethod
    def area(self):
        pass

class Circle(Shape):
    def __init__(self, r):
        self.r = r

    def area(self):
        return 3.14 * self.r * self.r

class Square(Shape):
    def __init__(self, side):
        self.side = side

    def area(self):
        return self.side * self.side
```

| 优点 | 缺点 |
|------|------|
| 类型安全，不实现抽象方法会报错 | 继承关系限制 |
| 自动注册 | 比__init_subclass__多了类型检查 |

**适合场景**: 需要强类型约束的插件/策略

---

## 九、方法对比速查

| 方法 | 注册时机 | 适合场景 | 推荐度 |
|------|---------|---------|--------|
| 1. 装饰器 | 导入时 | 固定工具集，数量少 | ⭐⭐⭐⭐⭐ |
| 2. 显式调用 | 手动控制 | 有条件注册 | ⭐⭐⭐⭐ |
| 3. 类继承 | 定义时自动 | 插件系统 | ⭐⭐⭐⭐ |
| 4. 导入即注册 | 导入时 | **不推荐** | ⭐ |
| 5. 入口点 | 安装时 | 第三方插件 | ⭐⭐⭐ |
| 6. 自发现 | 运行时扫描 | 约定式框架 | ⭐⭐⭐ |
| 7. 配置文件 | 运行时加载 | 用户可配 | ⭐⭐⭐⭐ |
| 8. 抽象基类 | 定义时自动 | 强类型插件 | ⭐⭐⭐ |

---

**文件结束时间**: 2026-06-17 12:49:01
