from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


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


def call_dashscope(api_key: str, model: str, base_url: str, prompt: str, max_tokens: int = 128) -> dict:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一个简洁的中文助手。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
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
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test DashScope Qwen text access without printing the API key.")
    parser.add_argument("--model", default="qwen-plus")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--prompt", default="请用一句话回答：DashScope API 连通性测试成功代表什么？")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("DASHSCOPE_API_KEY is not available in process or Windows user environment.", file=sys.stderr)
        return 2

    try:
        result = call_dashscope(api_key, args.model, args.base_url, args.prompt)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Network error: {error}", file=sys.stderr)
        return 1

    choice = (result.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    print("DashScope text smoke test: OK")
    print(f"model: {result.get('model') or args.model}")
    print(f"content: {message.get('content', '').strip()}")
    usage = result.get("usage")
    if usage:
        print("usage: " + json.dumps(usage, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
