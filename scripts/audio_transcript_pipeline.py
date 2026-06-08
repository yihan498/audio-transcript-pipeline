from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any


AUDIO_EXTENSIONS = {".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".opus", ".wma"}

PROFILE_DEFAULTS = {
    "domestic-balanced": {
        "engine": "dashscope-file-asr",
        "asr_model": "fun-asr",
        "cleanup_provider": "qwen",
        "cleanup_model": "qwen-plus",
        "review_provider": "deepseek",
        "review_model": "deepseek-v4-pro",
    },
    "domestic-low-cost": {
        "engine": "dashscope-file-asr",
        "asr_model": "paraformer-v2",
        "cleanup_provider": "deepseek",
        "cleanup_model": "deepseek-v4-flash",
        "review_provider": "qwen",
        "review_model": "qwen-plus",
    },
    "domestic-local-asr": {
        "engine": "local-whisper",
        "asr_model": "faster-whisper-large-v3",
        "cleanup_provider": "qwen",
        "cleanup_model": "qwen-plus",
        "review_provider": "deepseek",
        "review_model": "deepseek-v4-pro",
    },
}


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_out_root() -> Path:
    return package_root() / "jobs" / "audio-transcript"


def safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "audio-transcript"


def next_job_dir(out_root: Path, title: str, today: str | None = None) -> Path:
    date_part = today or dt.datetime.now().strftime("%Y%m%d")
    slug = safe_slug(title)
    out_root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 100):
        candidate = out_root / f"{date_part}-{slug}-v{index:02d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not allocate a versioned job directory")


