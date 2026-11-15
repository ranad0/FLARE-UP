"""Process selected non-investigation NASA reference folders without a global rerun."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import RAW_DATA_DIR, REPORTS_DIR
from handlers.csv_handler import handle_csv
from handlers.excel_handler import handle_excel
from handlers.ooxml_handler import handle_docx, handle_pptx
from handlers.pdf_handler import handle_pdf
from handlers.text_handler import handle_text
from source_registry import enrich_jsonl, origin_for

HANDLERS = {
    ".csv": handle_csv, ".xlsx": handle_excel, ".pdf": handle_pdf,
    ".txt": handle_text, ".docx": handle_docx, ".pptx": handle_pptx,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-prefix", action="append", required=True,
        help="Raw relative folder to process. Repeat for each selected folder.",
    )
    args = parser.parse_args()
    prefixes: list[tuple[str, ...]] = []
    for value in args.source_prefix:
        normalized = value.replace("\\", "/").strip("/")
        parts = tuple(Path(normalized).parts)
        if not parts or parts[0] != "nasa-combustion-reference" or any(p in {".", ".."} for p in parts):
            raise SystemExit("Source prefixes must stay under data/raw/nasa-combustion-reference.")
        prefixes.append(parts)

    files: list[Path] = []
    for parts in prefixes:
        folder = RAW_DATA_DIR.joinpath(*parts)
        if not folder.is_dir():
            raise FileNotFoundError(f"Reference folder not found: {folder}")
        files.extend(path for path in folder.rglob("*") if path.is_file())

    results = []
    for source_path in sorted(set(files)):
        relative = source_path.relative_to(RAW_DATA_DIR).as_posix()
        handler = HANDLERS.get(source_path.suffix.lower())
        if handler is None:
            results.append({"source_relative_path": relative, "status": "unsupported"})
            continue
        try:
            result = handler(source_path)
            output_path = result[0]
            enrich_jsonl(output_path, origin_for(relative))
            entry = {"source_relative_path": relative,
                     "output_relative_path": output_path.relative_to(ROOT).as_posix(),
                     "status": "processed", "record_count_or_rows": result[1]}
            if source_path.suffix.lower() in {".pdf", ".docx", ".pptx"}:
                entry["details"] = result[2]
            results.append(entry)
        except Exception as error:
            results.append({"source_relative_path": relative, "status": "failed", "error": str(error)})

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "manual_ingestion_nasa_combustion_references.json"
    report = {
        "schema_version": "2.0.0",
        "source_prefixes": ["/".join(parts) for parts in prefixes],
        "processed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "files": len(results),
            "processed": sum(result["status"] == "processed" for result in results),
            "unsupported": sum(result["status"] == "unsupported" for result in results),
            "failed": sum(result["status"] == "failed" for result in results),
        },
        "files": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
