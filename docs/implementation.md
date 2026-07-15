# Paste — Linux 剪切板管理器 · 实施计划

本文档是 architecture.md 的实施落地指南。按阶段拆分任务，标注依赖、预计工时、验收标准与已知障碍。

## 当前实现状态（2026-07-15）

- 托盘左键显示最近 5 条，右键提供显示/隐藏、热键配置、Recent 兼容入口和退出。
- Ubuntu GNOME 的 AppIndicator 后端可能无法区分左右键；应用会记录实际 `ActivationReason`，右键 Recent 子菜单作为回退。
- 主窗口第二次显示不再重复查询并重建未变化的 100 条列表；show 请求异步合并，并在按键释放前抑制 X11 自动重复（另过滤 250ms 内的重复请求）。
- 支持单条软删除、确认后清空全部历史，以及 `All / URLs / Images` 类型筛选；类型筛选可与搜索组合。
- `~/.paste/logs/paste.log` 使用 5MB × 5 轮转；UI 超过 8 秒无心跳时将线程堆栈写入 `~/.paste/logs/hang.log`。
- 日志避免记录剪切板正文。复现卡死后应同时提供 `paste.log`、`hang.log` 和桌面环境信息。

---

## Phase 0: 原型验证 (1 天)

**目标：** 在 X11 下跑通最小闭环：复制文本 → 写入数据库 → UI 展示 → 点击再复制。

### 任务清单

| # | 任务 | 产出文件 | 依赖 | 工时 |
|---|------|----------|------|------|
| 0.1 | 创建项目骨架 | `src/main.py` `src/app.py` | — | 0.5h |
| 0.2 | 初始化数据库 (含 FTS) | `src/database/db.py` `src/database/models.py` | 0.1 | 1h |
| 0.3 | X11 下 XFixes 监听文本复制 | `src/monitor/clipboard_monitor.py` `src/monitor/types.py` | 0.2 | 1.5h |
| 0.4 | 最小 GUI: QListWidget 展示历史 | `src/ui/main_window.py` `src/ui/history_list.py` | 0.3 | 1.5h |
| 0.5 | 点击条目 → 写回系统剪切板 | `main_window.py` (集成) | 0.4 | 0.5h |

### 验收标准

```
1. 启动 ./main.py，提示"正在监听剪切板…"
2. 在其他应用 Ctrl+C 复制任意文本
3. Paste 窗口显示新条目，包含内容摘要和时间
4. 点击该条目 → 在任意位置 Ctrl+V 可粘贴此内容
5. 复制不同的文本，列表增量刷新，不重复记录相同内容
```

### 已知障碍

- XFixes 需要系统安装 `python-xlib`。如果编译失败，fallback 到 pyperclip 轮询
- 首次启动需创建 `~/.paste/` 目录和数据库，如果权限有问题需明确提示

---

## Phase 1: 核心功能 (5 天)

**目标：** 完整的基础体验——文本/图片都支持、搜索可用、系统托盘常驻、开机自启配置。

### 1.1 剪切板监听完整版 — XFixes + wl-paste + 回退 (1.5d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 1.1.1 | XFixesMonitor: 增加 MIME 检测与图片读取 | `src/monitor/xfixes_monitor.py` | 3h |
| 1.1.2 | WaylandPasteWatch: wl-paste --watch 文本 + 图片 | `src/monitor/wayland_monitor.py` | 2h |
| 1.1.3 | PollingMonitor: 回退轮询 (纯文本) | `src/monitor/polling_monitor.py` | 1h |
| 1.1.4 | MonitorManager: 根据 session type 自动选择 | `src/monitor/monitor_manager.py` | 1h |
| 1.1.5 | 来源应用识别 (X11: xprop; Wayland: 留空) | `src/utils/app_detector.py` | 2h |

**依赖：** 0.3
**验收：** 在 X11 下监听文本 + 图片；Wayland 下至少监听文本；轮询回退正常工作。

