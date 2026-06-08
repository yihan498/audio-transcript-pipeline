# Audio Transcript Pipeline

[中文说明](README.zh-CN.md)

Turn a folder of long audio files into readable Markdown transcripts.

Supports **long-audio chunking, ASR transcription, resumable batch runs, central transcript export, optional cleanup, and reading notes**. It is designed for course audio, replay recordings, meetings, interviews, and similar batch transcription tasks.

---

## Core Workflow

1. Prepare local MP3 audio files.
2. Configure API keys.
3. Run smoke tests to confirm model access and billing.
4. Batch transcribe the audio folder.
5. If the run stops, rerun with the same output folder to resume.
6. Collect all completed transcripts into `transcripts/`.
7. Optionally generate cleaned transcripts, reading notes, or review outputs.

---

## Features

| Feature | Description |
|---------|-------------|
| Local batch audio processing | Scans `.mp3` files in a folder |
| Long-audio chunking | Splits MP3 files into API-sized chunks |
| ASR transcription | Uses DashScope / Bailian short-audio ASR by default |
| Resumable runs | Skips completed files and chunks |
| Central export | One `.raw.md` per audio file plus a combined file |
| Layered outputs | Keeps raw transcripts, cleaned transcripts, and notes separate |
| Privacy first | Audio, transcripts, logs, and keys are excluded by default |

---

## When To Use It

Use this project for:

- Course audio, replay audio, meeting recordings, and interviews
- Audio files too long for a single short-audio ASR call
- Batch jobs that may need to resume after interruption
- Centralized transcript output
- Optional cleanup, notes, or summaries based on raw transcripts

Not ideal for:

- Summarizing videos when no audio, subtitle, or transcript source is available
- Replacing source-faithful transcription with free-form summaries
- Publishing private audio or generated transcript content

---

## How It Works

```text
local audio folder
  -> scan MP3 files
  -> split long audio
  -> call ASR per chunk
  -> save chunk cache
  -> merge one raw transcript per audio file
  -> export to transcripts/
  -> optional cleanup / notes / review
```

Key points:

- **Chunking**: long audio is split to fit API limits.
- **Caching**: each chunk result is saved for restart and debugging.
- **Merging**: chunk transcripts are merged per audio file.
- **Central export**: final reading files live under `transcripts/`.

---

## Prerequisites

- Windows / macOS / Linux; examples below use Windows PowerShell
- Python 3.10+
- DashScope / Bailian API key
- Optional: DeepSeek API key

---

## Configure API Keys

In PowerShell:

```powershell
setx DASHSCOPE_API_KEY "your_dashscope_key"
setx DEEPSEEK_API_KEY "your_deepseek_key"
```

`setx` does not update the current PowerShell window. Refresh the current process:

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')
```

Check visibility:

```powershell
python -c "import os; print(bool(os.getenv('DASHSCOPE_API_KEY')))"
python -c "import os; print(bool(os.getenv('DEEPSEEK_API_KEY')))"
```

---

## Quick Start

Enter the project root:

```powershell
cd D:\path\to\audio-transcript-pipeline
```

### Step 1: Smoke Tests

Test DashScope text access:

```powershell
python scripts\dashscope_smoke_test.py --model qwen-plus
```

Test ASR with a short local audio file:

```powershell
python scripts\dashscope_asr_smoke_test.py `
  --audio "D:\path\to\short-sample.mp3" `
  --model qwen3-asr-flash
```

Optional: test DeepSeek:

```powershell
python scripts\deepseek_smoke_test.py --model deepseek-v4-flash
```

### Step 2: Batch Transcription

```powershell
$jobRoot = "D:\path\to\jobs\audio-transcript-YYYYMMDD-v01"

