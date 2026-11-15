import csv
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

# نضيف مجلد المشروع لمسار Python حتى نستورد الإعدادات
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import RAW_DATA_DIR, REPORTS_DIR
from data_contract import SCHEMA_VERSION, stable_id
from source_registry import load_registry


# تصنيف أولي حسب امتداد الملف.
# لاحقًا سنضيف فحصًا لمحتوى الملف، لأن الامتداد وحده لا يكفي دائمًا.
FILE_TYPES = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".xls": "excel",
    ".docx": "word_document",
    ".pptx": "presentation",
    ".csv": "csv",
    ".json": "json",
    ".jsonl": "jsonl",
    ".md": "markdown",
    ".vtt": "video_transcript",
    ".srt": "video_transcript",
    ".txt": "text",
    ".zip": "zip",
}


def calculate_sha256(file_path: Path) -> str:
    """احسب بصمة SHA-256 للملف على دفعات."""
    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def get_investigation_label(file_path: Path) -> str | None:
    """Return a folder label without assuming it is an official investigation ID."""
    relative_path = file_path.relative_to(RAW_DATA_DIR)

    if len(relative_path.parts) < 2:
        return None

    return relative_path.parts[0]


def build_manifest() -> Path:
    """امسح ملفات raw واكتب معلوماتها في ملف CSV."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_path = REPORTS_DIR / "manifest.csv"
    seen_hashes = {}
    rows = []
    source_origins = load_registry().get("sources", {})

    if RAW_DATA_DIR.exists():
        files = sorted(path for path in RAW_DATA_DIR.rglob("*") if path.is_file())
    else:
        files = []

    for file_path in files:
        relative_path = file_path.relative_to(RAW_DATA_DIR).as_posix()
        file_hash = ""
        status = "inventory_only"
        error_message = ""

        try:
            file_hash = calculate_sha256(file_path)
        except OSError as error:
            status = "inventory_error"
            error_message = str(error)

        duplicate_of = ""
        if file_hash:
            if file_hash in seen_hashes:
                duplicate_of = seen_hashes[file_hash]
            else:
                seen_hashes[file_hash] = relative_path

        origin = source_origins.get(relative_path, {})
        label = origin.get("source_group") or origin.get("source_folder_label") or get_investigation_label(file_path)
        canonical_id = None
        id_status = "unknown"
        if label:
            id_status = "unverified"
        if (origin.get("investigation_id_status") == "verified"
                and origin.get("canonical_investigation_id")
                and origin.get("investigation_id_evidence_url")):
            canonical_id = origin["canonical_investigation_id"]
            id_status = "verified"
        citation_url = origin.get("citation_url") or ""
        doi = origin.get("doi") or (citation_url.split("doi.org/", 1)[1] if "doi.org/" in citation_url else "")

        rows.append({
            "schema_version": SCHEMA_VERSION,
            "file_name": file_path.name,
            "relative_path": relative_path,
            "document_id": stable_id("doc", relative_path, file_hash or "hash_unavailable"),
            "extension": file_path.suffix.lower(),
            "file_type": FILE_TYPES.get(file_path.suffix.lower(), "unsupported"),
            "size_bytes": file_path.stat().st_size,
            "sha256": file_hash,
            "investigation_id": canonical_id or "",
            "investigation_label": label or "",
            "investigation_id_status": id_status,
            "citation_url": citation_url,
            "doi": doi,
            "source_url": origin.get("source_url") or origin.get("caption_source_url") or "",
            "duplicate_of": duplicate_of,
            "status": status,
            "processed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "error_message": error_message,
        })

    fieldnames = [
        "schema_version",
        "file_name",
        "relative_path",
        "document_id",
        "extension",
        "file_type",
        "size_bytes",
        "sha256",
        "investigation_id",
        "investigation_label",
        "investigation_id_status",
        "citation_url",
        "doi",
        "source_url",
        "duplicate_of",
        "status",
        "processed_at_utc",
        "error_message",
    ]

    with manifest_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Files found: {len(rows)}")
    print(f"Manifest: {manifest_path}")

    return manifest_path


if __name__ == "__main__":
    build_manifest()
