from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


BITRATES = {
    (3, 1): [None, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    (3, 2): [None, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    (3, 3): [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    (2, 1): [None, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    (2, 2): [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
    (2, 3): [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}

SAMPLE_RATES = {
    3: [44100, 48000, 32000],
    2: [22050, 24000, 16000],
    0: [11025, 12000, 8000],
}


@dataclass
class Frame:
    offset: int
    size: int
    duration: float


def skip_id3(data: bytes) -> int:
    if not data.startswith(b"ID3") or len(data) < 10:
        return 0
    size = 0
    for byte in data[6:10]:
        size = (size << 7) | (byte & 0x7F)
    return 10 + size


def parse_header(header: bytes) -> tuple[int, float] | None:
    if len(header) < 4:
        return None
    value = int.from_bytes(header, "big")
    if ((value >> 21) & 0x7FF) != 0x7FF:
        return None
    version_bits = (value >> 19) & 0x3
    layer_bits = (value >> 17) & 0x3
    bitrate_index = (value >> 12) & 0xF
    sample_rate_index = (value >> 10) & 0x3
    padding = (value >> 9) & 0x1
    if version_bits == 1 or layer_bits == 0 or bitrate_index in (0, 15) or sample_rate_index == 3:
        return None
    layer = 4 - layer_bits
    version_key = 3 if version_bits == 3 else 2
    bitrate = BITRATES.get((version_key, layer), [None] * 16)[bitrate_index]
    sample_rate = SAMPLE_RATES[version_bits][sample_rate_index]
    if not bitrate or not sample_rate:
        return None
    bitrate_bps = bitrate * 1000
    if layer == 1:
        frame_size = int(((12 * bitrate_bps / sample_rate) + padding) * 4)
        samples = 384
    elif layer == 3 and version_bits != 3:
        frame_size = int((72 * bitrate_bps / sample_rate) + padding)
        samples = 576
    else:
        frame_size = int((144 * bitrate_bps / sample_rate) + padding)
        samples = 1152
    return frame_size, samples / sample_rate


def parse_frames(data: bytes) -> list[Frame]:
    frames: list[Frame] = []
    index = skip_id3(data)
    limit = len(data) - 4
    while index < limit:
        parsed = parse_header(data[index : index + 4])
        if parsed:
            size, duration = parsed
            if size > 4 and index + size <= len(data):
                frames.append(Frame(index, size, duration))
                index += size
                continue
        index += 1
    return frames


def safe_stem(value: str) -> str:
    value = re.sub(r'[<>:"/\\\\|?*]+', "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:120] or "audio"


def split_mp3(path: Path, out_dir: Path, max_seconds: float, max_bytes: int) -> dict:
    data = path.read_bytes()
    frames = parse_frames(data)
    if not frames:
        raise RuntimeError(f"No MP3 frames found: {path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    current: list[Frame] = []
    current_seconds = 0.0
    current_bytes = 0
    chunk_index = 0
    start_seconds = 0.0
    elapsed = 0.0
    for frame in frames:
        would_exceed = current and (current_seconds + frame.duration > max_seconds or current_bytes + frame.size > max_bytes)
        if would_exceed:
            chunk_path = out_dir / f"chunk_{chunk_index:04d}.mp3"
            write_chunk(data, current, chunk_path)
            chunks.append(
                {
                    "index": chunk_index,
                    "path": str(chunk_path),
                    "start": round(start_seconds, 3),
                    "end": round(start_seconds + current_seconds, 3),
                    "duration": round(current_seconds, 3),
                    "bytes": chunk_path.stat().st_size,
                }
            )
            chunk_index += 1
            start_seconds += current_seconds
            current = []
            current_seconds = 0.0
            current_bytes = 0
        current.append(frame)
        current_seconds += frame.duration
        current_bytes += frame.size
        elapsed += frame.duration
    if current:
        chunk_path = out_dir / f"chunk_{chunk_index:04d}.mp3"
        write_chunk(data, current, chunk_path)
        chunks.append(
            {
                "index": chunk_index,
                "path": str(chunk_path),
                "start": round(start_seconds, 3),
                "end": round(start_seconds + current_seconds, 3),
                "duration": round(current_seconds, 3),
                "bytes": chunk_path.stat().st_size,
            }
        )
    manifest = {
        "source": str(path),
        "source_bytes": len(data),
        "frame_count": len(frames),
        "estimated_duration": round(elapsed, 3),
        "max_seconds": max_seconds,
        "max_bytes": max_bytes,
        "chunks": chunks,
    }
    (out_dir / "chunks-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def write_chunk(data: bytes, frames: list[Frame], out_path: Path) -> None:
    with out_path.open("wb") as output:
        for frame in frames:
            output.write(data[frame.offset : frame.offset + frame.size])


def main() -> int:
    parser = argparse.ArgumentParser(description="Split an MP3 into frame-aligned short chunks without ffmpeg.")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-seconds", type=float, default=240)
    parser.add_argument("--max-bytes", type=int, default=9_500_000)
    args = parser.parse_args()
    try:
        manifest = split_mp3(Path(args.audio), Path(args.out_dir), args.max_seconds, args.max_bytes)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps({"chunks": len(manifest["chunks"]), "duration": manifest["estimated_duration"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
