---
name: xiaoe-audio-transcript-pipeline
description: Build and run a China-domestic audio-to-transcript workflow for Xiaoe Tech course or replay audio, including source inventory, versioned output folders, domestic ASR engine selection, raw transcript capture, cleanup, faithful notes, and delivery QA. Use when the user has complete audio files and wants transcription, transcript cleanup, reading notes, summaries, or a reusable workflow using providers such as Alibaba Cloud DashScope/Bailian, Xfyun, Tencent Cloud, Volcengine, Baidu AI Cloud, Qwen, DeepSeek, Kimi, or local open-source ASR.
---

# Xiaoe Audio Transcript Pipeline

## Version Note v01

2026-06-08 v01: Created the initial project-level workflow skill for complete audio-to-transcript delivery. This version defines source inventory, pluggable ASR engine selection, normalized raw transcript output, cleanup, notes, and delivery QA so future transcription work can run consistently without being locked to one API provider.

## Version Note v02

2026-06-08 v02: Moved the workflow into a standalone versioned skill folder and changed the default job output location to the package-local `jobs/audio-transcript` directory. This keeps the new skill, scripts, examples, and generated transcript jobs separate from the existing Xiaoe project files.

## Version Note v03

2026-06-08 v03: Set `balanced-quality` as an initial mixed-provider processing profile for comparing cost and quality. This profile has been superseded by v04 for domestic-only operation.

## Version Note v04

2026-06-08 v04: Changed the default route to `domestic-balanced` after international API payment was not available. This version uses China-domestic ASR plus Chinese LLM providers for transcription, cleanup, notes, and review; the balanced default prefers DashScope/Bailian `fun-asr`, while the low-cost profile keeps `paraformer-v2`.

## Version Note v05

2026-06-08 v05: Updated DeepSeek defaults from the soon-to-be-deprecated chat alias to current v4 model names. This version uses `deepseek-v4-pro` for balanced review and `deepseek-v4-flash` for low-cost cleanup.

## Version Note v06

2026-06-08 v06: Added a DashScope smoke-test step before ASR integration. This version verifies `DASHSCOPE_API_KEY`, Qwen model access, billing, and network connectivity with a minimal text request before spending time on audio transcription adapters.

## Version Note v07

2026-06-08 v07: Added a short-audio DashScope ASR smoke test for local files under 10MB. This verifies domestic audio transcription access with a small sample before building the long-audio asynchronous file-transcription adapter.

## Version Note v08

2026-06-08 v08: Added a DeepSeek smoke-test step for the domestic review layer. This version verifies `DEEPSEEK_API_KEY`, model access, billing, and network connectivity with a minimal request before using DeepSeek for transcript review or reading notes.

## Version Note v09

2026-06-08 v09: Added a short-audio end-to-end pipeline script. This version creates a versioned job, runs DashScope short-audio ASR, writes the raw transcript layer, calls Qwen for a source-faithful cleaned transcript, and saves outputs under the standalone package job directory.

## Version Note v10

2026-06-08 v10: Increased the Qwen cleanup output budget for end-to-end transcript runs. This fixes a truncation found during the first sample run, where the cleanup layer reused the small smoke-test token limit.

## Version Note v11

2026-06-08 v11: Added a DeepSeek notes layer script. This version turns a cleaned transcript into source-faithful reading notes and a brief review without changing the raw or cleaned transcript layers.

## Version Note v12

2026-06-08 v12: Increased the DeepSeek notes output budget after the first notes sample exhausted its small smoke-test token limit in reasoning output. This version allows notes generation to produce visible source-faithful notes.

## Version Note v13

2026-06-08 v13: Added a DashScope asynchronous URL transcription script for long audio. This version can submit public media URLs to `qwen3-asr-flash-filetrans` or `fun-asr`, poll the task, fetch transcription result URLs, and save raw JSON plus markdown transcripts.

## Version Note v14

2026-06-08 v14: Added a local MP3 frame-splitting fallback after signed Xiaoe media URLs returned `FILE_403_FORBIDDEN` from DashScope async ASR. This version can split local MP3 files into short chunks and transcribe them with the already validated short-audio ASR path.

## Version Note v15

2026-06-08 v15: Added a transcript aggregation layer for chunked local ASR. This version keeps chunks as internal evidence but exports one integrated transcript per lesson plus a combined index under a central `transcripts/` folder so final outputs are not scattered across chunk directories.

## Version Note v16

2026-06-08 v16: Added source/evidence and version-note headers to generated raw transcript artifacts. This version makes clear that outputs are ASR transcriptions from user-authorized local MP3 files, with chunk files kept only as internal processing evidence.

## Version Note v17

2026-06-08 v17: Added machine-detectable local source URIs and chunk-level version headers. This version uses `file:///` source URIs for local evidence and strips chunk cache headers when merging so final transcripts remain clean.

## Core Rule

Treat audio transcription as an evidence workflow. First confirm that local audio files exist and are sufficient, then create separate raw, cleaned, notes, and delivery layers. Do not summarize or polish before a raw transcript exists.

