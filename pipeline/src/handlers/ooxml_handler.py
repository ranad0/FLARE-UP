"""Extract source-grounded text and embedded images from DOCX and PPTX files.

This uses OOXML relationships and document order. It does not create image
descriptions; extracted figures remain uncaptioned until a human verifies them.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from config.settings import RAW_DATA_DIR, PROCESSED_DATA_DIR

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 100 * 1024 * 1024
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".svg"}


def _investigation_id(source_path: Path) -> str:
    relative = source_path.relative_to(RAW_DATA_DIR)
    return relative.parts[0] if len(relative.parts) > 1 else "unassigned"


def _read_xml(archive: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        return ET.fromstring(archive.read(name))
    except KeyError:
        return None


def _relationship_targets(archive: zipfile.ZipFile, rels_path: str) -> dict[str, str]:
    root = _read_xml(archive, rels_path)
    if root is None:
        return {}
    result = {}
    for relation in root:
        if relation.attrib.get("TargetMode") == "External":
            continue
        relation_id = relation.attrib.get("Id")
        target = relation.attrib.get("Target")
        if relation_id and target and relation.attrib.get("Type", "").endswith("/image"):
            owner_dir = rels_path.split("/_rels/", 1)[0] if "/_rels/" in rels_path else ""
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(owner_dir, target))
            if member.startswith("../") or member == "..":
                continue
            result[relation_id] = member
    return result


def _store_image(
    archive: zipfile.ZipFile,
    member: str,
    output_asset_dir: Path,
    index: int,
) -> str | None:
    suffix = Path(member).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        return None
    try:
        info = archive.getinfo(member)
    except KeyError:
        return None
    if info.file_size <= 0 or info.file_size > MAX_IMAGE_BYTES:
        return None
    data = archive.read(member)
    digest = hashlib.sha256(data).hexdigest()
    output_asset_dir.mkdir(parents=True, exist_ok=True)
    filename = f"image_{index:03d}_{digest[:8]}{suffix}"
    target = output_asset_dir / filename
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise FileExistsError(f"Refusing to overwrite a different extracted image: {target}")
    else:
        target.write_bytes(data)
    return target.relative_to(PROCESSED_DATA_DIR).as_posix()


def _write_records(source_path: Path, records: list[dict]) -> Path:
    relative = source_path.relative_to(RAW_DATA_DIR)
    output_path = (PROCESSED_DATA_DIR / relative).with_suffix(".jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(output_path)
    return output_path


def handle_docx(source_path: Path) -> tuple[Path, int, dict[str, int]]:
    """Create section and table-row records with paragraph/table locations."""
    relative = source_path.relative_to(RAW_DATA_DIR).as_posix()
    investigation_id = _investigation_id(source_path)
    records: list[dict] = []
    asset_dir = PROCESSED_DATA_DIR / "assets" / investigation_id / source_path.stem
    image_bytes = 0
    with zipfile.ZipFile(source_path) as archive:
        document = _read_xml(archive, "word/document.xml")
        if document is None:
            raise ValueError(f"DOCX has no word/document.xml: {source_path.name}")
        relationships = _relationship_targets(archive, "word/_rels/document.xml.rels")
        body = document.find("w:body", NS)
        if body is None:
            raise ValueError(f"DOCX body is missing: {source_path.name}")
        section_heading = "Document"
        section_text: list[str] = []
        section_start: int | None = None
        section_end: int | None = None
        paragraph_number = 0
        table_number = 0
        image_number = 0
        images_extracted = 0

        def flush_section() -> None:
            nonlocal section_text, section_start, section_end
            text = "\n\n".join(section_text).strip()
            if text:
                records.append({
                    "record_type": "text_document", "source_file": source_path.name,
                    "source_relative_path": relative, "investigation_id": investigation_id,
                    "source_location": f"paragraphs:{section_start}-{section_end}",
                    "section_heading": section_heading, "paragraph_start": section_start,
                    "paragraph_end": section_end, "text": text,
                })
            section_text = []
            section_start = section_end = None

        for block in body:
            local = block.tag.rsplit("}", 1)[-1]
            if local == "p":
                paragraph_number += 1
                text = "".join(node.text or "" for node in block.findall(".//w:t", NS)).strip()
                style_node = block.find("w:pPr/w:pStyle", NS)
                style = style_node.attrib.get(f"{{{NS['w']}}}val", "") if style_node is not None else ""
                if text and style.lower().startswith("heading"):
                    flush_section()
                    section_heading = text
                if text:
                    if section_start is None:
                        section_start = paragraph_number
                    section_end = paragraph_number
                    section_text.append(text)
                for blip in block.findall(".//a:blip", NS):
                    relation_id = blip.attrib.get(f"{{{NS['r']}}}embed")
                    member = relationships.get(relation_id or "")
                    if not member:
                        continue
                    image_number += 1
                    stored = _store_image(archive, member, asset_dir, image_number)
                    if not stored:
                        continue
                    image_bytes += archive.getinfo(member).file_size
                    if image_bytes > MAX_TOTAL_IMAGE_BYTES:
                        raise ValueError(f"DOCX embedded images exceed the {MAX_TOTAL_IMAGE_BYTES} byte processing limit")
                    records.append({
                        "record_type": "figure_asset", "source_file": source_path.name,
                        "source_relative_path": relative, "investigation_id": investigation_id,
                        "source_location": f"paragraph:{paragraph_number}", "image_reference": stored,
                        "figure_context": "\n".join([section_heading, text]).strip() or None,
                        "caption": None, "caption_status": "needs_review",
                        "visual_interpretation_status": "not_interpreted",
                    })
                    images_extracted += 1
            elif local == "tbl":
                flush_section()
                table_number += 1
                for row_number, row in enumerate(block.findall("w:tr", NS), start=1):
                    cells = [" ".join(t.text or "" for t in cell.findall(".//w:t", NS)).strip()
                             for cell in row.findall("w:tc", NS)]
                    if not any(cells):
                        continue
                    records.append({
                        "record_type": "text_document", "source_file": source_path.name,
                        "source_relative_path": relative, "investigation_id": investigation_id,
                        "source_location": f"table:{table_number}:row:{row_number}",
                        "section_heading": section_heading,
                        "text": f"Table {table_number}, row {row_number}: " + " | ".join(cells),
                    })
        flush_section()
    output_path = _write_records(source_path, records)
    return output_path, len(records), {"sections_tables_and_figures": len(records), "images_extracted": images_extracted}


def handle_pptx(source_path: Path) -> tuple[Path, int, dict[str, int]]:
    """Create one text record per slide and separate extracted figure assets."""
    relative = source_path.relative_to(RAW_DATA_DIR).as_posix()
    investigation_id = _investigation_id(source_path)
    records: list[dict] = []
    asset_dir = PROCESSED_DATA_DIR / "assets" / investigation_id / source_path.stem
    total_image_bytes = 0
    with zipfile.ZipFile(source_path) as archive:
        presentation = _read_xml(archive, "ppt/presentation.xml")
        presentation_rels = _read_xml(archive, "ppt/_rels/presentation.xml.rels")
        relation_targets = {}
        if presentation_rels is not None:
            for relation in presentation_rels:
                if relation.attrib.get("TargetMode") != "External":
                    relation_targets[relation.attrib.get("Id", "")] = relation.attrib.get("Target", "")
        slide_members: list[str] = []
        if presentation is not None:
            slide_list = presentation.find("p:sldIdLst", NS)
            if slide_list is not None:
                for slide_id in slide_list:
                    target = relation_targets.get(slide_id.attrib.get(f"{{{NS['r']}}}id", ""))
                    if target:
                        member = posixpath.normpath(posixpath.join("ppt", target))
                        if member in archive.namelist():
                            slide_members.append(member)
        if not slide_members:
            slide_members = sorted(
                (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
                key=lambda name: int(re.search(r"slide(\d+)", name).group(1)),
            )
        if not slide_members:
            raise ValueError(f"PPTX has no readable slides: {source_path.name}")

        image_number = 0
        for slide_number, slide_member in enumerate(slide_members, start=1):
            slide = _read_xml(archive, slide_member)
            if slide is None:
                continue
            texts = [node.text or "" for node in slide.findall(".//a:t", NS)]
            slide_text = "\n".join(value.strip() for value in texts if value.strip()).strip()
            rels_path = posixpath.join(posixpath.dirname(slide_member), "_rels", posixpath.basename(slide_member) + ".rels")
            slide_relationships = _relationship_targets(archive, rels_path)
            refs: list[str] = []
            context = slide_text or None
            if slide_text:
                records.append({
                    "record_type": "text_document", "source_file": source_path.name,
                    "source_relative_path": relative, "investigation_id": investigation_id,
                    "source_location": f"slide:{slide_number}", "slide_number": slide_number,
                    "text": slide_text,
                })
            for pic in slide.findall(".//p:pic", NS):
                blip = pic.find(".//a:blip", NS)
                if blip is None:
                    continue
                relation_id = blip.attrib.get(f"{{{NS['r']}}}embed", "")
                member = slide_relationships.get(relation_id)
                if not member:
                    continue
                image_number += 1
                stored = _store_image(archive, member, asset_dir, image_number)
                if not stored:
                    continue
                total_image_bytes += archive.getinfo(member).file_size
                if total_image_bytes > MAX_TOTAL_IMAGE_BYTES:
                    raise ValueError(f"PPTX embedded images exceed the {MAX_TOTAL_IMAGE_BYTES} byte processing limit")
                refs.append(stored)
                nonvisual = pic.find(".//p:cNvPr", NS)
                alt_text = nonvisual.attrib.get("descr") if nonvisual is not None else None
                records.append({
                    "record_type": "figure_asset", "source_file": source_path.name,
                    "source_relative_path": relative, "investigation_id": investigation_id,
                    "source_location": f"slide:{slide_number}", "slide_number": slide_number,
                    "image_reference": stored, "alt_text": alt_text or None,
                    "figure_context": context, "caption": None, "caption_status": "needs_review",
                    "visual_interpretation_status": "not_interpreted",
                })
            if refs and slide_text:
                for record in reversed(records):
                    if record.get("record_type") == "text_document" and record.get("source_location") == f"slide:{slide_number}":
                        record["image_references"] = refs
                        break
    output_path = _write_records(source_path, records)
    return output_path, len(records), {"slides": len(slide_members), "images_extracted": image_number}