### 1.2 图片处理与存储 (1d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 1.2.1 | 文件管理器: 图片保存 + 目录结构初始化 | `src/storage/file_manager.py` | 1.5h |
| 1.2.2 | 缩略图异步生成 (QThread) | `src/utils/thumbnail.py` | 2h |
| 1.2.3 | 重复图片检测 (dHash 感知哈希) | `src/utils/dedup.py` | 1.5h |

**依赖：** 1.1
**验收：** 复制截图 → 图片保存到 `~/.paste/media/images/` → 缩略图在 `thumbnails/` → 缩略图 200x200 不超过 50KB。

### 1.3 数据库 CRUD + FTS 全文搜索 (1d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 1.3.1 | models.py: CRUD + 分页 + 搜索 API | `src/database/models.py` | 3h |
| 1.3.2 | FTS5 全文搜索集成 (SQLite 原生) | `src/database/search.py` | 2h |
| 1.3.3 | 历史清理策略 (按天数/最大条数) | `src/database/cleanup.py` | 1h |

**依赖：** 0.2
**验收：** 搜索"hello"返回所有包含 hello 的条目；分页每页 50 条；清理任务可手动触发。

### 1.4 UI 主界面完整版 (1.5d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 1.4.1 | 主窗口: 无边框浮动 + 位置记忆 + 自动隐藏 | `src/ui/main_window.py` | 3h |
| 1.4.2 | 历史列表: 图文混合 + 分组按日期 + 键盘导航 | `src/ui/history_list.py` | 4h |
| 1.4.3 | 搜索栏: 300ms debounce 实时搜索 | `src/ui/search_bar.py` | 2h |
| 1.4.4 | 预览面板: 文本渲染 + 图片显示 | `src/ui/preview.py` | 2h |

**依赖：** 1.2, 1.3
**验收：**
- 按 Ctrl+Shift+V 弹出无边框窗口
- 搜索框输入实时过滤列表
- ↑↓ 选择，Enter 复制并关闭窗口
- 失去焦点自动隐藏
- 列表按"今天/昨天/更早"分组

### 1.5 系统托盘 + 开机自启 + 退出逻辑 (0.5d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 1.5.1 | 系统托盘: 图标 + 菜单 (显示/设置/退出) | `src/ui/tray.py` | 1.5h |
| 1.5.2 | 开机自启: 写入 autostart .desktop | `src/utils/autostart.py` | 1h |
| 1.5.3 | 优雅退出: 关闭监听 → 关闭数据库 → 关闭 UI | `src/app.py` (完善) | 0.5h |

**依赖：** 1.4
**验收：** 启动后托盘图标出现；右键菜单工作；关闭主窗口 → 进程驻留托盘；退出 → 图标消失。

---

## Phase 2: 交互完善 (4 天)

### 2.1 全局快捷键 (1d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 2.1.1 | X11 下 XGrabKey 注册 (Ctrl+Shift+V) | `src/utils/hotkey.py` | 2h |
| 2.1.2 | Wayland 下提示用户手动设置 | `src/utils/hotkey.py` (扩展) | 1h |
| 2.1.3 | 快捷键配置: 支持用户自定义修改 | `src/ui/settings/hotkey_editor.py` | 3h |

**依赖：** 1.4
**验收：** X11 下安装后即可用快捷键唤出。Wayland 下按照提示可手动配置成功。

### 2.2 收藏夹 (Pinboards) (1d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 2.2.1 | 收藏夹侧边栏: 树形列表 + 新建/删除/重命名 | `src/ui/pinboard.py` | 3h |
| 2.2.2 | 条目拖拽到收藏夹 | `history_list.py` (拖拽集成) | 2h |
| 2.2.3 | 收藏夹筛选: 仅显示某个收藏夹的内容 | `main_window.py` (筛选逻辑) | 1h |

**依赖：** 1.4
**验收：** 右键条目 → 收藏 → 侧边栏收藏夹出现条目；点击收藏夹 → 只显示该分类内容；拖拽改变分类。

