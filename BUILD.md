# Windows 构建与 CI

在项目根目录运行以下 PowerShell 命令。使用 64 位 Python 3.12；BAT 始终使用项目的 `.venv`，无需激活环境。

## 首次准备

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

已有 `.venv` 时跳过创建命令。构建前退出旧的便携版程序，避免 EXE 被占用；构建会替换 `release\2.4GBatteryTray`，请先备份其中需要保留的个人设置和历史。

## 一次生成便携版与源码包

```powershell
.\build.bat
```

需要同时安装或更新依赖时：

```powershell
.\build.bat all --install-deps
```

分别打包：

```powershell
.\build.bat exe
.\build.bat source
```

源码打包只使用 Python 标准库，不要求安装 PyInstaller，也不依赖 Git。源码包包含当前文件内容（包括未提交的源码修改），排除虚拟环境、构建产物、Git 元数据及个人日志、设置和电量历史。

BAT 可从其他目录调用，会自动定位项目目录。也可直接复制 Python 命令：

```powershell
.\.venv\Scripts\python.exe tools\build.py all
```

## 输出

```text
release/
├── 2.4GBatteryTray/
│   ├── 2.4GBatteryTray.exe
│   ├── _internal/
│   └── README.txt
├── 2.4GBatteryTray-win64.zip
├── 2.4GBatteryTray-source.zip
└── SHA256SUMS.txt
```

便携版使用仓库中的 `2.4GBatteryTray.spec`，以 `onedir + windowed` 方式构建；保持 EXE 与 `_internal` 目录在一起。中间文件写入 `build\pyinstaller`；`release/` 和 `build/` 均已加入 `.gitignore`。

构建脚本会为 PyInstaller 单独设置 DLL 搜索路径，避免把其他工具的同名 DLL 打进包里；不会修改系统或用户 PATH。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\verify_release.py
```

最后一条命令校验两份 ZIP 的内容和 SHA-256，并在临时目录解压便携版、运行有超时限制的 EXE 托盘自检。它要求先完成 `all` 构建。

内存和句柄压力测试（包含本机 HID 枚举）可单独运行：

```powershell
.\.venv\Scripts\python.exe tools\runtime_soak.py
```

## GitHub Actions

`.github/workflows/ci.yml` 在 push、pull request 和手动触发时运行 Windows x64 / Python 3.12 检查、回归测试、两种打包和产物自检。CI 调用同一个 `build.bat`；成功后可在 Actions 运行页面的 Artifacts 下载 ZIP 与校验文件，保留 14 天。流程仅上传构建产物，不自动发布 GitHub Release。

参考：[PyInstaller spec 构建说明](https://pyinstaller.org/en/stable/spec-files.html)、[GitHub 构建产物上传](https://github.com/actions/upload-artifact)。
