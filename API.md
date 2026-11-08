# Fontscape / FontWizard 项目上下文

每次开始本项目工作时先读取本文件；接口、模块职责或构建方式变化时同步维护。

## 来源与当前状态

- 本地根目录：`D:\Fontscape`。
- 上游：<https://github.com/karnyadavdev/FontWizard>。
- 2026-11-06 克隆完整仓库，基线提交：`e0dbcf1`（`Update README.md`）。
- 当前分支：`main`，跟踪 `origin/main`。已加入可选中文兼容模式及资源管理器字体选项，改动尚未提交。
- 用户要求 GitHub 使用代理 `http://127.0.0.1:7892`；已配置在 Git 用户级的 `http.https://github.com.proxy`。

## 技术栈与入口

- Windows 桌面应用，Python + PySide6（Qt）+ fontTools；无独立 HTTP API。
- 依赖清单：`App/requirements.txt`（`fonttools>=4.40.0`、`PySide6-Essentials>=6.6.0`）。
- 程序入口：`App/src/main.py`。
- 启动命令：`python App/src/main.py`；默认请求管理员权限。
- 开发时可使用 `python App/src/main.py --no-admin` 跳过启动时提权；涉及系统字体的操作仍可能需要管理员权限。

## 主要模块

| 文件 | 职责 / 主要接口 |
| --- | --- |
| `App/src/ui.py` | Qt 界面，`FontWizardApp` |
| `App/src/core.py` | 控制器与字体选择状态，`FontWizardController` |
| `App/src/operation.py` | 字体工作流，`FontWorkflow`、`build_artifacts` |
| `App/src/font_generation.py` | 字体身份与构建，`build_font`、`build_variable_font` |
| `App/src/chinese_fonts.py` | 常用汉字/标点检查，`validate_chinese_source`；保留集合内所有身份的 `build_chinese_collection` |
| `App/src/explorer_fonts.py` | 当前用户 Shell 字体设置，`WindowsShellFonts`、`ExplorerFontService`；备份、应用、恢复及失败回滚 |
| `App/src/font_detection.py` | 字体检查与字重识别 |
| `App/src/win_registry.py` | Windows 字体注册表访问，`WindowsFontRegistry` |
| `App/src/checks.py` | 管理员权限与预检 |
| `App/src/app_state.py` | 托管状态持久化 |
| `App/src/paths.py` | 运行时路径 |

## 构建与验证

- 上游构建入口：`App/build.bat`；自动安装 Python 构建依赖，用 PyInstaller 打包，再调用 Inno Setup 6 生成安装包。
- 构建产物：`App/dist/`。脚本会清理原有 `App/build/`、`App/dist/`。
- 开发环境：`.venv`，Python 3.14.4、fontTools 4.68.0、PySide6-Essentials 6.12.0。
- 开发启动：`.\.venv\Scripts\python.exe App/src/main.py --no-admin`；实际替换需要管理员权限。
- 测试：`.\.venv\Scripts\python.exe -m unittest discover -s App/tests -v`（16 项通过）。
- 已用真实微软雅黑三份集合与本地中文 TTF 验证生成和全部成员身份；Qt 离屏界面验证通过。未打包安装程序，未应用系统字体或重启，未验证 QQ/微信实际显示效果。

## 中文兼容模式（2026-11-06）

- 用户明确允许通过系统中文字体替换覆盖 QQ/微信及其他使用微软雅黑的软件，不要求仅作用于这两个应用。
- 界面勾选“中文字体兼容（QQ / 微信）”，增加 `yahei_regular`、`yahei_bold`、`yahei_light` 字重卡片，可分别选择静态中文 TTF。
- `get_system_weights(fonts_dir=None, include_chinese=False)` 默认保留上游行为；开启后加入 `msyh.ttc`、`msyhbd.ttc`、`msyhl.ttc`。
- `FontWizardController.set_include_chinese(enabled)` 同步选项与字重；成功应用后在 `install.include_chinese` 保存选项。
- 每份 TTC 保留原集合所有成员（微软雅黑、微软雅黑 UI）及原有名称、字重等身份；替换沿用重启时原位覆盖流程。应用自带字体不保证变化。
- 替换前必须存在通过家族、厂商及字形数检查的原始中文备份；WinSxS 查询支持 TTC。此检查是启发式检查，不是密码学来源认证。
- 源字体检查常用汉字和标点，拒绝纯西文字体；不保证完整中文字符覆盖。
- 取消勾选仅停止后续中文替换，不自动恢复已应用的中文字体；保留安装清单，使用 Restore Original Fonts 恢复，恢复流程始终纳入已有中文备份。待重启时禁用模式切换。

## 资源管理器字体（2026-11-06）

- 用户要求增加资源管理器内的字体替换。新增可选“资源管理器字体（文件列表 / 侧栏 / 桌面）”，默认关闭。
- `FontWorkflow.include_explorer` 控制应用，保存到 `install.include_explorer`；设置跟随已替换的 `Segoe UI` 身份。现代 Shell 部分区域仍取决于系统字体替换与 Windows 版本，实际覆盖需要实机验证。
- 通过 `SystemParametersInfoW` 设置图标标题字体和 NONCLIENTMETRICS 中的标题、菜单、状态栏、消息字体；只更改字体名，保留字号、字重与其他 LOGFONT 字段，不修改间距。通知系统刷新，完整效果需重启。
- 此设置作用于当前用户，也影响其他使用系统界面字体的软件。取消勾选不恢复，使用 Restore Original Fonts 恢复。
- 原始会话 LOGFONT 与持久化 WindowMetrics 注册表字体分别备份到 `RuntimePaths.local_root/explorer-fonts.json`；两者可能不同。重新应用保留首次备份，恢复后下一次应用重新捕获用户设置。
- 原备份在安排系统字体替换前原子保存并回读校验；更改失败尝试回滚，备份损坏阻止覆盖。恢复不依赖选项是否勾选；存在活动 Shell 字体备份时保留 Recovery 入口。
- 本机只读检查了原生结构大小（LOGFONTW 92 / NONCLIENTMETRICSW 504 字节）、会话字体与持久化字体；未执行真实 Shell 字体写入。模拟测试与 Qt 离屏选项验证通过。
- Windows API 参考：<https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-systemparametersinfow>。