python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash
```

### Step 3: Collect Transcripts

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

Final transcript files are in:

```text
$jobRoot\transcripts\
```

---

## Batch Command Options

```text
--input-dir     local audio folder
--out-root      output directory for this job
--model         ASR model, default qwen3-asr-flash
--max-seconds   target seconds per chunk, default 240
--max-bytes     max bytes per chunk, default 9500000
--retries       retry count for a failed chunk
--limit         process only the first N files for testing
--start-at      start at the first filename containing this text
```

---

## Output Format

```text
jobRoot/
  <audio-title>/
    chunks/
      chunk_0000.mp3
      chunks-manifest.json
    raw/
      chunk-results/
        chunk_0000.json
        chunk_0000.txt
      transcript.raw.md
    lesson.json
  transcripts/
    index.md
    index.json
    part2.raw.combined.md
    <audio-title>.raw.md
```

Recommended files:

- `transcripts/index.md`: transcript index
- `transcripts/index.json`: machine-readable index
- `transcripts/part2.raw.combined.md`: combined transcript file
- `transcripts/<audio-title>.raw.md`: one transcript per audio file

Internal files:

- `chunks/`: audio chunks
- `raw/chunk-results/`: chunk cache and raw API results

---

## Resume After Interruption

If the job stops midway, run the same command again with the same `--out-root`:

```powershell
python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash
```

The script will:

- skip completed audio files
- reuse completed chunks
- continue from missing chunks
- allow central exports to be regenerated later

---

## Optional Cleanup And Notes

Short-audio end-to-end example:

```powershell
python scripts\run_short_audio_pipeline.py `
  --title "sample-title" `
  --audio "D:\path\to\short-sample.mp3"
```

Generate reading notes from a cleaned transcript:

```powershell
python scripts\deepseek_notes_from_cleaned.py --job-dir "D:\path\to\job"
```

Recommended layers:

```text
raw/transcript.raw.md              raw ASR transcript
cleaned/transcript.cleaned.md      cleaned transcript
notes/notes.source-faithful.md     source-faithful reading notes
summary.processed.md               optional processed summary
```

---

## Validation Checklist

Before delivery:

- input audio count matches `lesson.json` count
- every `lesson.json` has status `done`
- `transcripts/` contains the expected number of `.raw.md` files
- `part2.raw.combined.md` exists
- `index.json` parses as UTF-8 JSON
- final transcript files do not contain internal chunk markers

JSON check:

```powershell
python -c "from pathlib import Path; import json; p=Path(r'D:\path\to\job\transcripts\index.json'); d=json.loads(p.read_text(encoding='utf-8')); print(d['completed'], len(d['items']))"
```

---

## File Structure

```text
audio-transcript-pipeline/
  README.md
  README.zh-CN.md
  README.en.md
  scripts/
  references/
  examples/
  agents/
  .gitignore
```

Main scripts:

| Script | Purpose |
|--------|---------|
| `transcribe_local_mp3_batch.py` | batch split and transcribe local MP3 files |
| `collect_transcripts.py` | collect completed transcripts |
| `mp3_frame_splitter.py` | MP3 frame-level splitting |
| `dashscope_smoke_test.py` | test DashScope text API |
| `dashscope_asr_smoke_test.py` | test short-audio ASR |
| `deepseek_smoke_test.py` | test DeepSeek API |
| `run_short_audio_pipeline.py` | short-audio end-to-end sample |
| `deepseek_notes_from_cleaned.py` | generate notes from a cleaned transcript |

---

## Troubleshooting

### Python cannot see the API key after `setx`

Refresh the current PowerShell process:

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')
```

### DashScope cannot access an audio URL

Signed platform URLs may not be accessible to the ASR provider. Download the audio locally and use `transcribe_local_mp3_batch.py`.

### The job fails midway

Rerun with the same `--out-root`; completed work is skipped.

### Chinese text looks garbled in PowerShell

Do not immediately assume the file is corrupted. Read it as UTF-8 with Python or open it in a UTF-8-aware editor.

### Final transcripts are scattered

Run:

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

Then use:

```text
$jobRoot\transcripts\
```

---

## Privacy

Do not commit:

- audio files
- real transcripts
- `jobs/` outputs
- chunk cache
- logs
- `.env`
- API keys
- browser login state

These are excluded by `.gitignore`, but always check before committing.
