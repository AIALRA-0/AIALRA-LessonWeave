#!/usr/bin/env python3
"""Build a small, privacy-filtered reading bundle from completed local cases.

This packager reads saved outputs only. It does not run LessonWeave, contact a
model provider, fetch source material, or modify the input cases.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from urllib.parse import urlsplit, urlunsplit
import zipfile


REPO = Path(__file__).resolve().parents[1]
CASE_NAMES = ("web", "pdf", "code")
DROP_KEYS = {
    "system_prompt", "prompt", "prompt_text", "prompt_messages", "messages",
    "raw_request", "raw_response", "response", "receipt", "call", "calls",
    "call_history", "events", "logs", "cookies", "cookie", "set_cookie",
    "authorization", "auth_header", "access_token", "refresh_token", "api_key",
    "password", "secret", "credential", "credentials", "user_note", "user_notes",
    "definition_quote", "source_quotes", "quote", "original_texts", "file_fragments",
    "dom", "dom_path", "asset", "asset_path", "grounding_report_path",
    "note_block_id", "transitions_path", "transition_run", "writing_run",
    "material_run", "project_id", "run_id", "process_id", "worker_pid", "pid",
    "source_pack_path", "coverage_path", "inventory_path", "bindings_path",
    "catalog_path", "reader_repairs_path", "preview_provenance", "history",
}
DROP_SUFFIXES = ("_path", "_run", "_pid", "_token", "_secret", "_password")

WINDOWS_PATH = re.compile(r"(?i)(?<![A-Z0-9])[A-Z]:[\\/][^\s\"'<>`]+")
PRIVATE_POSIX_PATH = re.compile(
    r"/(?:Users|home|root|tmp|private/var|mnt|media|srv|var/lib|workspace)/[^\s\"'<>`]+",
    re.IGNORECASE,
)
EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL = re.compile(r"https?://[^\s\"'<>`]+", re.IGNORECASE)
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(bearer|token|password|passwd|secret|api[_ -]?key|authorization|cookie)\b"
    r"(\s*[:=]\s*)([^\s,;<>\"']{8,})"
)
IPV4 = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
INTERNAL_HOST = re.compile(r"(?i)(?:localhost|[a-z0-9-]+\.(?:local|lan|internal|corp|home|test|example))(?::\d+)?")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"无法读取案例 JSON：{path.name}（{type(error).__name__}）") from error
    if not isinstance(value, dict):
        raise SystemExit(f"案例 JSON 顶层必须是对象：{path.name}")
    return value


def dump_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def valid_public_url(value: str) -> str | None:
    candidate = value.strip()
    try:
        parts = urlsplit(candidate)
        host = (parts.hostname or "").rstrip(".").lower()
        if parts.scheme not in {"http", "https"} or not host or parts.username or parts.password:
            return None
        if host == "localhost" or host.endswith((".local", ".lan", ".internal", ".corp", ".home", ".test", ".example")):
            return None
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
        except ValueError:
            if "." not in host:
                return None
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")).rstrip("/")
    except ValueError:
        return None


def redact_ip(match: re.Match[str]) -> str:
    value = match.group(0)
    try:
        address = ipaddress.ip_address(value)
        return "[本机地址已省略]" if not address.is_global else value
    except ValueError:
        return value


def scrub_text(value: str) -> str:
    value = WINDOWS_PATH.sub("[本机路径已省略]", value)
    value = PRIVATE_POSIX_PATH.sub("[本机路径已省略]", value)
    value = EMAIL.sub("[邮箱已省略]", value)
    value = SECRET_ASSIGNMENT.sub(lambda match: match.group(1) + match.group(2) + "[凭据已省略]", value)
    value = INTERNAL_HOST.sub("[内部主机已省略]", value)

    def scrub_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        suffix = ""
        while raw and raw[-1] in ".,;:!?)]}”：，。；！？》」』":
            suffix = raw[-1] + suffix
            raw = raw[:-1]
        safe = valid_public_url(raw)
        return (safe or "[内部或含敏感参数的网址已省略]") + suffix

    value = URL.sub(scrub_url, value)
    value = IPV4.sub(redact_ip, value)
    return value


def clean_value(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            normalized = key.strip().lower().replace("-", "_")
            if normalized in DROP_KEYS or normalized.endswith(DROP_SUFFIXES):
                continue
            cleaned[scrub_text(key)] = clean_value(child)
        return cleaned
    if isinstance(value, list):
        return [clean_value(child) for child in value]
    if isinstance(value, str):
        return scrub_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return scrub_text(str(value))


def safe_relative(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", value):
        return None
    return path.as_posix()


def safe_image_copy(source: Path, destination: Path) -> None:
    try:
        from PIL import Image
    except ImportError as error:
        raise SystemExit("清理自编示例图片元数据需要 Pillow；请先安装 Pillow 后重新打包") from error
    try:
        with Image.open(source) as image:
            image.load()
            output = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            destination.parent.mkdir(parents=True, exist_ok=True)
            output.save(destination, format="PNG", optimize=True)
    except (OSError, ValueError) as error:
        raise SystemExit(f"自编示例图片无法安全重存：{source.name}") from error


def scrub_html(source: Path) -> str:
    text = source.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"(?is)<script\b[^>]*>.*?</script\s*>", "", text)
    text = re.sub(r"(?is)<form\b[^>]*>.*?</form\s*>", "", text)
    text = re.sub(r"(?is)<input\b[^>]*>", "", text)
    text = re.sub(r"(?im)^\s*(?:set-cookie|cookie|authorization)\s*:\s*[^\r\n]+", "", text)
    return scrub_text(text)


def read_book(case: Path, preview_ok: bool = False) -> tuple[dict, bool]:
    final = case / "05_writing/book.json"
    preview = case / "05_writing/preview-book.json"
    if final.is_file():
        return read_json(final), False
    if preview_ok and preview.is_file():
        return read_json(preview), True
    raise SystemExit(f"案例缺少已保存的最终书稿：{case.name}")


def clean_section(section: dict) -> dict:
    value = clean_value(section)
    if not isinstance(value, dict):
        raise SystemExit("小节清理结果不是对象")
    allowed = {
        "section_id", "section_number", "title", "opening_title", "core_questions",
        "units", "next_section_id", "next_title", "opening", "summary", "pitfalls",
        "quiz", "opening_forward", "local_notations", "glossary", "writing_contract_version",
    }
    return {key: child for key, child in value.items() if key in allowed}


def clean_book(book: dict, sections: list[tuple[dict, str]], preview: bool) -> dict:
    result = clean_value(book)
    if not isinstance(result, dict):
        raise SystemExit("书稿清理结果不是对象")
    allowed = {"title", "introduction", "goals", "chapters", "coverage", "preview", "status", "preview_status", "writing_rules_version"}
    result = {key: value for key, value in result.items() if key in allowed}
    result["preview"] = preview
    result["validation"] = {"passed": bool(book.get("validation", {}).get("passed", False))}
    paths = {source.get("id"): output_path for source, output_path in sections}
    for chapter in result.get("chapters", []):
        for section in chapter.get("sections", []):
            section_id = section.get("id")
            section["path"] = paths.get(section_id, "")
    return result


def public_source_path(value: object, repository_source: bool) -> str | None:
    path = safe_relative(value)
    if path is not None:
        if repository_source:
            parts = PurePosixPath(path).parts
            for index, part in enumerate(parts):
                if part.lower() == "repository" and index + 1 < len(parts):
                    return PurePosixPath(*parts[index + 1:]).as_posix()
        return path
    if repository_source and isinstance(value, str):
        normalized = value.replace("\\", "/")
        lowered = normalized.lower()
        marker = "/repository/"
        index = lowered.rfind(marker)
        if index >= 0:
            tail = normalized[index + len(marker):]
            return safe_relative(tail)
    return None


def locate_tree_sources(case: Path, referenced_source_ids: set[str]) -> dict[str, dict]:
    tree_path = case / "01_tree/tree.json"
    if not tree_path.is_file() or not referenced_source_ids:
        return {}
    document = read_json(tree_path)
    found: dict[str, dict] = {}
    pending = [document.get("tree")]
    allowed_source_fields = {"selector", "path", "start_line", "end_line"}
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id in referenced_source_ids:
            raw_source = node.get("source") if isinstance(node.get("source"), dict) else {}
            found[node_id] = {
                "kind": node.get("type"),
                "role": node.get("reading_role"),
                "source": {key: value for key, value in raw_source.items() if key in allowed_source_fields},
            }
        children = node.get("children")
        if isinstance(children, list):
            pending.extend(children)
    return found


def source_map(
    manifest: dict | None,
    origin_url: str | None,
    materials_included: bool = False,
    referenced_source_ids: set[str] | None = None,
    tree_sources: dict[str, dict] | None = None,
) -> dict:
    manifest = manifest if isinstance(manifest, dict) else {}
    pages: dict[str, dict] = {}
    file_rows: dict[str, dict] = {}
    sources: list[dict] = []
    raw_pages = manifest.get("pages") if isinstance(manifest.get("pages"), dict) else {}
    raw_files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    raw_sources = manifest.get("sources") if isinstance(manifest.get("sources"), dict) else {}
    selected_sources = {
        str(key): value for key, value in raw_sources.items()
        if isinstance(value, dict) and (referenced_source_ids is None or str(key) in referenced_source_ids)
    }
    used_page_ids = {
        str(page_id)
        for value in selected_sources.values()
        for page_id in value.get("page_ids", [])
    }
    used_file_ids = {
        str(file_id)
        for value in selected_sources.values()
        for file_id in value.get("file_ids", [])
    }
    for key, value in raw_pages.items():
        if not isinstance(value, dict) or (referenced_source_ids is not None and str(key) not in used_page_ids):
            continue
        page_id = f"page-{len(pages) + 1:03d}"
        pages[str(key)] = {"id": page_id, "kind": scrub_text(str(value.get("kind", "page"))),
                           "width": value.get("width"), "height": value.get("height"),
                           "coordinate_space": scrub_text(str(value.get("coordinate_space", "")))}
    repository_source = bool(origin_url and "github.com/" in origin_url.lower())
    file_ids_by_path: dict[str, str] = {}
    for key, value in raw_files.items():
        if not isinstance(value, dict) or (referenced_source_ids is not None and str(key) not in used_file_ids):
            continue
        path = public_source_path(value.get("path"), repository_source)
        row = {"id": f"file-{len(file_rows) + 1:03d}", "path": path,
               "line_count": value.get("line_count") if isinstance(value.get("line_count"), int) else None}
        file_rows[str(key)] = row
        if path:
            file_ids_by_path.setdefault(path, row["id"])
    sources_by_id: dict[str, dict] = {}
    for key, value in selected_sources.items():
        source = value.get("source") if isinstance(value.get("source"), dict) else {}
        status_counts: dict[str, int] = {}
        for sentence in (value.get("sentences") or {}).values() if isinstance(value.get("sentences"), dict) else []:
            if isinstance(sentence, dict):
                status = str(sentence.get("status", "unrecorded"))
                status_counts[status] = status_counts.get(status, 0) + 1
        locations = []
        for location in value.get("locations", []) if isinstance(value.get("locations"), list) else []:
            if not isinstance(location, dict):
                continue
            bbox = location.get("bbox")
            locations.append({"page": pages.get(str(location.get("page_id")), {}).get("id"),
                              "bbox": bbox if isinstance(bbox, list) and all(isinstance(x, (int, float)) for x in bbox) else None,
                              "precision": scrub_text(str(location.get("precision", "")))})
        sources_by_id[str(key)] = {
            "id": str(key),
            "kind": scrub_text(str(value.get("type", source.get("kind", "source")))),
            "role": scrub_text(str(source.get("kind", ""))),
            "pages": [pages[item]["id"] for item in value.get("page_ids", []) if str(item) in pages],
            "files": [file_rows[item]["id"] for item in value.get("file_ids", []) if str(item) in file_rows],
            "locations": locations,
            "sentence_statuses": status_counts,
            "mapping_status": "recorded",
        }
    for source_id, node in (tree_sources or {}).items():
        row = sources_by_id.get(source_id)
        if row is None:
            row = {
                "id": source_id,
                "kind": scrub_text(str(node.get("kind") or "source")),
                "role": scrub_text(str(node.get("role") or "")),
                "pages": [],
                "files": [],
                "locations": [],
                "sentence_statuses": {},
                "mapping_status": "tree_only",
            }
            sources_by_id[source_id] = row
        else:
            if not row.get("role") and node.get("role"):
                row["role"] = scrub_text(str(node["role"]))
            row["mapping_status"] = "recorded_with_tree"
        raw_source = node.get("source") if isinstance(node.get("source"), dict) else {}
        location: dict[str, object] = {}
        raw_path = raw_source.get("path")
        if raw_path:
            path = public_source_path(raw_path, repository_source)
            if path:
                file_id = file_ids_by_path.get(path)
                if file_id is None:
                    file_id = f"file-{len(file_rows) + 1:03d}"
                    file_row = {"id": file_id, "path": path, "line_count": None}
                    file_rows[f"tree:{file_id}"] = file_row
                    file_ids_by_path[path] = file_id
                if file_id not in row["files"]:
                    row["files"].append(file_id)
                location["file"] = file_id
        selector = raw_source.get("selector")
        if isinstance(selector, str) and selector:
            location["selector"] = scrub_text(selector)
        for field in ("start_line", "end_line"):
            number = raw_source.get(field)
            if isinstance(number, int) and not isinstance(number, bool) and number > 0:
                location[field] = number
        if location:
            row["locations"].append(location)
    sources = list(sources_by_id.values())
    files = [row for row in file_rows.values()]
    source_ids_without_mapping = sorted(
        source_id for source_id in (referenced_source_ids or set()) if source_id not in sources_by_id
    )
    return {
        "schema": "lessonweave-public-source-map-v1",
        "source_material_included": materials_included,
        "origin_url": valid_public_url(origin_url) if origin_url else None,
        "pages": list(pages.values()),
        "files": files,
        "sources": sources,
        "unmapped_source_ids": source_ids_without_mapping,
        "note": "此映射保留材料编号、网页定位、页码或源码行号；没有定位记录的材料编号会单独列出，原始第三方材料不随案例包发布。",
    }


def locate_manifest(case: Path) -> dict | None:
    index = case / "05_writing/source-location/index.json"
    if not index.is_file():
        return None
    value = read_json(index)
    versions = value.get("versions", [])
    for item in versions:
        if isinstance(item, dict) and isinstance(item.get("manifest"), str):
            relative = safe_relative(item["manifest"])
            if relative is None:
                manifest_value = item["manifest"].replace("\\", "/")
                prefix = "/05_writing/source-location/"
                if manifest_value.startswith(prefix):
                    relative = "05_writing/source-location/" + manifest_value[len(prefix):]
            path = case / relative if relative else None
            if path and path.is_file():
                return read_json(path)
    return None


def find_origin(case: Path, kind: str) -> str | None:
    if kind == "web":
        input_path = case / "00_source/input.json"
        if input_path.is_file():
            return valid_public_url(str(read_json(input_path).get("material", "")))
    tree_path = case / "01_tree/tree.json"
    if tree_path.is_file():
        tree = read_json(tree_path)
        original = tree.get("original", {}) if isinstance(tree.get("original"), dict) else {}
        for candidate in (original.get("original"), original.get("repository"), tree.get("repository")):
            url = valid_public_url(str(candidate or ""))
            if url:
                return url
    return None


def delivered_stats(case: Path) -> dict:
    delivery_path = case / "delivery.json"
    if not delivery_path.is_file():
        return {}
    delivery = read_json(delivery_path)
    coverage = delivery.get("book_coverage", {}) if isinstance(delivery.get("book_coverage"), dict) else {}
    return {
        "teaching_units": delivery.get("units"),
        "sections": delivery.get("sections"),
        "quiz_items": coverage.get("quiz"),
        "unique_terms": coverage.get("unique_terms"),
        "material_nodes": coverage.get("material_nodes"),
        "assigned_teaching_material_nodes": coverage.get("teaching_material_nodes"),
    }


def public_case_info(name: str, book: dict, preview: bool, origin_url: str | None, stats: dict) -> dict:
    if name == "web":
        source = {
            "type": "public web page",
            "origin_url": origin_url,
            "included": False,
            "reacquire": "重新提交记录中的公开网址；网站内容可能已经变化。",
        }
    elif name == "pdf":
        source = {
            "type": "local PDF input",
            "origin_url": None,
            "included": False,
            "reacquire": "原始记录只含本机 PDF 路径，打包时已移除。请自行提供有权使用的 PDF；没有可核实的公开下载网址，因此不生成下载链接。",
        }
    elif name == "code":
        source = {
            "type": "OpenROAD source repository",
            "origin_url": origin_url,
            "included": False,
            "reacquire": "可从记录的公开仓库重新克隆当前默认分支；原案例没有保存源码提交号，因此重新克隆不保证与原输入逐字相同。",
            "command": f"git clone --filter=blob:none {origin_url} openroad-source" if origin_url else None,
        }
    else:
        source = {
            "type": "self-authored web material",
            "origin_url": None,
            "included": True,
            "reacquire": "原始自编 HTML 与 PNG 已经过隐私清理后随此示例保存。",
        }
    return {
        "schema": "lessonweave-public-case-v1",
        "case": name,
        "title": scrub_text(str(book.get("title", name))),
        "reading_status": "preview" if preview else "completed",
        "validation_passed": bool(book.get("validation", {}).get("passed", False)),
        "original_material_included": name == "minimal-web",
        "statistics": stats,
        "source": source,
        "contents": ["final reading text", "media descriptions", "exercises", "pitfalls", "glossary", "source identifiers and location metadata"],
        "excluded": ["third-party source files", "WACZ archives", "original PDF", "model prompts and receipts", "call history", "personal notes", "runtime state", "cookies", "private paths and credentials"],
    }


def create_case(case: Path, destination: Path, name: str, *, preview_ok: bool = False, self_authored: bool = False) -> dict:
    book, preview = read_book(case, preview_ok=preview_ok)
    if not preview and book.get("validation", {}).get("passed") is not True:
        raise SystemExit(f"案例 {name} 的最终书稿没有通过记录验证；只接受已完成的最终稿")
    section_rows: list[tuple[dict, str]] = []
    source_docs: list[tuple[Path, Path]] = []
    referenced_source_ids: set[str] = set()
    serial = 0
    for chapter in book.get("chapters", []):
        for section in chapter.get("sections", []):
            relative = safe_relative(section.get("path"))
            source_path = case / relative if relative else None
            if source_path is None or not source_path.is_file():
                raise SystemExit(f"案例 {name} 缺少书稿引用的小节文件；停止输出不完整案例")
            serial += 1
            output_path = f"05_writing/sections/section-{serial:03d}.json"
            section_data = clean_section(read_json(source_path))
            for unit in section_data.get("units", []):
                if isinstance(unit, dict) and isinstance(unit.get("source_nodes"), list):
                    referenced_source_ids.update(str(item) for item in unit["source_nodes"])
            source_docs.append((source_path, destination / output_path))
            section_rows.append((section, output_path))
            dump_json(destination / output_path, section_data)
    public_book = clean_book(book, section_rows, preview)
    dump_json(destination / "05_writing/book.json", public_book)

    origin = find_origin(case, name)
    manifest = locate_manifest(case)
    tree_sources = locate_tree_sources(case, referenced_source_ids)
    map_value = source_map(
        manifest,
        origin,
        materials_included=self_authored,
        referenced_source_ids=referenced_source_ids,
        tree_sources=tree_sources,
    )
    dump_json(destination / "source-map.json", map_value)

    stats = delivered_stats(case) if not self_authored else {
        "teaching_units": sum(len(section["units"]) for _, section in [(row, read_json(destination / path)) for row, path in section_rows]),
        "sections": len(section_rows),
    }
    info = public_case_info(name, book, preview, origin, stats)
    dump_json(destination / "case-info.json", info)

    if self_authored:
        source_dir = case / "00_source/materials/source-0001"
        html_source = source_dir / "original.html"
        if not html_source.is_file():
            html_source = source_dir / "offline.html"
        if html_source.is_file():
            target = destination / "sources/original.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(scrub_html(html_source), encoding="utf-8")
        image_source = source_dir / "original.png"
        if image_source.is_file():
            safe_image_copy(image_source, destination / "sources/original.png")

    dump_json(destination / "source-map.json", map_value)
    html_page = make_reader_html(destination, public_book, section_rows, map_value, info)
    (destination / "index.html").write_text(html_page, encoding="utf-8")
    return info


def make_reader_html(destination: Path, book: dict, section_rows: list[tuple[dict, str]], source_map_value: dict, info: dict) -> str:
    sections: dict[str, dict] = {}
    for source_ref, output_path in section_rows:
        data_path = destination / output_path
        data = read_json(data_path)
        sections[str(source_ref.get("id", ""))] = data
    embedded = {
        "book": book,
        "sections": sections,
        "sourceMap": source_map_value,
        "caseInfo": info,
    }
    encoded = json.dumps(embedded, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return READER_HTML.replace("__LESSONWEAVE_CASE_JSON__", encoded)


READER_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><title>LessonWeave 公开案例</title>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#1c2630;background:#f4f6f7;line-height:1.7;--panel:#fff;--line:#d7dfe3;--muted:#596a74;--accent:#176b67}*{box-sizing:border-box}body{margin:0}.top{position:sticky;top:0;background:var(--panel);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;justify-content:space-between;gap:16px;align-items:center;z-index:2}.top h1{font-size:16px;margin:0}.top small{color:var(--muted)}.layout{display:grid;grid-template-columns:270px minmax(0,1fr) 300px;gap:16px;max-width:1500px;margin:18px auto;padding:0 16px}.pane{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}.nav{position:sticky;top:76px;align-self:start;max-height:calc(100vh - 94px);overflow:auto}.nav h2,.side h2{font-size:15px;margin:0 0 10px}.nav button,.tab{display:block;width:100%;text-align:left;border:0;background:transparent;color:inherit;padding:8px;border-radius:7px;cursor:pointer}.nav button:hover,.nav button[aria-current=true],.tab[aria-selected=true]{background:#e8f2f1;color:var(--accent)}.main{min-height:80vh;padding:26px clamp(20px,4vw,64px)}h2{font-size:24px;line-height:1.4}h3{font-size:19px;margin:32px 0 10px}h4{font-size:16px;margin:24px 0 8px}p{margin:12px 0}.muted{color:var(--muted)}.notice{padding:10px 12px;border-left:4px solid #b17c2a;background:#fcf4e7;margin:12px 0 20px}.block{margin:12px 0}.media{border:1px solid var(--line);padding:12px;border-radius:8px;background:#fafbfb}.media img{max-width:100%;height:auto}.media-caption{font-weight:600}.media-guide{color:var(--muted)}pre{overflow:auto;background:#18232b;color:#eaf0f2;padding:14px;border-radius:8px}table{border-collapse:collapse;width:100%;margin:14px 0}td,th{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}.quiz,.term{border-top:1px solid var(--line);padding:10px 0}.term h4{margin:4px 0}.side{position:sticky;top:76px;align-self:start;max-height:calc(100vh - 94px);overflow:auto}.search{width:100%;padding:8px;border:1px solid var(--line);border-radius:6px;margin:4px 0 12px}.source-row{border-top:1px solid var(--line);padding:8px 0;font-size:13px;overflow-wrap:anywhere}.source-row code{font-size:12px}.small{font-size:13px}.controls{display:flex;gap:6px;margin:4px 0 12px}.controls button{border:1px solid var(--line);background:var(--panel);color:inherit;padding:6px 9px;border-radius:6px;cursor:pointer}.footer{max-width:1500px;margin:0 auto 30px;padding:0 16px;color:var(--muted);font-size:12px}@media(max-width:1050px){.layout{grid-template-columns:220px minmax(0,1fr)}.side{position:static;grid-column:1/-1;max-height:none}.main{padding:22px}}@media(max-width:680px){.layout{display:block}.nav,.main,.side{position:static;max-height:none;margin-bottom:12px}.top{padding:10px 12px}.main{padding:18px}.top small{display:none}}
</style>
</head><body>
<header class="top"><div><h1 id="book-title">正在读取案例</h1><small>LessonWeave 离线阅读案例</small></div><div class="controls"><button id="source-tab">来源记录</button><button id="term-focus">术语搜索</button></div></header>
<div class="layout"><nav class="pane nav"><h2>全书目录</h2><div id="toc"></div></nav><main class="pane main"><div id="status" class="notice" hidden></div><article id="article"></article></main><aside class="pane side"><h2>本节术语</h2><input id="term-search" class="search" type="search" placeholder="搜索术语"><div id="terms"></div><section><h2>来源记录</h2><div id="sources"></div></section></aside></div>
<footer class="footer">本页面只展示案例包内的已保存阅读结果；来源映射帮助识别页码或源码位置，但不能代替原材料。案例包的来源范围与恢复方式见 case-info.json。</footer>
<script id="case-data" type="application/json">__LESSONWEAVE_CASE_JSON__</script>
<script>
(()=>{const data=JSON.parse(document.getElementById('case-data').textContent),book=data.book,sections=data.sections;const $=id=>document.getElementById(id);const add=(parent,tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;parent.append(n);return n};const flatten=value=>Array.isArray(value)?value.map(flatten).join('\n'):value&&typeof value==='object'?Object.values(value).map(flatten).join('\n'):String(value??'');
document.title=(book.title||'LessonWeave 公开案例')+' · LessonWeave';$('book-title').textContent=book.title||'LessonWeave 公开案例';const info=data.caseInfo;if(info.reading_status==='preview'||!info.validation_passed){$('status').hidden=false;$('status').textContent='此案例保留为预览稿；原保存记录没有标记为检查通过。请把正文当作流程示例阅读，不要把它视为已验证结论。'}
function block(parent,value){if(!value)return;if(Array.isArray(value)){value.forEach(v=>block(parent,v));return}if(typeof value==='string'){add(parent,'p',value);return}if(typeof value!=='object')return;const kind=value.kind||'';if(kind==='heading'){add(parent,'h4',value.text||value.caption);return}if(kind==='table'){const table=add(parent,'table');const rows=[];if(Array.isArray(value.headers))rows.push(value.headers);if(Array.isArray(value.rows))rows.push(...value.rows);rows.forEach((row,index)=>{const tr=add(table,'tr');(Array.isArray(row)?row:[]).forEach(cell=>add(tr,index===0&&Array.isArray(value.headers)?'th':'td',flatten(cell))) });return}if(kind==='code'||kind==='formula'||kind==='mermaid'){const pre=add(parent,'pre');add(pre,'code',value.text||value.code||value.caption||value.guide||'');return}if(kind==='image'||value.guide||value.caption){const figure=add(parent,'figure',undefined,'media');if(value.alt)add(figure,'p',value.alt,'muted');if(value.caption)add(figure,'figcaption',value.caption,'media-caption');if(value.guide)add(figure,'p',value.guide,'media-guide');if(value.asset)add(figure,'p','原始媒体文件未随此案例包发布。','muted');return}if(value.text)add(parent,'p',value.text)}
function renderSection(id){const section=sections[id];if(!section)return;const article=$('article');article.replaceChildren();add(article,'p',section.section_number||'','muted');add(article,'h2',section.title||'');if(section.opening?.text)block(article,section.opening);if(section.opening_forward?.text)block(article,section.opening_forward);for(const unit of section.units||[]){add(article,'h3',unit.title||unit.question_id||'问题');if(unit.problem?.text)block(article,unit.problem);block(article,unit.explanation||[]);if(unit.synthesis?.text)block(article,unit.synthesis)}if(section.summary?.length){add(article,'h3','本节回答');section.summary.forEach(row=>{const card=add(article,'section',undefined,'media');add(card,'h4',row.question_id||'答案');block(card,row.answer)})}if(section.pitfalls?.length){add(article,'h3','易错点');section.pitfalls.forEach(row=>{const card=add(article,'section',undefined,'media');if(row.question)add(card,'h4',row.question);block(card,row.body)})}if(section.quiz?.length){add(article,'h3','练习');section.quiz.forEach((row,index)=>{const card=add(article,'details',undefined,'quiz');add(card,'summary',row.prompt?.text||('练习 '+(index+1)));(row.options||[]).forEach((option,i)=>add(card,'p',String.fromCharCode(65+i)+'. '+flatten(option)));if(row.explanation){add(card,'p','答案与解释：','muted');block(card,row.explanation)}})}renderTerms(section.glossary||[]);document.querySelectorAll('#toc button').forEach(button=>button.setAttribute('aria-current',String(button.dataset.section===id)))}
function renderTerms(items){const needle=$('term-search').value.trim().toLocaleLowerCase();const box=$('terms');box.replaceChildren();let count=0;for(const term of items){const search=[term.display,term.chinese,term.english,term.definition,...(term.aliases||[])].join(' ').toLocaleLowerCase();if(needle&&!search.includes(needle))continue;count++;const card=add(box,'section',undefined,'term');add(card,'h4',term.display||term.chinese||term.english||'术语');if(term.definition)add(card,'p',term.definition);if(term.explanation)block(card,term.explanation);if(term.aliases?.length)add(card,'p','别名：'+term.aliases.join('、'),'muted')}if(!count)add(box,'p','没有匹配的术语','muted')}
function sources(){const box=$('sources');box.replaceChildren();const map=data.sourceMap;add(box,'p',map.note,'muted small');if(map.origin_url){const link=add(box,'a',map.origin_url);link.href=map.origin_url;link.target='_blank';link.rel='noopener noreferrer'}if(data.caseInfo.source?.reacquire)add(box,'p',data.caseInfo.source.reacquire,'small');if(data.caseInfo.source?.command)add(box,'pre',data.caseInfo.source.command);if(data.caseInfo.original_material_included){const link=add(box,'a','打开随包保存的自编原文');link.href='sources/original.html';link.target='_blank'}for(const source of map.sources||[]){const row=add(box,'div',undefined,'source-row');add(row,'strong',source.id+' · '+source.kind);if(source.pages?.length)add(row,'div','页：'+source.pages.join('、'));if(source.files?.length){const names=source.files.map(id=>{const file=(map.files||[]).find(item=>item.id===id);return file?.path||id}).filter(Boolean);add(row,'div','文件：'+names.join('、'))}const selectorLocation=(source.locations||[]).find(location=>location.selector);if(selectorLocation)add(row,'div','网页位置：'+selectorLocation.selector);const lineLocation=(source.locations||[]).find(location=>Number.isInteger(location.start_line));if(lineLocation)add(row,'div','源码行：'+lineLocation.start_line+(lineLocation.end_line?'-'+lineLocation.end_line:''));if(source.locations?.length)add(row,'div','定位记录：'+source.locations.length+' 处');const ref=(map.files||[]).find(file=>file.id===lineLocation?.file)||(map.files||[]).find(file=>source.files?.includes(file.id));if(ref?.path&&data.caseInfo.source?.origin_url){const lineHash=lineLocation?.start_line?'#L'+lineLocation.start_line+(lineLocation.end_line?'-L'+lineLocation.end_line:''):'';const url=data.caseInfo.source.origin_url.replace(/\/$/,'')+'/blob/main/'+encodeURI(ref.path)+lineHash;const a=add(row,'a',lineLocation?.start_line?'查看引用源码行':'在上游仓库查看文件');a.href=url;a.target='_blank';a.rel='noopener noreferrer'}}if(map.unmapped_source_ids?.length)add(box,'p','有 '+map.unmapped_source_ids.length+' 个材料编号没有定位记录。','muted');for(const file of map.files||[]){if(!map.sources?.some(source=>source.files?.includes(file.id))){const row=add(box,'div',undefined,'source-row');add(row,'code',file.path||file.id)}}if(!(map.sources||[]).length)add(box,'p','当前包没有可公开的原件位置记录。','muted')}
for(const chapter of book.chapters||[]){const heading=add($('toc'),'h3',chapter.number+' '+chapter.title);heading.style.fontSize='14px';for(const section of chapter.sections||[]){const button=add($('toc'),'button',section.number+' '+section.title);button.dataset.section=section.id;button.onclick=()=>renderSection(section.id)}}$('term-search').addEventListener('input',()=>{const id=document.querySelector('#toc button[aria-current=true]')?.dataset.section;renderTerms(sections[id]?.glossary||[])});$('source-tab').onclick=()=>document.querySelector('.side').scrollIntoView({behavior:'smooth',block:'start'});$('term-focus').onclick=()=>{$('term-search').focus();$('term-search').scrollIntoView({behavior:'smooth',block:'center'})};sources();const first=(book.chapters||[]).flatMap(chapter=>chapter.sections||[])[0];if(first)renderSection(first.id);
})();
</script></body></html>'''


def add_license_files(source_root: Path, destination: Path) -> list[str]:
    copied: list[str] = []
    if not source_root.is_dir():
        return copied
    for source in sorted(source_root.rglob("*")):
        if not source.is_file() or source.is_symlink():
            continue
        if source.name.lower().startswith(("license", "copying", "notice")):
            relative = source.relative_to(source_root).as_posix()
            target = destination / "licenses/OpenROAD" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(relative)
    return copied


def make_minimal_case(source: Path, destination: Path) -> dict:
    book, preview = read_book(source, preview_ok=True)
    if not preview:
        raise SystemExit("自编 minimal-web 示例预期为预览稿；发现不同状态时停止自动改写")
    case = create_case(source, destination, "minimal-web", preview_ok=True, self_authored=True)
    case["source"]["included"] = True
    case["source"]["type"] = "self-authored web material"
    case["original_material_included"] = True
    case["source_restoration"] = "The source HTML and PNG are included after text, URL, path and image-metadata cleanup."
    dump_json(destination / "case-info.json", case)
    html_path = destination / "sources/original.html"
    if not html_path.is_file():
        raise SystemExit("自编 minimal-web 示例缺少可随包保存的原始 HTML")
    return case


def write_bundle_readme(root: Path, cases: dict[str, dict]) -> None:
    lines = [
        "# LessonWeave 公开阅读案例",
        "",
        "每个案例的 `index.html` 都可以直接打开；页面展示打包时已经保存的正文、媒体说明、练习、易错点和术语。打包器只读取已有文件，不启动生成任务，也不会调用模型。",
        "",
        "## 案例包含什么",
        "",
        "| 案例 | 生成状态 | 教学单元 | 小节 | 来源原件 |",
        "|---|---:|---:|---:|---|",
    ]
    for name in ("web", "pdf", "code", "minimal-web"):
        info = cases[name]
        stats = info.get("statistics", {})
        units = stats.get("teaching_units", "—")
        sections = stats.get("sections", "—")
        source = "仅自编示例" if info.get("original_material_included") else "未随包发布"
        lines.append(f"| `{name}` | {info.get('reading_status')} | {units} | {sections} | {source} |")
    lines += [
        "",
        "## 原始材料和来源怎样处理",
        "",
        "网页、PDF 和 OpenROAD 案例保留最终阅读内容、材料编号与页码或源码位置映射；没有把 WACZ、原网页、原 PDF 或完整源码树装进案例包。代码案例随包保留输入树中实际找到的 OpenROAD 根许可证及子目录许可证文件。",
        "",
        "`web` 记录了原案例公开网址，页面后来可能发生变化；`code` 提供上游仓库地址，但原记录没有保存源码提交号，所以重新克隆当前默认分支不能保证得到完全相同的输入；`pdf` 原记录只有本机文件地址，打包时已删除，没有可核实的下载网址，复现时需要自己提供有权使用的 PDF。",
        "",
        "`minimal-web` 使用自编材料，包中包含经过文本和图片元数据清理的 HTML 与 PNG，可用于查看来源映射示例；这本旧样稿仍标记为预览，保存的检查结果没有通过记录。",
        "",
        "覆盖数字只描述脚本记录的材料去向、问题分配和来源映射；它们不能证明事实正确或讲解充分。案例包也不等同于原始材料的完整再分发。",
        "",
        "## 哪些内容不会进入案例包",
        "",
        "打包器只从最终书稿、其引用的小节文件和来源定位清单生成公开内容。它排除模型提示词与回执、调用历史、用户笔记、运行状态、Cookies、私有路径、凭据和第三方原始材料。",
        "",
    ]
    (root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def manifest_files(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append({"path": relative, "size": path.stat().st_size, "sha256": digest})
    return rows


def audit_text_files(root: Path) -> None:
    violations = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".html", ".md", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            violations.append(path.relative_to(root).as_posix() + ": not UTF-8 text")
            continue
        samples = [text]
        if path.suffix.lower() == ".json":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                samples = list(iter_string_values(parsed))
        elif path.suffix.lower() == ".html":
            embedded = re.search(
                r'(?is)<script\s+id="case-data"\s+type="application/json">(.*?)</script\s*>', text
            )
            if embedded:
                try:
                    parsed = json.loads(embedded.group(1))
                except json.JSONDecodeError:
                    parsed = None
                if parsed is not None:
                    samples = [text[:embedded.start()] + text[embedded.end():], *iter_string_values(parsed)]

        checks = (
            (WINDOWS_PATH, "Windows path"),
            (PRIVATE_POSIX_PATH, "local path"),
            (EMAIL, "email address"),
            (INTERNAL_HOST, "internal host"),
            (SECRET_ASSIGNMENT, "credential-like value"),
        )
        for sample in samples:
            for pattern, label in checks:
                if pattern.search(sample):
                    violations.append(path.relative_to(root).as_posix() + ": " + label)
                    break
    if violations:
        raise SystemExit("公开案例文本审查发现需要人工处理的字段：" + ", ".join(violations[:12]))


def iter_string_values(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_string_values(str(key))
            yield from iter_string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_string_values(child)
    elif isinstance(value, str):
        yield value


def build(args: argparse.Namespace) -> tuple[Path, Path]:
    cases_root = args.cases_root.resolve()
    minimal_root = args.minimal_web.resolve()
    output_zip = args.output.resolve()
    output_dir = output_zip.with_suffix("")
    if output_zip.suffix.lower() != ".zip":
        raise SystemExit("--output 必须指向 .zip 文件")
    if output_dir.is_relative_to(REPO) or output_zip.is_relative_to(REPO):
        raise SystemExit("公开案例产物必须写在仓库目录之外")
    if output_zip.exists() or output_dir.exists():
        raise SystemExit("输出文件或目录已经存在；请换一个新的目标路径")
    missing = [name for name in CASE_NAMES if not (cases_root / name).is_dir()]
    if missing:
        raise SystemExit("案例目录不完整：" + ", ".join(missing))
    if not minimal_root.is_dir():
        raise SystemExit("找不到自编 minimal-web 示例目录")
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    case_infos: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="lessonweave-public-cases-", dir=output_zip.parent) as temporary:
        staging = Path(temporary) / output_dir.name
        staging.mkdir()
        for name in CASE_NAMES:
            case_infos[name] = create_case(cases_root / name, staging / name, name)
        case_infos["minimal-web"] = make_minimal_case(minimal_root, staging / "minimal-web")
        licenses = add_license_files(cases_root / "code/00_source/materials/repository", staging / "code")
        case_infos["code"]["preserved_upstream_license_files"] = licenses
        dump_json(staging / "code/case-info.json", case_infos["code"])
        for name, notice in (("LESSONWEAVE-LICENSE.txt", REPO / "LICENSE"), ("LESSONWEAVE-NOTICE.txt", REPO / "NOTICE")):
            if notice.is_file():
                shutil.copyfile(notice, staging / name)
        write_bundle_readme(staging, case_infos)
        inventory = {"schema": "lessonweave-public-case-bundle-v1", "version": "0.1.0", "files": manifest_files(staging)}
        dump_json(staging / "MANIFEST.json", inventory)
        audit_text_files(staging)
        with zipfile.ZipFile(output_zip, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(staging).as_posix())
        shutil.copytree(staging, output_dir)
    return output_zip, output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="从已有生成结果制作脱敏公开案例包；不调用模型、不改原件")
    parser.add_argument("--cases-root", required=True, type=Path, help="包含 web、pdf、code 三个已完成案例目录的位置")
    parser.add_argument("--minimal-web", required=True, type=Path, help="仓库中的自编 framework/examples/minimal-web 目录")
    parser.add_argument("--output", required=True, type=Path, help="仓库之外的新 .zip 输出路径；目标必须不存在")
    args = parser.parse_args()
    archive, folder = build(args)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"公开案例包已写入新文件：{archive.name}")
    print(f"展开目录包含 {sum(path.is_file() for path in folder.rglob('*'))} 个文件")
    print(f"SHA-256：{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
