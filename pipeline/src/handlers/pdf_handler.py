import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR

try:
    import pymupdf
except ImportError:
    print("PyMuPDF is missing. Install it with: python -m pip install pymupdf")
    raise

def get_investigation_id(relative_path: Path) -> str:
    if len(relative_path.parts) >= 2:
        return relative_path.parts[0]

    return "unassigned"


def classify_page(text: str, image_count: int) -> str:
    """تصنيف تقريبي للصفحة اعتمادًا على النص والصور المستخرجة."""
    text_length = len(text.strip())

    if text_length < 40:
        return "little_text_possible_scan_review_for_ocr"

    if image_count >= 2:
        return "image_heavy_possible_figures"

    return "text_page"


def handle_pdf(source_path: Path) -> tuple[Path, int, int]:
    relative_path = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative_path).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image_directory = (
        PROCESSED_DATA_DIR
        / relative_path.parent
        / "assets"
        / source_path.stem
    )
    document = pymupdf.open(source_path)
    page_count = len(document)


    investigation_id = get_investigation_id(relative_path)
    extracted_image_count = 0

    try:
        with output_path.open("w", encoding="utf-8") as output_file:
            document_record = {
                "record_type": "document",
                "source_file": source_path.name,
                "source_relative_path": relative_path.as_posix(),
                "investigation_id": investigation_id,
                "page_count": page_count,
                "metadata": document.metadata,
            }
            output_file.write(
                json.dumps(document_record, ensure_ascii=False) + "\n"
            )

            for page_index, page in enumerate(document):
                page_number = page_index + 1
                text = page.get_text("text")

                image_references = []
                image_errors = []

                for image_index, image_info in enumerate(
                    page.get_images(full=True),
                    start=1,
                ):
                    xref = image_info[0]

                    try:
                        extracted = document.extract_image(xref)
                        image_extension = extracted.get("ext", "bin")
                        image_bytes = extracted["image"]

                        image_directory.mkdir(parents=True, exist_ok=True)
                        image_name = (
                            f"page_{page_number:03d}_"
                            f"image_{image_index:03d}.{image_extension}"
                        )
                        image_path = image_directory / image_name
                        image_path.write_bytes(image_bytes)

                        image_references.append(
                            image_path.relative_to(
                                PROCESSED_DATA_DIR
                            ).as_posix()
                        )
                        extracted_image_count += 1

                    except Exception as error:
                        image_errors.append(str(error))

                page_record = {
                    "record_type": "page",
                    "source_file": source_path.name,
                    "source_relative_path": relative_path.as_posix(),
                    "investigation_id": investigation_id,
                    "page_number": page_number,
                    "text": text,
                    "text_character_count": len(text.strip()),
                    "image_count": len(image_references),
                    "image_references": image_references,
                    "image_errors": image_errors,
                    "page_type_estimate": classify_page(
                        text,
                        len(image_references),
                    ),
                }

                output_file.write(
                    json.dumps(page_record, ensure_ascii=False) + "\n"
                )

    finally:
        document.close()

    return output_path, page_count, extracted_image_count


def main() -> None:
    pdf_files = sorted(
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )

    if not pdf_files:
        print(f"No PDF files found in: {RAW_DATA_DIR}")
        return

    for source_path in pdf_files:
        try:
            output_path, page_count, image_count = handle_pdf(source_path)
            print(f"Processed: {source_path.name}")
            print(f"Pages: {page_count}")
            print(f"Images extracted: {image_count}")
            print(f"Output: {output_path}")
        except Exception as error:
            print(f"FAILED: {source_path}")
            print(f"Reason: {error}")


if __name__ == "__main__":
    main()
