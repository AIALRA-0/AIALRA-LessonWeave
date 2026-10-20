"""从原始生成回执恢复可逐字核对的换行，阅读器单独读取显示记录"""
import argparse
import json
import re
from pathlib import Path

FIELDS = {'premise', 'claim', 'reasoning', 'grounding', 'supplement', 'answer',
          'generalization', 'genus', 'differentia', 'boundary', 'extension', 'anchor',
          'mapping', 'intuition', 'initial_conditions', 'mechanism', 'outcome'}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def candidates(value):
    if isinstance(value, dict):
        if value.get('kind') in {'code', 'formula', 'mermaid'}:
            return
        for key, child in value.items():
            if key in FIELDS and isinstance(child, str) and '\n' in child:
                flat = re.sub(r'[\r\n\u2028\u2029]+', ' ', child).replace('。', '；').rstrip('；')
                restored = re.sub(r'\r\n?|[\u2028\u2029]', '\n', child).replace('。', '；').rstrip('；')
                if flat != restored:
                    yield flat, restored
            elif isinstance(child, (dict, list)):
                yield from candidates(child)
    elif isinstance(value, list):
        for child in value:
            yield from candidates(child)


def build(root):
    root = Path(root)
    options = {}
    for path in (root / 'runtime/calls').rglob('response.json'):
        if any('repair' in part for part in path.parts):
            continue
        try:
            for flat, restored in candidates(json.loads(path.read_text(encoding='utf-8'))):
                options.setdefault(flat, set()).add(restored)
        except (ValueError, OSError):
            continue
    used = set()
    for folder in ['05_writing/preview', '05_writing/work']:
        for path in (root / folder).rglob('*.json'):
            try:
                used.update(s for s in strings(json.loads(path.read_text(encoding='utf-8'))) if s in options)
            except (ValueError, OSError):
                continue
    replacements = {s: next(iter(options[s])) for s in sorted(used) if len(options[s]) == 1}
    result = {'version': 1, 'replacements': replacements,
              'rule': '只有当前文字与原始回执的旧换行转换结果完全一致时，阅读器才恢复原换行',
              'ambiguous_omitted': sum(len(options[s]) > 1 for s in used)}
    target = root / '05_writing/reader-whitespace.json'
    target.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return {'root': str(root), 'restored_distinct_fields': len(replacements), 'ambiguous_omitted': result['ambiguous_omitted']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    print(json.dumps(build(parser.parse_args().root), ensure_ascii=False))
