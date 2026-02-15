# AI助手安装程序铁规

**创建时间**: 2026-02-05 12:14:52

---

## 一、文档概述

**目的**：规范AI助手在Windows下的软件安装行为，确保规范化、可追溯、可维护。

**核心原则**：
| 原则 | 说明 |
|-----|------|
| 统一管理 | 安装包→D盘，安装位置→E盘 |
| 版本清晰 | 目录名包含版本号 |
| 环境可控 | 环境变量可追溯、可配置 |
| 权限明确 | 区分用户级和系统级 |
| 例外审批 | 无法遵循规定时请示用户 |

---

## 二、安装包存放规则

**规定目录**：`D:\30AI编程工具\`

**命名规范**：
```
安装包_软件名_版本号_日期.扩展名
示例：安装包_Python_3.13.11_20260205.exe
```

**下载命令**：
```bash
curl -L -o "D:/30AI编程工具/安装包_Python_3.13.11_$(date +%Y%m%d).exe" \
  "https://www.python.org/ftp/python/3.13.11/python-3.13.11-amd64.exe"
```

**网络异常处理**：
1. **优先使用国内镜像源**（最可靠）
2. GitHub下载加 `--mtu 1400`
3. 多次重试
4. 仍失败 → **通知用户提供完整下载链接**

**国内镜像源**：
| 软件 | 镜像源 |
|-----|-------|
| Python | https://pypi.tuna.tsinghua.edu.cn/simple |
| Node.js | https://registry.npmmirror.com |
| Go | https://goproxy.cn |
| GitHub | https://ghproxy.com |

---

## 三、软件安装目录规则

**规定目录**：`E:\0APPsoftware\`

**目录结构**：
```
E:\0APPsoftware\
├── Python313\     # Python 3.13
├── Go\            # Go语言
├── Nodejs\        # Node.js
└── AI框架\        # AI相关框架
    └── memU\
```

**版本号管理**：
| 场景 | 处理方式 |
|-----|---------|
| 首次安装 | 创建 `软件名+版本号` 目录 |
| 版本升级 | 创建新目录，旧目录保留 |

---

## 四、环境变量配置规则

> ⚠️ **重要说明**：以下方法都是永久写入Windows注册表，不是临时的！

**PATH配置（PowerShell）**：
```powershell
# 添加用户级PATH
[Environment]::SetEnvironmentVariable("Path", "E:\0APPsoftware\Python313;$([Environment]::GetEnvironmentVariable('Path', 'User'))", "User")

# 查询PATH
echo $env:PATH
```

**常见环境变量**：
| 变量 | 值 |
|-----|-----|
| PYTHON_HOME | `E:\0APPsoftware\Python313` |
| GO111MODULE | `on` |
| GOPATH | `E:\0APPsoftware\Go\path` |

---

## 五、安装流程规范

```
步骤1: 下载安装包 → 直接存放到 D:\30AI编程工具\
  ↓
步骤2: 验证安装包完整性
  ↓
步骤3: 执行安装
  ↓
步骤4: 安装到 E:\0APPsoftware\（除非程序有内置规则）
  ↓
步骤5: 配置环境变量
  ↓
步骤6: 验证安装结果并记录日志
```

**验证安装完整性**：
```python
import hashlib

def verify_checksum(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    print(f'SHA256: {sha256_hash.hexdigest()}')
    return sha256_hash.hexdigest()

verify_checksum('D:/30AI编程工具/安装包_Python_3.13.11_20260205.exe')
```

**安装日志文件**：记录到 `D:\30AI编程工具\安装日志.txt`

**追加格式**：
```
【安装记录】软件名 版本号
**时间**: 2026-02-05 14:13:47
安装包: D:\30AI编程工具\安装包_xxx.exe
安装路径: E:\0APPsoftware\xxx\
SHA256: abc123...
状态: 成功
```

---

## 六、例外审批规则

**需审批情况**：
1. 软件必须安装到C盘
2. 软件必须使用默认安装路径
3. 需要修改系统级环境变量
4. 安装包来源不明确
5. 需要安装系统级驱动

**审批请求模板**：
```
【安装审批请求】
软件名称: [软件名]
版本号: [版本]
安装位置: [计划安装位置]
例外原因: [为什么不能遵循规定]

请确认是否继续安装？
```

---

## 七、附录

**常用镜像源**：
| 软件 | 镜像源 |
|-----|-------|
| Python | https://pypi.tuna.tsinghua.edu.cn/simple |
| Node.js | https://registry.npmmirror.com |
| Go | https://goproxy.cn |
| GitHub | https://ghproxy.com |

**注册表路径**：
| 作用域 | 路径 |
|-------|------|
| 用户环境变量 | `HKEY_CURRENT_USER\Environment` |
| 系统环境变量 | `HKEY_LOCAL_MACHINE\SYSTEM\...\Environment` |

---

## 八、版本记录

| 版本 | 日期 | 更新内容 |
|-----|------|---------|
| v1.0 | 2026-02-05 | 初始版本 |
| v1.1 | 2026-02-05 14:13:47 | 精简章节、补充网络异常处理 |

---

**更新时间**: 2026-02-05 14:13:47
**版本**: v1.1
