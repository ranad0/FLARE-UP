"""Read CSV text using conservative, explicit encoding fallbacks."""
from pathlib import Path


def read_csv_text(source_path: Path) -> tuple[str, str]:
    """Decode UTF-8 CSVs first, then Windows-1252 for legacy NASA exports.

    Windows-1252 is used only when UTF-8 decoding fails. Returning the chosen
    encoding makes the fallback visible in derived records and reports.
    """
    raw = source_path.read_bytes()
    try:
        return raw.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252"), "cp1252"
        except UnicodeDecodeError as error:
            raise UnicodeError(
                f"CSV is neither valid UTF-8 nor Windows-1252: {source_path}"
            ) from error
