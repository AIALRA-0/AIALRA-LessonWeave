"""把正文已说明的局部符号与专业术语分别核对，保留每次实际出现的位置"""
import copy
import re
import unicodedata

LETTER = r'A-Za-z\u0370-\u03ff'
_GREEK_COMMANDS = {'lambda': 'λ', 'theta': 'θ', 'gamma': 'γ', 'pi': 'π', 'Delta': 'Δ'}
_INDEX_CHARACTERS = [chr(value) for value in [*range(0x02B0, 0x0300), *range(0x1D2C, 0x1D6B),
                                             *range(0x2070, 0x20A0), 0x00B2, 0x00B3, 0x00B9]]
_INDEX_LETTERS = {character: unicodedata.normalize('NFKC', character) for character in _INDEX_CHARACTERS
                  if re.fullmatch('[' + LETTER + '0-9]', unicodedata.normalize('NFKC', character))
                  and any(name in unicodedata.name(character, '') for name in ['SUBSCRIPT', 'SUPERSCRIPT', 'MODIFIER LETTER'])}


def _greek_symbols(text):
    return re.sub(r'\\+([A-Za-z]+)', lambda match: _GREEK_COMMANDS.get(match[1], match[0]), text)


def _variable_text(symbol):
    # 原式保持原样，核对组成量时把正常上下标排版对应到同一个基础变量
    text = re.sub(r'\\+[A-Za-z]+', '', _greek_symbols(symbol))
    text = re.sub(r'_(?:\{[A-Za-z]{3,}\}|[A-Za-z]{3,})', '', text)
    return ''.join('_' + _INDEX_LETTERS[character] if character in _INDEX_LETTERS else character for character in text)


def notation_blocks(doc):
    yield doc['opening']
    if doc.get('opening_forward'):
        yield doc['opening_forward']
    for unit in doc['units']:
        yield unit['problem']
        yield from unit['explanation']
        yield unit['synthesis']
    for row in doc['summary']:
        yield row['answer']
    for row in doc['pitfalls']:
        yield row['body']
    for row in doc['quiz']:
        yield row['prompt']
        yield row['explanation']


def definition_text(block):
    """定义引文逐字取自可见正文，公式原式与图注也保留实际内容"""
    if block['kind'] == 'list':
        parts = [block.get('lead_in', ''), *block['items']]
    elif block['kind'] == 'table':
        parts = [*block['headers'], *(cell for row in block['rows'] for cell in row)]
    else:
        parts = [block.get('text', ''), block.get('caption', '')]
    return '\n'.join(part for part in parts if part)


def _pattern(symbol):
    logical = _greek_symbols(symbol)
    if re.fullmatch('[\u0370-\u03ff]', logical):
        variants = [re.escape(logical), *(r'\\+' + re.escape(name) + r'(?![A-Za-z])'
                                           for name, character in _GREEK_COMMANDS.items() if character == logical)]
        return re.compile(r'(?<![A-Za-z0-9])(?:' + '|'.join(variants) + r')(?![A-Za-z0-9])')
    return re.compile(r'(?<![A-Za-z0-9])' + re.escape(symbol) + r'(?![A-Za-z0-9])')


def _expression_letters(symbol):
    # 排版命令说明公式怎样显示，字母变量仍从命令参数及下标中逐个核对
    text = _variable_text(symbol)
    # 完整英文函数与专业名称保留给术语检查，不把它们虚构成一串局部变量
    text = re.sub(r'[A-Za-z]{3,}', '', text)
    return set(re.findall('[' + LETTER + ']', text))


def _expression_allowed(symbol):
    original = symbol
    symbol = re.sub(r'\s+', '', _variable_text(symbol))
    letters = _expression_letters(symbol)
    if not letters or re.search(r'[\u4e00-\u9fff]', symbol):
        return False
    if re.search(r'[A-Z]{2,}|[A-Za-z]{3,}', symbol):
        return False
    # 连写只接纳两个局部变量，专业缩写和完整英文仍进入术语检查
    if re.fullmatch('[' + LETTER + ']+', symbol):
        return (len(symbol) == 2 and (not symbol.isupper() or bool(re.search('[\u0370-\u03ff]', symbol)))
                or bool(re.search(r'_(?:\{[A-Za-z]{3,}\}|[A-Za-z]{3,})', original)))
    if re.fullmatch('[' + LETTER + r']\d+', symbol):
        return True
    return bool(re.search(r'[/+*=<>^_{}()\\−×÷∈∉≤≥≠≈∼∝±∓·-]', symbol)
                or re.search(r'\\+[A-Za-z]+', original))


