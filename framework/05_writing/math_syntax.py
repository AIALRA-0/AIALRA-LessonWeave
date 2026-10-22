"""批量使用阅读器的 KaTeX 检查公式，只自动采用解析器确认有效的确定性修正"""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

INLINE = re.compile(r'(?<!\\)\$\$([\s\S]*?)(?<!\\)\$\$|(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(?!\$)|\\\(([\s\S]*?)\\\)|\\\[([\s\S]*?)\\\]')
CODE = re.compile(r'```[\s\S]*?```|`[^`\n]+`')
READABLE = {'text','title','reader_title','title_premise','title_question','premise','question','body','claim','reasoning','grounding','supplement','definition','display','chinese','english','abbreviation','official_spelling','aliases','answer','reference_answer','generalization','caption','explanation','reading_guide','takeaway','purpose','label','conclusion','genus','differentia','boundary','extension','professional_definition','intuitive_explanation','typical_example','anchor','mapping','intuition','initial_conditions','mechanism','outcome','opening','opening_forward','carryover','options','headers','rows','rubric','items','summary','overview','relation_to_whole','collaboration'}
EVIDENCE = {'source','source_refs','source_nodes','source_quotes','source_links','raw_content','original','translation','english_original','bindings','coverage','preview_provenance','plan'}


def fields(value, parts=()):
    if isinstance(value, dict):
        if value.get('kind') == 'formula' and isinstance(value.get('text'), str):
            yield parts + ('text',), value['text']
        if value.get('math_label') is True and isinstance(value.get('label'), str):
            yield parts + ('label',), value['label']
        for key, child in value.items():
            if key in {'math_label', 'formula'} and isinstance(child, str) and child.strip():
                yield parts + (key,), child
            elif isinstance(child, (dict, list)):
                yield from fields(child, parts + (key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from fields(child, parts + (i,))


def readable(value, parts=(), active=False):
    """检查全部阅读字段，原件、代码和机器标识不进入自动修正"""
    if isinstance(value, str):
        if active and value.strip():yield parts,value
    elif isinstance(value, list):
        for index, item in enumerate(value):yield from readable(item,parts+(index,),active)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in EVIDENCE or (value.get('kind') in {'code','mermaid'} and key in {'text','code'}):continue
            yield from readable(child,parts+(key,),key in READABLE if not isinstance(child,list) else key in READABLE)


def check_documents(documents):
    import independent_checks as rules
    rows = []
    originals = {}
    for document, value in documents.items():
        explicit = dict(fields(value))
        for trail, text in explicit.items():
            path = rules.pointer(trail)
            originals[document, path] = text
            rows.append({'document': document, 'path': path, 'math': text, 'start': 0, 'end': len(text),
                         'inline_math_label': bool(trail and trail[-1] == 'label')})
        for trail, text in readable(value):
            if trail in explicit:continue
            path = rules.pointer(trail)
            originals[document, path] = text
            rows.append({'document': document, 'path': path, 'text': text})
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
