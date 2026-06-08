# Xiaoe Audio Transcript Pipeline

## Version Note v01

2026-06-08 v01: Added a GitHub-ready workflow README for the audio-to-text pipeline. This document explains the processing chain, setup, commands, restart behavior, output structure, and publishing precautions without exposing any concrete audio or transcript content.

## What This Is

This repository is a reusable audio-to-text workflow for course or replay audio. It is designed for local audio files and China-domestic model providers, with a clear separation between:

- source inventory
- raw ASR transcript
- optional cleaned transcript
- optional reading notes or review
- final collected transcript exports

The workflow treats transcription as an evidence pipeline. It first verifies that usable audio exists, then produces raw transcript artifacts, and only then creates cleaned or summarized layers.

## Privacy Boundary

Do not publish source audio, generated transcripts, chunk cache, logs, or API keys to GitHub.

The public repository should contain only:

- workflow documentation
- scripts
- examples that do not contain private content
- references and contracts
- `.gitignore`

Generated job output should stay local under `jobs/` unless you intentionally create a sanitized sample.

## Provider Strategy

Default route:

- ASR: Alibaba Cloud DashScope / Bailian short-audio ASR, usually `qwen3-asr-flash`
- Long local audio: split local MP3 into API-sized chunks, transcribe each chunk, then merge back to one transcript per lesson
- Cleanup: Qwen or DeepSeek, only after raw transcript exists
- Notes/review: DeepSeek or Qwen, saved as a separate processed layer

Fallback route:

- If a public or signed media URL cannot be fetched by the ASR provider, use local audio files instead.
- If a single API call fails because of temporary network interruption, rerun the batch command. Completed chunks and completed lessons are skipped automatically.
- If billing or quota fails, recharge or switch to another provider, then rerun from the same job folder.

## Directory Layout

```text
standalone-skill-xiaoe-audio-transcript-pipeline-v01/
  README.md
  SKILL.md
  .gitignore
  references/
    engine-contract.md
    cleanup-rules.md
    output-conventions.md
  scripts/
    audio_transcript_pipeline.py
    dashscope_smoke_test.py
    dashscope_asr_smoke_test.py
    deepseek_smoke_test.py
    run_short_audio_pipeline.py
    deepseek_notes_from_cleaned.py
    dashscope_url_transcribe.py
    mp3_frame_splitter.py
    transcribe_local_mp3_batch.py
    collect_transcripts.py
  examples/
  jobs/                  # local generated output, ignored by git
```

## Environment Setup

Use Python 3.10 or newer.

Set API keys in Windows PowerShell:

```powershell
setx DASHSCOPE_API_KEY "your_dashscope_key"
setx DEEPSEEK_API_KEY "your_deepseek_key"
```

`setx` writes the key to the Windows user environment, but it does not update the current PowerShell process. For the current shell, run:

```powershell
$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')
```

Check that the keys are visible:

```powershell
python -c "import os; print(bool(os.getenv('DASHSCOPE_API_KEY')))"
python -c "import os; print(bool(os.getenv('DEEPSEEK_API_KEY')))"
```

## Smoke Tests

Test DashScope text access:

```powershell
python scripts\dashscope_smoke_test.py --model qwen-plus
```

Test DashScope short-audio ASR with a small local audio file:

```powershell
python scripts\dashscope_asr_smoke_test.py --audio "D:\path\to\short-sample.mp3" --model qwen3-asr-flash
```

Test DeepSeek text access:

```powershell
python scripts\deepseek_smoke_test.py --model deepseek-v4-flash
```

Only start large batch transcription after these smoke tests pass.

## Batch Transcription Workflow

Create a versioned job folder:

```powershell
$jobRoot = "D:\path\to\jobs\part-transcript-YYYYMMDD-v01"
New-Item -ItemType Directory -Force -Path $jobRoot | Out-Null
```

Run local MP3 batch transcription:

```powershell
python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash
```

Optional parameters:

```powershell
--max-seconds 240
--max-bytes 9500000
--retries 3
--limit 3
--start-at "filename fragment"
```

The batch script does this:

