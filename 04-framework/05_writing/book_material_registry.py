"""给同一原图的真实文字和区域分配稳定 ID，供并行小节共享来源定位"""

from __future__ import annotations

import copy
import json
import re
import tempfile
import threading
import unicodedata
from collections import defaultdict
from pathlib import Path


_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"}


def _lock(path):
    key = str(path.resolve()).casefold()
    # Windows 在文件刚创建时可能返回带长路径前缀的同一路径，先统一锁的查找键
    if key.startswith("\\\\?\\unc\\"):
        key = "\\\\" + key[8:]
    elif key.startswith("\\\\?\\"):
        key = key[4:]
    with _GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def _registry_path(work_root, source_id):
    if not isinstance(source_id, str) or source_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", source_id):
        raise ValueError(f"材料来源 ID 的格式无效: {source_id!r}")
    return Path(work_root).resolve() / "material-registry" / source_id / "image-labels.json"


def _read_registry(path, source_id):
    if not path.is_file():
        return {"profile": "image-label-registry-v1", "source_id": source_id, "next_index": 1, "labels": []}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("profile") != "image-label-registry-v1" or value.get("source_id") != source_id:
        raise ValueError(f"原图文字登记文件与来源不一致: {source_id}")
    labels = value.get("labels", [])
    ids = [row["id"] for row in labels]
    if len(ids) != len(set(ids)) or any(not all(isinstance(row.get(k), str) and row[k].strip()
                                               for k in ("id", "original", "region")) for row in labels):
        raise ValueError(f"原图文字登记文件含重复 ID 或缺少文字及区域: {source_id}")
    return value


