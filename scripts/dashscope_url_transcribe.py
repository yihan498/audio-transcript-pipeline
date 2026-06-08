from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import requests


DEFAULT_REGION = "dashscope.aliyuncs.com"


def get_api_key() -> str | None:
    key = os.getenv("DASHSCOPE_API_KEY")
    if key:
        return key
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def submit_task(api_key: str, region: str, model: str, url: str, enable_words: bool) -> dict:
    endpoint = f"https://{region}/api/v1/services/audio/asr/transcription"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    if model.startswith("qwen3-asr"):
        payload = {
            "model": model,
            "input": {"file_url": url},
            "parameters": {
                "channel_id": [0],
                "enable_itn": True,
                "enable_words": enable_words,
            },
        }
    else:
        payload = {
            "model": model,
            "input": {"file_urls": [url]},
            "parameters": {
                "channel_id": [0],
                "language_hints": ["zh"],
            },
        }
    response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=60)
    return {"status_code": response.status_code, "body": response.json()}


def fetch_task(api_key: str, region: str, task_id: str) -> dict:
    endpoint = f"https://{region}/api/v1/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    response = requests.get(endpoint, headers=headers, timeout=60)
    return {"status_code": response.status_code, "body": response.json()}


def wait_for_task(api_key: str, region: str, task_id: str, poll_seconds: int, timeout_seconds: int) -> dict:
    started = time.time()
    latest: dict | None = None
    while True:
        latest = fetch_task(api_key, region, task_id)
        body = latest.get("body") or {}
        status = ((body.get("output") or {}).get("task_status") or "").upper()
        print(f"task {task_id}: {status or 'UNKNOWN'}")
        if status in {"SUCCEEDED", "FAILED", "CANCELED"}:
            return latest
        if time.time() - started > timeout_seconds:
            raise TimeoutError(f"Task did not finish within {timeout_seconds} seconds")
        time.sleep(poll_seconds)


def download_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def result_urls(task_body: dict) -> list[str]:
    output = task_body.get("output") or {}
    urls: list[str] = []
    for item in output.get("results") or []:
        if isinstance(item, dict):
            for key in ["transcription_url", "result_url", "url"]:
                value = item.get(key)
                if value:
                    urls.append(value)
    for key in ["transcription_url", "result_url", "url"]:
        value = output.get(key)
        if value:
            urls.append(value)
    return urls


def collect_text(result: dict) -> str:
    parts: list[str] = []
    transcripts = result.get("transcripts") or []
    for transcript in transcripts:
        text = transcript.get("text") if isinstance(transcript, dict) else None
        if text:
            parts.append(text.strip())
        for sentence in (transcript.get("sentences") or []) if isinstance(transcript, dict) else []:
            sentence_text = sentence.get("text")
            if sentence_text and not text:
                parts.append(sentence_text.strip())
    if not parts and result.get("text"):
        parts.append(str(result["text"]).strip())
    return "\n".join(p for p in parts if p)


def write_outputs(out_dir: Path, url: str, model: str, submit_response: dict, final_response: dict, result_docs: list[dict]) -> None:
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "submit-response.json").write_text(json.dumps(submit_response, ensure_ascii=False, indent=2), encoding="utf-8")
    (raw_dir / "task-final-response.json").write_text(json.dumps(final_response, ensure_ascii=False, indent=2), encoding="utf-8")
    for index, doc in enumerate(result_docs, start=1):
        (raw_dir / f"transcription-result-{index:02d}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    text = "\n\n".join(collect_text(doc) for doc in result_docs).strip()
    transcript = [
        "# Raw Transcript",
        "",
        f"- Source URL: {url}",
        "- Engine: dashscope-url-transcribe",
        f"- Model: {model}",
        "",
        "## Transcript",
        "",
        text,
        "",
    ]
    (raw_dir / "transcript.raw.md").write_text("\n".join(transcript), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit a public media URL to DashScope async ASR and save raw transcript outputs.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model", default="qwen3-asr-flash-filetrans")
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--enable-words", action="store_true")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("DASHSCOPE_API_KEY is not available in process or Windows user environment.", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    submit_response = submit_task(api_key, args.region, args.model, args.url, args.enable_words)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    (out_dir / "raw" / "submit-response.json").write_text(json.dumps(submit_response, ensure_ascii=False, indent=2), encoding="utf-8")
    if submit_response["status_code"] != 200:
        print(json.dumps(submit_response, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    task_id = ((submit_response.get("body") or {}).get("output") or {}).get("task_id")
    if not task_id:
        print("No task_id returned", file=sys.stderr)
        return 1
    final_response = wait_for_task(api_key, args.region, task_id, args.poll_seconds, args.timeout_seconds)
    if final_response["status_code"] != 200:
        print(json.dumps(final_response, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    task_status = (((final_response.get("body") or {}).get("output") or {}).get("task_status") or "").upper()
    if task_status != "SUCCEEDED":
        write_outputs(out_dir, args.url, args.model, submit_response, final_response, [])
        print(json.dumps(final_response, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    docs = []
    for url in result_urls(final_response["body"]):
        docs.append(download_json(url))
    write_outputs(out_dir, args.url, args.model, submit_response, final_response, docs)
    print(out_dir)
    print(out_dir / "raw" / "transcript.raw.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
