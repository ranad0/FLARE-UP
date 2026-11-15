import csv
import json
import sys
from io import StringIO
from pathlib import Path

# الوصول لمجلد المشروع وإعداداته
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR
from csv_encoding import read_csv_text


def get_investigation_id(relative_path: Path) -> str:
    """استخدم أول مجلد تحت raw كمعرّف للتحقيق."""
    if len(relative_path.parts) >= 2:
        return relative_path.parts[0]

    return "unassigned"


def handle_csv(source_path: Path) -> tuple[Path, int]:
    """حوّل صفوف CSV إلى JSONL مع حفظ الأعمدة والقيم كما هي."""
    relative_path = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative_path).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    investigation_id = get_investigation_id(relative_path)
    row_count = 0

    csv_text, source_encoding = read_csv_text(source_path)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    with StringIO(csv_text, newline="") as csv_file, temporary_path.open(
        "w", encoding="utf-8", newline="\n"
    ) as jsonl_file:
        reader = csv.reader(csv_file)
        column_names = next(reader, None)

        if column_names is not None:
            for row_number, values in enumerate(reader, start=2):
                if not any(str(value).strip() for value in values):
                    continue

                record = {
                    "source_file": source_path.name,
                    "source_relative_path": relative_path.as_posix(),
                    "investigation_id": investigation_id,
                    "row_number": row_number,
                    "columns": column_names,
                    "values": values,
                    "source_encoding": source_encoding,
                }

                jsonl_file.write(
                    json.dumps(record, ensure_ascii=False) + "\n"
                )
                row_count += 1

    temporary_path.replace(output_path)
    return output_path, row_count


def main() -> None:
    csv_files = sorted(
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".csv"
    )

    if not csv_files:
        print(f"No CSV files found in: {RAW_DATA_DIR}")
        return

    for source_path in csv_files:
        try:
            output_path, row_count = handle_csv(source_path)
            print(f"Processed: {source_path.name}")
            print(f"Rows: {row_count}")
            print(f"Output: {output_path}")
        except (OSError, UnicodeError, csv.Error) as error:
            print(f"FAILED: {source_path}")
            print(f"Reason: {error}")


if __name__ == "__main__":
    main()