def _write_registry(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix="image-labels-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _actual_image(raw, source):
    asset = source.get("asset")
    if not isinstance(asset, str) or Path(asset).suffix.lower() not in _IMAGE_EXTENSIONS:
        return False
    normalized = asset.replace("\\", "/").lstrip("/")
    # SVG 的模型输入是 PNG 预览，原图身份仍由完整 SVG 路径与来源 ID 对应
    for visual in raw.get("visual_assets", []):
        if visual.get("source_id") != source.get("id") or visual.get("asset") != asset:
            continue
        original = Path(visual.get("original_path", ""))
        model = Path(visual.get("model_path", ""))
        original_text = str(original).replace("\\", "/")
        if not original.is_file() or not model.is_file() or not (
                original_text == asset.replace("\\", "/") or original_text.endswith("/" + normalized)):
            continue
        preview = source.get("image_preview")
        if preview:
            if (preview.get("source_asset") != asset or Path(preview.get("path", "")).resolve() != model.resolve()
                    or preview.get("renderer") != visual.get("renderer") or preview.get("scale") != visual.get("scale")):
                continue
        elif original.resolve() != model.resolve() or visual.get("renderer") != "original":
            continue
        return True
    candidates = [Path(value) for value in raw.get("images", [])]
    if Path(asset).is_absolute():
        candidates.append(Path(asset))
    for path in candidates:
        path_text = str(path).replace("\\", "/")
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS and (
                path_text == asset.replace("\\", "/") or path_text.endswith("/" + normalized)):
            return True
    return False


def _label(row):
    return {key: copy.deepcopy(row.get(key, "")) for key in ("id", "original", "translation", "region")}


def _seed_existing(registry, source):
    """原材料已有的句 ID 优先保留，已有 ID 的原文与区域始终保持一致"""
    by_id = {row["id"]: row for row in registry["labels"]}
    for row in source.get("sentences", []):
        if not row.get("region") or not row.get("original", "").strip():
            continue
        existing = by_id.get(row["id"])
        if existing and (existing["original"], existing["region"]) != (row["original"], row["region"]):
            raise ValueError(f"同一原图文字 ID 对应了不同内容: {source['id']} {row['id']}")
        if not existing:
            registry["labels"].append(_label(row))
            by_id[row["id"]] = registry["labels"][-1]


def canonicalize_plan_labels(work_root, raw, plan):
    """按原文与区域精确登记 OCR，并把信息点引用同步到稳定的原句 ID"""
    result = copy.deepcopy(plan)
    sources = {source["id"]: source for source in raw["sources"]}
    grouped = defaultdict(list)
    for label in result.get("image_labels", []):
        source = sources.get(label.get("source_id"))
        if source is None or not _actual_image(raw, source):
            raise ValueError(f"原图文字缺少实际图片来源: {label.get('source_id')}")
        if not all(isinstance(label.get(key), str) and label[key].strip()
                   for key in ("id", "original", "translation", "region")):
            raise ValueError(f"原图文字缺少 ID、原文、译文或区域: {source['id']}")
        grouped[source["id"]].append(label)
    renamed = {}
    normalized = []
    for source_id, labels in grouped.items():
        source = sources[source_id]
        path = _registry_path(work_root, source_id)
        with _lock(path):
            registry = _read_registry(path, source_id)
            baseline = copy.deepcopy(registry)
            _seed_existing(registry, source)
            reserved = {row["id"] for row in registry["labels"]} | {row["id"] for row in source.get("sentences", [])}
            raw_rows = {row["id"]: row for row in source.get("sentences", [])}
            raw_pairs = {(row["original"], row.get("region")): row for row in source.get("sentences", []) if row.get("region")}
            pairs = {}
            for row in registry["labels"]:
                pairs.setdefault((row["original"], row["region"]), row)
            for label in labels:
                previous_id = label["id"]
                pair = (label["original"], label["region"])
                if previous_id in raw_rows:
                    row = raw_rows[previous_id]
                    if row["original"] != label["original"] or (row.get("region") and row["region"] != label["region"]):
                        raise ValueError(f"新增原图文字改写了已有原句: {source_id} {previous_id}")
                    selected_id = previous_id
                elif pair in raw_pairs:
                    selected_id = raw_pairs[pair]["id"]
                elif pair in pairs:
                    selected_id = pairs[pair]["id"]
                else:
                    next_index = registry.get("next_index", 1)
                    while f"{source_id}.ocr{next_index:04d}" in reserved:
                        next_index += 1
                    selected_id = f"{source_id}.ocr{next_index:04d}"
                    registry["next_index"] = next_index + 1
                    registered = dict(_label(label), id=selected_id)
                    registry["labels"].append(registered)
                    pairs[pair] = registered
                    reserved.add(selected_id)
                key = (source_id, previous_id)
                if key in renamed and renamed[key] != selected_id:
                    raise ValueError(f"本次清点把同一临时 ID 用于多个原图位置: {source_id} {previous_id}")
                renamed[key] = selected_id
                normalized.append({"source_id": source_id, **dict(_label(label), id=selected_id)})
            if registry != baseline or not path.is_file():
                _write_registry(path, registry)
    # 同一原图位置若在一次输出中重复出现，只保留一份原文条目，所有引用指向同一 ID
    unique = {}
    for label in normalized:
        key = (label["source_id"], label["id"])
        if key in unique and (unique[key]["original"], unique[key]["region"]) != (label["original"], label["region"]):
            raise ValueError(f"原图文字规范 ID 冲突: {key}")
        unique.setdefault(key, label)
    result["image_labels"] = list(unique.values())
    rows_by_source = defaultdict(dict)
    for source in raw["sources"]:
        rows_by_source[source["id"]].update({row["id"]: row for row in source.get("sentences", [])})
    for label in result["image_labels"]:
        rows_by_source[label["source_id"]][label["id"]] = label
    for point in result.get("points", []):
        for quote in point.get("source_quotes", []):
            source_id = quote.get("source_id")
            ids = quote.get("sentence_ids", [])
            if ids:
                quote["sentence_ids"] = list(dict.fromkeys(renamed.get((source_id, key), key) for key in ids))
            else:
                text = quote.get("quote", "")
                candidates = [row["id"] for row in rows_by_source[source_id].values()
                              if text.strip() and text in row.get("original", "")]
                if len(candidates) == 1:
                    quote["sentence_ids"] = candidates
    return result


def apply_known_image_labels(work_root, raw):
    """复用已登记的原图文字，保持原材料、已有句 ID 和已有译文原样"""
    result = copy.deepcopy(raw)
    for source in result["sources"]:
        path = _registry_path(work_root, source["id"])
        with _lock(path):
            if not path.is_file():
                continue
            if not _actual_image(result, source):
                raise ValueError(f"已登记的原图文字缺少实际图片来源: {source['id']}")
            registry = _read_registry(path, source["id"])
            rows = source.setdefault("sentences", [])
            existing_ids = {row["id"]: row for row in rows}
            existing_pairs = {(row["original"], row.get("region")) for row in rows}
            for label in registry["labels"]:
                if label["id"] in existing_ids:
                    row = existing_ids[label["id"]]
                    if (row["original"], row.get("region")) != (label["original"], label["region"]):
                        raise ValueError(f"已登记的原图文字 ID 与当前原句冲突: {source['id']} {label['id']}")
                    continue
                if (label["original"], label["region"]) in existing_pairs:
                    continue
                rows.append(_label(label))
                existing_ids[label["id"]] = rows[-1]
                existing_pairs.add((label["original"], label["region"]))
    return result


_PRINTING_REPLACEMENTS = {**{char: '"' for char in "“”„‟"},
                          **{char: "'" for char in "‘’‚‛"},
                          **{char: "-" for char in "‐‑‒–—−﹘﹣－"}}


def _printing_map(text):
    """归一化印刷形式，同时保留每个归一化字符对应的原文起止位置"""
    characters, spans = [], []
    offset = 0
    while offset < len(text):
        end = offset + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        cluster = text[offset:end]
        # 上下标数字与罗马数字各保留自己的数学形式，连字和全角字形按 NFKC 展开
        normalized = cluster if unicodedata.category(cluster[0]) in {"No", "Nl"} else unicodedata.normalize("NFKC", cluster)
        for char in normalized.casefold():
            if char in {"\u200b", "\ufeff", "\u00ad"}:
                continue
            char = _PRINTING_REPLACEMENTS.get(char, char)
            if char.isspace():
                if characters and characters[-1] == " ":
                    spans[-1] = (spans[-1][0], end)
                    continue
                char = " "
            characters.append(char)
            spans.append((offset, end))
        offset = end
    # 数值范围两侧空白属于排版，保留原文下标后再移去这些空白以进行匹配
    removed = set()
    for index, char in enumerate(characters):
        if char != "-":
            continue
        left, right = index - 1, index + 1
        while left >= 0 and characters[left] == " ":
            left -= 1
        while right < len(characters) and characters[right] == " ":
            right += 1
        if left >= 0 and right < len(characters) and characters[left].isdigit() and characters[right].isdigit():
            removed.update(range(left + 1, index))
            removed.update(range(index + 1, right))
    paired = [(char, span) for i, (char, span) in enumerate(zip(characters, spans)) if i not in removed]
    while paired and paired[0][0] == " ":
        paired.pop(0)
    while paired and paired[-1][0] == " ":
        paired.pop()
    return "".join(char for char, _ in paired), [span for _, span in paired]


def _numeric_boundary(text, start, end, quoted):
    if quoted[0].isdigit() and start:
        if text[start - 1].isdigit() or (text[start - 1] == "." and (start < 2 or text[start - 2].isdigit())):
            return False
    if quoted[-1].isdigit() and end < len(text):
        if text[end].isdigit() or (text[end] == "." and end + 1 < len(text) and text[end + 1].isdigit()):
            return False
    return True


def _actual_span(original, quoted, mapped=None, wanted=None):
    normalized, spans = _printing_map(original) if mapped is None else mapped
    if wanted is None:
        wanted, _ = _printing_map(quoted)
    if not wanted:
        return None
    matches = []
    start = normalized.find(wanted)
    while start >= 0:
        end = start + len(wanted)
        if _numeric_boundary(normalized, start, end, wanted):
            matches.append(original[spans[start][0]:spans[end - 1][1]])
        start = normalized.find(wanted, start + 1)
    if not matches:
        return None
    return quoted if quoted in matches else matches[0]


def _index_allowed(row, quoted, point, assignment):
    if row.get("evidence_kind") != "material_index":
        return True
    original, _ = _printing_map(row["original"])
    wanted, _ = _printing_map(quoted)
    if original == wanted:
        return True
    context = " ".join([point.get("description", ""), *point.get("checks", [])])
    keywords = ("索引", "目录", "文件路径", "文件清单", "文件名", "文件角色", "文件类型", "附件清单", "资源清单")
    if any(word in context for word in keywords):
        return True
    return assignment.get("role") == "container" and any(word in assignment.get("scope_note", "") for word in keywords)


def _line_identity(source, row):
    if row.get("evidence_kind") == "material_index" or not isinstance(row.get("original"), str):
        return None
    locator = row.get("source", {})
    first = row.get("start_line", locator.get("start_line"))
    last = row.get("end_line", locator.get("end_line"))
    if not isinstance(first, int) or not isinstance(last, int) or first < 1 or last < first:
        return None
    if len(row["original"].splitlines()) != last - first + 1:
        return None
    path = locator.get("path")
    fragments = source.get("file_fragments", [])
    if not path:
        matched = re.match(re.escape(source["id"]) + r"\.range(\d+)\.L", row.get("id", ""))
        if matched:
            index = int(matched.group(1)) - 1
            if not 0 <= index < len(fragments):
                return None
            path = fragments[index].get("source", {}).get("path")
        elif len(fragments) == 1:
            path = fragments[0].get("source", {}).get("path")
        elif not fragments:
            path = source.get("source", {}).get("path")
    if not path:
        return None
    return str(path).replace("\\", "/").casefold(), first, last


def _contiguous_chains(source):
    """按材料原顺序连接同一文件的相邻行块，重叠、缺行或缺定位时立即断开"""
    rows = source.get("sentences", [])
    identities = [_line_identity(source, row) for row in rows]
    ranges = defaultdict(list)
    for index, identity in enumerate(identities):
        if identity:
            ranges[identity[0]].append((identity[1], identity[2], index))
    overlapping = set()
    for located in ranges.values():
        active = []
        for first, last, index in sorted(located):
            active = [(end, prior) for end, prior in active if end >= first]
            if active:
                overlapping.add(index)
                overlapping.update(prior for _, prior in active)
            active.append((last, index))
    chains, current, previous = [], [], None
    for index, row in enumerate(rows):
        identity = identities[index] if index not in overlapping else None
        adjacent = identity and previous and identity[0] == previous[0] and identity[1] == previous[2] + 1
        if not adjacent and current:
            if len(current) > 1:
                chains.append(current)
            current = []
        if identity:
            current.append(row)
        previous = identity
    if len(current) > 1:
        chains.append(current)
    result = []
    for rows in chains:
        segments, position = [], 0
        for row in rows:
            end = position + len(row["original"])
            segments.append((row["id"], position, end))
            position = end
        text = "".join(row["original"] for row in rows)
        result.append((text, _printing_map(text), segments))
    return result


def _split_contiguous_quote(source, quote, chains):
    wanted, _ = _printing_map(quote.get("quote", ""))
    if not wanted:
        return None
    candidates = []
    for text, (normalized, spans), segments in chains:
        start = normalized.find(wanted)
        while start >= 0:
            end = start + len(wanted)
            if _numeric_boundary(normalized, start, end, wanted):
                actual_start, actual_end = spans[start][0], spans[end - 1][1]
                pieces = []
                for sentence_id, lower, upper in segments:
                    left, right = max(actual_start, lower), min(actual_end, upper)
                    if left < right and text[left:right].strip():
                        pieces.append({**quote, "quote": text[left:right], "sentence_ids": [sentence_id]})
                if len(pieces) >= 2:
                    candidates.append(pieces)
                    if len(candidates) > 1:
                        return None
            start = normalized.find(wanted, start + 1)
    return candidates[0] if len(candidates) == 1 else None


def _rtl_comments(text):
    """识别 RTL 中真实的整行注释与完整块注释，跳过字符串中的相同字符"""
    comments = {}
    blocks, block_start = [], None
    index, line_start, state = 0, 0, "code"
    while index < len(text):
        char = text[index]
        if char == "\n":
            line_start = index + 1
        if state == "string":
            if char == "\\" and index + 1 < len(text):
                if text[index + 1] == "\n":
                    line_start = index + 2
                index += 2
                continue
            if char == '"':
                state = "code"
        elif state == "block":
            if text.startswith("*/", index):
                blocks.append((block_start, index + 2))
                state = "code"
                index += 2
                continue
        elif char == '"':
            state = "string"
        elif text.startswith("/*", index):
            state = "block"
            block_start = index
            index += 2
            continue
        elif text.startswith("//", index):
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            if not text[line_start:index].strip():
                comments[line_start] = (index, end)
            index = end
            continue
        index += 1
    return comments, blocks


def _rtl_comment_datasets(source, chains):
    rows = {row["id"]: row for row in source.get("sentences", [])}
    datasets = list(chains)
    covered = {sentence_id for _, _, segments in chains for sentence_id, _, _ in segments}
    for row in source.get("sentences", []):
        if row["id"] not in covered and _line_identity(source, row):
            text = row["original"]
            datasets.append((text, None, [(row["id"], 0, len(text))]))
    result = []
    for text, _, segments in datasets:
        participating = [rows[sentence_id] for sentence_id, _, _ in segments]
        if not participating or not all(source.get("verbatim_code") or row.get("verbatim_code") for row in participating):
            continue
        identity = _line_identity(source, participating[0])
        if not identity or Path(identity[0]).suffix.lower() not in {".v", ".vh", ".sv", ".svh"}:
            continue
        starts_at_boundary = identity[1] == 1 or bool(re.match(
            r"\s*(?:module|interface|package|program|checker|primitive|config|function|task|class)\b", text))
        comments, blocks = _rtl_comments(text) if starts_at_boundary else (None, None)
        result.append((text, segments, comments, blocks))
    return result


def _restore_comment_decoration(source, quote, datasets):
    quoted = quote.get("quote", "")
    # 只去掉首行这一处装饰，后续单词、数值、空白和注释分隔符均逐字参与查找
    if quoted.startswith("// ") and all(re.match(r"^[ \t]*//", line) for line in quoted.splitlines()):
        mode, needle = "line", quoted[3:]
    elif quoted.startswith("* ") and all(re.match(r"^[ \t]*\*", line) for line in quoted.splitlines()):
        mode, needle = "block", quoted[2:]
    else:
        return None
    if not needle or not needle.strip():
        return None
    candidates = []
    for text, segments, comments, blocks in datasets:
        start = text.find(needle)
        while start >= 0:
            end = start + len(needle)
            if comments is None:
                return None
            if mode == "block":
                valid = any(lower + 2 <= start and end <= upper - 2 for lower, upper in blocks)
            else:
                line_start = text.rfind("\n", 0, start) + 1
                first = comments.get(line_start)
                valid = bool(first and start >= first[0] + 2)
                position = start
                while valid and position < end:
                    beginning = text.rfind("\n", 0, position) + 1
                    newline = text.find("\n", position)
                    newline = len(text) if newline < 0 else newline
                    if text[position:min(newline, end)].strip() and beginning not in comments:
                        valid = False
                        break
                    position = newline + 1
            if valid:
                pieces = []
                for sentence_id, lower, upper in segments:
                    left, right = max(start, lower), min(end, upper)
                    if left < right and text[left:right].strip():
                        pieces.append({**quote, "quote": text[left:right], "sentence_ids": [sentence_id]})
                if pieces:
                    candidates.append(pieces)
                    if len(candidates) > 1:
                        return None
            start = text.find(needle, start + 1)
    return candidates[0] if len(candidates) == 1 else None


def resolve_plan_quotes(raw, plan):
    """只校正可定位的原句 ID 和印刷形式，原材料、事实、检查项与教学职责保持原样"""
    result = copy.deepcopy(plan)
    sources = {source["id"]: source for source in raw["sources"]}
    rows_by_source = {}
    for source_id, source in sources.items():
        image = bool(source.get("asset") and Path(source["asset"]).suffix.lower() in _IMAGE_EXTENSIONS)
        rows_by_source[source_id] = {row["id"]: {**row, "_image_label": image and bool(row.get("region"))}
                                     for row in source.get("sentences", [])}
    for label in result.get("image_labels", []):
        source_id = label.get("source_id")
        if source_id not in sources:
            continue
        rows = rows_by_source[source_id]
        if label["id"] not in rows:
            rows[label["id"]] = {**label, "_image_label": bool(label.get("region"))}
    assignments = {a["source_id"]: a for a in result.get("source_assignments", [])}
    mapped_rows = {source_id: {key: _printing_map(row.get("original", "")) for key, row in rows.items()}
                   for source_id, rows in rows_by_source.items()}
    crossing = {}
    comment_sources = {}
    for point in result.get("points", []):
        resolved = []
        for quote in point.get("source_quotes", []):
            rows = rows_by_source.get(quote.get("source_id"), {})
            wanted, _ = _printing_map(quote.get("quote", ""))
            matches = {}
            for sentence_id, row in rows.items():
                if not _index_allowed(row, quote.get("quote", ""), point, assignments.get(quote.get("source_id"), {})):
                    continue
                span = _actual_span(row.get("original", ""), quote.get("quote", ""),
                                    mapped_rows[quote["source_id"]][sentence_id], wanted)
                if span is not None:
                    matches[sentence_id] = (row, span)
            given = list(dict.fromkeys(quote.get("sentence_ids", [])))
            # 已经通过原句定位的引文保持原值，重检时只因空白排版而改写会破坏冻结旧点
            literal = lambda text: re.sub(r"\s+", " ", text).strip().casefold()
            if (given and len(given) == len(quote.get("sentence_ids", []))
                    and all(sentence_id in matches and literal(quote["quote"]) in literal(rows[sentence_id]["original"])
                            for sentence_id in given)):
                resolved.append(quote)
                continue
            selected = [sentence_id for sentence_id in given if sentence_id in matches]
            if not selected and len(matches) == 1:
                selected = list(matches)
            elif not selected and len(matches) > 1:
                whole_labels = [key for key, (row, _) in matches.items()
                                if row.get("_image_label") and mapped_rows[quote["source_id"]][key][0] == wanted]
                if whole_labels:
                    selected = whole_labels
            if not selected:
                source_id = quote.get("source_id")
                if source_id in sources:
                    if source_id not in crossing:
                        crossing[source_id] = _contiguous_chains(sources[source_id])
                    pieces = _split_contiguous_quote(sources[source_id], quote, crossing[source_id])
                    if pieces:
                        resolved.extend(pieces)
                        continue
                    if source_id not in comment_sources:
                        comment_sources[source_id] = _rtl_comment_datasets(sources[source_id], crossing[source_id])
                    decorated = _restore_comment_decoration(sources[source_id], quote, comment_sources[source_id])
                    if decorated:
                        resolved.extend(decorated)
                        continue
                # 索引的部分文字只能用于明确的索引职责，留下空位置交给严格校验器报告
                forbidden_index = any(sentence_id in rows and rows[sentence_id].get("evidence_kind") == "material_index"
                                      and not _index_allowed(rows[sentence_id], quote.get("quote", ""), point,
                                                             assignments.get(quote.get("source_id"), {}))
                                      for sentence_id in given)
                if forbidden_index:
                    quote["sentence_ids"] = []
                resolved.append(quote)
                continue
            by_actual_quote = {}
            for sentence_id in selected:
                _, span = matches[sentence_id]
                by_actual_quote.setdefault(span, []).append(sentence_id)
            for span, sentence_ids in by_actual_quote.items():
                resolved.append({**quote, "quote": span, "sentence_ids": sentence_ids})
        point["source_quotes"] = resolved
    return result