### 2.3 排除规则 (1d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 2.3.1 | 排除规则 CRUD (数据库表 + 模型) | `src/database/models.py` (扩展) | 1h |
| 2.3.2 | 设置界面: 添加/删除排除规则 | `src/ui/settings/exclusion_editor.py` | 2h |
| 2.3.3 | ClipProcessor 集成排除检查 | `src/monitor/clip_processor.py` | 2h |
| 2.3.4 | 默认规则: 密码管理器排除 | `src/monitor/default_rules.py` | 0.5h |

**依赖：** 1.1, 1.4
**验收：** 设置中添加 KeePassXC 排除 → 复制 KeePassXC 中的密码 → Paste 不记录 → 日志记录"已排除"。

### 2.4 设置界面 (1d)

| # | 任务 | 产出 | 工时 |
|---|------|------|------|
| 2.4.1 | 设置对话框 UI 框架 (Tab 切换) | `src/ui/settings/settings_dialog.py` | 2h |
| 2.4.2 | 常规选项卡: 自动启动 / 关闭行为 / 主题 | 同上 (内联) | 1h |
| 2.4.3 | 存储选项卡: 历史保留天数 / 图片大小限制 | 同上 (内联) | 1h |
| 2.4.4 | 关于选项卡: 版本 / 快捷键参考 | 同上 (内联) | 0.5h |

**依赖：** 2.1, 2.2, 2.3
**验收：** 所有配置读写 `~/.paste/config.json`；修改后立即生效。

---

## Phase 3: 兼容性打磨 (5 天)

### 3.1 Wayland 兼容性 (2d)

| # | 任务 | 工时 | 说明 |
|---|------|------|------|
| 3.1.1 | wl-paste 图片监听验证与修复 | 4h | 实测 `wl-paste -t image/png` 在 GNOME + KDE 下行为 |
| 3.1.2 | wl-paste 子进程 watchdog | 2h | 崩溃自动重启 + 告警 |
| 3.1.3 | GNOME AppIndicator 支持 | 2h | 检测是否安装扩展，未安装给出提示 |
| 3.1.4 | Wayland 下来源应用识别（portal） | 4h | 调研 `org.freedesktop.portal` 获取前台窗口 |

### 3.2 性能调优 (1.5d)

| # | 任务 | 工时 | 指标 |
|---|------|------|------|
| 3.2.1 | 数据库写入队列批量处理 | 3h | 单次写入 < 5ms |
| 3.2.2 | 列表懒加载 + 虚拟滚动 | 4h | 万条数据不卡顿 |
| 3.2.3 | 大图片异步读取超时 + 降级 | 2h | > 20MB 图片读取不阻塞 UI |
| 3.2.4 | 内存使用 profiling + 优化 | 3h | Idle 状态 < 80MB |

### 3.3 错误处理与日志 (0.5d)

| # | 任务 | 工时 |
|---|------|------|
| 3.3.1 | logging 框架: 按级别 + 轮转文件 | 1h |
| 3.3.2 | 全局异常捕获 + 崩溃恢复 | 1h |
| 3.3.3 | 用户友好的错误通知 | 1h |

已落地：3.3.1、全局异常 hook、UI hang watchdog、`SIGUSR2` 手动线程堆栈；用户通知仍按具体错误场景逐步补充。

### 3.4 打包分发 (1d)

| # | 任务 | 工时 |
|---|------|------|
| 3.4.1 | PyInstaller spec 编写 + 测试 | 3h |
| 3.4.2 | AppImage 构建脚本 + GitHub Actions | 3h |
| 3.4.3 | .desktop 文件 + 应用图标 + mime 注册 | 2h |

---

## 依赖关系图

```
Phase 0
  └── 0.2 (DB)
        └── 0.3 (Monitor)
              └── 0.4 (UI)
                    └── 0.5 (Write back)
                          │
Phase 1 ──────────────────┘
  ├── 1.1 (Monitor full) ───── 依赖 0.3
  │     └── 1.2 (Image) ────── 依赖 1.1
  │           └── 1.4 (UI) ─── 依赖 1.2 + 1.3
  ├── 1.3 (DB CRUD+FTS) ────── 依赖 0.2
  └── 1.5 (Tray) ───────────── 依赖 1.4
        │
Phase 2 ────────────────────────┘
  ├── 2.1 (Hotkey) ──────────── 依赖 1.4
  ├── 2.2 (Pinboard) ────────── 依赖 1.4
  ├── 2.3 (Exclusion) ───────── 依赖 1.1
  └── 2.4 (Settings) ────────── 依赖 2.1 + 2.2 + 2.3
        │
Phase 3 ────────────────────────┘
  ├── 3.1 (Wayland) ─────────── 依赖 1.1 + 1.5
  ├── 3.2 (Performance) ─────── 依赖 1.4 + 1.3
  ├── 3.3 (Error handling) ──── 依赖 所有
  └── 3.4 (Packaging) ───────── 依赖 所有
```

