# Paste — Linux 剪切板管理器 · 架构设计文档

## 1. 概述

Paste 是一款运行在 Linux 桌面环境下的剪切板管理器，对标 macOS 上的 [PasteApp](https://pasteapp.io/)。核心价值：**自动记录每次复制操作的内容，让用户随时搜索、回顾、重用历史剪切板数据**。

本项目为纯本地版本，不依赖任何云端服务或用户账户。所有数据存储在用户家目录下的 `~/.paste/` 内。

---

## 2. 需求目标

| 需求 | 描述 | 优先级 |
|------|------|--------|
| 剪切板历史记录 | 自动捕获文本和图片的复制操作，按时间倒序呈现 | P0 |
| 搜索 | 对历史内容进行全文搜索，支持模糊匹配 | P0 |
| 再次复制 | 点击历史条目即可将其重新写入系统剪切板 | P0 |
| 系统托盘 | 后台常驻，托盘图标 + 右键菜单 | P0 |
| 全局快捷键 | 一键唤出主窗口，不打断当前工作流 | P0 |
| 图片预览 | 对历史中的图片生成缩略图并预览 | P1 |
| 收藏夹 (Pinboards) | 用户自定义分类，将常用条目固定到收藏夹 | P1 |
| 排除规则 | 按应用名或内容模式过滤，不记录敏感数据 | P1 |
| 纯文本粘贴 | 忽略原格式，仅粘贴纯文本 | P2 |
| 导出/导入 | JSON 格式的完整历史备份与恢复 | P2 |
| 多主题 | 亮色/暗色/跟随系统 | P2 |

> **不包含：** 跨设备 iCloud 同步、Siri 快捷键、iOS 键盘扩展（这些是 PasteApp 的 macOS/iOS 专属功能，Linux 下无对应生态）。

---

## 3. 语言与运行时

### 3.1 为什么是 Python？

| 对比项 | Python 3.11+ | Rust | Go | Electron (TS/JS) |
|--------|-------------|------|----|-------------------|
| GUI 生态 | PySide6/PyQt6（稳定成熟） | GTK4-rs / egui（生态较弱） | 无成熟原生 GUI | 最强，但太重 |
| 剪切板 API | xclip/wl-clipboard 生态完善 | x11rb / wayland-client 较复杂 | clipboard 库较新 | 有 clipboard API |
| 开发速度 | 快 | 慢 | 中 | 快 |
| 运行时体积 | ~15MB + 需 Python 解释器 | 单个静态二进制 ~5MB | 单个二进制 ~10MB | ~100-200MB 含 Chromium |
| 内存基线 | ~30MB (解释器) | ~5MB | ~8MB | ~120MB |
| 桌面集成 | Qt 系统托盘完美支持 | 需要额外绑定 | 较弱 | 托盘支持但耗电 |
| 社区维护 | 开源项目多，参考多 | 少 | 少 | 非常多 |

Python 的缺点（在桌面应用场景下）也明确：
- 不支持静态编译为单二进制，PyInstaller 打包后解压体积约 60MB+
- GIL 限制，图片缩略图批量处理时需要开多进程
- 用户系统需要预装 Python/PySide6 或依赖打包后的虚拟环境

**结论：** 综合开发速度、生态成熟度、调试便利性，Python 是当前最务实的选择。若将来有性能瓶颈，核心模块（缩略图生成、全文搜索）可抽离为 Rust/C 扩展。

### 3.2 Python 版本要求

- **最低：** Python 3.10+（需要 `match` 语句和 `zoneinfo`）
- **推荐：** Python 3.11 / 3.12
- **包管理器：** `pip` 或 `poetry`

### 3.3 核心依赖

| 依赖 | 版本 | 用途 | 替代方案 |
|------|------|------|----------|
| `PySide6` | ≥ 6.5 | Qt6 绑定：GUI、系统托盘、信号机制 | PyQt6（GPL 许可证） |
| `Pillow` | ≥ 10.0 | 图片处理、缩略图生成 | — |
| `Xlib` | ≥ 0.29 | X11 Clipboard 事件监听 (XFixes) | python-xlib |
| `pyperclip` | ≥ 1.8 | 跨桌面环境剪切板读写回退 | xclip / wl-clipboard CLI |
| `psutil` | ≥ 5.9 | 获取当前活跃窗口所在应用名 | xprop |

### 3.4 系统依赖 (需用户额外安装)

| 包名 | 安装方式 | 用途 |
|------|----------|------|
| `xclip` 或 `wl-clipboard` | 系统包管理器 | 剪切板读写（Python 包底层依赖） |
| `python3-pyqt6` / `python3-pyside6` | 部分发行版可直接安装 | Qt6 绑定 |
| `libxfixes-dev` | 编译 Xlib 依赖 | XFixes 扩展支持 |
| `libnotify` | 系统包管理器 | 桌面通知 |

---

## 4. 运行环境兼容性

### 4.1 桌面环境 (DE)

| 桌面环境 | 支持情况 | 注意事项 |
|----------|----------|----------|
| GNOME (Wayland) | ✅ 完整支持 | wl-paste --watch 监听，GTK 系统托盘需 AppIndicator 扩展 |
| KDE Plasma (Wayland) | ✅ 完整支持 | 系统托盘原生支持 |
| Xfce (X11) | ✅ 完整支持 | XFixes 事件监听，托盘原生支持 |
| i3 / Sway (WM) | ✅ 支持 | Sway 原生支持 wl-paste；i3/X11 使用 XFixes |
| Budgie / Cinnamon | ✅ 支持 | 均可正常工作 |
| Weston / River | ⚠️ 需验证 | 缺少成熟的系统托盘规范 |

### 4.2 X11 vs Wayland

这是本项目的核心兼容性挑战。两套协议在剪切板实现上差异很大：

| 特性 | X11 | Wayland |
|------|-----|---------|
| 剪切板模型 | 被动读取（IPC 到持有者进程） | 安全沙箱，仅前台应用可读 |
| 监听机制 | XFixes: `SelectionNotify` 事件 | `wl_data_device` 事件，通过 `wl-paste --watch` |
| 读取大图片 | 每次读取都 IPC 传输，复制浏览器图片时延迟明显 | 同左，但 Wayland 安全策略更严格 |
| 获取来源 App | `_NET_WM_PID` 窗口属性 | `xdg-foreign` / 套接字凭据（不通用） |
| 托盘图标 | 标准 `_NET_SYSTEM_TRAY` | 需要 `StatusNotifierItem` 规范；GTK 不支持原生，需 AppIndicator |
| 全局快捷键 | XGrabKey / keybinder | `zwp_keyboard_shortcuts_inhibit_v1` / 需 portal 或 DE 支持 |

**核心矛盾：** Wayland 的"安全设计"对剪切板管理器这种需要"后台读取全部复制内容"的应用极其不友好。用户每次切换到 Paste 窗口时才能读取剪切板，这在 Wayland 安全模型下是强制的。

**应对策略 (WAYLAND 关键问题)：**
- 监听方式：使用 `wl-paste --watch`（wg-clipboard 包提供），在子进程标准输出中实时接收剪切板数据
- 读取时机：只能在获得焦点时读取。监听方案可以绕过——`wl-paste --watch` 在数据可用时主动推送
- 托盘图标：在 KDE Plasma 下原生支持；GNOME 需安装 `gnome-shell-extension-appindicator`
- 全局快捷键：GNOME 下只能用自定义快捷键调用脚本；KDE 支持 `kglobalaccel`

**检测策略：**

```python
import os
desktop = os.environ.get('XDG_SESSION_TYPE', 'x11')  # 'x11' | 'wayland' | 'tty'
```

### 4.3 其他潜在限制

- 在 Flatpak/Snap 容器化应用中运行，需要对宿主 D-Bus 和剪切板的访问权限（通常受限）
- Wayland 下远程桌面 (RDP/VNC) 会话中剪切板监听可能失效
- `sudo` 或特权应用复制的内容可能无法被普通用户读取

---

## 5. 技术架构

### 5.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户操作层                                │
│    Ctrl+C (复制)    Ctrl+Shift+V (唤出)   托盘左键 (唤出)        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         事件监听层                               │
│  ┌─────────────────────┐    ┌───────────────────────────────┐   │
│  │ ClipboardMonitor     │    │ GlobalHotkeyManager          │   │
│  │  ├ XFixes (X11)     │    │  ├ X11: XGrabKey             │   │
│  │  ├ wl-paste --watch │    │  ├ Wayland: 桌面级快捷键配置 │   │
│  │  └ QTimer (回退)    │    │  └ Qt: QShortcut (应用内)    │   │
│  └─────────┬───────────┘    └───────────────────────────────┘   │
└─────────────┼────────────────────────────────────────────────────┘
              │ 信号：on_clipboard_changed(type, data)
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         处理层                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ ClipProcessor                                            │    │
│  │  ① 类型检测 (text/image/file) + 去重 (SHA256 fingerprint) │   │
│  │  ② 排除规则过滤                                           │    │
│  │  ③ 图片→保存文件→生成缩略图                                │    │
│  │  ④ 写入数据库 (异步队列) + 更新 FTS 索引                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         数据存储层                               │
│  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐  │
│  │ SQLite:      │  │ 文件系统:      │  │ Whoosh (可选):       │  │
│  │ paste.db     │  │ media/images/ │  │ 全文搜索索引         │  │
│  │ entries      │  │ media/thumb/  │  │ (或直接用 SQLite FTS5)│  │
│  │ pinboards    │  │ export/       │  └──────────────────────┘  │
│  └──────┬───────┘  └───────────────┘                            │
└─────────┼────────────────────────────────────────────────────────┘
          │ 变更信号
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                         UI 层 (PySide6)                         │
│  ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ 主窗口      │ │ 历史列表   │ │搜索栏    │ │ 预览面板      │  │
│  │ (无边浮动) │ │ (图/文混合) │ │(实时过滤)│ │ (文本渲染/   │  │
│  │            │ │            │ │          │ │  图片显示)    │  │
│  └────────────┘ └────────────┘ └──────────┘ └──────────────┘  │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐               │
│  │ 收藏夹面板  │ │ 设置对话框  │ │ 系统托盘      │               │
│  │ (树形分类)  │ │ (排除/保留)│ │ (QSystemTray) │               │
│  └────────────┘ └────────────┘ └──────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 进程模型

```
┌─────────────────────────────────────┐
│         主进程 (main.py)             │
│  PID 1: 整个应用               │
│  ├─ QApplication (事件循环)         │
│  ├─ UIController (UI 管理器)        │
│  │  ├─ TrayManager                 │
│  │  ├─ MainWindow (延迟加载)        │
│  │  └─ SettingsDialog             │
│  ├─ ClipboardMonitor (子线程)       │
│  │  └─ 事件 → main 线程信号        │
│  ├─ DatabaseManager (单例)          │
│  └─ HotkeyManager                  │
│                                     │
│  子进程 (按需)：                     │
│  ├─ wl-paste --watch (Wayland 监听) │
│  └─ thumbnail_generator (批量缩略图)│
└─────────────────────────────────────┘
```

**线程模型说明：**
- **UI 线程（主线程）：** 所有 PySide6 操作只能在主线程
- **工作线程：** ClipboardMonitor 本身不需要单独线程（它是事件驱动的），但图片保存和缩略图生成应放到后台线程 (`QThread`) 以避免 UI 卡顿
- **数据库访问：** SQLite 在单线程模式下访问，写入操作通过信号队列串行化

### 5.3 数据流

```
【复制触发】
用户 Ctrl+C
   ↓
系统剪切板更新
   ↓
ClipboardMonitor 收到通知 (XFixes / wl-paste)
   ↓
ClipProcessor.detect_content_type()
   ├── MIME 检测 → 'text/plain' | 'image/png' | 'text/uri-list' | ...
   ├── 文本 → 检查是否为 URL 链接 → 'text' | 'link'
   └── 文件 → 检查 URI 协议 → 'file'
   ↓
ClipProcessor.is_duplicate()
   ├── 计算 SHA256(data)
   ├── 查数据库最近 N 条记录
   └── 重复 → 丢弃 (更新当前条目的时间戳)
   ↓
ClipProcessor.check_exclusion_rules()
   ├── 获取当前前台窗口应用名 (psutil / xprop)
   └── 匹配排除表 → 丢弃
   ↓
ClipProcessor.save()
   ├── TEXT/LINK → 直接写入数据库
   ├── IMAGE → 保存 PNG → 生成缩略图 → 写入数据库
   └── FILE → 记录路径 → 写入数据库
   ↓
信号 → UI 历史列表增量刷新

【用户操作】
搜索 → SQLite FTS5 全文索引 → 结果列表
点击条目 → 预览加载 → 重新写入系统剪切板
收藏 → 更新数据库 pinned=1 或 pinboard_id
删除 → 软删除 / 硬删除（图片文件保留在磁盘）
```

---

## 6. 详细模块设计

### 6.1 数据库层 (`database/`)

#### 6.1.1 表结构

```sql
PRAGMA journal_mode = WAL;           -- 写入性能优化
PRAGMA foreign_keys = ON;

-- 主条目表
CREATE TABLE IF NOT EXISTS entries (
    id            TEXT PRIMARY KEY,               -- UUID v4
    type          TEXT NOT NULL CHECK(type IN (
                    'text', 'image', 'file', 'link'
                  )),
    content       TEXT NOT NULL,                  -- 文本内容 / 绝对路径 / URL
    plain_text    TEXT,                           -- 纯文本剥离版本（用于搜索）
    mime_type     TEXT,                           -- 原始 MIME，如 'image/png'
    thumbnail_path TEXT,                          -- 缩略图相对路径
    source_app    TEXT,                           -- 来源应用可执行文件名
    window_title  TEXT,                           -- 来源窗口标题
    fingerprint   TEXT NOT NULL,                  -- SHA256(data) 用于去重
    pinned        INTEGER NOT NULL DEFAULT 0,     -- 0: 未收藏  1: 收藏
    pinboard_id   TEXT REFERENCES pinboards(id) ON DELETE SET NULL,
    byte_size     INTEGER,                        -- 数据大小 (bytes)
    created_at    TEXT NOT NULL,                  -- ISO 8601 (UTC)
    updated_at    TEXT NOT NULL DEFAULT '',       -- 上次被复制/操作的时间
    is_deleted    INTEGER NOT NULL DEFAULT 0      -- 软删除标记
);

CREATE INDEX idx_entries_created ON entries(created_at DESC);
CREATE INDEX idx_entries_type ON entries(type);
CREATE INDEX idx_entries_pinned ON entries(pinned);
CREATE INDEX idx_entries_fingerprint ON entries(fingerprint);

-- 收藏夹表
CREATE TABLE IF NOT EXISTS pinboards (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    icon        TEXT DEFAULT 'folder',            -- 图标名称
    sort_order  INTEGER NOT NULL DEFAULT 0,       -- 排序权重
    created_at  TEXT NOT NULL
);

-- 排除规则表
CREATE TABLE IF NOT EXISTS exclusion_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type   TEXT NOT NULL CHECK(rule_type IN (
                  'app_name', 'window_title', 'content_pattern'
                )),
    pattern     TEXT NOT NULL,                    -- 应用名 / 窗口标题关键词 / regex
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

-- 配置表（KV 存储）
CREATE TABLE IF NOT EXISTS config (
    key         TEXT PRIMARY KEY,
    value       TEXT
);

-- FTS5 全文搜索虚拟表
CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    content,
    plain_text,
    source_app,
    content='entries',
    content_rowid='rowid'
);

-- 触发器保持 FTS 同步
CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, content, plain_text, source_app)
    VALUES (new.rowid, new.content, new.plain_text, new.source_app);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, content, plain_text, source_app)
    VALUES ('delete', old.rowid, old.content, old.plain_text, old.source_app);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, content, plain_text, source_app)
    VALUES ('delete', old.rowid, old.content, old.plain_text, old.source_app);
    INSERT INTO entries_fts(rowid, content, plain_text, source_app)
    VALUES (new.rowid, new.content, new.plain_text, new.source_app);
END;
```

#### 6.1.2 数据库连接管理

```python
# database/db.py  — 线程安全的单例

import sqlite3, threading, os, uuid
from datetime import datetime, timezone

DB_PATH = os.path.expanduser('~/.paste/paste.db')

class DatabaseManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.conn = sqlite3.connect(
            DB_PATH, check_same_thread=False
        )
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.Lock()
        self._init_schema()

    def execute(self, sql, params=()):
        with self._lock:           # 保证写入线程安全
            return self.conn.execute(sql, params)

    def fetchall(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def fetchone(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()
```

**注意：** Python 的 `sqlite3` 模块默认不支持并发写入。这里用 `threading.Lock` + WAL 模式来解决多线程安全，但需要确保锁粒度足够细，不阻塞长时间查询。

#### 6.1.3 序列化

条目在数据库和 Python 对象之间的映射：

```python
@dataclass
class ClipboardEntry:
    id: str
    type: Literal['text', 'image', 'file', 'link']
    content: str
    plain_text: str | None
    mime_type: str | None
    thumbnail_path: str | None
    source_app: str | None
    window_title: str | None
    fingerprint: str
    pinned: bool
    pinboard_id: str | None
    byte_size: int
    created_at: datetime
    updated_at: datetime
```

### 6.2 剪切板监听层 (`monitor/`)

#### 6.2.1 核心策略：事件驱动 + 回退轮询

```
detect_session_type()
       │
       ├── "x11"       → XFixesMonitor (优先级1)
       │                   ├ 监听 SelectionNotify
       │                   └ 收到事件后读取内容
       │
       ├── "wayland"   → WaylandPasteWatch (优先级1)
       │                   ├ 子进程: wl-paste --watch
       │                   ├ 从 stdout 实时接收数据
       │                   └ 管道断裂时自动重启
       │
       └── "tty" / 未知 → PollingMonitor (回退)
                          ├ QTimer 每 1000ms
                          ├ 读取 clipboard → 比对 fingerprint
                          └ 有变化 → 触发保存
```

#### 6.2.2 XFixes 实现 (X11)

```python
# monitor/xfixes_monitor.py
from Xlib import display, X, XFixes
from Xlib.ext import xfixes

class XFixesMonitor(QObject):
    changed = Signal(str, bytes, str)  # mime_type, data, source_app

    def __init__(self):
        super().__init__()
        self.disp = display.Display()
        self.screen = self.disp.screen()
        self.window = self.screen.root.create_window(
            -1, -1, 1, 1, 0, self.screen.root_depth
        )
        # 订阅剪切板所有者变更事件
        XFixes.select_selection_input(
            self.disp, self.window,
            self.disp.get_atom('CLIPBOARD'),
            XFixes.XFixesSetSelectionOwnerNotifyMask
        )
        self.disp.flush()

    def poll(self):
        """在主线程 QTimer 中调用，非阻塞检查事件"""
        while self.disp.pending_events():
            event = self.disp.next_event()
            if event.type == self.disp.get_extension_data(
                xfixes.get_extension_data(self.disp)[0]
            ):
                self._on_selection_changed()

    def _on_selection_changed(self):
        # 通过 xclip / 直接 X11 API 读取 clipboard
        data, mime = read_clipboard_x11(self.disp)
        if data and not self.is_duplicate(data):
            app = get_active_window_app_x11(self.disp)
            self.changed.emit(mime, data, app or '')
```

**已知问题：**
- XFixes 只通知"所有者变更"，不通知"内容是否真正变化"。同一个应用连续复制相同内容会产生多次 `SelectionNotify`，需要额外去重
- 某些应用（如 Firefox）在选中文本时会短暂持有 PRIMARY 选择，可能产生冗余事件
- 需要在主线程事件循环中轮询 `pending_events()`，不能阻塞

#### 6.2.3 Wayland wl-paste 方案

```python
# monitor/wayland_monitor.py
import subprocess, threading

class WaylandPasteWatch(QObject):
    changed = Signal(str, bytes, str)

    def __init__(self):
        super().__init__()
        self._process = None

    def start(self):
        """启动 wl-paste --watch 子进程 (仅支持文本 + 图片)"""
        def _run():
            self._process = subprocess.Popen(
                ['wl-paste', '--watch', '--', 'wl-paste', '--type', 'text/plain'],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
            for line in iter(self._process.stdout.readline, b''):
                text = line.decode('utf-8', errors='replace').rstrip('\n')
                self.changed.emit('text/plain', text.encode(), '')
        threading.Thread(target=_run, daemon=True).start()

    def stop(self):
        if self._process:
            self._process.terminate()
```

**已知问题：**
- `wl-paste --watch` 对图片支持较弱，需要额外调用 `wl-paste --type image/png`
- 子进程可能因 Wayland 协议断开而崩溃，需要自动重启机制
- `wl-paste` 工具本身可能有性能瓶颈（大数据量时）

#### 6.2.4 回退轮询

```python
# monitor/polling_monitor.py
from PySide6.QtCore import QTimer

class PollingMonitor(QObject):
    changed = Signal(str, bytes, str)

    def __init__(self, interval_ms=1000):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self._check)
        self.timer.start(interval_ms)
        self._last_fingerprint = None

    def _check(self):
        data = read_clipboard_fallback()  # pyperclip
        if not data:
            return
        fp = hashlib.sha256(data).hexdigest()
        if fp != self._last_fingerprint:
            self._last_fingerprint = fp
            self.changed.emit('text/plain', data, '')
```

**缺点：** 只支持文本，不支持图片。图片读取需要额外的 `xclip -selection clipboard -t image/png -o`，且在 Wayland 下不可靠。

### 6.3 去重策略 (`utils/dedup.py`)

去重是一个比预期更复杂的问题。需要做**多重维度**的去重：

| 维度 | 方法 | 适用场景 |
|------|------|----------|
| 精确内容 | SHA256(data) = 最近 N 条中有相同指纹 | 完全相同的内容 |
| 文本归一化 | 去前后空白、统一换行符后再算 SHA256 | 编辑器自动加换行 |
| 渐进式去重 | 同应用 + 同类型 + 时间 < 3s → 认为是重复 | 连续误触 Ctrl+C |
| 图片模糊去重 | dHash + 汉明距离 < 10 | 相同图片截图压缩级别不同 |

**去重不应该是"拒绝写入"，而应该是"更新已存在条目的时间戳"**——用户可能想保留最新一次复制的时间上下文。

### 6.4 获取来源应用

这是已知的困难问题之一，各方案均有局限：

| 方案 | 工作方式 | X11 | Wayland | 准确度 |
|------|----------|-----|---------|--------|
| `xprop -id $(xdotool getactivewindow) \| grep _NET_WM_PID` | 读取窗口 PID → /proc/PID/comm | ✅ | ❌ | 高 |
| `psutil.Process(PID).name()` | 同上，Python 封装 | ✅ | ❌ | 高 |
| `gdbus call --session` 获取焦点窗口 | D-Bus 调用 | ✅ | ✅ | 中 |
| `wl-paste --watch` 配合 `swaymsg` | i3/Sway IPC | ❌ | 仅 Sway | 中 |
| 监听剪贴板时记录前台窗口 | 事件发生时快照 | ✅ | 部分 | 中 |

**结论：** X11 下通过 `xprop` 获取准确。Wayland 下没有标准 API，GNOME 通过 D-Bus 可获取，KDE 通过 `KWindowSystem`，但都不是通用方案。

### 6.5 UI 层 (`ui/`)

#### 6.5.1 主窗口设计

主窗口是一个**无边框、半透明、浮动**的弹窗，类似 macOS Spotlight 或 Albert：

```
┌────────────────────────────────────────────────────────────┐
│  🔍  搜索剪切板...                                      ⚙️ ✕ │
├────────────────────────────────────────────────────────────┤
│ ┌──────────┐  ┌─────────────────────────────────────────┐  │
│ │ 📋 全部   │  │  条目 1: 文本片段                        │  │
│ │ 🔖 收藏   │  │  ─────────────────────────────────      │  │
│ │ 📝 文本   │  │  条目 2: 图片缩略图 [🖼]                 │  │
│ │ 🖼️ 图片   │  │  ─────────────────────────────────      │  │
│ │ 📎 文件   │  │  条目 3: 链接 https://...               │  │
│ │           │  │  ─────────────────────────────────      │  │
│ │ ───────── │  │  条目 4: 代码片段 (语法高亮)            │  │
│ │ 📁 收藏夹1 │  │  ─────────────────────────────────      │  │
│ │ 📁 收藏夹2 │  │  条目 5: 图片 [🖼]                     │  │
│ │ 📁 + 新建 │  │  ─────────────────────────────────      │  │
│ └──────────┘  └─────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

**交互细节：**
- 窗口默认居中屏幕，自适应宽度（最多 800px）
- 失去焦点时自动隐藏（类似 Spotlight 行为）
- 支持键盘导航（↑↓ 选择，Enter 复制并粘贴，Ctrl+C 复制）
- 预览在右侧面板或点击展开
- 每条记录显示：图标(类型) + 内容摘要(单行) + 时间(相对时间如"2 分钟前")

#### 6.5.2 条目渲染

不同类型在列表中的展现：

| 类型 | 图标 | 内容摘要 | 预览行为 |
|------|------|----------|----------|
| text | 📝 | 前 120 字符 + 尾部省略 | 等宽字体全文展示 |
| link | 🔗 | URL 域名 + 路径 | 可点击打开浏览器 |
| image | 🖼️ | 文件名 / 缩略图 | 缩略图 → 点击大图 |
| file | 📎 | 文件名 + 扩展名图标 | 显示路径，双击打开 |

#### 6.5.3 系统托盘

当前交互：

- 左键 `Trigger`：动态查询并弹出最近 5 条记录；选择后写回系统剪切板。
- 右键 `Context`：显示/隐藏主窗口、配置热键、Recent 备用子菜单和退出。
- 菜单及 `QAction` 必须保存为 `TrayManager` 实例成员并设置父对象，防止 PySide 回收后菜单只剩分隔线。
- 每次激活记录 `ActivationReason`，用于判断桌面 Shell 实际送达的是左键还是右键事件。

Qt 能在支持完整托盘协议的桌面区分 `Trigger` 与 `Context`。但 GNOME 的 AppIndicator/StatusNotifier 扩展可能把主键和右键统一映射到上下文菜单，应用无法绕过 Shell 强制拆分。因此右键菜单同时提供 Recent 子菜单作为兼容回退。KDE/X11 等能提供 `Trigger` 的环境仍保持左右键不同功能。

#### 6.5.4 删除与内容筛选

- 每条历史记录提供删除按钮，使用软删除 `is_deleted=1`，删除后立即刷新当前搜索和类型筛选。
- 标题栏提供“Clear All”，二次确认后软删除全部历史；媒体文件仍由存储清理任务统一回收。
- 主列表提供 `All / URLs / Images` 三个筛选栏目。URLs 不只依赖历史 `type='link'`，还通过 SQLite 自定义函数识别正文中的 `http/https/ftp/www/常见域名`，兼容过去误存为 `text` 的地址内容。
- 搜索关键词与类型筛选可以组合，数据库查询同时应用 `LIKE` 条件和 `entry_type` 条件。
- 删除或清空后清除进程内短期去重缓存，允许用户再次复制相同内容。

### 6.6 存储与文件管理 (`storage/`)

#### 6.6.1 目录布局

```
~/.paste/
├── paste.db              # SQLite 数据库 (含 FTS 索引)
├── config.json           # 用户配置 (也存于 DB config 表作为镜像)
├── media/
│   ├── images/           # 原始图片 UUID.png / UUID.jpg
│   ├── thumbnails/       # 缩略图 UUID_thumb.jpg (200x200)
│   └── files/            # (预留) 用户主动保存的文件副本
├── export/               # 导出备份目录
└── logs/                 # 日志文件 (滚动写入)
```

#### 6.6.2 文件存储策略

```python
IMAGE_DIR = Path("~/.paste/media/images").expanduser()
THUMB_DIR = Path("~/.paste/media/thumbnails").expanduser()

def save_image(data: bytes) -> tuple[str, str, str]:
    """
    保存图片文件
    返回: (uuid_hex, image_path, thumbnail_path)
    """
    uid = uuid.uuid4().hex
    img_path = IMAGE_DIR / f"{uid}.png"
    thumb_path = THUMB_DIR / f"{uid}_thumb.jpg"

    # 保存原图
    img_path.write_bytes(data)

    # 生成缩略图 (Pillow)
    with Image.open(io.BytesIO(data)) as img:
        img.thumbnail((200, 200), Image.Lanczos)
        img.convert('RGB').save(thumb_path, 'JPEG', quality=85)

    return uid, str(img_path), str(thumb_path)
```

**大图片处理：** 如果图片 > 50MB（如截图工具生成的大 PNG），保存和缩略图都在后台 QThread 中进行，UI 列表先显示"加载中"占位。

### 6.7 全局快捷键 (`utils/hotkey.py`)

这是另一个跨桌面环境的痛点：

| 方案 | X11 | Wayland | 说明 |
|------|-----|---------|------|
| python-xlib + XGrabKey | ✅ | ❌ | 经典方案，Wayland 不支持 |
| QHotkey (qthotkey) | ✅ | ⚠️ 部分 | 底层也使用 XGrabKey / evdev |
| keybinder3 (GTK) | ✅ | ❌ | GTK 绑定，但只支持 X11 |
| 桌面系统级别设置 | ✅ | ✅ | 用户在系统设置中绑定快捷键 → 调用脚本 |

**推荐方案：**

```python
# utils/hotkey.py
from PySide6.QtCore import QObject, Signal
import platform

class HotkeyManager(QObject):
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        desktop = os.environ.get('XDG_SESSION_TYPE', 'x11')

    def register(self, key='Ctrl+Shift+V'):
        if self._desktop == 'x11':
            # 使用 python-xlib XGrabKey (全局)
            self._register_x11(key)
        else:
            # Wayland: 无法注册全局快捷键
            # 提示用户在桌面系统设置中手动配置
            QMessageBox.information(
                None, "快捷键设置",
                "在 Wayland 下请到系统设置中为 Paste 绑定快捷键：\n"
                f"设置 → 键盘 → 自定义快捷键 → 添加 → 命令: {sys.argv[0]}"
            )
```

**现状：** Wayland 下全局快捷键无标准 API。这是已知的未解决问题，需要用户手动在 GNOME/KDE 设置中配置。

---

## 7. 配置系统

配置文件 `~/.paste/config.json`：

```json
{
  "appearance": {
    "theme": "system",
    "max_width": 800,
    "show_thumbnail": true
  },
  "clipboard": {
    "max_history": 1000,
    "max_days": 30,
    "watch_images": true,
    "watch_files": false,
    "dedup_exact": true,
    "dedup_normalize": true,
    "dedup_interval_ms": 3000
  },
  "hotkeys": {
    "toggle_window": "Ctrl+Shift+V",
    "paste_previous": "Ctrl+Shift+P"
  },
  "storage": {
    "media_limit_mb": 2000,
    "auto_clean_days": 30
  },
  "behavior": {
    "auto_start": true,
    "close_to_tray": true,
    "hide_on_focus_lost": true
  },
  "exclusions": [
    {"type": "app_name", "pattern": "keepassxc"},
    {"type": "app_name", "pattern": "1password"},
    {"type": "content_pattern", "pattern": "^password.*"}
  ]
}
```

---

## 8. 错误处理与异常策略

| 异常场景 | 处理方式 |
|----------|----------|
| 数据库损坏 | 自动备份 `paste.db.corrupted.{timestamp}` → 重建空数据库 |
| 磁盘空间不足 | 写入失败 → 通知用户 → 自动清理最旧条目 |
| 图片文件写入失败 | 跳过图片保存，仅记录文本信息 → 下次复制时重试 |
| wl-paste 子进程崩溃 | 自动重启，最多 3 次/分钟，超过则切回轮询模式 |
| XFixes 连接断开 | 重新连接 Display，恢复事件监听 |
| 权限不足 | 提示用户检查 ~/.paste/ 目录权限 |
| 大文件卡住 (> 100MB) | 设置超时 5s → 取消读取 → 跳过该条目 |
| UI 事件循环卡死 | 8 秒无心跳时由后台 watchdog 把所有线程堆栈写入 `~/.paste/logs/hang.log` |
| 未捕获异常 | `sys.excepthook` / `threading.excepthook` 记录完整 traceback |
| 日志增长 | `paste.log` 单文件 5MB，保留 5 个轮转备份 |

运行日志位于 `~/.paste/logs/paste.log`，记录启动、托盘激活原因、窗口 show/hide、列表刷新耗时、筛选、删除和清空操作。日志只记录记录 ID、类型、数量和耗时，不记录剪切板正文。Linux 下可向进程发送 `SIGUSR2`，主动把所有线程堆栈写入 `hang.log`。

---

## 9. 安全注意事项

1. **敏感数据过滤：** 默认排除密码管理器 (KeePassXC, Bitwarden, 1Password) 的复制操作。检测方式：来源应用名匹配 + 内容正则匹配 `(?i)^(password|secret|token)`
2. **数据本地存储：** 所有数据在 `~/.paste/`，文件权限建议 `0700`
3. **不记录密码字段：** HTML 表单中 `type=password` 对应的文本通过内容分析可部分识别
4. **清理策略：** 默认自动清理 30 天前的非收藏条目；“Clear All”软删除数据库历史，媒体文件由后续存储清理任务回收
5. **启动时不自启：** 用户主动选择"开机启动"后才写入 autostart `.desktop` 文件

---

## 10. 已知问题与风险 (Open Issues)

### P0 - 必须解决

| 问题 | 描述 | 影响范围 | 当前状态 |
|------|------|----------|----------|
| Wayland 全局快捷键 | Wayland 协议不允许第三方应用注册全局快捷键 | 所有 Wayland 用户 | **未解决**。需用户手动在 DE 设置中配置 |
| Wayland 托盘图标 | GNOME 下需要 AppIndicator 扩展 | GNOME Wayland 用户 | **未解决**。需安装扩展 |
| 大图片读取性能 | 读取 > 20MB 图片时 QClipboard/image 操作可能卡顿数秒 | 频繁复制截图用户 | **待优化**。需异步读取 + 超时机制 |
| 来源应用识别 (Wayland) | Wayland 无标准 API 获取焦点窗口 PID | Wayland 下 `source_app` 字段为空 | **未解决**。正在调研 `org.freedesktop.portal` 方案 |

### P1 - 重要

| 问题 | 描述 | 影响范围 | 当前状态 |
|------|------|----------|----------|
| Flatpak 限制 | Flatpak 沙箱隔离导致无法访问宿主剪切板 | Flatpak 用户 | **未解决**。需在 Flatpak 清单中授予 `--socket=x11` `--talk-name=org.freedesktop.portal.*` |
| 多显示器位置记忆 | 主窗口应在当前活跃显示器上弹出 | 多屏用户 | **未解决**。需通过 `QScreen` API 检测 |
| Firefox 冗余事件 | X11 下 Firefox 选中文本会同时更新 PRIMARY 和 CLIPBOARD，产生 2 次事件 | X11 / Firefox 用户 | **待处理**。需丢弃 PRIMARY 选择事件 |
| 深色/浅色主题切换 | 跟随系统主题变化需要 `QStyleHints` 信号监听 | 所有用户 | **待实现** |

### P2 - 增强

| 问题 | 描述 | 影响范围 | 当前状态 |
|------|------|----------|----------|
| 图片在 Wayland 下的监控 wl-paste 对 `image/png` 支持不稳定 | Wayland 下图片监控不准 | **待验证** |
| Wayland 下 `wl-paste --watch` 子进程重启 | 某些 Wayland 实现（如 Weston）下子进程可能在锁屏后断开 | Wayland 用户 | **待处理**。需 watchdog 自动重启 |
| SQLite 数据库并发 | 多线程写入可能出现 `SQLITE_BUSY` 错误 | 高频复制场景 | **待优化**。当前用线程锁，可改用 WAL + `timeout=5000` |

---

## 11. 开发路线图与阶段

| 阶段 | 时间估计 | 交付内容 | 里程碑 |
|------|----------|----------|--------|
| **Phase 0: 原型验证** | 1 天 | 最小可用的剪切板监听 + 数据库写入 + 简单列表 UI | 在 X11 下能跑通文本复制 |
| **Phase 1: 核心功能** | 5 天 | 完整剪切板监听 + 图片支持 + 搜索 + 系统托盘 | 可以日常使用 |
| **Phase 2: 交互完善** | 4 天 | 快捷键 + 预览 + 收藏夹 + 排除规则 + 设置 | 功能完整 |
| **Phase 3: 兼容性打磨** | 5 天 | Wayland 全兼容 + 性能调优 + 打包分发 | 可作为正式工具发布 |

---

## 12. 打包与分发

| 打包格式 | 说明 | 体积估计 |
|----------|------|----------|
| PyInstaller | 单目录打包，包含 Python 解释器和所有依赖 | ~60MB |
| AppImage | Linux 通用格式，一次打包到处运行 | ~80MB (含 PySide6) |
| Arch Linux AUR | PKGBUILD 脚本，自动安装 pip 依赖 | ~10KB 脚本 |
| Debian .deb | deb 包，依赖系统 PySide6 包 | ~5MB (不含依赖) |

**推荐：** 同时提供 AppImage（即开即用）和 AUR/PyPI（社区维护）两种渠道。AppImage 构建通过 GitHub Actions 自动完成。

---

## 13. 测试策略

| 层级 | 工具 | 覆盖 |
|------|------|------|
| 单元测试 | pytest | 数据库操作、去重算法、类型检测、配置读写 |
| 集成测试 | pytest + QtTest | 剪切板监听 → 数据库写入 → UI 刷新 的完整链路 |
| 手动测试 | — | X11 下 GNOME/KDE/Xfce 每个复制场景测试 3 轮 |
| 兼容性测试 | — | 在 3 种主要发行版 (Ubuntu/Fedora/Arch) 上验证 |

**自动化测试难点：** 剪切板监听依赖真实桌面环境，在无头 CI (GitHub Actions) 中很难模拟。需要 `xvfb` + 模拟复制操作，但 Wayland 在 CI 中几乎无法模拟。

---

## 14. 未实现的功能 (Future Scope)

这些功能不在当前设计范围内，但作为参考记录：

- **跨设备同步：** 需要后端服务器和登录系统（当前明确排除）
- **Snippets 模板：** 预设常用文本模板快速插入
- **OCR 图片文字识别：** 对图片中的文字建立搜索索引（需要 tesseract + 离线模型）
- **富文本格式保留 (RTF/HTML)：** 目前只保存纯文本；富文本需要额外处理
- **历史对比 (diff)：** 同一来源多次复制内容的变更对比
- **浏览器扩展集成：** 在浏览器侧直接保存选中内容到 Paste
- **命令行接口 (CLI)：** `paste list` `paste search` 等终端操作
- **历史条目合并成 Pinboard：** 自动按项目/话题归类

---

*最后更新: 2026-07-13*
*文档版本: v2.0*
