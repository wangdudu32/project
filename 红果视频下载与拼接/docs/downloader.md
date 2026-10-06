# 红果视频下载器

[返回项目首页](../README.md)

下载器负责获取分集视频，`merge_videos.py` 负责将下载完成的本地视频合并。两者通过视频目录衔接：下载完成后，将实际的分集目录传给拼接脚本。

## 安装包信息

以下信息对应 Release `hongguo-downloader-v1.0.0.72` 分发的 Windows 安装包：

| 项目 | 值 |
| --- | --- |
| 文件名 | `HongguoDownloader-Setup.exe` |
| 产品名称 | `Hongguo Downloader` |
| 产品版本 | `1.0.0.72`（来自 EXE 版本资源） |
| 文件大小 | 142,018,614 字节，约 135.44 MiB |
| SHA-256 | `9D77A2548CC1BDE92C4A269A3F482655B4F5FC538421F328AF8D959D6739B592` |

本项目通过 GitHub Releases 提供该 Windows 安装包，下载器的源代码和配套操作手册未随包提供。以上信息来自文件检查，未通过安装运行验证下载功能。

## 获取与安装

安装包下载入口：

- [直接下载 Windows 安装包 v1.0.0.72](https://github.com/wangdudu32/project/releases/download/hongguo-downloader-v1.0.0.72/HongguoDownloader-Setup.exe)
- [查看 Release 发布页及附件](https://github.com/wangdudu32/project/releases/tag/hongguo-downloader-v1.0.0.72)

在发布页的 **Assets** 中选择 `HongguoDownloader-Setup.exe`。Git 克隆、仓库的 Download ZIP 以及 Release 自动生成的 Source code 归档均不包含安装包。

下载后可将安装包放在本项目根目录（仓库中的 `红果视频下载与拼接/` 目录），也可以保存在其他位置。`.gitignore` 会忽略项目根目录中的安装包，本地文件可以保留。

1. 通过上述链接下载 `HongguoDownloader-Setup.exe`，可按下方命令核对 SHA-256。
2. 双击安装包，按实际安装向导完成安装。
3. 启动安装后的下载器，在其界面中完成所需剧集的下载。
4. 等待下载完成，再找到直接存放各集视频的目录，按下一节执行检查与拼接。

具体的搜索、登录、剧集选择和保存位置设置，以安装后的实际界面为准；当前提供的文件不足以确认这些界面的按钮名称或操作细节。

若已将安装包放在项目根目录，可在该目录用 PowerShell 计算文件校验值，与上表比对；保存在其他位置时，将命令中的路径替换为实际路径：

```powershell
Get-FileHash -LiteralPath .\HongguoDownloader-Setup.exe -Algorithm SHA256
```

此校验值用于确认是否为同一份文件。更换安装包版本后，需要发布新的 Release 附件，并同步更新本页及项目首页的下载链接、版本、大小和校验值。

## 下载目录与拼接衔接

按剧名和季分别存放视频，例如：

```text
downloads/
└── 剧名/
    ├── 第1季/
    │   ├── 第001集.mp4
    │   ├── 第002集.mp4
    │   ├── 第003集.mp4
    │   ├── poster.jpg
    │   └── .series.json
    └── 第2季/
        ├── 第001集.mp4
        └── 第002集.mp4
```

该结构仅为示例，不代表下载器默认生成的结构。视频可以保存在项目之外；无需为了拼接将文件复制进仓库。

- 将直接包含 `第001集.mp4` 等文件的那一层目录传给脚本。上例中应选择 `第1季`，而非 `downloads` 或 `剧名`。
- 同一季内每个集数只能有一个视频。不同季应分开处理，即便使用 `S01E01` 命名，脚本也只提取集数，不按季号分组。
- 支持阿拉伯数字集数，如 `第001集.mp4`、`001 标题.mp4`、`EP01.mp4`、`S01E01.mp4`。中文数字如 `第一集.mp4` 需要先改名。
- 海报、`.series.json` 等非视频文件会被忽略。脚本不读取 `.series.json` 中的集数、下载状态或排序信息。
- `--dry-run` 可以发现空文件、无法识别的命名和部分媒体读取问题，但不能确认下载器的任务是否全部完成；先在下载器中确认下载完成。

在项目根目录安装好 Python 依赖后运行：

```powershell
# 检查第1季
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --dry-run

# 检查通过后，无损拼接
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季"

# 若提示媒体参数不兼容，则转码后拼接
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode
```

如果视频在其他磁盘上，直接使用绝对路径：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py "D:\红果视频\剧名\第1季" --dry-run
```

示例中的目录名为 `第1季`，因此成品名称为 `第1季_全集.mp4`，保存在同一目录中。若希望成品名包含剧名，可以先将输入目录命名为 `剧名第1季`，成品便会命名为 `剧名第1季_全集.mp4`。

完整参数、转码和覆盖已有文件的用法见[拼接说明](merging.md)。