---

## 关键技术决策与风险

### ✅ 已确认的决策

| 决策 | 结论 | 原因 |
|------|------|------|
| 使用 PySide6 而非 PyQt6 | PySide6 | PyQt6 使用 GPL 许可证，闭源分发需商业授权 |
| 使用 SQLite FTS5 而非 Whoosh | SQLite FTS5 | 少一个依赖，性能足够，触发器自动同步 |
| 使用 SHA256 而非 MD5 做去重 | SHA256 | MD5 有理论碰撞风险，SHA256 开销可忽略 |
| 缩略图格式 JPEG 而非 PNG | JPEG | 缩略图不需要透明通道，JPEG 体积更小 |
| 配置存 JSON 而非 YAML/TOML | JSON | Python 原生支持，无需额外依赖 |

### ❌ 已排除的方案

| 方案 | 排除理由 |
|------|----------|
| Electron/Tauri | 内存 ~200MB+，远超 Qt/Python 方案 |
| Rust + GTK4 | 开发速度慢，代码量 3x，且桌面集成仍依赖系统库 |
| 纯 Wayland 协议 (wl_data_device 直接绑定) | 需要 C 绑定 libwayland-client，跨语言桥接复杂 |
| MongoDB / LevelDB | 为管理 1000 条剪切板历史引入外部数据库，太重 |

### ⚠️ 风险矩阵

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Wayland 全局快捷键无标准方案 | 高 | 高 | Phase 2 时给出系统级配置指引，可接受 |
| wl-paste 对图片支持不完整 | 中 | 中 | X11 下完全支持；Wayland 下走 fallback，记录但不保存图片 |
| PySide6 / python-xlib 在某些发行版打包不完整 | 中 | 中 | AppImage 打包所有依赖；提供 pip 安装指南 |
| GNOME 45+ 移除 AppIndicator 支持 | 低 | 中 | 使用 `gsconnect` / 原生 Notification 作为替代 |
| 数据库在多进程下损坏 | 低 | 高 | 单进程架构，写入加锁，定期 VACUUM，自动备份 |
| 用户复制超大文件（> 1GB）导致 OOM | 低 | 高 | 文件类型只记录路径，不读取内容；图片大小限制的可配置上限 |

---

## 环境准备

### 开发环境

```bash
# 1. Python 版本
python3 --version   # 需要 ≥ 3.10

# 2. 虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装 Python 依赖
pip install PySide6 Pillow python-xlib pyperclip psutil

# 4. 安装系统依赖 (Ubuntu/Debian)
sudo apt install xclip wl-clipboard libxfixes-dev

# 5. 安装系统依赖 (Fedora)
sudo dnf install xclip wl-clipboard libXfixes-devel

# 6. 安装系统依赖 (Arch)
sudo pacman -S xclip wl-clipboard libxfixes
```

### 验证环境

```bash
# 确认 Qt6 可用
python3 -c "from PySide6.QtWidgets import QApplication; print('OK')"

# 确认 Xlib 可用
python3 -c "from Xlib import display; print('OK')"

# 确认 wl-paste 可用 (Wayland 下)
wl-paste --version   # 需要 ≥ 2.0
```

### IDE 配置

推荐 VSCode + 以下扩展：
- Python (ms-python.python)
- Pylance (类型检查)
- Qt for Python (PySide6 智能提示)

---

## 运行方式

### 开发模式 (直接运行)

```bash
cd paste
python src/main.py
```

### 调试模式 (带日志)

