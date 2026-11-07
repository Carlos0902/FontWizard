
<p align="center">
  <img src="App/src/assets/font-wizard-icon.png" alt="Font Wizard" width="110"/>
</p>

<h1 align="center"> Font Wizard 5</h1>

<p align="center">
  <b>Change Windows 11 & 10 system font Everywhere</b>. <br>  Start, Taskbar, Lockscreen, Old Apps, New UWP & WinUI apps, everywhere <br>
  


  

---




 <h1 align="center">📸 Screenshots</h1>
</p>

<p align="center">
  <img src="App/src/assets/screenshots/system-wide2.png" alt="System-wide font preview" width="100%"/>
</p>

<p align="center">
  <img src="App/src/assets/screenshots/app-variants.png" alt="Font Wizard Apply Screen" width="100%"/>
</p>
<p align="center">
  <img src="App/src/assets/screenshots/app-variants2.png" alt="Font Wizard Apply Screen" width="100%"/>
</p>


<p align="center">
  <img src="App/src/assets/screenshots/screenshot (2).png" alt="Font Wizard screenshot 2" width="100%"/>
</p>







---

## Download for Windows

Download **FontWizard-Windows-x64.zip** from [GitHub Releases](https://github.com/Carlos0902/FontWizard/releases).
Extract the ZIP, open **FontWizard.exe**, and approve the Windows administrator prompt.
The portable build runs on 64-bit Windows 10 and 11 and bundles its Python dependencies.
To undo a font change, use **Restore Original Fonts** in the app and restart Windows.

### Install the upstream release via WinGet

```powershell
winget install -e --id karnyadavdev.FontWizard
```


## Build from Source


```bat
.\App\build.bat
```

Build output goes to `App\dist\`.

## 中文字体兼容（QQ / 微信）

选择包含中文的静态 `.ttf` 后，勾选 **中文字体兼容（QQ / 微信）**，
在新增的中文常规、粗体、细体卡片中检查或分别指定字体，再点击 **Apply Changes** 并重启 Windows。
程序生成保留 Microsoft YaHei 和 Microsoft YaHei UI 身份的 `.ttc` 集合，并沿用原始备份与恢复流程。

该选项替换系统微软雅黑，因此其他使用这些字体的软件也会变化；QQ、微信使用内置字体的页面不保证变化。
常用汉字和标点检查不代表完整字库覆盖。取消勾选仅停止后续替换，恢复原始中文字体请使用 **Restore Original Fonts**，然后重启。

如需文件列表、资源管理器侧栏和桌面图标字体跟随选择，同时勾选 **资源管理器字体（文件列表 / 侧栏 / 桌面）**。
该选项保留字号和字重，自动备份当前用户的原始字体设置；会影响其他使用系统菜单、消息等字体的软件。
完整效果需重启 Windows，现代资源管理器的实际覆盖仍需实机验证。使用 **Restore Original Fonts** 可恢复原设置，取消勾选不会自动恢复。

开发运行与测试（在项目根目录）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r App\requirements.txt
.\.venv\Scripts\python.exe App\src\main.py --no-admin
.\.venv\Scripts\python.exe -m unittest discover -s App\tests -v
```

实际应用或恢复系统字体需要管理员权限。自动测试使用临时文件与模拟系统操作，不修改系统字体。
