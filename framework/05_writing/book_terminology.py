"""复用可唯一确认的规范术语名称，保留本节作者新写的定义与解释"""
import copy
import importlib.util
from pathlib import Path
import re


_spec = importlib.util.spec_from_file_location('known_term_format', Path(__file__).with_name('build_demo.py'))
_format = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_format)

CANONICAL_FIELDS = ['id', 'abbreviation', 'chinese', 'english', 'kind', 'components',
                    'display', 'official_spelling', 'case_source']


def _key(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def _valid(entry):
    try:
        return (all(isinstance(entry.get(key), str) and entry[key].strip() for key in ['id', 'chinese', 'english'])
                and entry.get('kind') in {'concept', 'initialism', 'unit', 'official_name'}
                and not _format.check_terminology(entry))
    except (KeyError, TypeError, AttributeError):
        return False


def _named_match(current, registered):
    chinese = _key(current.get('chinese'))
    english = _key(current.get('english'))
    return bool(chinese and chinese == _key(registered.get('chinese'))
                or english and english == _key(registered.get('english')))


def _abbreviation_match(current, registered):
    abbreviation = _key(current.get('abbreviation'))
    if not abbreviation or abbreviation != _key(registered.get('abbreviation')):
        return False
    # 缩写只辅助识别同一含义，中文另有实际含义时保持原稿，交给作者核对
    chinese = _key(current.get('chinese'))
    known = {_key(registered.get('chinese')), _key(registered.get('english')), abbreviation}
    english = _key(current.get('english'))
    return (not chinese or chinese in known) and (not english or english in known)


def _numeric_conflict(current, registered):
    for field in ['english', 'abbreviation']:
        left = re.findall(r'\d+(?:\.\d+)*', current.get(field) or '')
        right = re.findall(r'\d+(?:\.\d+)*', registered.get(field) or '')
        if left and right and left != right:
            return True
    return False


def _split_numeric_value(entry):
    return _format.split_numeric_value(entry)


def _protected_case_conflict(current, registered):
    old_words = {}
    for word in re.findall(r'[A-Za-z]+', registered.get('english', '')):
        old_words.setdefault(word.casefold(), set()).add(word)
    for word in re.findall(r'[A-Za-z]+', current.get('english', '')):
        protected = len(word) > 1 and any(letter.isupper() for letter in word[1:])
        known = old_words.get(word.casefold(), set())
        if protected and known and word not in known:
            return True
    return False


def _canonical(current, entries):
    entries = [entry for entry in entries if not _numeric_conflict(current, entry)
               and not _protected_case_conflict(current, entry)]
    names = [entry for entry in entries if _named_match(current, entry)]
    primary = [entry for entry in names if entry['id'] == current.get('id')]
    if len(primary) == 1:
        # 已登记的中文和英文若分别指向不同条目，保留这个歧义，避免用 ID 掩盖事实冲突
        if any(entry['id'] != primary[0]['id'] for entry in names):
            return None
        return primary[0]
    if primary:
        return None
    if len(names) == 1:
        return names[0]
    if names:
        return None
    abbreviations = [entry for entry in entries if _abbreviation_match(current, entry)]
    return abbreviations[0] if len(abbreviations) == 1 else None


def _aliases(current, registered):
    # 旧额外别名尚未经过本节语义审查，只保留本次作者明确提交的别名和规范全称
    values = [*current.get('aliases', []), registered.get('chinese'), registered.get('english'),
              registered.get('abbreviation')]
    result, seen = [], set()
    for value in values:
        if not isinstance(value, str) or not value.strip() or _key(value) in seen:
            continue
        result.append(value)
        seen.add(_key(value))
    return result


def normalize_known_terms(terms, existing_catalog):
    """只规范已确认的名称字段，新定义和本节解释不从旧清单复制"""
    catalog = existing_catalog.get('entries', []) if isinstance(existing_catalog, dict) else existing_catalog
    entries = [entry for entry in catalog if isinstance(entry, dict) and _valid(entry) and not _split_numeric_value(entry)]
    result = []
    for original in terms:
        current = copy.deepcopy(original)
        registered = _canonical(current, entries)
        if registered:
            # 当前稿已通过格式检查时保留作者的新元数据与删改别名，旧格式通过并不等于旧语义正确
            if _valid(current):
                current['id'] = registered['id']
                result.append(current)
                continue
            for field in CANONICAL_FIELDS:
                if field in registered:
                    current[field] = copy.deepcopy(registered[field])
                else:
                    current.pop(field, None)
            current['aliases'] = _aliases(original, registered)
        result.append(current)
    return result


_ENGLISH_WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
_ENGLISH_COMPOUND = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")
_SMALL_WORDS = {'of', 'and', 'the', 'in', 'to', 'for', 'on', 'at', 'a', 'an', 'per'}


def _ordinary_title(english):
    words = list(_ENGLISH_WORD.finditer(english))
    # 连续大写和品牌式混合大小写需要真实名称来源，脚本保留原词交给作者确认
    if any(len(match[0]) > 1 and any(letter.isupper() for letter in match[0][1:]) for match in words):
        return None
    position = 0

    def replace(match):
        nonlocal position
        word = match[0]
        value = word.lower() if position and word.lower() in _SMALL_WORDS else word[0].upper() + word[1:].lower()
        position += 1
        return value

    return _ENGLISH_WORD.sub(replace, english)


def _component_format(term):
    abbreviation = term.get('abbreviation') or ''
    components = term.get('components')
    if not isinstance(components, list):
        return False
    if not abbreviation:
        return not components
    if not all(isinstance(part, dict) and isinstance(part.get('symbol'), str) and part['symbol']
               and isinstance(part.get('word'), str) and part['word'] for part in components):
        return False
    joined = ''.join(part['symbol'] for part in components)
    if len(joined) != len(abbreviation) or joined.lower() != abbreviation.lower() or _split_numeric_value(term):
        return False
    english = term['english']
    unit_fragments = (term['kind'] == 'unit'
                      and re.sub(r'\s+', '', ''.join(part['word'] for part in components)).lower()
                      == re.sub(r'\s+', '', english).lower())
    for part in components:
        matches = list(re.finditer(r'(?<![A-Za-z])' + re.escape(part['word']) + r'(?![A-Za-z])', english, re.I))
        if len(matches) == 1:
            part['word'] = matches[0][0]
        elif not unit_fragments:
            # 没有唯一的实际单词可供核对时，不补词、不改顺序，也不猜分量含义
            return False
    if term['kind'] != 'unit':
        words = _ENGLISH_WORD.findall(english)
        compounds = _ENGLISH_COMPOUND.findall(english)
        layouts = [words, [word for word in words if word.lower() not in _SMALL_WORDS],
                   compounds, [word for word in compounds if word.lower() not in _SMALL_WORDS]]
        if [part['word'] for part in components] not in layouts:
            return False
        if any(len(part['symbol']) != 1 and not part['symbol'].isdigit() for part in components):
            return False
    offset = 0
    for part in components:
        end = offset + len(part['symbol'])
        part['symbol'] = abbreviation[offset:end]
        offset = end
    return True


def format_term_metadata(terms):
    """只调整可逐字确认的格式，返回副本和实际改动，含义与原始模型记录保持原样"""
    result, changes = [], []
    for authored in terms:
        original = copy.deepcopy(authored)
        if isinstance(original, dict) and isinstance(original.get('aliases'), list) and all(isinstance(alias, str) for alias in original['aliases']):
            unique = list(dict.fromkeys(original['aliases']))
            if unique != original['aliases']:
                changes.append({'term_id': original.get('id'), 'field': 'aliases',
                                'before': copy.deepcopy(original['aliases']), 'after': unique})
                original['aliases'] = unique
        current = copy.deepcopy(original)
        try:
            if (not isinstance(current, dict)
                    or current.get('kind') not in {'concept', 'initialism', 'unit', 'official_name'}
                    or not isinstance(current.get('english'), str) or not current['english']
                    or not isinstance(current.get('chinese'), str)
                    or current.get('abbreviation') is not None and not isinstance(current['abbreviation'], str)):
                result.append(current)
                continue
            if current['kind'] != 'official_name':
                english = _ordinary_title(current['english'])
                if english is None:
                    result.append(current)
                    continue
                current['english'] = english
            if current['kind']=='unit' and current.get('abbreviation'):
                words=lambda value:[word.rstrip('s') for word in re.findall(r'[a-z]+',value.casefold())]
                if words(current['abbreviation'])==words(current['english']):
                    current['aliases']=list(dict.fromkeys([*current.get('aliases',[]),current['abbreviation']]))
                    current['abbreviation']=None
                    current['components']=[]
            if not _component_format(current):
                result.append(copy.deepcopy(original))
                continue
            current['display'] = ((current.get('abbreviation') + ' ') if current.get('abbreviation') else '')
            current['display'] += current['chinese'] + '（' + current['english'] + '）'
            if _format.check_terminology(current):
                result.append(copy.deepcopy(original))
                continue
            if isinstance(current.get('aliases'), list):
                current['aliases'] = list(dict.fromkeys(current['english'] if isinstance(value, str)
                                      and value.lower() == original['english'].lower() else value
                                      for value in current['aliases']))
            for field in ['english', 'display', 'aliases', 'abbreviation', 'components']:
                if current.get(field) != original.get(field):
                    changes.append({'term_id': current['id'], 'field': field,
                                    'before': copy.deepcopy(original.get(field)),
                                    'after': copy.deepcopy(current.get(field))})
            for index, (before, after) in enumerate(zip(original['components'], current['components'])):
                for field in ['word', 'symbol']:
                    if before[field] != after[field]:
                        changes.append({'term_id': current['id'], 'field': f'components.{index}.{field}',
                                        'before': before[field], 'after': after[field]})
            result.append(current)
        except (KeyError, TypeError, AttributeError):
            result.append(copy.deepcopy(original))
    return result, changes
