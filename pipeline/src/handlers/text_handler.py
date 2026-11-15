import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR


def get_investigation_id(relative_path: Path) -> str:
    if len(relative_path.parts) >= 2:
        return relative_path.parts[0]

    return "unassigned"


def handle_text(source_path: Path) -> tuple[Path, int]:
    """احفظ محتوى TXT كما هو داخل سجل JSONL واحد."""
    relative_path = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative_path).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw_bytes = source_path.read_bytes()
    content = None
    detected_encoding = None

    for encoding in ("utf-8-sig", "cp1252"):
        try:
            content = raw_bytes.decode(encoding)
            detected_encoding = encoding
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise UnicodeError("Could not decode this text file as UTF-8 or Windows-1252.")

    record = {
        "record_type": "text_document",
        "source_file": source_path.name,
        "source_relative_path": relative_path.as_posix(),
        "investigation_id": get_investigation_id(relative_path),
        "encoding_used": detected_encoding,
        "line_count": len(content.splitlines()),
        "text": content,
    }

    with output_path.open("w", encoding="utf-8") as output_file:
        output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    return output_path, record["line_count"]


def main() -> None:
    text_files = sorted(
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".txt"
    )

    if not text_files:
        print(f"No TXT files found in: {RAW_DATA_DIR}")
        return

    for source_path in text_files:
        try:
            output_path, line_count = handle_text(source_path)
            print(f"Processed: {source_path.name}")
            print(f"Lines: {line_count}")
            print(f"Output: {output_path}")
        except (OSError, UnicodeError) as error:
            print(f"FAILED: {source_path}")
            print(f"Reason: {error}")


if __name__ == "__main__":
    main()