def collect_audio_paths(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            paths.extend(p for p in path.rglob("*") if p.suffix.lower() in AUDIO_EXTENSIONS)
        elif path.suffix.lower() in AUDIO_EXTENSIONS:
            paths.append(path)
        else:
            paths.append(path)
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def probe_with_ffprobe(path: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def inventory_one(path: Path) -> dict[str, Any]:
    exists = path.exists()
    item: dict[str, Any] = {
        "path": str(path),
        "exists": exists,
        "extension": path.suffix.lower() or None,
        "size_bytes": path.stat().st_size if exists else None,
        "duration_seconds": None,
        "codec": None,
        "sample_rate": None,
        "channels": None,
        "probe_source": None,
        "warnings": [],
    }
    if not exists:
        item["warnings"].append("file_missing")
        return item
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        item["warnings"].append("extension_not_recognized_as_audio")

    probe = probe_with_ffprobe(path)
    if not probe:
        item["warnings"].append("ffprobe_unavailable_or_failed")
        return item

    item["probe_source"] = "ffprobe"
    fmt = probe.get("format") or {}
    duration = fmt.get("duration")
    if duration is not None:
        try:
            item["duration_seconds"] = round(float(duration), 3)
        except ValueError:
            item["warnings"].append("duration_parse_failed")

    audio_streams = [s for s in probe.get("streams", []) if s.get("codec_type") == "audio"]
    if audio_streams:
        stream = audio_streams[0]
        item["codec"] = stream.get("codec_name")
        item["sample_rate"] = stream.get("sample_rate")
        item["channels"] = stream.get("channels")
    else:
        item["warnings"].append("no_audio_stream_found")
    return item


def write_inventory(job_dir: Path, audio_paths: list[Path]) -> list[dict[str, Any]]:
    inventory = [inventory_one(path) for path in audio_paths]
    (job_dir / "source-inventory.json").write_text(
        json.dumps({"audio_files": inventory}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = ["# Source Inventory", ""]
    for index, item in enumerate(inventory, start=1):
        lines.append(f"## {index}. {item['path']}")
        lines.append("")
        lines.append(f"- Exists: {item['exists']}")
        lines.append(f"- Extension: {item['extension']}")
        lines.append(f"- Size bytes: {item['size_bytes']}")
        lines.append(f"- Duration seconds: {item['duration_seconds']}")
        lines.append(f"- Codec: {item['codec']}")
        lines.append(f"- Sample rate: {item['sample_rate']}")
        lines.append(f"- Channels: {item['channels']}")
        lines.append(f"- Probe source: {item['probe_source']}")
        warnings = ", ".join(item["warnings"]) if item["warnings"] else "none"
        lines.append(f"- Warnings: {warnings}")
        lines.append("")
    (job_dir / "source-inventory.md").write_text("\n".join(lines), encoding="utf-8")
    return inventory


def create_job(args: argparse.Namespace) -> Path:
    out_root = Path(args.out_root) if args.out_root else default_out_root()
    job_dir = next_job_dir(out_root, args.title, args.date)
    for subdir in ["raw", "cleaned", "notes", "delivery", "logs"]:
        (job_dir / subdir).mkdir(parents=True, exist_ok=True)

    audio_paths = collect_audio_paths(args.audio)
    profile = resolve_profile(args)
    job = {
        "job_id": job_dir.name,
        "title": args.title,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "language": args.language,
        "preferred_engine": profile["engine"],
        "asr_model": profile["asr_model"],
        "processing_profile": args.profile,
        "cleanup_provider": profile["cleanup_provider"],
        "cleanup_model": profile["cleanup_model"],
        "review_provider": profile["review_provider"],
        "review_model": profile["review_model"],
        "provider_policy": "china-domestic-only",
        "audio_inputs": [str(path) for path in audio_paths],
        "status": "initialized",
    }
    (job_dir / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    (job_dir / "version-note.md").write_text(
        "\n".join(
            [
                "# Version Note",
                "",
                f"- Version: {job_dir.name}",
                "- Change: Initial audio transcription job scaffold.",
                f"- Preferred engine: {profile['engine']}",
                f"- ASR model: {profile['asr_model']}",
                f"- Processing profile: {args.profile}",
                f"- Cleanup model: {profile['cleanup_provider']} / {profile['cleanup_model']}",
                f"- Review model: {profile['review_provider']} / {profile['review_model']}",
                f"- Language: {args.language}",
                "- Provider policy: China-domestic-only.",
                "- Caveats: Raw transcription has not been produced yet.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_inventory(job_dir, audio_paths)
    return job_dir


def resolve_profile(args: argparse.Namespace) -> dict[str, str]:
    profile = dict(PROFILE_DEFAULTS.get(args.profile, PROFILE_DEFAULTS["domestic-balanced"]))
    if args.engine:
        profile["engine"] = args.engine
    if args.asr_model:
        profile["asr_model"] = args.asr_model
    if args.cleanup_provider:
        profile["cleanup_provider"] = args.cleanup_provider
    if args.cleanup_model:
        profile["cleanup_model"] = args.cleanup_model
    if args.review_provider:
        profile["review_provider"] = args.review_provider
    if args.review_model:
        profile["review_model"] = args.review_model
    return profile


def inventory_existing(args: argparse.Namespace) -> Path:
    job_dir = Path(args.job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    audio_paths = collect_audio_paths(args.audio)
    write_inventory(job_dir, audio_paths)
    return job_dir


def write_engine_plan(args: argparse.Namespace) -> Path:
    job_dir = Path(args.job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    plan_path = job_dir / "raw" / "engine-plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        "engine": args.engine,
        "model": args.model,
        "language": args.language,
        "provider_policy": "china-domestic-only",
        "status": "planned",
        "next_step": "Implement or call the selected engine adapter, then write raw/engine-output.json and raw/transcript.raw.md.",
    }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return plan_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and manage versioned audio transcript jobs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_job = subparsers.add_parser("init-job", help="Create a versioned transcript job folder and inventory audio.")
    init_job.add_argument("--title", required=True)
    init_job.add_argument("--audio", nargs="+", required=True, help="Audio files or directories.")
    init_job.add_argument("--out-root", default=None, help="Default: package-local jobs/audio-transcript.")
    init_job.add_argument("--language", default="zh")
    init_job.add_argument("--engine", default=None)
    init_job.add_argument("--asr-model", default=None)
    init_job.add_argument("--cleanup-provider", default=None)
    init_job.add_argument("--cleanup-model", default=None)
    init_job.add_argument("--review-provider", default=None)
    init_job.add_argument("--review-model", default=None)
    init_job.add_argument("--profile", default="domestic-balanced")
    init_job.add_argument("--date", default=None, help="Override date prefix, e.g. 20260608.")
    init_job.set_defaults(func=create_job)

    inventory = subparsers.add_parser("inventory", help="Write source inventory for an existing job folder.")
    inventory.add_argument("--job-dir", required=True)
    inventory.add_argument("--audio", nargs="+", required=True, help="Audio files or directories.")
    inventory.set_defaults(func=inventory_existing)

    plan = subparsers.add_parser("plan-engine", help="Record the selected engine plan without calling an API.")
    plan.add_argument("--job-dir", required=True)
    plan.add_argument("--engine", required=True)
    plan.add_argument("--model", default=None)
    plan.add_argument("--language", default="zh")
    plan.set_defaults(func=write_engine_plan)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
