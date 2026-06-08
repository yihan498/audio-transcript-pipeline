from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from audio_transcript_pipeline import create_job  # noqa: E402
from dashscope_asr_smoke_test import call_dashscope_asr, get_api_key as get_dashscope_key  # noqa: E402
from dashscope_smoke_test import call_dashscope  # noqa: E402


def extract_content(result: dict) -> str:
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return (message.get("content") or "").strip()


def write_raw(job_dir: Path, audio_path: Path, asr_model: str, asr_result: dict, text: str) -> None:
    raw_dir = job_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "engine-output.json").write_text(json.dumps(asr_result, ensure_ascii=False, indent=2), encoding="utf-8")
    transcript = [
        "# Raw Transcript",
        "",
        f"- Source file: {audio_path}",
        "- Engine: dashscope-short-audio-asr",
        f"- Model: {asr_model}",
        "- Note: Short-audio pipeline. Timestamps are unavailable unless the ASR response includes them.",
        "",
        "## 00:00:00",
        "",
        text,
        "",
    ]
    (raw_dir / "transcript.raw.md").write_text("\n".join(transcript), encoding="utf-8")


def cleanup_transcript(api_key: str, model: str, raw_text: str, max_tokens: int) -> dict:
    prompt = "\n".join(
        [
            "请把下面的中文音频转写稿整理成忠实的 cleaned transcript。",
            "要求：",
            "1. 只修正明显的标点、断句、重复口头语和轻微错别字。",
            "2. 不要改写结构，不要加入原文没有的信息。",
            "3. 保留讲述顺序、例子、提醒和语气中的关键信息。",
            "4. 对不确定术语用 [疑似：...] 标出。",
            "",
            "原始转写：",
            raw_text,
        ]
    )
    return call_dashscope(api_key, model, "https://dashscope.aliyuncs.com/compatible-mode/v1", prompt, max_tokens=max_tokens)


def write_cleaned(job_dir: Path, cleanup_model: str, cleanup_result: dict, cleaned_text: str) -> None:
    cleaned_dir = job_dir / "cleaned"
    logs_dir = job_dir / "logs"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "cleanup-output.json").write_text(json.dumps(cleanup_result, ensure_ascii=False, indent=2), encoding="utf-8")
    cleaned = [
        "# Cleaned Transcript",
        "",
        "- Cleanup provider: dashscope",
        f"- Cleanup model: {cleanup_model}",
        "- Policy: source-faithful cleanup; no unsupported additions.",
        "",
        cleaned_text,
        "",
    ]
    (cleaned_dir / "transcript.cleaned.md").write_text("\n".join(cleaned), encoding="utf-8")


def update_job_status(job_dir: Path, status: str) -> None:
    job_path = job_dir / "job.json"
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job["status"] = status
    job["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a short-audio domestic transcript pipeline.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--asr-model", default="qwen3-asr-flash")
    parser.add_argument("--cleanup-model", default="qwen-plus")
    parser.add_argument("--cleanup-max-tokens", type=int, default=4096)
    parser.add_argument("--profile", default="domestic-balanced")
    parser.add_argument("--date", default=None)
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        return 2

    api_key = get_dashscope_key()
    if not api_key:
        print("DASHSCOPE_API_KEY is not available in process or Windows user environment.", file=sys.stderr)
        return 2

    job_args = SimpleNamespace(
        title=args.title,
        audio=[str(audio_path)],
        out_root=None,
        language="zh",
        engine="dashscope-short-audio-asr",
        asr_model=args.asr_model,
        cleanup_provider="qwen",
        cleanup_model=args.cleanup_model,
        review_provider="deepseek",
        review_model="deepseek-v4-pro",
        profile=args.profile,
        date=args.date,
    )
    job_dir = create_job(job_args)

    try:
        asr_result = call_dashscope_asr(api_key, args.asr_model, "https://dashscope.aliyuncs.com/compatible-mode/v1", audio_path)
        raw_text = extract_content(asr_result)
        write_raw(job_dir, audio_path, args.asr_model, asr_result, raw_text)
        cleanup_result = cleanup_transcript(api_key, args.cleanup_model, raw_text, args.cleanup_max_tokens)
        cleaned_text = extract_content(cleanup_result)
        write_cleaned(job_dir, args.cleanup_model, cleanup_result, cleaned_text)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {body}", file=sys.stderr)
        update_job_status(job_dir, "failed")
        return 1
    except urllib.error.URLError as error:
        print(f"Network error: {error}", file=sys.stderr)
        update_job_status(job_dir, "failed")
        return 1
    except ValueError as error:
        print(str(error), file=sys.stderr)
        update_job_status(job_dir, "failed")
        return 2

    update_job_status(job_dir, "short_audio_cleaned")
    print(job_dir)
    print("raw/transcript.raw.md")
    print("cleaned/transcript.cleaned.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
