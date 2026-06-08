from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dashscope_asr_smoke_test import call_dashscope_asr, get_api_key  # noqa: E402
from mp3_frame_splitter import split_mp3  # noqa: E402


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\\\|?*]+', "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:150] or "audio"


def format_time(seconds: float) -> str:
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def extract_content(result: dict) -> str:
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return (message.get("content") or "").strip()


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def chunk_text_header(audio_path: Path, chunk_path: Path) -> str:
    return "\n".join(
        [
            "# Chunk ASR Cache",
            "",
            "## Version Note v01",
            "",
            "2026-06-08 v01: Generated a chunk-level ASR cache from a user-authorized local MP3 source. This file is an intermediate artifact used to rebuild the merged lesson transcript.",
            "",
            "## Source / Evidence Note",
            "",
            "- Source type: user-authorized local MP3 audio split into processing chunks.",
            f"- Parent audio file: {audio_path}",
            f"- Parent Source URI: {file_uri(audio_path)}",
            f"- Chunk file: {chunk_path}",
            f"- Chunk Source URI: {file_uri(chunk_path)}",
            "- Source sufficiency: original audio content is available and was used for transcription.",
            "- Boundary: this chunk cache is not a standalone research document, factual verification, or final deliverable.",
            "- Final transcript: use the merged `raw/transcript.raw.md` or the central `transcripts/` export.",
            "",
            "## Chunk Transcript",
            "",
        ]
    )


def strip_chunk_header(text: str) -> str:
    marker = "## Chunk Transcript"
    if marker not in text:
        return text.strip()
    return text.split(marker, 1)[1].strip()


def raw_header(audio_path: Path, model: str, max_seconds: float) -> list[str]:
    return [
        "# Raw Transcript",
        "",
        "## Version Note v01",
        "",
        "2026-06-08 v01: Generated a raw ASR transcript from a user-authorized local MP3 file. The audio was split only to satisfy short-audio API limits, then merged back into a single lesson-level transcript.",
        "",
        "## Source / Evidence Note",
        "",
        f"- Source type: user-authorized local MP3 audio file.",
        f"- Source file: {audio_path}",
        f"- Source URI: {file_uri(audio_path)}",
        "- Source sufficiency: original audio content is available and was used for transcription.",
        "- Method: local MP3 frame splitting -> DashScope short-audio ASR -> lesson-level merged raw transcript.",
        "- Boundary: this is an automatic raw transcript, not a factual verification, citation-backed research note, or polished summary.",
        "- Chunk note: chunk files are internal processing evidence only; final reading should use this merged lesson transcript or the central transcripts folder.",
        "- External references: none used for content claims; all transcript text comes from the source audio.",
        "",
        "## Transcription Metadata",
        "",
        "- Engine: dashscope-short-audio-asr chunked local MP3",
        f"- Model: {model}",
        f"- Chunk target seconds: {max_seconds}",
        "",
    ]


