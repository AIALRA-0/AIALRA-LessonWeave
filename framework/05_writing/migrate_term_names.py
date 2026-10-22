"""只生成术语名称迁移建议，不直接改写输入文档。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

import book_terminology


def _pointer_part(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def _walk(value, path=""):
    if isinstance(value, dict):
        if (isinstance(value.get("chinese"), str)
                and isinstance(value.get("english"), str)
                and "abbreviation" in value
                and isinstance(value.get("aliases"), list)
                and isinstance(value.get("components"), list)):
            yield path, value
        for key, child in value.items():
            yield from _walk(child, path + "/" + _pointer_part(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + "/" + str(index))


def propose_term_migration(document, source_sha256=None):
    """为每个可识别的术语对象返回名称字段补丁和处理记录。"""
    patches = []
    records = []
    for path, term in _walk(document):
        formatted, changes = book_terminology.format_term_metadata([term])
        findings = book_terminology.term_name_findings(formatted[0])
        status = "proposed" if changes else "needs_review" if findings else "unchanged"
        records.append({
            "path": path,
            "term_id": term.get("id"),
            "status": status,
            "changed_fields": [row["field"] for row in changes],
            "findings": copy.deepcopy(findings),
        })
        if not changes:
            continue
        before = {}
        after = {}
        for change in changes:
            field = change["field"]
            before[field] = copy.deepcopy(change.get("before"))
            after[field] = copy.deepcopy(change.get("after"))
        patches.append({
            "path": path,
            "term_id": term.get("id"),
            "before": before,
            "after": after,
        })
    return {
        "format": "lessonweave-term-name-migration-v1",
        "source_sha256": source_sha256,
        "patches": patches,
        "records": records,
    }



_PATCHABLE_FIELDS = {
    "english", "official_spelling", "display", "aliases",
    "abbreviation", "components",
}


def _pointer_value(document, pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ValueError("补丁位置必须是JSON Pointer")
    value = document
    for raw in pointer[1:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not key.isdigit():
                raise ValueError("JSON Pointer数组下标无效")
            value = value[int(key)]
        elif isinstance(value, dict):
            value = value[key]
        else:
            raise ValueError("JSON Pointer没有指向对象或数组")
    return value


def apply_term_patches(document, patches):
    """只把名称补丁应用到一份内存副本，并逐项核对术语ID和原值。"""
    result = copy.deepcopy(document)
    original = copy.deepcopy(document)
    seen = set()
    if not isinstance(patches, list):
        raise ValueError("patches必须是列表")
    for patch in patches:
        if not isinstance(patch, dict) or set(patch) != {"path", "term_id", "before", "after"}:
            raise ValueError("补丁结构不完整")
        identity = (patch["path"], patch["term_id"])
        if identity in seen:
            raise ValueError("补丁重复指定同一术语")
        seen.add(identity)
        before = patch["before"]
        after = patch["after"]
        if not isinstance(before, dict) or not isinstance(after, dict):
            raise ValueError("补丁名称字段必须是对象")
        if set(before) != set(after) or set(after) - _PATCHABLE_FIELDS:
            raise ValueError("补丁只能修改已列出的术语名称字段")
        term = _pointer_value(result, patch["path"])
        if not isinstance(term, dict) or term.get("id") != patch["term_id"]:
            raise ValueError("补丁位置上的术语ID已变化")
        for field, expected in before.items():
            if term.get(field) != expected:
                raise ValueError("补丁原值与当前术语名称不一致")
        for field, value in after.items():
            term[field] = copy.deepcopy(value)

    restored = copy.deepcopy(result)
    for patch in patches:
        before_term = _pointer_value(original, patch["path"])
        restored_term = _pointer_value(restored, patch["path"])
        for field in patch["after"]:
            if field in before_term:
                restored_term[field] = copy.deepcopy(before_term[field])
            else:
                restored_term.pop(field, None)
    if restored != original:
        raise ValueError("补丁产生了名称字段以外的差异")
    return result


def apply_proposal_file(input_path, proposal_path, output_path):
    """校验源文件哈希后，把单文件名称补丁写到一个新的输出副本。"""
    source = Path(input_path).resolve(strict=True)
    destination = Path(output_path).resolve()
    if source == destination:
        raise ValueError("输出文件必须与源文件分开")
    if destination.exists():
        raise ValueError("输出文件已经存在；请指定一个新的副本路径")
    raw = source.read_bytes()
    proposal = json.loads(Path(proposal_path).read_text(encoding="utf-8"))
    if proposal.get("format") != "lessonweave-term-name-migration-v1":
        raise ValueError("补丁文件格式不受支持")
    actual_hash = hashlib.sha256(raw).hexdigest()
    if proposal.get("source_sha256") != actual_hash:
        raise ValueError("源文件哈希已改变，未写入输出副本")
    document = json.loads(raw.decode("utf-8"))
    result = apply_term_patches(document, proposal.get("patches"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"patches": len(proposal["patches"]), "source_sha256": actual_hash,
            "source_modified": False, "output": str(destination)}

def _main():
    parser = argparse.ArgumentParser(description="为旧读本生成术语名称补丁建议，不改写输入文件")
    parser.add_argument("--input", required=True, type=Path, help="要检查或生成副本的单个 JSON 文件")
    parser.add_argument("--output", required=True, type=Path, help="补丁报告或新文件副本的路径")
    parser.add_argument("--apply-proposal", type=Path,
                        help="校验并应用单文件补丁；省略时只生成补丁报告")
    args = parser.parse_args()
    if args.apply_proposal:
        try:
            result = apply_proposal_file(args.input, args.apply_proposal, args.output)
        except (OSError, ValueError, json.JSONDecodeError, KeyError, IndexError) as error:
            parser.error(str(error))
        print(json.dumps(result, ensure_ascii=True))
        return
    source = args.input.resolve()
    destination = args.output.resolve()
    if source == destination:
        parser.error("输出文件必须与输入文件分开")
    if destination.exists():
        parser.error("补丁报告已经存在；请指定一个新的输出路径")
    raw = source.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    proposal = propose_term_migration(document, hashlib.sha256(raw).hexdigest())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    _main()