```bash
PASTE_DEBUG=1 python src/main.py
# 日志输出到 ~/.paste/logs/paste.log
# UI 卡死线程堆栈输出到 ~/.paste/logs/hang.log
```

复现卡死后收集：

```bash
tail -n 300 ~/.paste/logs/paste.log
tail -n 300 ~/.paste/logs/hang.log

# 进程仍存活时可手动抓取所有线程堆栈
kill -USR2 <paste-pid>
```

### 打包运行

```bash
# PyInstaller
pyinstaller paste.spec
./dist/paste/paste

# AppImage (需要 linuxdeploy)
./build_appimage.sh
./Paste-x86_64.AppImage
```

---

## 测试指南

### 单元测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行某个模块的测试
pytest tests/test_database.py -v
pytest tests/test_dedup.py -v

# 带覆盖率
pytest tests/ --cov=src --cov-report=html
```

### 手动测试场景

执行完每个 Phase 后，运行以下场景验证：

```
场景 1: 基本文本复制
  1. 复制 "Hello World"
  2. 复制 "Foo Bar"
  3. ✅ 列表显示 2 条记录
  4. 搜索 "Hello" → 显示 1 条结果

场景 2: 图片复制
  1. 在浏览器右键复制图片
  2. ✅ 列表显示图片缩略图
  3. 点击缩略图 → 预览大图

场景 3: 去重
  1. 复制 "test"
  2. 再次复制 "test"
  3. ✅ 列表中只有 1 条且时间戳更新
  4. 复制 "test " (尾部多空格)
  5. 如果归一化去重开启 → 更新已有条目的时间
  6. 如果关闭 → 新增一条

场景 4: 排除规则
  1. 设置排除规则: app_name = "gedit"
  2. 在 gedit 中复制文本
  3. ✅ 列表不记录

场景 5: 跨场景 (X11)
  1. 在终端复制 URL
  2. 在浏览器复制图片
  3. 在 IDE 复制代码
  4. ✅ 列表混合展示不同类型
  5. 按类型筛选 → 正确过滤
```

### 兼容性测试矩阵

| 发行版 | 桌面环境 | 显示协议 | 测试状态 |
|--------|----------|----------|----------|
| Ubuntu 24.04 | GNOME 46 | Wayland | 待测试 |
| Ubuntu 24.04 | GNOME 46 | X11 (回退) | 待测试 |
| Fedora 40 | GNOME 46 | Wayland | 待测试 |
| Fedora 40 | KDE Plasma 6 | Wayland | 待测试 |
| Arch Linux | KDE Plasma 6 | Wayland | 待测试 |
| Arch Linux | Sway | Wayland | 待测试 |
| Linux Mint 22 | Cinnamon | X11 | 待测试 |
| Debian 12 | GNOME 43 | X11 | 待测试 |

---

## 代码规范

### 命名约定

```python
# 文件/模块: snake_case
# 类: PascalCase
# 函数/变量: snake_case
# 常量: UPPER_SNAKE_CASE
# 私有: _leading_underscore
# 信号: camelCase (Qt 约定)
```

### 类型提示

所有公共 API 必须标注类型。配置 mypy 严格模式：

```toml
# pyproject.toml
[tool.mypy]
strict = true
python_version = "3.11"
```

### 提交信息规范

```
<type>(<scope>): <description>  # 72 字以内

type: feat | fix | refactor | docs | style | perf | test | chore
scope: db | monitor | ui | tray | hotkey | settings | storage

