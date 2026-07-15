# Paste

Paste 是一个 Linux 本地剪切板管理器：自动保存复制过的文本和图片，支持搜索、筛选、再次复制和系统托盘操作。

## 功能

- 自动记录文本、URL 和图片剪切板内容
- 主窗口实时搜索历史记录
- `All / URLs / Images` 类型筛选；URLs 筛选兼容旧的文本型地址记录
- 点击记录重新写入系统剪切板
- 单条删除与确认后清空全部历史
- 托盘左键显示最近 5 条记录；右键提供显示/隐藏、热键配置、Recent 和退出
- X11 全局快捷键；Wayland 下提供系统快捷键配置指引
- 轮转日志与 UI 卡死线程堆栈采集

所有历史数据默认存放在 `~/.paste/`，不会上传到网络。

## 安装

项目使用 Python 3.8+ 和 PySide2。

```bash
git clone git@github.com:carlosfranco9/paste.git
cd paste
bash packaging/install.sh
```

安装完成后可以运行：

```bash
paste
paste --show
```

安装脚本会创建 `/usr/local/bin/paste`，并复制桌面启动器、应用图标和自动启动配置。更新源码后请再次运行安装脚本，然后退出并重新启动 Paste。

## 开发运行

安装依赖后可直接运行：

```bash
python3 -m pip install PySide2 Pillow python-xlib pyperclip psutil
python3 -m src.main --show
```

运行测试：

```bash
QT_QPA_PLATFORM=offscreen XDG_SESSION_TYPE=wayland pytest -q
```

## 使用说明

- 单击托盘图标：显示最近 5 条记录，点击即可复制。
- 右击托盘图标：显示/隐藏窗口、配置热键、查看 Recent、退出。
- 主窗口：使用顶部搜索框搜索，使用 `All`、`URLs`、`Images` 进行筛选。
- 删除：每条记录右侧的 `×` 可删除该条；`Clear All` 会在确认后清空历史。

部分 GNOME AppIndicator 扩展会把左右键都映射为右键菜单；此时可通过右键菜单中的 `Recent` 访问近期列表。

## 日志与卡死排查

```bash
# 常规运行、托盘事件、窗口刷新及数据库操作日志
tail -f ~/.paste/logs/paste.log

# UI 超过 8 秒无响应时自动写入的全部线程堆栈
tail -f ~/.paste/logs/hang.log

# 进程仍在运行时，手动抓取线程堆栈
kill -USR2 <paste-pid>
```

日志不会记录剪切板正文。若启动失败且日志没有新增记录，请从终端运行：

```bash
/usr/local/bin/paste --show
```

这能显示日志初始化前的 Python 或安装错误。

## 项目结构

```text
src/
  ui/          主窗口、历史列表、托盘和筛选栏
  monitor/     剪切板监听与内容处理
  database/    SQLite 历史数据与搜索
  storage/     配置与文件存储
  utils/       热键、去重、诊断与 URL 识别
packaging/     安装脚本、桌面入口和原始图标素材
resources/     运行时图标和样式资源
docs/          架构与实施文档
tests/         自动化测试
```

更多实现细节见 [架构文档](docs/architecture.md) 和 [实施文档](docs/implementation.md)。