def check_local_notations(doc):
    """只认可原文定义位置、实际引文及明确范围都有效的登记，语义另交独立审查"""
    records = copy.deepcopy(doc.get('local_notations', []))
    if not records:
        return {'registered_count': 0, 'valid_count': 0, 'registrations': [], 'errors': []}
    blocks = list(notation_blocks(doc))
    block_index = {block['id']: block for block in blocks}
    errors = []
    indexed = {}
    invalid = set()
    fields = {'id', 'kind', 'symbol', 'meaning', 'definition_block_id', 'definition_quote',
              'scope_block_ids', 'component_ids'}
    for row in records:
        key = row.get('id', '')
        def reject(reason):
            invalid.add(key)
            errors.append((key or '局部符号') + '：' + reason)
        if set(row) != fields or not isinstance(key, str) or not key.strip():
            reject('登记字段缺失或包含额外字段')
            continue
        if key in indexed:
            reject('登记 ID 重复')
            continue
        indexed[key] = row
        if any(not isinstance(row[name], str) or not row[name].strip()
               for name in ['symbol', 'meaning', 'definition_block_id', 'definition_quote']):
            reject('符号、含义和逐字定义引文都需要实际内容')
            continue
        scope = row['scope_block_ids']
        if (not isinstance(scope, list) or not scope or any(not isinstance(item, str) for item in scope)
                or len(scope) != len(set(scope)) or set(scope) - set(block_index)):
            reject('定义范围需要逐个引用存在且唯一的正文块')
            continue
        defining = block_index.get(row['definition_block_id'])
        if not defining or row['definition_block_id'] not in scope:
            reject('定义位置需要存在并属于该符号的明确范围')
            continue
        if defining['kind'] == 'code':
            reject('局部符号的含义需要在讲解正文或公式图注中实际说明')
        quote = row['definition_quote']
        if quote not in definition_text(defining) or not _pattern(row['symbol']).search(quote):
            reject('定义引文需要逐字来自指定正文，并实际写出该符号')
        prose = re.sub(re.escape(row['symbol']), '', quote)
        prose = re.sub(r'\\+[A-Za-z]+', '', prose)
        if not re.search(r'[\u4e00-\u9fff]{2,}|[A-Za-z]{2,}', prose):
            reject('定义引文需要包含实际解释含义的文字')
        components = row['component_ids']
        if not isinstance(components, list) or any(not isinstance(item, str) for item in components):
            reject('组成符号需要逐项引用登记 ID')
            continue
        if row['kind'] == 'symbol':
            if not re.fullmatch('[' + LETTER + ']', _greek_symbols(row['symbol'])) or components:
                reject('原子符号只接受一个区分大小写的字母，且没有组成项')
        elif row['kind'] == 'expression':
            if (not _expression_allowed(row['symbol']) or not components
                    or len(components) != len(set(components))):
                reject('复合表达式需要实际算式或两个局部变量连写，专业缩写仍需登记术语')
        else:
            reject('登记类型需要是 symbol 或 expression')
    # 同一字母可以在不同片段承担不同含义，范围相交时要求作者明确其实际归属
    rows = list(indexed.values())
    for index, row in enumerate(rows):
        if row['id'] in invalid:
            continue
        for other in rows[index + 1:]:
            if (other['id'] not in invalid and _greek_symbols(row['symbol']) == _greek_symbols(other['symbol'])
                    and set(row['scope_block_ids']) & set(other['scope_block_ids'])):
                invalid.update([row['id'], other['id']])
                errors.append(row['id'] + ' 与 ' + other['id'] + ' 在相同正文范围重复定义了同一符号')
    for row in rows:
        if row['id'] in invalid or row['kind'] != 'expression':
            continue
        components = [indexed.get(key) for key in row['component_ids']]
        if (any(item is None or item['id'] in invalid or item['kind'] != 'symbol' for item in components)
                or {_greek_symbols(item['symbol']) for item in components if item} != _expression_letters(row['symbol'])
                or any(set(row['scope_block_ids']) - set(item['scope_block_ids']) for item in components if item)):
            invalid.add(row['id'])
            errors.append(row['id'] + ' 的每个组成字母都需要在表达式全部范围内有各自有效定义')
    valid = [row for row in rows if row['id'] not in invalid]
    return {'registered_count': len(records), 'valid_count': len(valid),
            'registrations': valid, 'errors': errors}


def notation_spans(report, location, text):
    """返回当前块内确有定义的完整跨度，范围外的同名符号继续要求解释"""
    block_id = location.removesuffix(':formula')
    matches = []
    for row in report['registrations']:
        if block_id in row['scope_block_ids']:
            matches.extend({'notation_id': row['id'], 'symbol': row['symbol'],
                            'location': location, 'start': match.start(), 'end': match.end()}
                           for match in _pattern(row['symbol']).finditer(text))
    # 长表达式优先遮住其组成符号，但每个原子定义仍独立保留并检查
    selected = []
    for row in sorted(matches, key=lambda item: (item['start'], -(item['end'] - item['start']))):
        if not any(other['start'] <= row['start'] and other['end'] >= row['end'] for other in selected):
            selected.append(row)
    return selected


def formula_chunks(doc):
    """公式参与符号清点，排版命令与环境名称不作为英文专业名称"""
    if 'local_notations' not in doc:
        return
    for block in notation_blocks(doc):
        if block['kind'] == 'formula':
            yield block['id'] + ':formula', block['text']


def formula_markup_spans(location, text):
    if not location.endswith(':formula'):
        return []
    return [match.span() for match in re.finditer(
        r'\\+(?:begin|end)\{[A-Za-z*]+\}|\\+[A-Za-z]+', text)]
