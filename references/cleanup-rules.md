# Cleanup Rules

## Version Note v01

2026-06-08 v01: Created the initial transcript cleanup and reading-notes rules. This version defines what can be changed between raw and cleaned transcript layers, and why source-faithful notes must remain separate from processed summaries.

## Raw Transcript

Keep the raw layer close to ASR output:

- Preserve source file boundaries.
- Preserve timestamps or chunk ranges.
- Preserve speaker labels only when supported.
- Mark unintelligible audio as `[听不清]`.
- Mark uncertain terms as `[疑似：术语]`.

## Cleaned Transcript

Allowed:

- remove repeated filler words that do not affect meaning
- repair obvious punctuation and sentence breaks
- correct obvious ASR homophones when context is strong
- add section headings based on source order or natural topic transitions

Not allowed:

- rewrite the speaker's argument into a new order
- remove examples, caveats, Q&A, or transitions because they feel verbose
- add unsupported slide text, names, dates, or external facts

## Reading Notes

For source-faithful notes:

- follow the original order
- keep examples under the section where they appeared
- separate main talk, Q&A, and announcements when the transcript supports it
- mark missing or partial sections instead of smoothing over gaps

For processed summaries:

- put synthesis in a separate file or section
- make clear it is extracted from the transcript layer
- avoid using weak metadata as if it came from the audio