## Workflow

1. Create a versioned job folder.
   - Use the package-local `jobs/audio-transcript/<date>-<slug>-vNN/` by default.
   - Do not overwrite previous long-form outputs.
   - Run `scripts/audio_transcript_pipeline.py init-job ...` when possible.

2. Inventory the audio.
   - Record file path, size, extension, duration when available, and any missing metadata.
   - Prefer `ffprobe` for duration when installed; otherwise keep duration as missing instead of guessing.
   - Save `source-inventory.json` and `source-inventory.md`.

3. Choose a transcription engine.
   - Use `dashscope-file-asr` as the default domestic ASR plan for complete local audio files.
   - Use `xfyun-lfasr`, `tencent-asr`, `volcengine-asr`, or `baidu-asr` when those accounts, quotas, or recognition features fit the job better.
   - Use `local-whisper` or other local open-source ASR only when avoiding cloud APIs is more important than speed and punctuation quality.
   - Keep engine output normalized to the contract in `references/engine-contract.md`.

## Default Profile

Use `domestic-balanced` unless the user asks for the cheapest or highest-quality path:

- Transcription: Alibaba Cloud DashScope/Bailian file ASR, preferably `fun-asr` for recorded course audio; use `paraformer-v2` for a lower-cost fallback when quality is acceptable.
- Cleanup and segmentation: Qwen Plus or DeepSeek `deepseek-v4-flash` / `deepseek-v4-pro`, depending on available API keys and current pricing.
- Final reading notes or spot review: Kimi, Qwen stronger model, or DeepSeek `deepseek-v4-pro` for difficult sections.
- Keep all API keys, billing, and generated data within domestic providers unless the user explicitly changes the policy.

4. Produce the raw transcript layer.
   - Save raw engine output under `raw/`.
   - Save normalized transcript as `transcript.raw.md`.
   - Preserve timestamps, file boundaries, speaker labels, and uncertain fragments.

5. Produce the cleanup layer only after raw transcript exists.
   - Save `transcript.cleaned.md`.
   - Remove obvious filler and repair punctuation, but preserve order, examples, caveats, and meaning.
   - Mark uncertain terms instead of silently inventing corrections.

6. Produce notes or summaries as a separate processed layer.
   - For "讲了什么", "分为哪些部分", or "阅读笔记", stay source-faithful.
   - For "提炼", "方法论", or "改成文章", add a separate processed layer.

7. Validate the delivery.
   - Check that headings, timestamps, speaker labels, and source boundaries are present.
   - For `.docx` outputs, verify document structure, not only file existence.

## CLI

Project-local helper:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\audio_transcript_pipeline.py init-job `
  --title "课程名称" `
  --audio "path\to\audio1.mp3" "path\to\audio2.m4a" `
  --profile domestic-balanced
```

Inventory an existing job:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\audio_transcript_pipeline.py inventory `
  --job-dir "standalone-skill-xiaoe-audio-transcript-pipeline-v01\jobs\audio-transcript\20260608-course-v01" `
  --audio "path\to\audio-dir"
```

Smoke-test DashScope text access:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\dashscope_smoke_test.py --model qwen-plus
```

Smoke-test DashScope short-audio ASR:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\dashscope_asr_smoke_test.py --audio "path\to\short.mp3"
```

Smoke-test DeepSeek text access:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\deepseek_smoke_test.py --model deepseek-v4-flash
```

Run a short-audio end-to-end sample:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\run_short_audio_pipeline.py `
  --title "小样本测试" `
  --audio "path\to\short.mp3"
```

Generate DeepSeek notes from a cleaned transcript:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\deepseek_notes_from_cleaned.py `
  --job-dir "standalone-skill-xiaoe-audio-transcript-pipeline-v01\jobs\audio-transcript\YYYYMMDD-title-v01"
```

Transcribe a long public media URL asynchronously:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\dashscope_url_transcribe.py `
  --url "https://example.com/audio.mp3" `
  --out-dir "path\to\lesson-output"
```

Transcribe local MP3 files by splitting them into short chunks:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\transcribe_local_mp3_batch.py `
  --input-dir "path\to\mp3-dir" `
  --out-root "path\to\part2-transcript"
```

Collect completed lesson transcripts into one folder:

```powershell
python standalone-skill-xiaoe-audio-transcript-pipeline-v01\scripts\collect_transcripts.py `
  --root "path\to\part2-transcript"
```

## Reference Map

- `references/engine-contract.md`: normalized transcript schema and engine adapter rules.
- `references/output-conventions.md`: versioned folder structure and artifact names.
- `references/cleanup-rules.md`: raw-to-cleaned transcript and notes rules.

## Guardrails

- Do not present title, intro, tags, or missing subtitle access as a transcript-derived summary.
- Do not convert unavailable duration, subtitles, chapters, or speaker labels into factual negative claims.
- Do not merge multiple lessons into one continuous transcript unless source boundaries support it.
- If Chinese appears garbled in terminal output, check file encoding and rendered content before declaring the file damaged.