def transcribe_lesson(api_key: str, audio_path: Path, lesson_dir: Path, model: str, max_seconds: float, max_bytes: int, retries: int) -> dict:
    chunks_dir = lesson_dir / "chunks"
    raw_dir = lesson_dir / "raw"
    raw_json_dir = raw_dir / "chunk-results"
    raw_json_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = chunks_dir / "chunks-manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = split_mp3(audio_path, chunks_dir, max_seconds, max_bytes)
    sections = raw_header(audio_path, model, max_seconds)
    for chunk in manifest["chunks"]:
        chunk_path = Path(chunk["path"])
        result_path = raw_json_dir / f"chunk_{chunk['index']:04d}.json"
        text_path = raw_json_dir / f"chunk_{chunk['index']:04d}.txt"
        if result_path.exists() and text_path.exists():
            text = strip_chunk_header(text_path.read_text(encoding="utf-8"))
        else:
            last_error: Exception | None = None
            for attempt in range(1, retries + 1):
                try:
                    result = call_dashscope_asr(api_key, model, "https://dashscope.aliyuncs.com/compatible-mode/v1", chunk_path)
                    text = extract_content(result)
                    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    text_path.write_text(chunk_text_header(audio_path, chunk_path) + text.strip() + "\n", encoding="utf-8")
                    (raw_json_dir / "source-note.md").write_text(
                        "\n".join(
                            [
                                "# Chunk Source Note",
                                "",
                                "## Version Note v01",
                                "",
                                "2026-06-08 v01: Recorded the provenance for chunk-level ASR cache files.",
                                "",
                                "## Source / Evidence Note",
                                "",
                                f"- Parent audio file: {audio_path}",
                                f"- Parent Source URI: {file_uri(audio_path)}",
                                "- Source type: user-authorized local MP3 audio split into processing chunks.",
                                "- Boundary: chunk `.txt` files are intermediate ASR cache artifacts, not standalone research documents or final deliverables.",
                                "- Final transcript: use the merged `raw/transcript.raw.md` or the central `transcripts/` export.",
                                "",
                            ]
                        ),
                        encoding="utf-8",
                    )
                    break
                except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as error:
                    last_error = error
                    if attempt == retries:
                        raise
                    wait = min(10 * attempt, 30)
                    print(f"retry {attempt}/{retries} {audio_path.name} chunk {chunk['index']}: {error}; wait {wait}s", flush=True)
                    time.sleep(wait)
            else:
                raise RuntimeError(f"Failed chunk {chunk['index']}: {last_error}")
        sections.append(f"## {format_time(chunk['start'])}-{format_time(chunk['end'])}")
        sections.append("")
        sections.append(text)
        sections.append("")
        (raw_dir / "transcript.raw.md").write_text("\n".join(sections), encoding="utf-8")
        print(f"done {audio_path.name} chunk {chunk['index'] + 1}/{len(manifest['chunks'])}", flush=True)
    lesson = {
        "source": str(audio_path),
        "status": "done",
        "chunks": len(manifest["chunks"]),
        "estimated_duration": manifest["estimated_duration"],
        "completed_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    (lesson_dir / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8")
    return lesson


def export_transcript(out_root: Path, lesson_dir: Path, audio_path: Path) -> None:
    transcript_path = lesson_dir / "raw" / "transcript.raw.md"
    if not transcript_path.exists():
        return
    transcripts_dir = out_root / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    target = transcripts_dir / f"{safe_name(audio_path.stem)}.raw.md"
    target.write_text(transcript_path.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe local MP3 files by frame-splitting and short-audio DashScope ASR.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--model", default="qwen3-asr-flash")
    parser.add_argument("--max-seconds", type=float, default=240)
    parser.add_argument("--max-bytes", type=int, default=9_500_000)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-at", default=None, help="Start at first filename containing this text.")
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("DASHSCOPE_API_KEY is not available in process or Windows user environment.", file=sys.stderr)
        return 2
    input_dir = Path(args.input_dir)
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    files = sorted(input_dir.glob("*.mp3"), key=lambda p: p.name)
    if args.start_at:
        files = files[next((i for i, p in enumerate(files) if args.start_at in p.name), len(files)) :]
    if args.limit:
        files = files[: args.limit]
    batch = {"input_dir": str(input_dir), "out_root": str(out_root), "model": args.model, "files": []}
    for index, audio_path in enumerate(files, start=1):
        lesson_dir = out_root / safe_name(audio_path.stem)
        lesson_json = lesson_dir / "lesson.json"
        if lesson_json.exists():
            existing = json.loads(lesson_json.read_text(encoding="utf-8"))
            if existing.get("status") == "done":
                print(f"skip done {audio_path.name}", flush=True)
                export_transcript(out_root, lesson_dir, audio_path)
                batch["files"].append(existing)
                continue
        print(f"lesson {index}/{len(files)} {audio_path.name}", flush=True)
        lesson_dir.mkdir(parents=True, exist_ok=True)
        try:
            lesson = transcribe_lesson(api_key, audio_path, lesson_dir, args.model, args.max_seconds, args.max_bytes, args.retries)
            export_transcript(out_root, lesson_dir, audio_path)
        except Exception as error:  # noqa: BLE001 - preserve restartable batch state
            lesson = {
                "source": str(audio_path),
                "status": "failed",
                "error": str(error),
                "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
            }
            (lesson_dir / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"failed {audio_path.name}: {error}", file=sys.stderr, flush=True)
            batch["files"].append(lesson)
            (out_root / "batch-manifest.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
            return 1
        batch["files"].append(lesson)
        (out_root / "batch-manifest.json").write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
