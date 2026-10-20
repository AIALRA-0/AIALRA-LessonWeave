"""批量使用阅读器的 KaTeX 检查公式，只自动采用解析器确认有效的确定性修正"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

INLINE = re.compile(r'(?<!\\)\$\$([\s\S]*?)(?<!\\)\$\$|(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)|\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]')
CODE = re.compile(r'```[\s\S]*?```|`[^`\n]+`')


def fields(value, parts=()):
    if isinstance(value, dict):
        if value.get('kind') == 'formula' and isinstance(value.get('text'), str):
            yield parts + ('text',), value['text']
        for key, child in value.items():
            if key in {'math_label', 'formula'} and isinstance(child, str) and child.strip():
                yield parts + (key,), child
            elif isinstance(child, (dict, list)):
                yield from fields(child, parts + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from fields(child, parts + (i,))


def check_documents(documents):
    import independent_checks as rules
    rows = []
    originals = {}
    for document, value in documents.items():
        for trail, text in fields(value):
            path = rules.pointer(trail)
            originals[document, path] = text
            rows.append({'document': document, 'path': path, 'math': text, 'start': 0, 'end': len(text)})
        for trail, text in rules.prose(value):
            path = rules.pointer(trail)
            originals[document, path] = text
            protected = CODE.sub(lambda m: ' ' * len(m.group()), text)
            for match in INLINE.finditer(protected):
                group = next(i for i, part in enumerate(match.groups(), 1) if part is not None)
                # 阅读器会把夹杂普通中文的候选保留为原文，检查器沿用这一显示规则
                visible = re.sub(r'\\(?:text|mathrm)\{[^}]*\}', '', match.group(group))
                if re.search(r'[\u4e00-\u9fff]', visible):
                    continue
                rows.append({'document': document, 'path': path, 'math': match.group(group),
                             'start': match.start(group), 'end': match.end(group)})
    if not rows:
        return []
    base = Path(__file__).resolve().parent
    node = shutil.which('node')
    if not node:
        return [dict(rules.issue('math_tool', '/', '运行环境没有找到 Node，尚未执行公式语法检查'), document='05_writing')]
    vendor = base.parent / 'reader/media-vendor/katex/dist/katex.min.js'
    with tempfile.TemporaryDirectory(prefix='lessonweave-math-') as directory:
        input_path = Path(directory) / 'input.json'
        output_path = Path(directory) / 'output.json'
        input_path.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf8')
        result = subprocess.run([node, str(base / 'math_syntax.cjs'), str(vendor), str(input_path), str(output_path)],
                                capture_output=True, text=True, encoding='utf8', timeout=30)
        if result.returncode:
            return [dict(rules.issue('math_tool', '/', 'KaTeX 批量检查未完成：' + result.stderr[:300]), document='05_writing')]
        errors = json.loads(output_path.read_text('utf8'))['errors']
    grouped = {}
    for row in errors:
        grouped.setdefault((row['document'], row['path']), []).append(row)
    findings = []
    for (document, path), errors in grouped.items():
        row = dict(rules.issue('math_syntax', path, '；'.join(dict.fromkeys(e['error'] for e in errors))), document=document)
        if all(e['deterministic_fix'] is not None for e in errors):
            text = originals[document, path]
            for error in sorted(errors, key=lambda e: e['start'], reverse=True):
                text = text[:error['start']] + error['deterministic_fix'] + text[error['end']:]
            row.update(script_value=text, original_value=originals[document, path])
        findings.append(row)
    return findings