1. Reads local MP3 files from `--input-dir`.
2. Creates a per-audio lesson folder under `--out-root`.
3. Splits each MP3 by frame boundaries into API-sized chunks.
4. Sends each chunk to DashScope short-audio ASR.
5. Saves chunk-level JSON and text cache.
6. Merges chunk text into one `raw/transcript.raw.md` per audio file.
7. Writes `lesson.json` with status, chunk count, duration estimate, and completion time.
8. Exports each completed transcript into the central `transcripts/` folder.

## Restart And Resume

The workflow is restartable.

If a run stops because of network interruption, quota, billing, or process shutdown, run the same command again with the same `--out-root`.

Behavior on rerun:

- lessons with `lesson.json` status `done` are skipped
- chunk cache files already written are reused
- incomplete lessons continue from the first missing chunk
- final central exports can be regenerated at any time

## Collect Final Transcripts

After batch transcription, collect completed lesson transcripts into one folder:

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

This creates:

```text
$jobRoot/
  transcripts/
    index.md
    index.json
    part2.raw.combined.md
    <one-file-per-audio>.raw.md
```

Use `transcripts/` as the final reading/export folder. Chunk folders are internal evidence and restart cache.

## Optional Cleanup Layer

Run cleanup only after raw transcript files exist.

For a short sample job:

```powershell
python scripts\run_short_audio_pipeline.py `
  --title "sample-title" `
  --audio "D:\path\to\short-sample.mp3"
```

For reading notes from an already cleaned transcript:

```powershell
python scripts\deepseek_notes_from_cleaned.py --job-dir "D:\path\to\job"
```

Keep these layers separate:

- `raw/transcript.raw.md`: ASR output, closest to source audio
- `cleaned/transcript.cleaned.md`: punctuation and readability cleanup
- `notes/notes.source-faithful.md`: source-faithful notes
- `summary.processed.md`: optional higher-level rewrite or extraction

## Output Rules

Every substantial output should include:

- a version note
- a source/evidence note
- source file or source URI
- a boundary statement explaining whether this is raw ASR, cleaned transcript, notes, or processed summary

Do not present raw ASR as factual verification. Transcript text comes from source audio only unless a later review layer explicitly adds external citations.

## Validation Checklist

Before delivery:

```powershell
python scripts\collect_transcripts.py --root "$jobRoot"
```

Then verify:

- `lesson.json` count equals the number of input audio files
- every `lesson.json` has status `done`
- `transcripts/` contains one `.raw.md` per input audio file
- `part2.raw.combined.md` exists
- `index.json` can be parsed as UTF-8 JSON
- final transcript files include `## Version Note` and `## Source / Evidence Note`
- final transcript files do not contain internal chunk markers

Example JSON check:

```powershell
python -c "from pathlib import Path; import json; p=Path(r'D:\path\to\job\transcripts\index.json'); d=json.loads(p.read_text(encoding='utf-8')); print(d['completed'], len(d['items']))"
```

If Chinese text appears garbled in PowerShell output, do not immediately assume the file is damaged. Check the file with UTF-8 reads in Python or open it in a proper editor.

## GitHub Publishing

Initialize git from this package folder:

```powershell
cd D:\path\to\standalone-skill-xiaoe-audio-transcript-pipeline-v01
git init
git add README.md SKILL.md .gitignore scripts references examples agents
git status
git commit -m "Add audio transcript pipeline workflow"
```

Create a GitHub repository, then connect and push:

```powershell
git branch -M main
git remote add origin https://github.com/<your-name>/<your-repo>.git
git push -u origin main
```

Before pushing, confirm that these are not staged:

- `jobs/`
- audio files
- transcript files containing private content
- logs
- `.env`
- API keys
- browser auth/cache folders

## Typical End-To-End Sequence

```powershell
cd D:\path\to\standalone-skill-xiaoe-audio-transcript-pipeline-v01

$env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable('DASHSCOPE_API_KEY','User')

python scripts\dashscope_smoke_test.py --model qwen-plus
python scripts\dashscope_asr_smoke_test.py --audio "D:\path\to\short-sample.mp3" --model qwen3-asr-flash

$jobRoot = "D:\path\to\jobs\audio-transcript-YYYYMMDD-v01"

python scripts\transcribe_local_mp3_batch.py `
  --input-dir "D:\path\to\audio-folder" `
  --out-root "$jobRoot" `
  --model qwen3-asr-flash

python scripts\collect_transcripts.py --root "$jobRoot"
```

The final user-facing transcript files are in:

```text
$jobRoot\transcripts\
```

