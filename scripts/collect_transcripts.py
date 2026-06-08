from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


def safe_name(value: str) -> str:
    value = re.sub(r'[<>:"/\\\\|?*]+', "-", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:150] or "audio"


def file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def ensure_header(text: str, source: Path) -> str:
    if "## Version Note v01" in text and "## Source / Evidence Note" in text and "Source URI:" in text:
        return text
    header = [
        "# Raw Transcript",
        "",
        "## Version Note v01",
        "",
        "2026-06-08 v01: Exported this lesson-level raw transcript into the central Part2 transcripts folder. The content was transcribed from a user-authorized local MP3 file and merged from API-sized chunks.",
        "",
        "## Source / Evidence Note",
        "",
        "- Source type: user-authorized local MP3 audio file.",
        f"- Source file: {source}",
        f"- Source URI: {file_uri(source)}",
        "- Source sufficiency: original audio content is available and was used for transcription.",
        "- Method: local MP3 frame splitting -> DashScope short-audio ASR -> merged lesson transcript.",
        "- Boundary: this is an automatic raw transcript, not a factual verification, citation-backed research note, or polished summary.",
        "- External references: none used for content claims; all transcript text comes from the source audio.",
        "",
        "## Transcript Body",
        "",
    ]
    if text.startswith("# Raw Transcript"):
        lines = text.splitlines()
        body_start = 1
        while body_start < len(lines) and not lines[body_start].startswith("## "):
            body_start += 1
        return "\n".join(header + lines[body_start:]) + "\n"
    return "\n".join(header) + text.strip() + "\n"


def combined_header(root: Path) -> list[str]:
    return [
        "# Part2 Raw Transcripts",
        "",
        "## Version Note v01",
        "",
        "2026-06-08 v01: Combined completed Part2 lesson-level raw transcripts into a single file. This is a central export layer; individual lesson transcripts remain available in this folder.",
        "",
        "## Source / Evidence Note",
        "",
        "- Source type: user-authorized local MP3 audio files from Part2.",
        f"- Source root: {root}",
        f"- Source root URI: {file_uri(root)}",
        "- Source sufficiency: original audio files were available and used for transcription.",
        "- Method: local MP3 frame splitting -> DashScope short-audio ASR -> merged lesson transcripts -> combined Part2 export.",
        "- Boundary: this is an automatic raw transcript collection, not a factual verification, citation-backed research report, or polished summary.",
        "- External references: none used for content claims; transcript text comes from source audio only.",
        "",
    ]


def collect(root: Path) -> dict:
    transcripts_dir = root / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    combined_sections = combined_header(root)
    for lesson_json in sorted(root.glob("*/lesson.json"), key=lambda p: p.parent.name):
        data = json.loads(lesson_json.read_text(encoding="utf-8"))
        if data.get("status") != "done":
            continue
        source = Path(data.get("source", lesson_json.parent.name))
        raw = lesson_json.parent / "raw" / "transcript.raw.md"
        if not raw.exists():
            continue
        target_name = f"{safe_name(source.stem)}.raw.md"
        target = transcripts_dir / target_name
        text = raw.read_text(encoding="utf-8")
        exported_text = ensure_header(text, source)
        target.write_text(exported_text, encoding="utf-8")
        rows.append(
            {
                "title": source.stem,
                "source": str(source),
                "transcript": str(target),
                "chars": len(exported_text),
                "chunks": data.get("chunks"),
                "estimated_duration": data.get("estimated_duration"),
            }
        )
        combined_sections.append(f"## {source.stem}")
        combined_sections.append("")
        combined_sections.append(exported_text)
        combined_sections.append("")
    index = {"root": str(root), "completed": len(rows), "transcripts_dir": str(transcripts_dir), "items": rows}
    (transcripts_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Part2 Transcript Index", ""]
    for item in rows:
        lines.append(f"- [{item['title']}]({Path(item['transcript']).name})")
    lines.append("")
    (transcripts_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    (transcripts_dir / "part2.raw.combined.md").write_text("\n".join(combined_sections), encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect completed per-lesson raw transcripts into one folder.")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    index = collect(Path(args.root))
    print(json.dumps({"completed": index["completed"], "transcripts_dir": index["transcripts_dir"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
