from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = Path(
    os.getenv("FLARE_UP_RAW_DIR", PROJECT_ROOT / "data" / "raw")
)
PROCESSED_DATA_DIR = Path(
    os.getenv("FLARE_UP_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed")
)
SHARED_DATA_DIR = PROJECT_ROOT / "data" / "shared"
REPORTS_DIR = PROJECT_ROOT / "reports"


if __name__ == "__main__":
    print(f"Project:   {PROJECT_ROOT}")

    for name, path in [
        ("Raw data", RAW_DATA_DIR),
        ("Processed", PROCESSED_DATA_DIR),
        ("Shared", SHARED_DATA_DIR),
        ("Reports", REPORTS_DIR),
    ]:
        status = "OK" if path.exists() else "MISSING"
        print(f"{name:11} [{status}] {path}")