示例:
feat(monitor): add XFixes clipboard event listener
fix(ui): history list not scrolling to latest item
refactor(db): extract FTS index logic into separate module
```

---

## 产出物清单

### 最终目录结构

```
paste/
├── src/                          # 源代码
│   ├── main.py                   # 入口
│   ├── app.py                    # QApplication 初始化
│   ├── __init__.py
│   │
│   ├── database/                 # 数据持久化
│   │   ├── __init__.py
│   │   ├── db.py                 # 连接管理 + schema
│   │   ├── models.py             # CRUD 操作
│   │   ├── search.py             # FTS5 搜索
│   │   └── cleanup.py            # 过期清理
│   │
│   ├── monitor/                  # 剪切板监听
│   │   ├── __init__.py
│   │   ├── types.py              # ContentType, ClipboardData
│   │   ├── monitor_manager.py    # 自动选择监听器
│   │   ├── xfixes_monitor.py     # X11 事件驱动
│   │   ├── wayland_monitor.py    # Wayland wl-paste
│   │   ├── polling_monitor.py    # 回退轮询
│   │   ├── clip_processor.py     # 类型检测 + 去重 + 排除
│   │   └── default_rules.py      # 默认排除规则
│   │
│   ├── storage/                  # 文件与配置存储
│   │   ├── __init__.py
│   │   ├── file_manager.py       # 图片文件管理
│   │   └── config.py             # 配置读写
│   │
│   ├── ui/                       # 用户界面
│   │   ├── __init__.py
│   │   ├── main_window.py        # 主窗口
│   │   ├── history_list.py       # 历史列表
│   │   ├── search_bar.py         # 搜索框
│   │   ├── preview.py            # 预览面板
│   │   ├── pinboard.py           # 收藏夹侧边栏
│   │   ├── tray.py               # 系统托盘
│   │   └── settings/             # 设置界面
│   │       ├── __init__.py
│   │       ├── settings_dialog.py
│   │       ├── hotkey_editor.py
│   │       └── exclusion_editor.py
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       ├── hotkey.py             # 全局快捷键
│       ├── app_detector.py       # 来源应用识别
│       ├── dedup.py              # 去重算法
│       ├── thumbnail.py          # 缩略图生成
│       └── autostart.py          # 开机自启
│
├── tests/                        # 测试
│   ├── test_database.py
│   ├── test_dedup.py
│   ├── test_clip_processor.py
│   ├── test_config.py
│   └── test_models.py
│
├── resources/                    # 静态资源
│   ├── icons/
│   │   ├── paste.svg             # 应用图标
│   │   ├── paste.png             # 托盘图标
│   │   └── types/                # 类型图标
│   │       ├── text.svg
│   │       ├── image.svg
│   │       ├── link.svg
│   │       └── file.svg
│   └── styles/
│       ├── light.qss             # 亮色主题
│       └── dark.qss              # 暗色主题
│
├── packaging/                    # 打包脚本
│   ├── paste.spec                # PyInstaller spec
│   ├── paste.desktop             # 桌面入口
│   ├── build_appimage.sh         # AppImage 构建
│   └── github-actions.yml        # CI 配置
│
├── docs/                         # 文档
│   ├── architecture.md           # 整体架构
│   └── implementation.md         # 实现计划 (本文档)
│
├── requirements.txt              # Python 依赖
├── pyproject.toml                # 项目元数据 + lint 配置
├── README.md                     # 项目简介
└── AGENTS.md                     # AI 辅助开发规范
```

### 文件计数

| 类别 | 文件数 |
|------|--------|
| Python 源文件 (.py) | ~30 个 |
| QSS 样式表 | 2 个 |
| SVG/PNG 图标 | ~6 个 |
| 打包脚本 | 4 个 |
| 测试 | 5 个 |
| 文档 | 2 个 |
| **总计** | **~49 个文件** |

### 总代码量估计

| 模块 | 预估行数 |
|------|----------|
| monitor/ (监听 + 处理器) | ~600 |
| database/ (DB + 模型 + 搜索) | ~500 |
| ui/ (窗口 + 列表 + 设置) | ~1500 |
| utils/ (快捷键 + 去重 + 缩略图) | ~400 |
| storage/ (文件 + 配置) | ~200 |
| tests/ | ~500 |
| **总计** | **~3700 行 Python** |

---

## 附：打包命令速查

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
python src/main.py

# 测试
pytest tests/ -v

# 类型检查
mypy src/

# Lint
ruff check src/
ruff format src/

# 打包 AppImage
bash packaging/build_appimage.sh

# 打包 deb
dpkg-deb --build packaging/deb paste_1.0_amd64.deb
```

---

*最后更新: 2026-07-13*
*文档版本: v2.0*
