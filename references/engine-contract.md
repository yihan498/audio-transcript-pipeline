# Engine Contract

## Version Note v01

2026-06-08 v01: Created the initial normalized ASR engine contract. This version explains how provider-specific ASR outputs should map into one shared transcript schema so downstream cleanup and notes can reuse the same pipeline.

## Version Note v02

2026-06-08 v02: Switched the recommended engine contract to a China-domestic provider set. This version keeps the same normalized schema but makes DashScope/Bailian, Xfyun, Tencent Cloud, Volcengine, Baidu AI Cloud, Qwen, DeepSeek, Kimi, and local ASR the expected provider families.

## Goal

Every ASR engine should output the same normalized shape so cleanup, notes, and document generation do not depend on a single vendor.

## Normalized JSON

```json
{
  "job_id": "20260608-course-v01",
  "engine": "dashscope-file-asr",
  "engine_model": "fun-asr",
  "language": "zh",
  "source_files": [
    {
      "path": "audio/lesson-01.mp3",
      "duration_seconds": 3600
    }
  ],
  "segments": [
    {
      "source_file": "audio/lesson-01.mp3",
      "start": 0.0,
      "end": 42.5,
      "speaker": null,
      "text": "这里是转录文本。",
      "confidence": null,
      "uncertain": false
    }
  ],
  "warnings": []
}
```

## Adapter Rules

- Keep missing values as `null`; do not invent duration, speaker, confidence, or timestamps.
- Preserve vendor raw output under `raw/engine-output.*`.
- Normalize each audio file separately before merging course-level output.
- Use role labels only when supported by source or diarization output.
- If an engine returns plain text only, create one segment per file or per chunk with coarse timestamps.

## Engine Notes

- `dashscope-file-asr`: default domestic option for recorded course audio when Alibaba Cloud/Bailian access is available; use `fun-asr` for balanced quality and `paraformer-v2` for lower cost.
- `xfyun-lfasr`: useful for long-form Chinese speech transcription and speaker-oriented speech products.
- `tencent-asr`, `volcengine-asr`, `baidu-asr`: reasonable alternates when an existing domestic cloud account is easier to pay or integrate.
- `local-whisper`: useful when avoiding cloud APIs is required; slower and may need stronger punctuation cleanup.
- Text cleanup models should stay domestic by default: Qwen, DeepSeek, Kimi, GLM, MiniMax, or equivalent.
