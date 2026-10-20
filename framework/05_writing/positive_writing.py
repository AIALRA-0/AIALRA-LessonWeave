"""检查新教材直接说明事实、条件和结果，并定位需要改写的句式"""
import re


WRITING_RULES_VERSION = 4
# 完整的绕写句式继续定位，单个否定词及必要的数值、条件对比不触发模型返修
FORBIDDEN = re.compile(r'不是[^\n；。！？]{0,120}而是')


def block_texts(block):
    if 'guide' in block:
        from media_contract import authored_texts
        if block.get('caption'):
            yield 'caption', block['caption']
        yield from authored_texts(block['guide'], 'guide')
        return
    if block.get('lead_in'):
        yield 'lead_in', block['lead_in']
    kind = block['kind']
    if kind == 'paragraph':
        yield 'text', block['text']
    elif kind == 'list':
        for index, value in enumerate(block['items']):
            yield f'items[{index}]', value
    elif kind == 'table':
        for index, value in enumerate(block['headers']):
            yield f'headers[{index}]', value
        for row, values in enumerate(block['rows']):
            for col, value in enumerate(values):
                yield f'rows[{row}][{col}]', value
    if block.get('caption'):
        yield 'caption', block['caption']


def authored_texts(doc):
    """固定题干与代码沿用来源，其余新写文字进入表达检查"""
    yield from ((f"opening.{key}", text) for key, text in block_texts(doc['opening']))
    if doc.get('opening_forward'):
        yield from ((f"opening_forward.{key}", text) for key, text in block_texts(doc['opening_forward']))
    for unit in doc['units']:
        for block in [unit['problem'], *unit['explanation'], unit['synthesis']]:
            for field, text in block_texts(block):
                yield f"{block['id']}.{field}", text
    for row in doc['summary']:
        for field, text in block_texts(row['answer']):
            yield f"{row['answer']['id']}.{field}", text
    for row in doc['pitfalls']:
        yield row['id'] + '.title', row['premise'] + row['question']
        for field, text in block_texts(row['body']):
            yield f"{row['body']['id']}.{field}", text
    for row in doc['quiz']:
        for block in [row['prompt'], row['explanation']]:
            for field, text in block_texts(block):
                yield f"{block['id']}.{field}", text
        for index, option in enumerate(row.get('options', [])):
            yield f"{row['id']}.options[{index}]", option
        if row['kind'] == 'short_answer':
            yield row['id'] + '.reference_answer', row['reference_answer']
            for index, text in enumerate(row['rubric']):
                yield f"{row['id']}.rubric[{index}]", text
    for term in doc['glossary']:
        yield term['id'] + '.definition', term['definition']
        for index, text in enumerate(term['explanation']):
            yield f"{term['id']}.explanation[{index}]", text
    if doc.get('book_introduction'):
        yield 'book_introduction', doc['book_introduction']
    for row in doc.get('context_goals', []):
        yield row['question_id'] + '.answer', row['answer']


def check_positive_writing(doc):
    if doc.get('writing_rules_version', 1) < WRITING_RULES_VERSION:
        return []
    errors = []
    for location, text in authored_texts(doc):
        for match in FORBIDDEN.finditer(text):
            errors.append(f'{location} 第 {match.start() + 1} 字使用了“{match.group()}”，请直接说明事实、条件和结果')
    aliases = {}
    for term in doc['glossary']:
        names = [term.get('chinese'), term.get('english'), term.get('abbreviation'), *term.get('aliases', [])]
        for alias in filter(None, names):
            aliases.setdefault(alias.casefold(), set()).add(term['id'])
    for alias, terms in aliases.items():
        if len(terms) > 1:
            errors.append('术语别名存在多个归属：' + alias + ' → ' + '、'.join(sorted(terms)))
    return errors
