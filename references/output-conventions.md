# Output Conventions

## Version Note v01

2026-06-08 v01: Created the initial versioned output layout for audio transcript jobs. This version separates evidence inventory, raw transcript, cleaned transcript, notes, final delivery files, logs, and version notes to avoid overwriting previous long-form deliverables.

## Version Note v02

2026-06-08 v02: Updated the default job layout for the standalone skill package. Generated transcript jobs now live under the package-local `jobs/audio-transcript` directory by default so they do not mix with existing project outputs.

## Folder Layout

```text
standalone-skill-xiaoe-audio-transcript-pipeline-v01/jobs/audio-transcript/YYYYMMDD-title-v01/
  job.json
  version-note.md
  source-inventory.json
  source-inventory.md
  raw/
    engine-output.json
    transcript.raw.md
  cleaned/
    transcript.cleaned.md
  notes/
    notes.source-faithful.md
    summary.processed.md
  delivery/
    transcript.docx
  logs/
```

## Version Notes

Every substantial iteration gets a new folder or filename. `version-note.md` should state:

- what source files were used
- what engine or method was used
- what changed in this version
- remaining caveats, missing metadata, or uncertain terms

## Artifact Layers

- `source-inventory.*`: evidence and file metadata.
- `raw/transcript.raw.md`: raw transcript, minimally formatted.
- `cleaned/transcript.cleaned.md`: readable transcript, still source-faithful.
- `notes/notes.source-faithful.md`: ordered reading notes based on the transcript.
- `notes/summary.processed.md`: optional higher-level synthesis.
- `delivery/`: final rich-text or client-facing outputs.
