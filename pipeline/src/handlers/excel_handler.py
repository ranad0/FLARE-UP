import json
import sys
from datetime import date, datetime, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR

try:
    from openpyxl import load_workbook
except ImportError:
    print("openpyxl is missing. Install it with: python -m pip install openpyxl")
    raise


def make_json_safe(value):
    """حوّل قيم التاريخ إلى نص حتى يمكن حفظها بصيغة JSON."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    return value


def get_investigation_id(relative_path: Path) -> str:
    if len(relative_path.parts) >= 2:
        return relative_path.parts[0]

    return "unassigned"


def handle_excel(source_path: Path) -> tuple[Path, int]:
    """احفظ معلومات المصنف وأوراقه وصفوفها في ملف JSONL."""
    relative_path = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative_path).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workbook = load_workbook(
        source_path,
        read_only=True,
        data_only=False,
    )

    row_count = 0
    investigation_id = get_investigation_id(relative_path)

    with output_path.open("w", encoding="utf-8") as output_file:
        workbook_record = {
            "record_type": "workbook",
            "source_file": source_path.name,
            "source_relative_path": relative_path.as_posix(),
            "investigation_id": investigation_id,
            "sheet_names": workbook.sheetnames,
        }
        output_file.write(
            json.dumps(workbook_record, ensure_ascii=False) + "\n"
        )

        for worksheet in workbook.worksheets:
            sheet_record = {
                "record_type": "sheet",
                "sheet_name": worksheet.title,
                "max_row": worksheet.max_row,
                "max_column": worksheet.max_column,
            }
            output_file.write(
                json.dumps(sheet_record, ensure_ascii=False) + "\n"
            )

            for row_number, row in enumerate(
                worksheet.iter_rows(values_only=True),
                start=1,
            ):
                row_record = {
                    "record_type": "row",
                    "sheet_name": worksheet.title,
                    "row_number": row_number,
                    "values": [make_json_safe(value) for value in row],
                }
                output_file.write(
                    json.dumps(row_record, ensure_ascii=False) + "\n"
                )
                row_count += 1

    workbook.close()
    return output_path, row_count


def main() -> None:
    excel_files = sorted(
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".xlsx"
    )

    if not excel_files:
        print(f"No .xlsx files found in: {RAW_DATA_DIR}")
        return

    for source_path in excel_files:
        try:
            output_path, row_count = handle_excel(source_path)
            print(f"Processed: {source_path.name}")
            print(f"Rows: {row_count}")
            print(f"Output: {output_path}")
        except Exception as error:
            print(f"FAILED: {source_path}")
            print(f"Reason: {error}")


if __name__ == "__main__":
    main()
    