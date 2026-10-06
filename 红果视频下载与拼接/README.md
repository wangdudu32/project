# 红果视频下载与全集合并

配合红果视频下载器与 Python 拼接脚本，将下载好的多集短视频按集数合并为一个完整的长视频。

使用流程：**安装下载器 → 下载各集视频 → 检查集数和媒体参数 → 合并全集**。

下载器作为独立的 Windows 安装包提供；本仓库中的 Python 代码负责处理本地视频。下载完成后，需要手动运行拼接命令。

## 项目组成

```text
.
├── README.md
├── merge_videos.py                 # 拼接入口
├── requirements.txt               # Python 依赖
├── .gitignore
├── HongguoDownloader-Setup.exe     # 从 Releases 单独下载后可放在此处，不纳入 Git
├── docs/
│   ├── downloader.md              # 下载器与视频目录说明
│   └── merging.md                 # 拼接参数、规则与常见问题
└── tests/
    └── test_merge_videos.py
```

## 快速开始（Windows PowerShell）

以下命令均在本项目根目录运行，即仓库中的 `红果视频下载与拼接/` 目录。准备 Python 3.12；从 [GitHub Releases](https://github.com/wangdudu32/project/releases/tag/hongguo-downloader-v1.0.0.72) 单独获取 Windows 下载器安装包，版本及校验信息见[下载器说明](docs/downloader.md)。

### 1. 下载并整理视频

先[下载 Windows 安装包 v1.0.0.72](https://github.com/wangdudu32/project/releases/download/hongguo-downloader-v1.0.0.72/HongguoDownloader-Setup.exe)，再双击 `HongguoDownloader-Setup.exe`，按安装向导完成安装，并通过下载器完成所需剧集的下载。具体界面与操作以该版本下载器为准。

等所有下载任务完成后，找到直接包含分集视频的目录。一部剧的每一季应分别存放，例如：

```text
downloads/
└── 剧名/
    └── 第1季/
        ├── 第001集.mp4
        ├── 第002集.mp4
        └── 第003集.mp4
```

`downloads` 是示例目录，并非下载器的固定输出路径。也可以使用任意磁盘上的现有目录。脚本按文件名识别集数，只扫描指定目录的直接子文件；更多要求见[下载目录与拼接衔接](docs/downloader.md#下载目录与拼接衔接)。

### 2. 准备拼接环境

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\merge_videos.py --help
```

如果没有 `py` 命令，可使用已安装的 Python 3.12 执行 `python -m venv .venv`，再运行上面的依赖安装命令。直接调用虚拟环境中的 Python，无须激活环境或修改 PowerShell 执行策略。

如果已经安装了 `uv`，也可以用下面两条命令代替创建环境和安装依赖的步骤：

```powershell
uv venv .venv --python 3.12
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
```

依赖为 `av==19.0.1`（读取媒体信息）和 `imageio-ffmpeg==0.6.0`（提供 FFmpeg）。脚本优先使用系统 PATH 中的 FFmpeg，否则使用 `imageio-ffmpeg` 提供的版本，也可通过 `--ffmpeg` 指定路径。

### 3. 检查视频

将下方路径替换为实际的分集目录：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --dry-run
```

该命令列出集数顺序、缺集提示、时长和输出位置，并检查能否直接拼接，不生成视频。出现重复集数、无法识别的文件名或损坏文件时，需要先处理对应输入。缺集只会提示，脚本仍允许合并已有集数。

如果仅提示媒体参数不同，可以使用 `--reencode --dry-run` 检查转码流程的输入；这仍不会实际转码，也不会验证 GPU 或编码器是否可用。

### 4. 合并全集

参数一致时，直接无损拼接：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季"
```

脚本提示参数不兼容时，逐集转为 H.264 / AAC 后再拼接：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode
```

具备 NVIDIA NVENC 编码环境时，可以使用 GPU 转码：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode --gpu
```

示例的输出为 `downloads\剧名\第1季\第1季_全集.mp4`。原始分集保留。若已存在同名成品，需要显式加上 `--overwrite`；新文件生成并通过校验后才会替换原成品。

## 拼接模式与规则

| 模式 | 用途 | 结果 |
| --- | --- | --- |
| 默认 | 输入媒体参数一致 | 复制原音视频流，保持原编码和画质 |
| `--reencode` | 输入参数不同，或需要统一为 H.264 / AAC | CPU 逐集转码后拼接，有画质损失 |
| `--reencode --gpu` | 使用 NVIDIA NVENC 编码 | GPU 逐集转码后拼接，有画质损失 |

- 输出固定为 MP4，位于输入目录内，名称为 `<目录名>_全集.mp4`。
- 支持 `第001集.mp4`、`001.mp4`、`EP01.mp4`、`S01E01.mp4` 等阿拉伯数字集数命名。
- 只保留第一条有效视频轨和第一条音频轨，额外音轨、软字幕、附件及章节不合并。
- 转码以第一集的分辨率和帧率为目标，必要时添加黑边；音频统一为 AAC 48 kHz 双声道，部分集缺少音轨时补静音。
- 输出校验检查可读取性、时长和音轨，并在音频轨时长可读取时检查音视频时长差；它不是完整的逐帧解码或主观同步检查。

全部参数、空间要求与故障处理见[拼接说明](docs/merging.md)。

## 运行测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前包含 4 项单元测试，覆盖集数识别和数值排序、重复及无法识别的命名、缺集区间、自动排除已有全集。测试使用临时目录中的占位文件，不生成真实视频；实际拼接、转码、GPU 编码、成品校验、覆盖保护及清理流程尚未被这些测试覆盖。

## 仓库文件与安装包

源码、依赖清单、说明文档和测试保存在 [wangdudu32/project](https://github.com/wangdudu32/project) 仓库的 `红果视频下载与拼接/` 目录中。`.gitignore` 排除了虚拟环境、缓存、视频素材、合并成品、临时文件、日志以及 `HongguoDownloader-Setup.exe`。

Windows 安装包通过 [GitHub Releases](https://github.com/wangdudu32/project/releases/tag/hongguo-downloader-v1.0.0.72) 的附件分发，可在发布页的 **Assets** 中下载 `HongguoDownloader-Setup.exe`。Git 克隆、仓库的 Download ZIP 以及 Release 自动生成的 Source code 归档均不包含该安装包，需要单独下载。下载后可将安装包放在本项目目录中保留，不会随普通 Git 提交上传。

更新安装包版本时，应发布新的 Release 附件，并同步更新本页下载链接及[下载器说明](docs/downloader.md)中的版本、大小和 SHA-256 校验值。
