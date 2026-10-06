# 视频拼接说明

[返回项目首页](../README.md)

`merge_videos.py` 将指定目录中的视频按集数排序，合并成 `<目录名>_全集.mp4`，输出到输入目录中。原始分集视频会保留。

下文命令均在项目根目录的 Windows PowerShell 中执行，假定已经按[项目首页](../README.md#2-准备拼接环境)创建 `.venv` 并安装依赖。将 `downloads\剧名\第1季` 替换为实际的分集目录。

## 命令与参数

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py --help
```

| 参数 | 含义 |
| --- | --- |
| `directory` | 必填，直接存放分集视频的目录，不递归子目录 |
| `--dry-run` | 读取输入并检查集数、顺序和媒体参数，不生成视频 |
| `--reencode` | 逐集统一媒体参数，再拼接 |
| `--gpu` | 配合 `--reencode` 使用 NVIDIA `h264_nvenc` 编码器 |
| `--crf 0-51` | 转码质量参数，默认 18；CPU 使用 CRF，GPU 使用 CQ，数值较小通常画质较高、文件较大 |
| `--overwrite` | 新文件生成并通过校验后，替换已有的同名成品 |
| `--ffmpeg 路径` | 手动指定 FFmpeg 可执行文件 |

`--gpu` 和 `--crf` 仅在 `--reencode` 模式下生效。单独使用 `--gpu` 仍走默认的直接拼接流程。CPU 的 CRF 和 GPU 的 CQ 是不同编码器的质量控制参数，相同数值不保证相同画质或文件大小。

### 先检查输入

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --dry-run
```

如果只因媒体参数不同而无法通过默认检查，可以检查转码模式的输入：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode --dry-run
```

`--dry-run` 不调用 FFmpeg，不检查编码器、GPU 驱动或实际输出能力。输入文件不可读取、命名不合要求等问题仍会报错。

### 无损拼接

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季"
```

默认模式使用 FFmpeg concat demuxer 并复制音视频流，保持原编码和画质。脚本会严格比较轨道排列、编码、分辨率、帧率、时间基准、色彩参数、编码参数头和音频参数等信息。

参数头不同不一定表示绝对无法拼接，但脚本会保守停止并提示使用 `--reencode`。若原编码不能封装进 MP4，也需要改用转码模式。

### CPU 或 GPU 转码

```powershell
# CPU 转码
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode

# NVIDIA NVENC 转码
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode --gpu

# 调整转码质量
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode --crf 20
```

转码会逐集生成统一参数的临时视频，再拼接为成品，不会同时打开全部输入文件。

- **视频**：使用第一集的宽、高和帧率作为目标，宽高向上调整为偶数；缩放后居中添加黑边，输出 H.264、yuv420p，像素比例设为 1。输入旋转由 FFmpeg 自动处理，带旋转或非方形像素的素材应检查实际输出的方向和比例。
- **CPU 编码**：使用 `libx264`、`medium` preset，默认 CRF 18。
- **GPU 编码**：使用 `h264_nvenc`、`p5` preset、VBR 和 CQ 质量参数，默认 CQ 18。需要可用的 NVIDIA 显卡驱动及带该编码器的 FFmpeg；编码失败时不会自动回退到 CPU。
- **音频**：有任意一集包含音频时，统一为 AAC、48 kHz、双声道、192 kbit/s；无音轨的集补静音，音频按每集视频时长补齐或截断。全部输入无音轨时，输出也无音轨。

重新编码有画质损失，通常比直接拼接慢。H.264 成品可能显著大于原 HEVC 素材；所有临时转码片段和最终成品会同时占用输入目录所在磁盘的空间。

### 重新生成已有成品

```powershell
# 参数一致时重新拼接
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --overwrite

# 需要转码时重新生成
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode --overwrite
```

默认拒绝覆盖同名成品。带 `--overwrite` 时，旧文件会保留到新文件通过校验之后，再被替换。

## 输入、排序与输出规则

- 支持扩展名：MP4、MKV、MOV、AVI、M4V、WebM、TS、MTS、M2TS、FLV、WMV、MPG、MPEG、3GP；扩展名不区分大小写，实际解码能力取决于 FFmpeg。
- 文件名支持 `第001集.mp4`、`第2集 标题.mp4`、`001.mp4`、`001 标题.mp4`、`EP01.mp4`、`S01E01.mp4` 等。中文数字如“第一集”需要改成阿拉伯数字。
- 按数字排序，例如第2集排在第10集前。集数必须大于 0；重复集数、无法识别的命名或零字节视频都会报错并停止。
- 只提取集数，不按季号分组。不同季分目录处理，避免集数重复。
- 从第1集到已发现的最大集数之间存在缺集时，显示缺集提示，继续按已有集数处理；不会推测最大集数之后是否仍有遗漏。
- 不递归子目录。`poster.jpg`、`.series.json` 等非视频文件被忽略。文件名以 `_全集` 结尾的视频会被当作已有合并结果排除。
- 仅保留第一条有效视频轨（排除封面图轨）和第一条音频轨。额外音轨、软字幕、附件及章节不合并；画面中已经烧录的字幕会保留。
- 固定输出 MP4 到输入目录，文件名为 `<目录名>_全集.mp4`，没有单独的输出路径参数。

## FFmpeg 与环境

脚本按以下顺序定位 FFmpeg：

1. 命令中显式指定的 `--ffmpeg`。
2. 系统 PATH 中的 `ffmpeg`。
3. `imageio-ffmpeg` 提供的可执行文件。

Windows 依赖包提供 FFmpeg；PyAV 用于读取媒体信息，无须另装 ffprobe。本地整理环境使用的是 FFmpeg 7.1，转码可优先使用该版本或更新版本。若系统 PATH 中的旧版本不支持转码参数，可以指定另一个可执行文件：

```powershell
.\.venv\Scripts\python.exe .\merge_videos.py ".\downloads\剧名\第1季" --reencode --ffmpeg "C:\Tools\ffmpeg\bin\ffmpeg.exe"
```

## 输出校验与临时文件

脚本先在输入目录内创建 `.merge-videos-*` 临时目录，完成拼接后再检查：

- 成品存在、非空，且可以读取媒体信息。
- 总时长与输入片段时长之和相符，允许误差为 `max(1 秒, 片段数 × 0.1 秒)`；转码模式以转码后片段的时长为基准。
- 是否包含音频轨与预期一致。
- 当音频轨时长可读取时，音视频轨时长差不超过 0.25 秒。

校验通过后保存成品。该检查不是逐帧解码验证，也不能判断所有时间点的实际音画同步；成品仍可通过抽查片头、拼接点和片尾确认播放效果。

成功、普通错误或 Ctrl+C 取消时会尝试清理临时目录。强制结束进程、断电或文件占用可能留下临时目录；确认对应拼接进程已经结束后，再处理残留目录。原始分集视频不会因拼接而删除。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| 提示没有可合并的视频 | 检查是否选择了直接包含分集视频的目录；脚本不递归扫描 |
| 提示无法识别集数 | 按上述规则重命名；移出不属于该季的宣传片等视频 |
| 提示重复集数 | 检查是否混入其他季或重复下载了同一集 |
| 提示缺集 | 先核对下载任务；若继续，成品只包含已有集数 |
| 媒体参数或编码参数头不同 | 使用 `--reencode`；可以先用 `--reencode --dry-run` 检查输入 |
| NVENC 初始化或编码失败 | 检查显卡驱动和 FFmpeg，或去掉 `--gpu` 使用 CPU 转码 |
| 找不到 PyAV 或 FFmpeg | 用项目 `.venv` 中的 Python 运行，并重新安装 `requirements.txt` 中的依赖 |
| 输出已经存在 | 确认需要重新生成后，添加 `--overwrite` |
| 输出音视频时长差超过 0.25 秒 | 检查源视频的音轨与时长；若此前直接拼接，可改用 `--reencode` 对齐每集音频后重试 |
| 磁盘空间不足或成品很大 | 为临时片段和成品预留空间；参数一致时使用直接拼接，转码时可适度调高 `--crf` |

## 测试范围

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

当前 4 项测试使用系统临时目录中的占位文件，验证：

1. 集数识别和数值排序。
2. 重复集数及无法识别的文件名被拒绝。
3. 缺集区间计算。
4. 已有 `_全集` 文件被排除。

这些测试不调用 FFmpeg，也不生成真实短视频。实际拼接顺序、CPU/GPU 转码、输出校验、覆盖保护、进程取消及临时文件清理尚无自动化测试覆盖。
