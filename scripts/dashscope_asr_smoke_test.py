from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3-asr-flash"
MAX_BYTES = 10 * 1024 * 1024


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


def audio_to_data_url(path: Path) -> str:
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"Audio file is {size} bytes; short-audio smoke test requires <= {MAX_BYTES} bytes.")
    mime_type = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def call_dashscope_asr(api_key: str, model: str, base_url: str, audio_path: Path) -> dict:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_to_data_url(audio_path),
                        },
                    },
                ],
            }
        ],
        "asr_options": {
            "language": "zh",
            "enable_itn": True,
        },
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test DashScope short-audio ASR without printing the API key.")
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--max-preview-chars", type=int, default=500)
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        return 2

    api_key = get_api_key()
    if not api_key:
        print("DASHSCOPE_API_KEY is not available in process or Windows user environment.", file=sys.stderr)
        return 2

    try:
        result = call_dashscope_asr(api_key, args.model, args.base_url, audio_path)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Network error: {error}", file=sys.stderr)
        return 1

    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = (message.get("content") or "").strip()
    print("DashScope ASR smoke test: OK")
    print(f"model: {result.get('model') or args.model}")
    print(f"audio: {audio_path}")
    print("content_preview:")
    print(content[: args.max_preview_chars])
    usage = result.get("usage")
    if usage:
        print("usage: " + json.dumps(usage, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
