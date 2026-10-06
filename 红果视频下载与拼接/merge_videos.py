"""按集数合并指定目录中的视频。运行 python merge_videos.py --help 查看用法。"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm", ".ts", ".mts", ".m2ts", ".flv", ".wmv", ".mpg", ".mpeg", ".3gp"}
EPISODE_PATTERNS = (
    re.compile(r"第\s*(\d+)\s*[集话話]"),
    re.compile(r"(?:^|[\s._-])S\d+E(\d+)(?=$|[\s._-])", re.I),
    re.compile(r"(?:^|[\s._-])(?:EP?|Episode)[\s._-]*(\d+)(?=$|[\s._-])", re.I),
    re.compile(r"^(\d+)(?:$|[\s._-])"),
)


class MergeError(Exception):
    """可向用户直接展示的错误。"""


@dataclass
class MediaInfo:
    path: Path
    duration: float
    video_duration: float
    audio_duration: float | None
    video_index: int
    audio_index: int | None
    width: int
    height: int
    fps: Fraction
    signature: dict


def episode_number(path: Path) -> int:
    for pattern in EPISODE_PATTERNS:
        matches = pattern.findall(path.stem)
        if matches:
            if len(matches) != 1:
                raise MergeError(f"文件名包含多个集数：{path.name}")
            number = int(matches[0])
            if number < 1:
                raise MergeError(f"集数必须大于 0：{path.name}")
            return number
    raise MergeError(f"无法识别集数：{path.name}（支持 第001集、001、EP01、S01E01 等命名）")


def discover(directory: Path) -> list[tuple[int, Path]]:
    episodes = []
    errors = []
    seen = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        # 输出采用固定后缀，重复运行时不会把之前的全集再次加入。
        if path.stem.endswith("_全集"):
            continue
        try:
            number = episode_number(path)
            if number in seen:
                raise MergeError(f"第 {number} 集重复：{seen[number].name}、{path.name}")
            if path.stat().st_size == 0:
                raise MergeError(f"空视频文件：{path.name}")
            seen[number] = path
            episodes.append((number, path))
        except MergeError as exc:
            errors.append(str(exc))
    if errors:
        raise MergeError("\n".join(errors))
    if not episodes:
        raise MergeError("该目录没有可合并的视频；只扫描当前目录，不递归子目录。")
    return sorted(episodes)


def missing_ranges(numbers: list[int]) -> list[str]:
    result = []
    previous = 0
    for number in numbers:
        if number > previous + 1:
            start, end = previous + 1, number - 1
            result.append(str(start) if start == end else f"{start}–{end}")
        previous = number
    return result


def find_ffmpeg(explicit: str | None) -> str:
    if explicit:
        executable = shutil.which(explicit)
        if not executable and Path(explicit).is_file():
            executable = str(Path(explicit).resolve())
        if not executable:
            raise MergeError(f"找不到指定的 FFmpeg：{explicit}")
        return executable
    if executable := shutil.which("ffmpeg"):
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise MergeError("找不到 FFmpeg。请激活虚拟环境后执行：uv pip install -r requirements.txt") from exc


def probe(path: Path) -> MediaInfo:
    try:
        import av
    except ImportError as exc:
        raise MergeError("缺少 PyAV。请激活虚拟环境后执行：uv pip install -r requirements.txt") from exc
    try:
        with av.open(str(path)) as container:
            videos = [s for s in container.streams.video if not (s.disposition & av.stream.Disposition.attached_pic)]
            if not videos:
                raise MergeError(f"没有有效的视频轨：{path.name}")
            video = videos[0]
            audio = container.streams.audio[0] if container.streams.audio else None
            ctx = video.codec_context
            duration = float(container.duration / av.time_base) if container.duration is not None else 0.0
            video_duration = float(video.duration * video.time_base) if video.duration is not None else duration
            audio_duration = (
                float(audio.duration * audio.time_base)
                if audio is not None and audio.duration is not None and audio.time_base is not None
                else None
            )
            duration = duration or video_duration
            if not math.isfinite(duration) or duration <= 0 or video_duration <= 0:
                raise MergeError(f"无法确定视频时长：{path.name}")
            fps = video.average_rate or video.guessed_rate
            if not fps or fps <= 0 or ctx.width <= 0 or ctx.height <= 0:
                raise MergeError(f"无法确定分辨率或帧率：{path.name}")
            signature = {
                "轨道排列": tuple((s.type, s.codec_context.name if s.codec_context else None) for s in container.streams),
                "视频轨索引": video.index,
                "视频编码": ctx.name,
                "视频规格": ctx.profile,
                "分辨率": (ctx.width, ctx.height),
                "像素格式": ctx.format.name if ctx.format else None,
                "像素比例": str(video.sample_aspect_ratio or Fraction(1)),
                "帧率": str(fps),
                "视频时间基准": str(video.time_base),
                "色彩参数": (ctx.color_range, ctx.colorspace, ctx.color_primaries, ctx.color_trc),
                "视频编码参数头": hashlib.sha256(ctx.extradata or b"").hexdigest(),
                "旋转标签": video.metadata.get("rotate", "0"),
                "音频": None,
            }
            if audio:
                actx = audio.codec_context
                signature["音频"] = (
                    audio.index, actx.name, actx.sample_rate, actx.layout.name,
                    actx.format.name if actx.format else None, str(audio.time_base),
                    hashlib.sha256(actx.extradata or b"").hexdigest(),
                )
            return MediaInfo(path, duration, video_duration, audio_duration, video.index,
                             audio.index if audio else None, ctx.width, ctx.height,
                             Fraction(fps), signature)
    except MergeError:
        raise
    except Exception as exc:
        raise MergeError(f"读取视频失败：{path.name}\n{exc}") from exc


def compatibility_issues(infos: list[MediaInfo]) -> list[str]:
    first = infos[0]
    issues = []
    for info in infos[1:]:
        changed = [key for key in first.signature if info.signature[key] != first.signature[key]]
        if changed:
            issues.append(f"{info.path.name}：{'、'.join(changed)}与 {first.path.name} 不同")
    return issues


def time_text(seconds: float) -> str:
    seconds = max(0, round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def create_workdir(directory: Path) -> Path:
    """创建可由普通 Windows 文件权限清理的临时目录。"""
    for _ in range(10):
        candidate = directory / f".merge-videos-{uuid.uuid4().hex[:10]}"
        try:
            # 不使用 tempfile.mkdtemp；其 0700 权限在部分 Windows 沙箱中会
            # 让后续的清理进程无法访问目录。
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise MergeError("无法创建临时目录，请检查输入目录权限。")


def run_ffmpeg(executable: str, arguments: list[str], duration: float, label: str) -> None:
    command = [executable, "-hide_banner", "-nostdin", "-y", "-loglevel", "warning",
               "-nostats", "-progress", "pipe:1", *arguments]
    # 不经 shell，中文、空格、引号和命令行元字符均作为原样文件路径传递。
    with tempfile.TemporaryFile(mode="w+b") as error_log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=error_log, text=True, encoding="utf-8", errors="replace",
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        last_update = 0.0
        current = 0.0
        try:
            assert process.stdout is not None
            for line in process.stdout:
                key, _, value = line.strip().partition("=")
                if key == "out_time_us":
                    try:
                        current = int(value) / 1_000_000
                    except ValueError:
                        pass
                if key == "progress" and (time.monotonic() - last_update >= 2 or value == "end"):
                    # muxer 可能在写索引，进度完成不等同于文件已通过校验。
                    percent = min(100, max(0, current / duration * 100))
                    print(f"  {label}：{percent:5.1f}%  {time_text(current)} / {time_text(duration)}", flush=True)
                    last_update = time.monotonic()
            returncode = process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        finally:
            if process.stdout:
                process.stdout.close()
        error_log.seek(0)
        lines = deque((line.decode("utf-8", errors="replace").rstrip() for line in error_log), maxlen=25)
        details = "\n".join(lines)
        if returncode:
            raise MergeError(f"FFmpeg 处理失败（退出码 {returncode}）。\n{details}")
        if details:
            print(f"  FFmpeg 提示（最后 25 行以内）：\n{details}", flush=True)


def concat_quote(path: Path) -> str:
    value = path.resolve().as_posix()
    if "\n" in value or "\r" in value:
        raise MergeError(f"文件路径不能包含换行符：{path.name!r}")
    return "'" + value.replace("'", "'\\''") + "'"


def concatenate(executable: str, infos: list[MediaInfo], workdir: Path, output: Path) -> None:
    manifest = workdir / "inputs.ffconcat"
    manifest.write_text("ffconcat version 1.0\n" + "".join(
        f"file {concat_quote(info.path)}\n" for info in infos), encoding="utf-8")
    first = infos[0]
    args = ["-f", "concat", "-safe", "0", "-i", str(manifest), "-map", f"0:{first.video_index}"]
    if first.audio_index is not None:
        args += ["-map", f"0:{first.audio_index}"]
    args += ["-c", "copy", "-map_metadata", "-1", "-map_chapters", "-1",
             "-metadata", "comment=merge_videos.py",
             "-movflags", "+faststart", str(output)]
    run_ffmpeg(executable, args, sum(info.duration for info in infos), "拼接")


def normalize(executable: str, infos: list[MediaInfo], workdir: Path, crf: int, use_gpu: bool) -> list[MediaInfo]:
    first = infos[0]
    width, height = first.width + first.width % 2, first.height + first.height % 2
    fps = first.fps
    with_audio = any(info.audio_index is not None for info in infos)
    encoder = "h264_nvenc" if use_gpu else "libx264"
    print(f"统一为 {width}×{height}、{fps} fps、{encoder}" + (" / AAC 48 kHz 双声道" if with_audio else "（无音频）"))
    normalized = []
    for index, info in enumerate(infos, 1):
        target = workdir / f"normalized_{index:06d}.mp4"
        args = ["-i", str(info.path)]
        if with_audio and info.audio_index is None:
            args += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        args += ["-map", f"0:{info.video_index}"]
        if with_audio:
            args += ["-map", f"0:{info.audio_index}" if info.audio_index is not None else "1:a:0"]
        filters = (
            f"setpts=PTS-STARTPTS,scale={width}:{height}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p"
        )
        args += ["-vf", filters, "-c:v", encoder]
        if use_gpu:
            # NVENC 使用 cq 控制恒定质量；-b:v 0 让编码器按 cq 自行分配码率。
            args += ["-preset", "p5", "-rc", "vbr", "-cq", str(crf), "-b:v", "0", "-profile:v", "high"]
        else:
            args += ["-preset", "medium", "-crf", str(crf)]
        args += ["-pix_fmt", "yuv420p", "-video_track_timescale", "90000"]
        if with_audio:
            args += ["-af", "aresample=48000:async=1:first_pts=0,apad",
                     "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
        args += ["-t", f"{info.video_duration:.9f}", "-map_metadata", "-1", "-map_chapters", "-1", str(target)]
        print(f"转码 [{index}/{len(infos)}] {info.path.name}", flush=True)
        run_ffmpeg(executable, args, info.video_duration, "转码")
        normalized.append(probe(target))
    return normalized


def validate_output(output: Path, infos: list[MediaInfo]) -> MediaInfo:
    if not output.is_file() or output.stat().st_size == 0:
        raise MergeError("FFmpeg 未生成有效的输出文件。")
    result = probe(output)
    expected = sum(info.duration for info in infos)
    # 允许容器四舍五入和 AAC 编码延迟，但拒绝明显截断的输出。
    tolerance = max(1.0, len(infos) * 0.1)
    if abs(result.duration - expected) > tolerance:
        raise MergeError(f"输出时长异常：预期 {time_text(expected)}，实际 {time_text(result.duration)}。")
    if (result.audio_index is None) != (infos[0].audio_index is None):
        raise MergeError("输出音频轨与预期不一致。")
    if result.audio_duration is not None:
        sync_delta = abs(result.audio_duration - result.video_duration)
        if sync_delta > 0.25:
            raise MergeError(
                f"输出音视频时长相差 {sync_delta:.3f} 秒，超过 0.25 秒，已拒绝输出。"
            )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按集数将指定目录中的视频合并为 <目录名>_全集.mp4。")
    parser.add_argument("directory", type=Path, help="视频目录（只处理直接位于其中的视频）")
    parser.add_argument("--reencode", action="store_true", help="逐集统一分辨率、帧率和编码后拼接，速度较慢")
    parser.add_argument("--gpu", action="store_true", help="重新编码时使用 NVIDIA NVENC（需要支持 h264_nvenc 的显卡和驱动）")
    parser.add_argument("--dry-run", action="store_true", help="仅检查集数、顺序及媒体参数，不生成视频")
    parser.add_argument("--overwrite", action="store_true", help="成功生成并校验新文件后替换已有全集")
    parser.add_argument("--ffmpeg", help="手动指定 FFmpeg 可执行文件路径")
    parser.add_argument("--crf", type=int, default=18, choices=range(0, 52), metavar="0-51", help="重新编码的画质参数，默认 18；越小质量越高、体积越大")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        directory = args.directory.expanduser().resolve()
        if not directory.is_dir():
            raise MergeError(f"目录不存在或不是目录：{directory}")
        output = directory / f"{directory.name}_全集.mp4"
        if output.is_symlink():
            raise MergeError(f"输出路径是符号链接，请先换用普通文件路径：{output}")
        if output.exists() and not args.dry_run:
            if not output.is_file():
                raise MergeError(f"输出路径不是普通文件：{output}")
            if not args.overwrite:
                raise MergeError(f"输出已存在：{output}\n如需重新生成，请加 --overwrite。")
        episodes = discover(directory)
        missing = missing_ranges([number for number, _ in episodes])
        if missing:
            print(f"提示：缺少以下集数，将按已有文件合并：{', '.join(missing)}")
        print(f"目录：{directory}\n找到 {len(episodes)} 个视频，按集数升序处理。", flush=True)
        infos = []
        for index, (number, path) in enumerate(episodes, 1):
            info = probe(path)
            infos.append(info)
            print(f"  [{index}/{len(episodes)}] 第 {number} 集  {path.name}  {time_text(info.duration)}", flush=True)
        print(f"总时长约 {time_text(sum(info.duration for info in infos))}\n输出：{output}", flush=True)
        issues = compatibility_issues(infos)
        if issues and not args.reencode:
            raise MergeError("无法确认这些文件能安全地直接拼接：\n" + "\n".join(issues[:20])
                             + (f"\n另有 {len(issues) - 20} 个文件存在差异。" if len(issues) > 20 else "")
                             + "\n请加 --reencode 统一参数后拼接。")
        if args.reencode and issues:
            print(f"检测到 {len(issues)} 个文件参数不同，将逐集转码统一。")
        if args.dry_run:
            print("检查完成；未生成或修改视频文件。")
            return 0
        executable = find_ffmpeg(args.ffmpeg)
        print(f"FFmpeg：{executable}\n模式：{'重新编码后拼接' if args.reencode else '直接复制音视频流（无损）'}", flush=True)
        # 临时目录与成品位于同一磁盘，成功前不触碰已有输出。
        workdir = create_workdir(directory)
        try:
            merge_infos = normalize(executable, infos, workdir, args.crf, args.gpu) if args.reencode else infos
            pending = workdir / "result.mp4"
            concatenate(executable, merge_infos, workdir, pending)
            result = validate_output(pending, merge_infos)
            if args.overwrite:
                os.replace(pending, output)
            else:
                # 同盘硬链接以原子方式创建目标；即使其他进程刚写入同名文件，也不覆盖。
                try:
                    os.link(pending, output)
                except FileExistsError as exc:
                    raise MergeError("输出文件已被另一个进程创建，未覆盖该文件。") from exc
                except OSError:
                    if os.name == "nt":
                        # Windows rename 在目标存在时失败，同时支持无硬链接的文件系统。
                        os.rename(pending, output)
                    else:
                        raise
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        print(f"完成：{output}\n时长：{time_text(result.duration)}，大小：{output.stat().st_size / 1024**3:.3f} GiB")
        return 0
    except KeyboardInterrupt:
        print("\n已取消，临时文件已清理，原视频和已有全集保持不变。", file=sys.stderr)
        return 130
    except (MergeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
