# Fontscape for Windows

Fontscape 是面向中文用户的 Windows 系统字体工具，支持本地字体预览、系统界面字体替换和原始字体恢复。

## 下载与使用

1. 在 [GitHub Releases](https://github.com/Carlos0902/FontWizard/releases) 下载 Fontscape Windows x64 便携包。
2. 解压后运行 **Fontscape.exe**，在 Windows 提示时批准管理员权限。支持 64 位 Windows 10 和 11，无需另外安装 Python。
3. 选择本地静态 `.ttf`。可为不同字重单独选文件，也可用 **替换字体大小** 在 100%–125% 之间实时预览。
4. 确认样式后点击 **应用字体**，然后重启 Windows。撤销时点击 **恢复原始字体**，再重启。

## 中文界面

勾选 **替换系统中文字体（微软雅黑）** 后，可分别选择并预览中文常规、粗体和细体。程序会检查常用界面用字，并在确认可恢复的原始文件后生成微软雅黑和微软雅黑 UI 字体集合。常用字检查不覆盖全部汉字。

微信输入框等界面如果使用应用自带字体，会保留原有字形。**资源管理器字体** 选项还会修改当前用户的桌面图标、系统菜单等字体设置。取消勾选只影响后续操作，已应用的设置可通过 **恢复原始字体** 撤销。

在线字体库依赖 GitHub 网络连接。本地字体选择、预览和替换可以离线使用。

## 从源码构建

在仓库根目录运行 `App\build.bat`。可执行文件位于 `App\dist\Fontscape.exe`，安装包使用 Inno Setup 6 构建。

运行自动测试：

```powershell
python -m unittest discover -s App/tests
```

## 项目来源

Fontscape for Windows 基于 [Font Wizard](https://github.com/karnyadavdev/FontWizard) 开发，沿用其 MIT 许可证。版权与第三方许可见 [LICENSE](LICENSE) 和 [third-party-notices.txt](third-party-notices.txt)。
