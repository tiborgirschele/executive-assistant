from __future__ import annotations

import os
import subprocess
from pathlib import Path


TELEGRAM_MAX_UPLOAD_BYTES = 49 * 1024 * 1024


def build_downscale_cmd(src_path: str, dst_path: str) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-i",
        src_path,
        "-vf",
        "scale='min(1920,iw)':-2",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        dst_path,
    ]


def enforce_video_size_limit(
    src_path: str,
    *,
    max_bytes: int = TELEGRAM_MAX_UPLOAD_BYTES,
    dry_run: bool = False,
) -> tuple[str, dict]:
    src = Path(src_path)
    size = src.stat().st_size
    meta = {"source_bytes": int(size), "max_bytes": int(max_bytes), "action": "pass"}
    if size <= int(max_bytes):
        return str(src), meta

    dst = src.with_name(f"{src.stem}_tg_1080p.mp4")
    cmd = build_downscale_cmd(str(src), str(dst))
    meta = {
        "source_bytes": int(size),
        "max_bytes": int(max_bytes),
        "action": "transcode",
        "ffmpeg_cmd": cmd,
        "output_path": str(dst),
    }
    if dry_run:
        return str(dst), meta

    proc = subprocess.run(
        cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg_failed:{proc.returncode}:{proc.stderr[-240:]}")
    if not dst.exists():
        raise RuntimeError("ffmpeg_missing_output")
    dst_size = os.path.getsize(dst)
    meta["output_bytes"] = int(dst_size)
    if dst_size > int(max_bytes):
        raise RuntimeError(f"ffmpeg_output_too_large:{dst_size}")
    return str(dst), meta

