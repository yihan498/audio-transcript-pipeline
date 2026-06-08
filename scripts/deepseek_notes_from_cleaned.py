from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from deepseek_smoke_test import call_deepseek, get_api_key  # noqa: E402


def extract_content(result: dict) -> str:
    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    return (message.get("content") or "").strip()


def build_prompt(cleaned_text: str) -> str:
    return "\n".join(
        [
            "请基于下面的 cleaned transcript 生成忠实阅读笔记。",
            "要求：",
            "1. 严格按原文顺序整理，不要重排成方法论文章。",
            "2. 先列出这段内容讲了什么，再按自然段/主题列要点。",
            "3. 保留原文中的例子、提醒、课程名、日期和行动要求。",
            "4. 不要加入原文没有的信息；不确定内容标注为 [需回听确认]。",
            "5. 最后给一个“转写质量复核”小节，只指出明显错词、截断、可疑术语。",
            "",
            "cleaned transcript:",
            cleaned_text,
        ]
    )


def update_job_status(job_dir: Path, status: str) -> None:
    job_path = job_dir / "job.json"
    if not job_path.exists():
        return
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job["status"] = status
    job["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate source-faithful notes from a cleaned transcript using DeepSeek.")
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-cleaned-chars", type=int, default=12000)
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    cleaned_path = job_dir / "cleaned" / "transcript.cleaned.md"
    if not cleaned_path.exists():
        print(f"Cleaned transcript not found: {cleaned_path}", file=sys.stderr)
        return 2

    api_key = get_api_key()
    if not api_key:
        print("DEEPSEEK_API_KEY is not available in process or Windows user environment.", file=sys.stderr)
        return 2

    cleaned_text = cleaned_path.read_text(encoding="utf-8")
    if len(cleaned_text) > args.max_cleaned_chars:
        cleaned_text = cleaned_text[: args.max_cleaned_chars] + "\n\n[后续内容因单次测试长度限制截断，批量流程应分段处理。]"

    try:
        result = call_deepseek(api_key, args.model, args.base_url, build_prompt(cleaned_text), max_tokens=args.max_tokens)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {body}", file=sys.stderr)
        update_job_status(job_dir, "notes_failed")
        return 1
    except urllib.error.URLError as error:
        print(f"Network error: {error}", file=sys.stderr)
        update_job_status(job_dir, "notes_failed")
        return 1

    notes_text = extract_content(result)
    notes_dir = job_dir / "notes"
    logs_dir = job_dir / "logs"
    notes_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "deepseek-notes-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    notes = [
        "# Source-Faithful Notes",
        "",
        "- Notes provider: deepseek",
        f"- Notes model: {args.model}",
        "- Policy: source-faithful notes; no unsupported additions.",
        "",
        notes_text,
        "",
    ]
    (notes_dir / "notes.source-faithful.md").write_text("\n".join(notes), encoding="utf-8")
    update_job_status(job_dir, "notes_generated")
    print(notes_dir / "notes.source-faithful.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
