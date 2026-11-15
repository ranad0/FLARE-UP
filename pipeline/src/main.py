import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR, REPORTS_DIR
from handlers.csv_handler import handle_csv
from handlers.excel_handler import handle_excel
from handlers.pdf_handler import handle_pdf
from handlers.text_handler import handle_text
from handlers.json_handler import handle_json
from handlers.ooxml_handler import handle_docx, handle_pptx
from handlers.youtube_handler import handle_youtube_transcript
from source_registry import enrich_jsonl, origin_for

HANDLERS = {
    ".csv": handle_csv,
    ".xlsx": handle_excel,
    ".docx": handle_docx,
    ".pptx": handle_pptx,
    ".pdf": handle_pdf,
    ".txt": handle_text,
    ".json": handle_json,
    ".jsonl": handle_json,
    ".vtt": handle_youtube_transcript,
    ".srt": handle_youtube_transcript,
}


def main() -> None:
    if not RAW_DATA_DIR.exists():
        print(f"Raw data folder does not exist: {RAW_DATA_DIR}")
        return

    files = sorted(
        path for path in RAW_DATA_DIR.rglob("*")
        if path.is_file()
    )

    results = []

    for source_path in files:
        relative_source = source_path.relative_to(RAW_DATA_DIR).as_posix()
        handler = HANDLERS.get(source_path.suffix.lower())

        # ZIPs are retained as source archives; ingest_sources.py has already
        # extracted them safely into a sibling raw folder for normal handlers.
        if source_path.suffix.lower() == ".zip":
            results.append({"source": relative_source, "status": "retained_archive", "error": ""})
            continue

        if handler is None:
            results.append({
                "source": relative_source,
                "status": "unsupported",
                "error": "No handler is registered for this file extension.",
            })
            print(f"UNSUPPORTED: {source_path.name}")
            continue

        try:
            result = handler(source_path)
            output_path = result[0]
            enrich_jsonl(output_path, origin_for(relative_source))

            if source_path.suffix.lower() == ".pdf":
                details = {
                    "pages": result[1],
                    "images_extracted": result[2],
                }
            elif source_path.suffix.lower() in {".vtt", ".srt"}:
                details = {"transcript_segments": result[1]}
            else:
                details = {"rows": result[1]}

            results.append({
                "source": relative_source,
                "status": "processed",
                "output": output_path.relative_to(
                    PROCESSED_DATA_DIR
                ).as_posix(),
                "details": details,
                "error": "",
            })
            print(f"PROCESSED: {source_path.name}")

        except Exception as error:
            results.append({
                "source": relative_source,
                "status": "failed",
                "error": str(error),
            })
            print(f"FAILED: {source_path}")
            print(f"Reason: {error}")

    summary = {
        "files_found": len(files),
        "processed": sum(r["status"] == "processed" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "unsupported": sum(r["status"] == "unsupported" for r in results),
        "retained_archives": sum(r["status"] == "retained_archive" for r in results),
    }

    report = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "files": results,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "qa_report.json"

    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=2)

    print("\nSummary")
    print(f"Files found: {summary['files_found']}")
    print(f"Processed:   {summary['processed']}")
    print(f"Failed:      {summary['failed']}")
    print(f"Unsupported: {summary['unsupported']}")
    print(f"Retained ZIP archives: {summary['retained_archives']}")
    print(f"QA report:   {report_path}")


if __name__ == "__main__":
    main()
