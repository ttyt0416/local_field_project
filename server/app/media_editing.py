from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess
import tempfile


_MAX_VIDEO_BYTES = 500 * 1024 * 1024
_FFPROBE_TIMEOUT_SECONDS = 30
_FFMPEG_TIMEOUT_SECONDS = 180


class MediaEditError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration: float
    fps: float


@dataclass(frozen=True)
class VideoEditResult:
    content: bytes
    filename: str
    width: int
    height: int
    duration: float
    frame_count: int


def probe_video(*, content: bytes, filename: str) -> VideoMetadata:
    if len(content) > _MAX_VIDEO_BYTES:
        raise MediaEditError("확인할 영상 파일이 너무 큽니다.")
    with tempfile.TemporaryDirectory(prefix="local-field-video-probe-") as directory:
        source = Path(directory) / (Path(filename).suffix.lower() or ".mp4")
        source.write_bytes(content)
        return _probe(source)


def edit_video(
    *,
    content: bytes,
    filename: str,
    start_seconds: float,
    end_seconds: float | None,
    crop_x: int | None,
    crop_y: int | None,
    crop_width: int | None,
    crop_height: int | None,
    rotate: int,
) -> VideoEditResult:
    if len(content) > _MAX_VIDEO_BYTES:
        raise MediaEditError("편집할 영상 파일이 너무 큽니다.")
    if rotate not in {0, 90, 180, 270}:
        raise MediaEditError("지원하지 않는 회전 값입니다.")
    with tempfile.TemporaryDirectory(prefix="local-field-video-edit-") as directory:
        workdir = Path(directory)
        source = workdir / (Path(filename).suffix.lower() or ".mp4")
        output = workdir / "edited.mp4"
        source.write_bytes(content)
        source_info = _probe(source)
        duration = source_info.duration
        if start_seconds >= duration:
            raise MediaEditError("시작 시간이 영상 길이보다 짧아야 합니다.")
        if end_seconds is not None and (end_seconds <= start_seconds or end_seconds > duration):
            raise MediaEditError("종료 시간이 올바르지 않습니다.")

        x = 0 if crop_x is None else crop_x
        y = 0 if crop_y is None else crop_y
        width = source_info.width if crop_width is None else crop_width
        height = source_info.height if crop_height is None else crop_height
        if x < 0 or y < 0 or width < 2 or height < 2 or x + width > source_info.width or y + height > source_info.height:
            raise MediaEditError("crop 영역이 영상 크기를 벗어났습니다.")

        filters = [f"crop={width}:{height}:{x}:{y}"]
        if rotate == 90:
            filters.append("transpose=1")
        elif rotate == 180:
            filters.append("hflip,vflip")
        elif rotate == 270:
            filters.append("transpose=2")
        filters.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ss",
            f"{start_seconds:.3f}",
        ]
        if end_seconds is not None:
            command.extend(["-t", f"{end_seconds - start_seconds:.3f}"])
        command.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-vf",
                ",".join(filters),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
        _run(command, _FFMPEG_TIMEOUT_SECONDS, "영상을 편집하지 못했습니다.")
        if not output.is_file() or output.stat().st_size == 0:
            raise MediaEditError("편집된 영상 결과가 없습니다.")
        output_info = _probe(output)
        return VideoEditResult(
            content=output.read_bytes(),
            filename=f"{Path(filename).stem or 'video'}-edited.mp4",
            width=output_info.width,
            height=output_info.height,
            duration=output_info.duration,
            frame_count=max(1, round(output_info.duration * output_info.fps)),
        )


def _probe(path: Path) -> VideoMetadata:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,duration,avg_frame_rate:format=duration",
        "-of",
        "json",
        str(path),
    ]
    raw = _run(command, _FFPROBE_TIMEOUT_SECONDS, "영상 정보를 읽을 수 없습니다.", capture_output=True)
    try:
        payload = json.loads(raw)
        stream = payload["streams"][0]
        format_duration = payload.get("format", {}).get("duration")
        duration = float(stream.get("duration") or format_duration or 0)
        fps = _parse_rate(stream.get("avg_frame_rate"))
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MediaEditError("영상 정보를 읽을 수 없습니다.") from exc
    if width < 2 or height < 2 or duration <= 0 or not math.isfinite(duration) or fps <= 0:
        raise MediaEditError("편집할 수 있는 영상 정보가 아닙니다.")
    return VideoMetadata(width=width, height=height, duration=duration, fps=fps)


def _parse_rate(value: object) -> float:
    if not isinstance(value, str) or not value:
        return 0
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            return 0
    try:
        return float(value)
    except ValueError:
        return 0


def _run(command: list[str], timeout: int, error_message: str, *, capture_output: bool = False) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        raise MediaEditError(error_message) from exc
    if completed.returncode != 0:
        raise MediaEditError(error_message)
    return completed.stdout if capture_output else ""
