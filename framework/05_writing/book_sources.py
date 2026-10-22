"""读取冻结材料并保存原文、来源范围与完整索引，供各小节独立清点信息"""

from __future__ import annotations

import copy
import io
import json
import re
from collections import defaultdict
from pathlib import Path
from zipfile import BadZipFile, ZipFile


INLINE_CHARACTER_LIMIT = 320_000
FILE_INLINE_LIMIT = 192_000
CHUNK_CHARACTER_LIMIT = 12_000
TEXT_ROLES = {"source", "document"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"}
MODEL_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
READABLE_RESOURCE_RULES_VERSION = 1
FONT_EXTENSIONS = {".flf", ".tlf", ".flc"}
SOURCE_FILE_NAMES = {"runme", "makefile", "gnumakefile", "dockerfile", ".gitignore", ".gitattributes", ".editorconfig"}
DOCUMENT_FILE_NAMES = {"license", "licence", "metadata", "wheel", "installer"}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _walk(node):
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def question_owners(qnodes,nodes,questions):
    """子项已有明确负责的问题时，父列表只提供阅读上下文，不重复分配讲解职责"""
    direct=defaultdict(list)
    for q in questions.values():
        if not q.get('children'):
            for nid in q['source_nodes']:direct[nid].append(q['id'])
    owners=defaultdict(list)
    for q in qnodes:
        for nid in q['source_nodes']:
            if q['id']not in owners[nid]:owners[nid].append(q['id'])
            if nodes[nid]['type']in {'figure','list','table'}:
                for child in _walk(nodes[nid]):
                    if not direct[child['id']] and q['id']not in owners[child['id']]:owners[child['id']].append(q['id'])
    return owners



def planned_question_owners(question_doc, material, qnodes):
    """后续取材沿用已确认用途，展开真实问题分支并保留多个问题的共同引用"""
    from source_disposition import evaluate
    requested = {q['id'] for q in qnodes}
    owners = defaultdict(list)
    for row in evaluate(question_doc, material)['nodes']:
        if row['role'] in {'teach', 'preface', 'reference'}:
            owners[row['material_node']] = sorted(requested & set(row.get('question_ids', [])))
    return owners

def complete_metadata(nodes, selected, owners, required):
    """标题被选中时同时带入其实际页头字段，不把整篇正文扩给引用问题"""
    for nid,node in nodes.items():
        anchor=node.get('content',{}).get('metadata_for')
        if anchor in selected:
            selected.add(nid);owners[nid]=list(owners[anchor])
            if nid not in required:required.append(nid)


def _local(root, value):
    value = str(value).replace("\\", "/")
    path = Path(value)
    # 材料树中的 /00_source 等路径相对于案例根，Windows 盘符路径按原样处理
    if not re.match(r"^[A-Za-z]:/", value):
        path = root / value.lstrip("/")
    path = path.resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"材料路径超出案例目录: {value}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def _decode(data):
    if not data:
        return "", "utf-8"
    # PDF 和压缩容器可能含有大量可打印字符，它们仍应交给对应解析器，不能当作源码或待翻译正文
    if data.startswith((b'%PDF-',b'PK\x03\x04',b'PK\x05\x06',b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'GIF87a',b'GIF89a',b'wOFF',b'wOF2')):
        return None,None
    encodings = ["utf-16"] if data.startswith((b"\xff\xfe", b"\xfe\xff")) else ["utf-8-sig", "cp1252"]
    for encoding in encodings:
        try:
            text = data.decode(encoding)
        except UnicodeError:
            continue
        if "\x00" not in text and sum(c.isprintable() or c.isspace() for c in text) / len(text) >= .94:
            return text, encoding
    return None, None


def _sentences(source_id, text, start_line=None):
    """保留逐句原文，完整空白与表格结构另由 original_texts 和 raw_content 保存"""
    if start_line is not None:
        lines = text.splitlines(keepends=True)
        return [{"id": f"{source_id}.L{start_line + i}-L{start_line + min(i + 19, len(lines) - 1)}",
                 "original": "".join(lines[i:i + 20]), "translation": "",
                 "start_line": start_line + i, "end_line": start_line + min(i + 19, len(lines) - 1)}
                for i in range(0, len(lines), 20) if "".join(lines[i:i + 20]).strip()]
    parts = re.split(r"(?<=[.!?。！？])\s+(?=[A-Z\d\u4e00-\u9fff(\[“\"])", text)
    return [{"id": f"{source_id}.s{i}", "original": part, "translation": ""}
            for i, part in enumerate(parts, 1) if part.strip()]


def _texts(node):
    content = node.get("content", {})
    values = []
    for key in ("text", "raw_text", "alt"):
        value = content.get(key)
        if isinstance(value, str) and value.strip() and value not in values:
            values.append(value)
    # 表格单元格与顺序都保留，TSV 仅用于逐行引用，原始二维数组仍在 raw_content 中
    if isinstance(content.get("rows"), list):
        values.append("\n".join("\t".join(str(cell) for cell in row) for row in content["rows"]))
    for item in content.get("source_text", []):
        value = item if isinstance(item, str) else item.get("text", "") if isinstance(item, dict) else ""
        if value.strip() and value not in values:
            values.append(value)
    return values


def generated_pdf_container_sentence(root, source):
    """核对旧解析器生成的文件名和整页编号，实际正文及局部标题继续参与逐句检查"""
    if source.get('type') not in {'document','section'} or not source.get('child_ids'):
        return None
    content=source.get('raw_content',{})
    if content.get('source_text') or len(source.get('sentences',[]))!=1:
        return None
    ref=source.get('source',{})
    try:
        path=_local(Path(root),ref.get('path',''))
        if path.suffix.lower()!='.pdf':
            return None
        if source['type']=='document' and ref.get('kind')=='file':
            expected=path.stem
        elif source['type']=='section' and ref.get('kind')=='pdf':
            import fitz
            with fitz.open(path) as pdf:
                page=pdf[int(ref['page'])-1]
                if len(ref.get('bbox',[]))!=4 or any(abs(a-b)>0.1 for a,b in zip(ref['bbox'],list(page.rect))):
                    return None
            expected=str(ref['page'])
        else:
            return None
        sentence=source['sentences'][0]
        if content.get('text')!=expected or sentence.get('original')!=expected:
            return None
        return {'source_id':source['id'],'sentence_id':sentence['id'],'kind':'generated_pdf_container_label','original':expected,'file':path.relative_to(root).as_posix()}
    except (OSError,ValueError,KeyError,IndexError):
        return None


def _derived_file_role(path, text, mime, declared_role):
    """用实际文本和明确文件名补充角色，字体、图像和安装文件索引继续保留原职责"""
    if text is None:
        return declared_role
    name = path.name.casefold()
    if (path.suffix.lower() in FONT_EXTENSIONS or text.startswith(("flf2a", "tlf2a"))
            or _is_image(path, mime) or name == "record"):
        return declared_role
    if path.suffix.lower() == ".csv" or name in SOURCE_FILE_NAMES or text.startswith("#!"):
        return "source"
    if name in DOCUMENT_FILE_NAMES:
        return "document"
    return declared_role


def _repository_root(root):
    record=root/'00_source/source.json'
    relative=_read(record).get('repository','00_source/materials/repository') if record.is_file() else '00_source/materials/repository'
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('仓库目录超出当前项目')
    return path


def _file_fragments(root, node, legacy_resource_roles=False):
    """始终从实际文件读取源码，树中的概括说明只作为 tree_metadata 保留"""
    fragments = []
    seen = set()
    for locator in node.get("source", []):
        value=locator.get('path','').replace('\\','/')
        if not value or not (root/value.lstrip('/')).resolve().is_relative_to(_repository_root(root)):
            continue
        path = _local(root, locator["path"])
        data = path.read_bytes()
        text, encoding = _decode(data)
        start = locator.get("start_byte", 0)
        end = locator.get("end_byte", len(data))
        if not 0 <= start <= end <= len(data):
            raise ValueError(f"源码范围无效: {node['id']} {locator}")
        fragment, fragment_encoding = _decode(data[start:end]) if text is not None else (None, None)
        key = (str(path), start, end)
        if key in seen:
            continue
        seen.add(key)
        start_line = data[:start].count(b"\n") + 1
        source = dict(locator, kind="code" if fragment is not None else "file", start_byte=start, end_byte=end,
                      start_line=start_line, end_line=start_line + max(0, len(data[start:end].splitlines()) - 1))
        mime = node.get("content", {}).get("mime", "")
        declared = node.get("content", {}).get("role", "document" if path.suffix.lower() in {".md", ".rst", ".txt"} else "source")
        role = declared if legacy_resource_roles else _derived_file_role(path, text, mime, declared)
        entry = {"source": source, "absolute_path": str(path), "file_bytes": len(data),
                 "encoding": fragment_encoding or encoding, "text": fragment, "mime": mime, "role": role}
        if role != declared:
            entry.update(role_rule="readable-resource-v1", declared_role=declared)
        fragments.append(entry)
    return fragments


def _store_text(work, source_id, index, text, source, persist=True):
    dest = work / "raw-texts" / f"{source_id}-{index}.json"
    lines = text.splitlines(keepends=True)
    chunks = []
    current = ""
    offset = source.get("start_line", 1)
    first = offset
    for line in lines:
        if current and len(current) + len(line) > CHUNK_CHARACTER_LIMIT:
            chunks.append({"start_line": first, "end_line": offset - 1, "text": current})
            first = offset
            current = ""
        current += line
        offset += 1
    if current or not lines:
        chunks.append({"start_line": first, "end_line": max(first, offset - 1), "text": current})
    if persist:
        _save(dest, {"source_id": source_id, "source": source, "text": text, "chunks": chunks})
    return {"path": str(dest), "characters": len(text), "chunk_count": len(chunks),
            "start_line": source.get("start_line", 1), "end_line": source.get("end_line", max(1, len(lines)))}


def _index_record(node, fragments):
    content = node.get("content", {})
    index = {"id": node["id"], "type": node["type"]}
    for key in ("path", "name", "role", "mime", "bytes"):
        if key in content:
            index[key] = copy.deepcopy(content[key])
    index["child_ids"] = [c["id"] for c in node.get("children", [])]
    if fragments and "path" not in index:
        index["files"] = [{"path": f["source"]["path"], "bytes": f["file_bytes"],
                           "start_byte": f["source"]["start_byte"], "end_byte": f["source"]["end_byte"]}
                          for f in fragments]
    return index


def _generated_file_index_audit(root, node):
    """仅识别架构适配器固定生成的归档列表分组，并核对实际归档和解压文件"""
    content = node.get("content", {})
    if (node.get("type") != "section" or content.get("text") != "原始文件与附件"
            or content.get("view") != "files" or content.get("source_text", []) != []
            or set(content) - {"text", "view", "source_text"}):
        return None
    children = node.get("children", [])
    if not children or any(child.get("type") not in {"file", "directory"} for child in children):
        return None
    locators = node.get("source", [])
    if len(locators) != 1 or locators[0].get("kind") != "file":
        return None
    files = [child for child in _walk(node) if child.get("type") == "file"]
    if not files:
        return None
    try:
        archive = _local(root, locators[0].get("path", ""))
        if not archive.is_relative_to(root / "00_source/materials") or archive.suffix.lower() != ".zip":
            return None
        with ZipFile(archive) as original:
            members = {entry.filename: entry for entry in original.infolist() if not entry.is_dir()}
            seen = set()
            for file in files:
                member = file.get("content", {}).get("archive_member")
                refs = file.get("source", [])
                if member not in members or member in seen or len(refs) != 1 or refs[0].get("kind") != "file":
                    return None
                path = _local(root, refs[0].get("path", ""))
                if (not path.is_relative_to(_repository_root(root))
                        or path.stat().st_size != members[member].file_size
                        or file.get("content", {}).get("bytes") != members[member].file_size):
                    return None
                seen.add(member)
    except (OSError, ValueError, BadZipFile):
        return None
    return {"rule": "architecture-file-inventory-label-v1",
            "adapter": "01_tree/architecture.py::parse_architecture",
            "archive_path": archive.relative_to(root).as_posix(), "verified_file_count": len(files),
            "reason": "架构适配器为归档文件列表生成这段分组文字，冻结节点没有真实源文本，已核对归档成员和本地解压文件，这段记录保留给 Debug 核对"}


def _mark_generated_file_index(source, audit):
    source["evidence_kind"] = "material_index"
    source["material_index_audit"] = copy.deepcopy(audit)
    for sentence in source.get("sentences", []):
        sentence["evidence_kind"] = "material_index"


def refresh_generated_material_indices(root, raw, pack):
    """给已生成材料标明可证实的树分组文字，原句、译文与既有信息点全部保持原样"""
    root = Path(root).resolve()
    raw2, pack2 = copy.deepcopy(raw), copy.deepcopy(pack)
    if any(raw.get(key) != pack.get(key) for key in ("section_id", "material_run", "material_path")):
        raise ValueError("核对树分组文字时，原始材料与已清点材料需要对应同一小节和冻结版本")
    material = _read(_local(root, raw["material_path"]))
    nodes = {node["id"]: node for node in _walk(material["tree"])}
    raw_sources = {source["id"]: source for source in raw2.get("sources", [])}
    pack_sources = {source["id"]: source for source in pack2.get("sources", [])}
    for source_id in raw_sources.keys() & pack_sources.keys() & nodes.keys():
        node = nodes[source_id]
        audit = _generated_file_index_audit(root, node)
        if not audit:
            continue
        expected = {"type": node["type"], "source_refs": node.get("source", []),
                    "raw_content": node["content"], "original_texts": {source_id: node["content"]["text"]},
                    "child_ids": [child["id"] for child in node.get("children", [])]}
        expected_sentences = {row["id"]: row["original"] for row in _sentences(source_id, node["content"]["text"])}
        candidates = (raw_sources[source_id], pack_sources[source_id])
        if any(any(source.get(key) != value for key, value in expected.items())
               or source.get("file_fragments")
               or {row["id"]: row["original"] for row in source.get("sentences", [])} != expected_sentences
               for source in candidates):
            continue
        for source in candidates:
            _mark_generated_file_index(source, audit)
    return raw2, pack2


def _is_image(path, mime=""):
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS or str(mime).startswith("image/")


def _record_image_path(root, source):
    # 仓库文件优先使用实际文件定位，避免把另一个 PNG 当成该 SVG 的原图
    candidates = [(file["source"]["path"], file.get("mime", "")) for file in source.get("file_fragments", [])]
    candidates += [(source.get("source", {}).get("path", ""), source.get("tree_metadata", {}).get("mime", ""))]
    candidates += [(source.get("asset", ""), "")]
    for path, mime in candidates:
        if path and _is_image(path, mime):
            return _local(root, path), mime
    return None, ""


def _add_visual(root, work, source, cache, persist=True):
    path, mime = _record_image_path(root, source)
    if path is None:
        return None
    asset = "/" + path.relative_to(root).as_posix()
    source["asset"] = asset
    key = str(path)
    if key not in cache:
        svg = path.suffix.lower() == ".svg" or mime == "image/svg+xml"
        if svg or path.suffix.lower() not in MODEL_IMAGE_EXTENSIONS:
            preview = work / "image-previews" / f"{source['id']}.png"
            renderer = "cairosvg" if svg else "pillow"
            if persist:
                preview.parent.mkdir(parents=True, exist_ok=True)
                if svg:
                    import cairosvg
                    import xml.etree.ElementTree as ET
                    attributes = ET.parse(path).getroot().attrib
                    box = re.split(r'[\s,]+', attributes.get('viewBox', attributes.get('viewbox', '')).strip())
                    if len(box) == 4:
                        width, height = map(float, box[2:])
                        cairosvg.svg2png(url=str(path), write_to=str(preview), output_width=1200,
                                        output_height=max(1, round(1200 * height / width)))
                    else:
                        cairosvg.svg2png(url=str(path), write_to=str(preview), output_width=1200, output_height=600)
                else:
                    from PIL import Image
                    with Image.open(path) as image:
                        image.convert("RGBA").save(preview, format="PNG")
            cache[key] = {"asset": asset, "original_path": str(path), "model_path": str(preview),
                          "renderer": renderer, "scale": 2 if svg else 1}
        else:
            cache[key] = {"asset": asset, "original_path": str(path), "model_path": str(path),
                          "renderer": "original", "scale": 1}
    visual = dict(cache[key], source_id=source["id"])
    if visual["renderer"] != "original":
        source["image_preview"] = {"path": visual["model_path"], "source_asset": asset,
                                   "renderer": visual["renderer"], "scale": visual["scale"]}
    return visual


def refresh_visual_sources(root, raw, pack, work):
    """给已有材料补上遗漏的原图与视觉输入，保留原句、OCR 和现有信息点原样"""
    root, work = Path(root).resolve(), Path(work).resolve()
    if raw.get("section_id") != pack.get("section_id") or raw.get("material_run") != pack.get("material_run"):
        raise ValueError("补充原图时原始材料与已清点材料需要对应同一小节和冻结版本")
    raw2, pack2 = copy.deepcopy(raw), copy.deepcopy(pack)
    originals = {source["id"]: source for source in raw["sources"]}
    packaged = {source["id"]: source for source in pack["sources"]}
    cache, visuals, newly_visible = {}, [], []
    old_images = {str(Path(path).resolve()) for path in raw.get("images", [])}
    for source in raw2["sources"]:
        visual = _add_visual(root, work, source, cache)
        if visual is None:
            continue
        visuals.append(visual)
        source_id = source["id"]
        prior = originals[source_id]
        in_pack = packaged.get(source_id, {})
        seen = str(Path(visual["model_path"]).resolve()) in old_images
        if prior.get("asset") != visual["asset"] or in_pack.get("asset") != visual["asset"] or not seen:
            newly_visible.append(source_id)
    for source in pack2["sources"]:
        _add_visual(root, work, source, cache)
    images = list(dict.fromkeys(visual["model_path"] for visual in visuals))
    raw2.update(images=images, visual_assets=copy.deepcopy(visuals))
    pack2.update(images=copy.deepcopy(images), visual_assets=copy.deepcopy(visuals))
    return raw2, pack2, list(dict.fromkeys(newly_visible))


def refresh_confirmed_regions(root, raw, pack):
    """从当前 demo 指向的冻结材料中继承已确认区域，原图与材料版本都要相同"""
    root = Path(root).resolve()
    raw2, pack2 = copy.deepcopy(raw), copy.deepcopy(pack)
    demo_path = root / "05_writing/demo.json"
    if not demo_path.is_file():
        return raw2, pack2
    demo = _read(demo_path)
    source_pack_path = demo.get("grounding", {}).get("source_pack_path")
    if not source_pack_path:
        return raw2, pack2
    confirmed = _read(_local(root, source_pack_path))
    for field in ("material_run", "material_path"):
        value = confirmed.get(field)
        if not isinstance(value, str) or not value or raw.get(field) != value or pack.get(field) != value:
            return raw2, pack2
    old_sources = {source["id"]: source for source in confirmed.get("sources", [])}
    raw_sources = {source["id"]: source for source in raw.get("sources", [])}
    pack_sources = {source["id"]: source for source in pack.get("sources", [])}
    for source_id, regions in confirmed.get("image_regions", {}).items():
        if not isinstance(regions, dict) or not regions:
            continue
        asset = old_sources.get(source_id, {}).get("asset")
        if (not asset or raw_sources.get(source_id, {}).get("asset") != asset
                or pack_sources.get(source_id, {}).get("asset") != asset):
            continue
        for target in (raw2, pack2):
            current = target.setdefault("image_regions", {}).setdefault(source_id, {})
            # 已确认的同名区域保持冻结坐标，其他既有区域继续保留
            current.update(copy.deepcopy(regions))
    return raw2, pack2


def prepare_session(root):
    """原生材料树一次加载与展开，后续小节沿用同一份来源索引"""
    path=Path(root)/'01_tree/tree.json'
    if not path.is_file():
        return None
    material = _read(path)
    if material.get('format') == 'full-material-tree':
        from native_sources import NativeSources
        return NativeSources(root, material)
    return None


def prepare_sources(root: Path, section_id: str, work: Path, session=None) -> dict:
    if session is not None:
        return session.pack(section_id, work)
    return _prepare_sources(root, section_id, work, persist=True)


def _refresh_reading_metadata(pack, changed_ids):
    """根据实际保留的全文和文件职责重新计算读取状态，不修改任何信息点"""
    families = defaultdict(list)
    deferred, unresolved = [], []
    for source in pack["sources"]:
        for index, fragment in enumerate(source.get("file_fragments", []), 1):
            storage = fragment.get("text_storage")
            if not storage:
                continue
            family = str(Path(fragment["source"]["path"]).parent).replace("\\", "/")
            families[family].append({"source_id": source["id"], "path": fragment["source"]["path"],
                                    "role": fragment["role"], "characters": storage["characters"],
                                    "read_policy": fragment["read_policy"]})
            if fragment["read_policy"] == "indexed_complete":
                entry = {"source_id": source["id"], "fragment": index, "family": family, **copy.deepcopy(storage)}
                deferred.append(entry)
                if fragment["role"] in TEXT_ROLES:
                    unresolved.append(copy.deepcopy(entry))
    metadata = pack.setdefault("metadata", {})
    metadata.update(readable_resource_rules_version=READABLE_RESOURCE_RULES_VERSION,
                    inline_characters=sum(len(text) for source in pack["sources"] for text in source.get("original_texts", {}).values()),
                    deferred_fragments=deferred, unresolved_required_fragments=unresolved,
                    file_families=[{"path": path, "members": members} for path, members in families.items()])
    sources = {source["id"]: source for source in pack["sources"]}
    for item in pack.get("material_manifest", []):
        if item["id"] in changed_ids:
            source = sources[item["id"]]
            item["sentence_ids"] = [row["id"] for row in source["sentences"]]
            item["file_fragments"] = copy.deepcopy(source.get("file_fragments", []))


def refresh_readable_resource_sources(root, raw, pack, work):
    """补上实际可读脚本和配置的原句，保留旧索引、译文、图标签与既有引用"""
    root, work = Path(root).resolve(), Path(work).resolve()
    if any(raw.get(key) != pack.get(key) for key in ("section_id", "material_run", "material_path")):
        raise ValueError("补充可读资源时，原始材料与已清点材料需要对应同一小节和冻结版本")
    fresh = _prepare_sources(root, raw["section_id"], work / "readable-resource-refresh", persist=False)
    if any(raw.get(key) != fresh.get(key) for key in ("material_run", "material_path")):
        raise ValueError("可读资源的实际材料版本与冻结小节引用不一致")
    candidates = {source["id"]: source for source in fresh["sources"] if any(
        fragment.get("role_rule") == "readable-resource-v1" and fragment["role"] in TEXT_ROLES
        for fragment in source.get("file_fragments", []))}
    raw2, pack2 = copy.deepcopy(raw), copy.deepcopy(pack)
    if not candidates:
        return raw2, pack2, []
    added = []
    for target in (raw2, pack2):
        sources = {source["id"]: source for source in target["sources"]}
        for source_id, expected in candidates.items():
            if source_id not in sources:
                raise ValueError("需要补充真实正文的节点未保留在材料包中：" + source_id)
            source = sources[source_id]
            if source.get("source_refs") != expected.get("source_refs"):
                raise ValueError("需要补充正文的节点实际文件定位发生变化：" + source_id)
            old_files = source.get("file_fragments", [])
            if len(old_files) != len(expected.get("file_fragments", [])):
                raise ValueError("需要补充正文的文件范围数量发生变化：" + source_id)
            updated_files = []
            for index, (old_file, new_file) in enumerate(zip(old_files, expected["file_fragments"]), 1):
                if old_file["source"] != new_file["source"]:
                    raise ValueError("补充正文前需要核对同一实际文件范围：" + source_id)
                merged = {**copy.deepcopy(old_file), **copy.deepcopy(new_file)}
                if new_file.get("text_storage"):
                    locator = new_file["source"]
                    data = _local(root, locator["path"]).read_bytes()[locator["start_byte"]:locator["end_byte"]]
                    text, _ = _decode(data)
                    if text is None:
                        raise ValueError("需要补充正文的文件已无法按原编码读取：" + source_id)
                    storage = old_file.get("text_storage")
                    if storage:
                        stored = _read(storage["path"])
                        if (stored.get("source") != locator or stored.get("text") != text
                                or "".join(row.get("text", "") for row in stored.get("chunks", [])) != text):
                            raise ValueError("已保存全文与实际文件不同，保留旧记录等待外层修复：" + source_id)
                        merged["text_storage"] = copy.deepcopy(storage)
                    else:
                        merged["text_storage"] = _store_text(work / "readable-resource-refresh", source_id, index, text, locator)
                updated_files.append(merged)
            source["file_fragments"] = updated_files
            for key, text in expected.get("original_texts", {}).items():
                if key in source["original_texts"] and source["original_texts"][key] != text:
                    raise ValueError("已有原文与实际新增文件范围不同：" + source_id)
                source["original_texts"][key] = text
            by_id = {row["id"]: row for row in source.get("sentences", [])}
            if len(by_id) != len(source.get("sentences", [])):
                raise ValueError("已有材料的原句 ID 重复：" + source_id)
            for row in expected.get("sentences", []):
                if row["id"] in by_id:
                    old = by_id[row["id"]]
                    if any(old.get(key) != row.get(key) for key in ("original", "start_line", "end_line", "verbatim_code", "evidence_kind")):
                        raise ValueError("同一原句 ID 的实际文字或范围发生变化：" + row["id"])
                    continue
                source["sentences"].append(copy.deepcopy(row))
                if row.get("evidence_kind") != "material_index" and source_id not in added:
                    added.append(source_id)
            source["type"] = expected["type"]
            if "material_type" in expected:
                source["material_type"] = expected["material_type"]
        _refresh_reading_metadata(target, set(candidates))
    return raw2, pack2, added


def _prepare_sources(root: Path, section_id: str, work: Path, persist: bool, legacy_resource_roles: bool = False) -> dict:
    """按冻结问题归属收集本节全部材料，超出上下文预算的文件另存全文并明确标记"""
    root, work = Path(root).resolve(), Path(work).resolve()
    if persist:
        work.mkdir(parents=True, exist_ok=True)
    plan = _read(root / "04_transitions/transitions.json")
    material = _read(_local(root, plan["material_tree"]))
    question_doc = _read(_local(root, plan["question_tree"]))
    chapters = _read(_local(root, plan["chapters_path"]))
    nodes = {n["id"]: n for n in _walk(material["tree"])}
    questions = {n["id"]: n for n in _walk(question_doc["tree"])}
    sections = {n["id"]: n for n in _walk(chapters["tree"]) if n.get("kind") == "section"}
    if section_id not in sections:
        raise ValueError(f"冻结目录没有这个小节: {section_id}")
    qnodes = [questions[qid] for qid in sections[section_id]["question_ids"] if not questions[qid].get("children")]
    if not qnodes:
        raise ValueError(f"小节没有具体问题: {section_id}")
    modern_owners = planned_question_owners(question_doc, material, qnodes) if question_doc.get('planning_version') == 2 else None
    required = [nid for nid in nodes if modern_owners[nid]] if modern_owners is not None else list(dict.fromkeys(nid for q in qnodes for nid in q['source_nodes']))
    missing = [nid for nid in required if nid not in nodes]
    if missing:
        raise ValueError(f"问题引用的材料节点不存在: {missing}")
    selected = set(required)
    # 图组、列表和表格按完整对象读取，文档和章节容器保留结构而不递归展开整本材料
    for nid in required:
        if nodes[nid]["type"] in {"figure", "list", "table"}:
            selected.update(child["id"] for child in _walk(nodes[nid]))
    owners = modern_owners if modern_owners is not None else question_owners(qnodes,nodes,questions)
    complete_metadata(nodes,selected,owners,required)
    ordered = [nid for nid in nodes if nid in selected]
    sources, manifest, images, deferred, visual_assets = [], [], [], [], []
    visual_cache = {}
    families = defaultdict(list)
    inline_chars = 0
    budget_chars = 0
    for nid in ordered:
        node = nodes[nid]
        content = node.get("content", {})
        locators = copy.deepcopy(node.get("source", []))
        record = {"id": nid, "type": node["type"], "source": locators[0] if locators else {},
                  "source_refs": locators, "original_texts": {}, "sentences": [],
                  "question_ids": owners[nid], "child_ids": [c["id"] for c in node.get("children", [])]}
        fragments = _file_fragments(root, node, legacy_resource_roles=legacy_resource_roles)
        if fragments:
            record["tree_metadata"] = copy.deepcopy(content)
            record["file_fragments"] = []
            for index, fragment in enumerate(fragments, 1):
                text = fragment.pop("text")
                entry = dict(fragment)
                if text is None:
                    entry["read_policy"] = "original_attachment"
                    record.setdefault("asset", "/" + fragment["source"]["path"])
                else:
                    storage = _store_text(work, nid, index, text, fragment["source"], persist=persist)
                    entry["text_storage"] = storage
                    family = str(Path(fragment["source"]["path"]).parent).replace("\\", "/")
                    role = fragment["role"]
                    promoted = fragment.get("role_rule") == "readable-resource-v1" and fragment.get("declared_role") not in TEXT_ROLES
                    if promoted and role == "source":
                        record["type"] = "code"
                        record["material_type"] = node["type"]
                    # 新识别的脚本和配置单独读入，既有源码的预算顺序保持稳定，大文件仍明确列入待补范围
                    use_inline = role in TEXT_ROLES and len(text) <= FILE_INLINE_LIMIT and (promoted or budget_chars + len(text) <= INLINE_CHARACTER_LIMIT)
                    entry["read_policy"] = "inline_complete" if use_inline else "indexed_complete"
                    if use_inline:
                        key = nid if len(fragments) == 1 else f"{nid}.range{index}"
                        record["original_texts"][key] = text
                        sentences = _sentences(key, text, fragment["source"]["start_line"]) if role == "source" else _sentences(key, text)
                        if role == "source":
                            record["type"] = "code"
                            record["material_type"] = node["type"]
                            for sentence in sentences:
                                sentence.update(translation=sentence["original"], verbatim_code=True)
                        record["sentences"].extend(sentences)
                        inline_chars += len(text)
                        if not promoted:
                            budget_chars += len(text)
                    else:
                        deferred.append({"source_id": nid, "fragment": index, "family": family, **storage})
                    families[family].append({"source_id": nid, "path": fragment["source"]["path"],
                                             "role": role, "characters": len(text), "read_policy": entry["read_policy"]})
                record["file_fragments"].append(entry)
            record["source"] = copy.deepcopy(record["file_fragments"][0]["source"])
        else:
            record["raw_content"] = copy.deepcopy(content)
            texts = _texts(node)
            for index, text in enumerate(texts, 1):
                key = nid if len(texts) == 1 else f"{nid}.text{index}"
                record["original_texts"][key] = text
                record["sentences"].extend(_sentences(key, text))
                inline_chars += len(text)
                budget_chars += len(text)
        if not record["sentences"]:
            index = _index_record(node, record.get("file_fragments", []))
            record["index_record"] = index
            record["sentences"] = [{"id": f"{nid}.index", "original": json.dumps(index, ensure_ascii=False, separators=(",", ":")),
                                    "translation": "", "evidence_kind": "material_index"}]
        audit = _generated_file_index_audit(root, node)
        if audit:
            _mark_generated_file_index(record, audit)
        if content.get("asset"):
            path = _local(root, content["asset"])
            record["asset"] = "/" + path.relative_to(root).as_posix()
        elif fragments and (content.get("role") == "attachment" or any(Path(f["source"]["path"]).suffix.lower() == ".pdf" for f in record["file_fragments"])):
            record["asset"] = "/" + record["file_fragments"][0]["source"]["path"]
            record["coverage_scope"] = "file_role"
            record["scope_note"] = "本节讲解项目如何使用这份附件，附件全文作为资料附录完整保留，逐页讲解将在用户选择深入这份附件时展开"
        if node["type"] == "figure":
            record["source_ids"] = [n["id"] for n in _walk(node)]
            if not record.get("asset"):
                asset = next((n.get("content", {}).get("asset") for n in _walk(node) if n.get("content", {}).get("asset")), None)
                if asset:
                    record["asset"] = "/" + _local(root, asset).relative_to(root).as_posix()
        visual = _add_visual(root, work, record, visual_cache, persist=persist)
        if visual:
            visual_assets.append(visual)
            if visual["model_path"] not in images:
                images.append(visual["model_path"])
        manifest.append({"id": nid, "type": node["type"], "question_ids": owners[nid],
                         "directly_mapped": nid in required, "sentence_ids": [s["id"] for s in record["sentences"]],
                         "asset": record.get("asset"), "file_fragments": copy.deepcopy(record.get("file_fragments", [])),
                         "child_ids": record["child_ids"]})
        sources.append(record)
    result = {"profile": "writing-raw-sources-v1", "section_id": section_id,
              "material_run": plan["material_run"], "material_path": plan["material_tree"],
              "question_path": plan["question_tree"], "chapters_path": plan["chapters_path"],
              "questions": [{key: copy.deepcopy(q.get(key, [] if key in {"source_nodes", "depends_on"} else ""))
                             for key in ("id", "premise", "question", "intent", "source_nodes", "depends_on")} for q in qnodes],
              "sources": sources, "required_source_ids": required, "images": images, "visual_assets": visual_assets,
              "material_manifest": manifest,
              "metadata": {"mapped_nodes": len(required), "included_nodes": len(sources),
                           "inline_characters": inline_chars, "deferred_fragments": deferred,
                           "unresolved_required_fragments": [d for d in deferred
                               if next(f for s in sources if s["id"] == d["source_id"]
                                       for i, f in enumerate(s.get("file_fragments", []), 1) if i == d["fragment"])["role"] in TEXT_ROLES],
                           "file_families": [{"path": path, "members": members} for path, members in families.items()],
                           "text_files_are_complete": True, "original_assets_are_unchanged": True,
                           "scope": "每个映射节点均保留原文、图片、实际源码范围或完整分类索引，图组、列表和表格连同子对象读取，其他结构容器保留其直接子节点索引",
                           "code_scope": "代码按实际文件范围读取，树中的概括说明只供定位，附件与字体家族保留完整本地索引，PDF 等附件按 file_role 讲解项目如何使用这些资料，附件页内内容作为资料附录保留，indexed_complete 文件的完整文字和逐行分块位于 text_storage，清点任务需要读取与当前问题有关的细节，并明确记录每个家族的教学职责",
                           "coverage_boundary": "本文件只保证材料收集与可读取性，信息点讲解完成情况由后续清点、正文绑定和独立审查计算"}}
    if not legacy_resource_roles:
        result["metadata"]["readable_resource_rules_version"] = READABLE_RESOURCE_RULES_VERSION
    result, _ = refresh_confirmed_regions(root, result, result)
    if persist:
        _save(work / "raw-sources.json", result)
    return result


def model_context(raw: dict) -> dict:
    """给模型提供完整节点清单与已读原文，省去重复保存的定位和原始树描述"""
    sources = []
    manifest = []
    for source in raw["sources"]:
        entry = {key: copy.deepcopy(source[key]) for key in
                 ("id", "type", "source", "sentences", "question_ids", "asset", "source_ids", "material_type", "image_preview", "coverage_scope", "scope_note", "evidence_kind", "material_index_audit")
                 if key in source}
        for sentence in entry.get("sentences", []):
            if source.get("verbatim_code") or sentence.get("verbatim_code"):
                sentence.pop("translation", None)
        if len(source.get("source_refs", [])) > 1:
            entry["source_refs"] = copy.deepcopy(source["source_refs"])
        files = []
        for fragment in source.get("file_fragments", []):
            file = {key: copy.deepcopy(fragment[key]) for key in ("source", "role", "read_policy", "text_storage") if key in fragment}
            files.append(file)
        required_deferred = [f for f in files if f.get("role") in TEXT_ROLES and f.get("read_policy") == "indexed_complete"]
        if required_deferred:
            entry["unresolved_required_fragments"] = required_deferred
        if source.get("index_record") and files:
            entry["source"] = {"kind": "file_index"}
        if "rows" in source.get("raw_content", {}):
            entry["table_rows"] = copy.deepcopy(source["raw_content"]["rows"])
        if source.get("raw_content", {}).get("ordered") is not None:
            entry["list_order"] = {k: source["raw_content"][k] for k in ("ordered", "start", "marker", "ordinal") if k in source["raw_content"]}
        sources.append(entry)
        manifest.append({"id": source["id"],
                         "directly_mapped": source["id"] in raw.get("required_source_ids", {s["id"] for s in raw["sources"]}),
                         "read_policy": sorted({f["read_policy"] for f in files}) if files else ["inline_complete"]})
    return {key: copy.deepcopy(raw[key]) for key in
            ("profile", "section_id", "material_run", "material_path", "questions", "required_source_ids", "images", "visual_assets", "image_regions") if key in raw} | {
                "sources": sources, "material_manifest": manifest,
                "metadata": {"inline_characters": raw["metadata"]["inline_characters"],
                             "scope": raw["metadata"]["scope"], "code_scope": raw["metadata"]["code_scope"],
                             "coverage_boundary": raw["metadata"]["coverage_boundary"],
                             "deferred_source_ids": sorted({d["source_id"] for d in raw["metadata"]["deferred_fragments"]}),
                             "unresolved_required_fragments": copy.deepcopy(raw["metadata"].get("unresolved_required_fragments", [])),
                             "deferred_text_requires_injection": bool(raw["metadata"].get("unresolved_required_fragments", []))}}


def source_view(pack: dict) -> dict:
    """清点、写作与审查复用同一份紧凑材料视图，来源已冻结时也可调用"""
    return model_context(pack)


def _verify_source_visual(root, source, original, pack, rendered):
    errors = []
    path, _ = _record_image_path(root, original)
    if path is None:
        return errors
    visuals = [row for row in pack.get("visual_assets", []) if row.get("source_id") == source["id"]]
    if len(visuals) > 1:
        errors.append(f"{source['id']} 的视觉输入重复登记")
    visual = visuals[0] if visuals else None
    expected_preview = original.get("image_preview")
    if visual:
        if visual.get("asset") != original["asset"] or Path(visual.get("original_path", "")).resolve() != path:
            errors.append(f"{source['id']} 的视觉输入没有对应同一份原图")
    if not expected_preview:
        if source.get("image_preview"):
            errors.append(f"{source['id']} 添加了原材料没有使用的图像转换")
        if path not in {Path(image).resolve() for image in pack.get("images", [])}:
            errors.append(f"{source['id']} 的原图没有进入视觉输入")
        if visual and (Path(visual.get("model_path", "")).resolve() != path
                       or visual.get("renderer") != "original" or visual.get("scale") != 1):
            errors.append(f"{source['id']} 的原图身份与视觉输入记录不一致")
        return errors
    preview = source.get("image_preview", {})
    if (preview.get("source_asset") != original["asset"] or preview.get("renderer") != expected_preview["renderer"]
            or preview.get("scale") != expected_preview["scale"] or not visual
            or visual.get("renderer") != expected_preview["renderer"] or visual.get("scale") != expected_preview["scale"]):
        return errors + [f"{source['id']} 缺少与原图对应的模型预览记录"]
    model_path = Path(preview.get("path", "")).resolve()
    if (model_path.suffix.lower() != ".png" or not model_path.is_file()
            or model_path != Path(visual.get("model_path", "")).resolve()
            or model_path not in {Path(image).resolve() for image in pack.get("images", [])}):
        return errors + [f"{source['id']} 的模型预览文件缺失或没有进入视觉输入"]
    try:
        from PIL import Image
        key = str(path)
        if key not in rendered:
            if preview["renderer"] == "cairosvg":
                import cairosvg
                png = cairosvg.svg2png(url=str(path), scale=preview["scale"])
                with Image.open(io.BytesIO(png)) as expected:
                    expected = expected.convert("RGBA")
                    rendered[key] = (expected.size, expected.tobytes())
            else:
                with Image.open(path) as expected:
                    expected = expected.convert("RGBA")
                    rendered[key] = (expected.size, expected.tobytes())
        with Image.open(model_path) as actual:
            actual = actual.convert("RGBA")
            if (actual.size, actual.tobytes()) != rendered[key]:
                errors.append(f"{source['id']} 的模型预览与原图实际渲染的像素不一致")
    except (OSError, ValueError) as exc:
        errors.append(f"{source['id']} 的模型预览读取失败: {exc}")
    return errors


def verify_source_pack(root: Path, pack: dict, material: dict | None = None, require_readable_resources: bool = False) -> list[str]:
    """重新读取冻结原文和实际文件，检查原句、范围和图像仍与清点前一致"""
    root = Path(root).resolve()
    errors = []
    if pack.get("profile") != "teaching-source-pack-v1":
        return ["材料包的 profile 与全书材料检查器不一致"]
    try:
        expected = _prepare_sources(root, pack["section_id"], root / "05_writing" / "verification-read-only", persist=False)
    except (OSError, ValueError, KeyError) as exc:
        return [f"重新读取冻结材料失败: {exc}"]
    latest = expected
    version = pack.get("metadata", {}).get("readable_resource_rules_version")
    applicable = any(fragment.get("role_rule") == "readable-resource-v1" and fragment["role"] in TEXT_ROLES
                     for source in latest["sources"] for fragment in source.get("file_fragments", []))
    if version not in (None, READABLE_RESOURCE_RULES_VERSION):
        errors.append("材料包的可读资源规则版本尚未得到当前检查器支持")
    if require_readable_resources and applicable and version != READABLE_RESOURCE_RULES_VERSION:
        errors.append("历史材料包仅保留资源索引，发布前需要补齐实际脚本、配置和数据正文")
    legacy = None
    if version is None:
        try:
            legacy = _prepare_sources(root, pack["section_id"], root / "05_writing/verification-read-only", persist=False,
                                      legacy_resource_roles=True)
            expected = legacy
        except (OSError, ValueError, KeyError) as exc:
            return errors + [f"重新读取历史资源范围失败: {exc}"]
    for key in ("material_run", "material_path"):
        if pack.get(key) != expected[key]:
            errors.append(f"材料包的 {key} 与冻结章节引用不一致")
    if material is not None:
        actual_material = _read(_local(root, expected["material_path"]))
        supplied_tree = material.get("tree", material)
        if supplied_tree != actual_material["tree"]:
            errors.append("调用方提供的材料树与冻结文件不一致")
    actual_sources = pack.get("sources", [])
    actual = {s.get("id"): s for s in actual_sources}
    wanted = {s["id"]: s for s in expected["sources"]}
    if len(actual) != len(actual_sources):
        errors.append("材料包包含重复的来源 ID")
    if set(actual) != set(wanted):
        errors.append(f"材料包的来源集合与冻结问题映射不一致: 缺少 {sorted(set(wanted) - set(actual))}，多出 {sorted(set(actual) - set(wanted))}")
    # 刷新追加真实原句时保留的旧索引和旧范围仍需逐字核对，不能把它们当作任意 OCR 放行
    retained = version == READABLE_RESOURCE_RULES_VERSION and any(
        any(fragment.get("role_rule") == "readable-resource-v1" and fragment["role"] in TEXT_ROLES
            for fragment in wanted[sid].get("file_fragments", []))
        and (actual[sid].get("index_record") is not None
             or {row["id"] for row in actual[sid].get("sentences", [])} - {row["id"] for row in wanted[sid].get("sentences", [])})
        for sid in actual.keys() & wanted.keys())
    if retained and legacy is None:
        try:
            legacy = _prepare_sources(root, pack["section_id"], root / "05_writing/verification-read-only", persist=False,
                                      legacy_resource_roles=True)
        except (OSError, ValueError, KeyError) as exc:
            return errors + [f"核对保留的旧索引失败: {exc}"]
    legacy_sources = {source["id"]: source for source in legacy["sources"]} if legacy else {}
    rendered = {}
    for sid in sorted(set(actual) & set(wanted)):
        source, original = actual[sid], copy.deepcopy(wanted[sid])
        if retained and sid in legacy_sources:
            old = legacy_sources[sid]
            if source.get("index_record") is not None and source.get("index_record") == old.get("index_record"):
                original["index_record"] = copy.deepcopy(old["index_record"])
            ids = {row["id"] for row in original.get("sentences", [])}
            present = {row["id"] for row in source.get("sentences", [])}
            for row in old.get("sentences", []):
                if row["id"] in present and row["id"] not in ids:
                    original["sentences"].append(copy.deepcopy(row))
            for key, text in old.get("original_texts", {}).items():
                if key in source.get("original_texts", {}):
                    original["original_texts"].setdefault(key, text)
        for key in ("type", "source", "source_refs", "original_texts", "asset", "source_ids", "index_record", "raw_content", "tree_metadata", "child_ids", "question_ids", "evidence_kind", "material_index_audit"):
            if source.get(key) != original.get(key):
                errors.append(f"{sid} 的 {key} 与冻结原文或实际文件范围不一致")
        errors.extend(_verify_source_visual(root, source, original, pack, rendered))
        if "title" in source:
            errors.append(f"{sid} 添加了原材料没有的外层标题")
        expected_rows = {row["id"]: row for row in original.get("sentences", [])}
        rows = source.get("sentences", [])
        actual_rows = {row.get("id"): row for row in rows}
        if len(rows) != len(actual_rows):
            errors.append(f"{sid} 的原句 ID 重复")
        if set(expected_rows) - set(actual_rows):
            errors.append(f"{sid} 缺少已保留的原句: {sorted(set(expected_rows) - set(actual_rows))}")
        for sentence_id in set(expected_rows) & set(actual_rows):
            row, baseline = actual_rows[sentence_id], expected_rows[sentence_id]
            for key in ("original", "start_line", "end_line", "verbatim_code", "evidence_kind"):
                if row.get(key) != baseline.get(key):
                    errors.append(f"{sid} {sentence_id} 的 {key} 与原始材料不一致")
            if baseline.get("verbatim_code") and row.get("translation") != baseline["original"]:
                errors.append(f"{sid} {sentence_id} 的源码在翻译字段中发生了改写")
        extra = set(actual_rows) - set(expected_rows)
        if extra:
            try:
                asset = _local(root, source["asset"])
                if asset.suffix.lower() not in IMAGE_EXTENSIONS:
                    raise ValueError("来源对象不是原图")
            except (OSError, ValueError, KeyError):
                errors.append(f"{sid} 的新增原图标签缺少实际图片来源")
            for sentence_id in extra:
                row = actual_rows[sentence_id]
                if not all(isinstance(row.get(key), str) and row[key].strip() for key in ("original", "translation", "region")):
                    errors.append(f"{sid} {sentence_id} 的新增原图标签缺少文字、译文或区域")
        expected_files = original.get("file_fragments", [])
        actual_files = source.get("file_fragments", [])
        if len(expected_files) != len(actual_files):
            errors.append(f"{sid} 的文件范围数量发生变化")
        for index, (file, baseline) in enumerate(zip(actual_files, expected_files), 1):
            for key in ("source", "file_bytes", "encoding", "role", "read_policy", "role_rule", "declared_role"):
                if file.get(key) != baseline.get(key):
                    errors.append(f"{sid} 文件范围 {index} 的 {key} 与实际文件不一致")
            if bool(file.get("text_storage")) != bool(baseline.get("text_storage")):
                errors.append(f"{sid} 文件范围 {index} 的完整文字存储记录发生变化")
            if file.get("text_storage"):
                try:
                    stored = _read(file["text_storage"]["path"])
                    path = _local(root, baseline["source"]["path"])
                    data = path.read_bytes()[baseline["source"]["start_byte"]:baseline["source"]["end_byte"]]
                    text, _ = _decode(data)
                    if stored.get("text") != text or stored.get("source") != baseline["source"]:
                        errors.append(f"{sid} 文件范围 {index} 保存的全文与原文件字节范围不一致")
                    if "".join(chunk.get("text", "") for chunk in stored.get("chunks", [])) != text:
                        errors.append(f"{sid} 文件范围 {index} 的分块没有完整恢复原文")
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    errors.append(f"{sid} 文件范围 {index} 读取保存的全文失败: {exc}")
    if version == READABLE_RESOURCE_RULES_VERSION:
        recomputed = copy.deepcopy(pack)
        _refresh_reading_metadata(recomputed, set())
        for key in ("inline_characters", "deferred_fragments", "unresolved_required_fragments", "file_families"):
            if pack.get("metadata", {}).get(key) != recomputed["metadata"].get(key):
                errors.append("材料包的 " + key + " 与实际文件读取状态不一致")
        if require_readable_resources:
            required = {(source["id"], index) for source in pack["sources"]
                        for index, fragment in enumerate(source.get("file_fragments", []), 1)
                        if fragment.get("role_rule") == "readable-resource-v1" and fragment["role"] in TEXT_ROLES
                        and fragment.get("read_policy") == "indexed_complete"}
            if required:
                errors.append("仍有可读资源正文只保存在全文索引中，发布前需要把实际内容交给清点与讲解：" + str(sorted(required)))
    return errors


def read_deferred_text(raw: dict, source_id: str, fragment: int = 1, start_line: int | None = None, end_line: int | None = None) -> dict:
    """按完整索引读取延迟提供的源码范围，供模型在清点与审查时继续取原材料"""
    source = next((s for s in raw["sources"] if s["id"] == source_id), None)
    if source is None:
        raise KeyError(source_id)
    entry = source["file_fragments"][fragment - 1]
    stored = _read(entry["text_storage"]["path"])
    if start_line is None and end_line is None:
        return stored
    first = stored["source"].get("start_line", 1)
    lines = stored["text"].splitlines(keepends=True)
    lower = first if start_line is None else start_line
    upper = first + len(lines) - 1 if end_line is None else end_line
    if lower < first or upper < lower or upper >= first + len(lines):
        raise ValueError(f"读取行号超出已保存的源码范围: {source_id} {lower}:{upper}")
    return {"source_id": source_id, "source": dict(stored["source"], start_line=lower, end_line=upper),
            "text": "".join(lines[lower - first:upper - first + 1])}
