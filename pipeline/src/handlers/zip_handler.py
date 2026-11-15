"""Safety-limited ZIP extraction for source archives (never executes members)."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_MEMBERS = 10_000
MAX_UNPACKED_BYTES = 2_000_000_000
MAX_COMPRESSION_RATIO = 1_000
COPY_CHUNK_BYTES = 1024 * 1024


def _safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("/")
        or "\x00" in normalized
        or any(part in {"", ".", ".."} for part in member.parts)
        or (member.parts and ":" in member.parts[0])
    ):
        raise ValueError(f"Unsafe ZIP member path: {name!r}")
    return member


def handle_zip(
    archive_path: Path,
    destination_dir: Path,
    *,
    max_members: int = MAX_ARCHIVE_MEMBERS,
    max_unpacked_bytes: int = MAX_UNPACKED_BYTES,
    max_compression_ratio: int = MAX_COMPRESSION_RATIO,
) -> list[Path]:
    """Extract a ZIP into a new destination after validating every member.

    Returns extracted file paths. Existing destinations are never overwritten.
    """
    destination_dir = destination_dir.resolve()
    if destination_dir.exists():
        raise FileExistsError(f"Extraction destination already exists: {destination_dir}")
    destination_dir.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path) as source_zip:
        infos = source_zip.infolist()
        if len(infos) > max_members:
            raise ValueError(f"ZIP has {len(infos)} entries; limit is {max_members}.")

        regular_files = []
        total_size = 0
        for info in infos:
            member = _safe_member_path(info.filename)
            if info.is_dir():
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError(f"ZIP symlink is not allowed: {info.filename!r}")
            if info.flag_bits & 0x1:
                raise ValueError(f"Encrypted ZIP member is not supported: {info.filename!r}")
            total_size += info.file_size
            if total_size > max_unpacked_bytes:
                raise ValueError("ZIP exceeds the maximum uncompressed size.")
            if info.file_size and not info.compress_size:
                raise ValueError(f"Invalid ZIP compression size: {info.filename!r}")
            if info.compress_size and info.file_size / info.compress_size > max_compression_ratio:
                raise ValueError(f"ZIP compression ratio exceeds limit: {info.filename!r}")
            regular_files.append((info, member))

        extracted: list[Path] = []
        with tempfile.TemporaryDirectory(prefix="flare-up-zip-", dir=destination_dir.parent) as temporary:
            staging = Path(temporary) / "contents"
            staging.mkdir()
            for info, member in regular_files:
                target = (staging / Path(*member.parts)).resolve()
                if not target.is_relative_to(staging.resolve()):
                    raise ValueError(f"ZIP member escapes extraction directory: {info.filename!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise ValueError(f"Duplicate ZIP output path: {info.filename!r}")
                written = 0
                with source_zip.open(info, "r") as member_stream, target.open("xb") as output:
                    while block := member_stream.read(COPY_CHUNK_BYTES):
                        written += len(block)
                        if written > info.file_size or written > max_unpacked_bytes:
                            raise ValueError(f"ZIP member exceeded its declared size: {info.filename!r}")
                        output.write(block)
                if written != info.file_size:
                    raise ValueError(f"ZIP member size mismatch: {info.filename!r}")
                extracted.append(target)

            os.replace(staging, destination_dir)

        return [destination_dir / path.relative_to(staging) for path in extracted]
