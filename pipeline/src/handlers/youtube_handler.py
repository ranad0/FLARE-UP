"""Convert user-provided YouTube VTT/SRT captions into timestamped records.

The handler does not fetch videos, scrape YouTube, or infer scientific meaning.
It only structures a caption file that the user is authorized to access.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR

TIMESTAMP_RE = re.compile(
    r"(?:(\d{2,}):)?(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
    r"(?:(\d{2,}):)?(\d{2}):(\d{2})[,.](\d{3})"
)
TAG_RE = re.compile(r"<[^>]*>")


def _seconds(hours: str | None, minutes: str, seconds: str, millis: str) -> float:
    return (int(hours or 0) * 3600) + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_caption_text(content: str) -> list[dict[str, object]]:
    """Parse WebVTT or SubRip blocks, retaining cue time boundaries."""
    cues: list[dict[str, object]] = []
    block: list[str] = []

    def emit() -> None:
        if not block:
            return
        timestamp_index = next((i for i, line in enumerate(block) if "-->" in line), None)
        if timestamp_index is None:
            return
        match = TIMESTAMP_RE.search(block[timestamp_index])
        if not match:
            return
        start = _seconds(*match.group(1, 2, 3, 4))
        end = _seconds(*match.group(5, 6, 7, 8))
        text = " ".join(
            TAG_RE.sub("", html.unescape(line)).strip()
            for line in block[timestamp_index + 1 :]
            if line.strip() and not line.strip().startswith(("NOTE", "STYLE", "REGION"))
        ).strip()
        if text and end >= start:
            cues.append({"cue_index": len(cues) + 1, "start_seconds": start, "end_seconds": end, "text": text})

    for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip():
            block.append(line.strip())
        else:
            emit()
            block = []
    emit()
    return cues


def handle_youtube_transcript(source_path: Path) -> tuple[Path, int]:
    """Write one video metadata record followed by timestamped transcript cues."""
    relative_path = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative_path).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = source_path.read_text(encoding="utf-8-sig")
    cues = parse_caption_text(content)
    if not cues:
        raise ValueError("No valid timestamped VTT/SRT caption cues were parsed.")

    source_file = source_path.name
    source_relative_path = relative_path.as_posix()
    base = {
        "source_file": source_file,
        "source_relative_path": source_relative_path,
        "investigation_id": None,
    }
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps({**base, "record_type": "video_document", "caption_format": source_path.suffix.lower().lstrip(".")}, ensure_ascii=False) + "\n")
        for cue in cues:
            output.write(json.dumps({**base, "record_type": "transcript_segment", **cue}, ensure_ascii=False) + "\n")
    return output_path, len(cues)
