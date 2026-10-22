"""复用可唯一确认的规范术语名称，保留本节作者新写的定义与解释"""
import copy
import importlib.util
from pathlib import Path
import re


_spec = importlib.util.spec_from_file_location('known_term_format', Path(__file__).with_name('build_demo.py'))
_format = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_format)

CANONICAL_FIELDS = ['id', 'abbreviation', 'chinese', 'english', 'kind', 'components',
                    'display', 'official_spelling', 'case_source',
                    'abbreviation_case_exception', 'english_case_exception']
CASE_FLAGS = ('abbreviation_case_exception', 'english_case_exception')


def _key(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def _valid(entry):
    try:
        if (not all(isinstance(entry.get(key), str) and entry[key].strip()
                    for key in ['id', 'chinese', 'english'])
                or entry.get('kind') not in {'concept', 'initialism', 'unit', 'official_name'}
                or term_name_findings(entry)):
            return False
        return (entry['kind'] != 'official_name'
                or entry.get('official_spelling') == entry.get('english')
                and isinstance(entry.get('case_source'), str) and bool(entry['case_source'].strip()))
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
_PROTECTED_NAME_PART = re.compile(
    r"(?P<math>\$\$.*?\$\$|(?<!\\)\$(?:\\.|[^$])*?(?<!\\)\$|"
    r"\\\(.*?\\\)|\\\[.*?\\\])"
    r"|(?P<tex_command>\\[A-Za-z]+(?:\*)?(?:(?:[_^]\{[^{}]*\})|(?:[_^][A-Za-z0-9]+)|(?:\{[^{}]*\}))*)"
    r"|(?P<identifier>(?<![A-Za-z0-9_])[A-Za-z_][A-Za-z0-9_]*_[A-Za-z0-9_]*(?![A-Za-z0-9_]))",
    re.DOTALL,
)


def _map_unprotected_name_parts(value, transform, on_protected=None):
    """让大小写转换跳过明确的 TeX 公式、命令和下划线标识符"""
    result = []
    start = 0
    for match in _PROTECTED_NAME_PART.finditer(value):
        result.append(transform(value[start:match.start()]))
        result.append(match[0])
        if on_protected is not None:
            on_protected(match)
        start = match.end()
    result.append(transform(value[start:]))
    return ''.join(result)


def _ordinary_title(english):
    position = 0

    def format_fragment(fragment):
        nonlocal position

        def replace(match):
            nonlocal position
            word = match[0]
            value = word.lower() if position and word.lower() in _SMALL_WORDS else word[0].upper() + word[1:].lower()
            position += 1
            return value

        return _ENGLISH_WORD.sub(replace, fragment)

    def count_protected_name_parts(_match):
        nonlocal position
        position += 1

    return _map_unprotected_name_parts(english, format_fragment, count_protected_name_parts)


def _ordinary_abbreviation(abbreviation):
    """缩写中的普通字母转大写，TeX 内容和代码标识符维持来源拼写"""
    return _map_unprotected_name_parts(abbreviation, str.upper)


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
        if term['kind'] == 'initialism' and any(
                len(part['symbol']) == 1 and part['symbol'].isalpha()
                and part['word'][0].isalpha()
                and part['symbol'].casefold() != part['word'][0].casefold()
                for part in components):
            return False
    offset = 0
    for part in components:
        end = offset + len(part['symbol'])
        part['symbol'] = abbreviation[offset:end]
        offset = end
    return True


def _same_name(left, right):
    return (isinstance(left, str) and isinstance(right, str) and bool(left.strip()) and bool(right.strip())
            and re.sub(r'\s+', '', left).casefold() == re.sub(r'\s+', '', right).casefold())


def _case_flag(term, field):
    # 历史条目可能省略该位或显式保存 null；两种情况都沿用默认规则。
    value = term.get(field)
    if value is None:
        return 0
    return value if type(value) is int and value in (0, 1) else None


def _normalize_term_names(term):
    """整理能由名称文本直接确定的字段，并单独记录无法核实的元数据"""
    original = copy.deepcopy(term)
    if not isinstance(original, dict):
        return original, [], [('entry', '术语记录需要是对象')]

    current = copy.deepcopy(original)
    issues = []
    flags = {field: _case_flag(original, field) for field in CASE_FLAGS}
    for field, value in flags.items():
        if value is None:
            issues.append((field, '大小写例外位只能是整数 0 或 1'))

    kind = original.get('kind')
    kind_valid = kind in {'concept', 'initialism', 'unit', 'official_name'}
    if not kind_valid:
        issues.append(('kind', '术语类型无法识别，缩写拆解需要交统一修复核对'))

    old_english = original.get('english')
    english_valid = isinstance(old_english, str) and bool(old_english.strip())
    if not english_valid:
        issues.append(('english', '英文全称缺失或格式无效，不能整理名称'))

    chinese = original.get('chinese')
    chinese_valid = isinstance(chinese, str) and bool(chinese.strip())
    if not chinese_valid:
        issues.append(('chinese', '中文名称缺失或格式无效，不能重建展示名'))

    old_abbreviation = original.get('abbreviation')
    abbreviation_valid = old_abbreviation is None or isinstance(old_abbreviation, str)
    if not abbreviation_valid:
        issues.append(('abbreviation', '缩写字段格式无效，已保留原值'))

    aliases = original.get('aliases')
    aliases_valid = isinstance(aliases, list) and all(isinstance(alias, str) for alias in aliases)
    if not aliases_valid:
        issues.append(('aliases', '别名字段格式不完整，已保留原值'))

    components = original.get('components')
    components_valid = isinstance(components, list)
    if not components_valid:
        issues.append(('components', '缩写拆解字段不是列表，已保留原值'))

    official_valid = True
    if kind == 'official_name':
        official = original.get('official_spelling')
        official_valid = (isinstance(official, str) and bool(_key(official))
                          and english_valid and _same_name(official, old_english))
        if not official_valid:
            issues.append(('official_spelling', '正式名称与英文全称无法对应，已保留原拼写'))
        if not str(original.get('case_source') or '').strip():
            issues.append(('case_source', '正式名称缺少原材料拼写位置，留给统一修复补充'))

    normalized_abbreviation = old_abbreviation
    if abbreviation_valid and isinstance(old_abbreviation, str) and flags['abbreviation_case_exception'] == 0:
        normalized_abbreviation = _ordinary_abbreviation(old_abbreviation)
        current['abbreviation'] = normalized_abbreviation

    if english_valid and flags['english_case_exception'] == 0:
        current['english'] = _ordinary_title(old_english)
        if kind == 'official_name' and official_valid:
            current['official_spelling'] = current['english']

    redundant_abbreviation = (
        abbreviation_valid and english_valid
        and _same_name(current.get('abbreviation'), current.get('english'))
    )
    if redundant_abbreviation:
        current['abbreviation'] = None

    if aliases_valid:
        normalized_aliases = []
        for alias in aliases:
            value = alias
            if english_valid and _key(alias) == _key(old_english):
                value = current.get('english', old_english)
            if isinstance(old_abbreviation, str) and _key(alias) == _key(old_abbreviation):
                value = current.get('english', old_english) if redundant_abbreviation else current.get('abbreviation', old_abbreviation)
            if _key(value) not in {_key(item) for item in normalized_aliases}:
                normalized_aliases.append(value)
        current['aliases'] = normalized_aliases

    # 只按现有符号和英文词核对components；无法唯一对应时保留原拆解。
    if components_valid and kind_valid and english_valid and abbreviation_valid:
        if redundant_abbreviation and not components:
            current['components'] = []
        else:
            probe = copy.deepcopy(current)
            if redundant_abbreviation:
                probe['abbreviation'] = normalized_abbreviation
            if _component_format(probe):
                if redundant_abbreviation:
                    current['components'] = []
                else:
                    current['components'] = probe['components']
            else:
                current['components'] = copy.deepcopy(components)
                issues.append(('components', '缩写拆解无法与整理后的名称对应，已保留原值并交统一修复核对'))
    elif components_valid and components:
        issues.append(('components', '当前名称无法支持可靠核对缩写拆解，已保留原值并交统一修复核对'))

    # 展示名只依赖已经存在的中文名、全称和缩写，不依赖components或case_source。
    if chinese_valid and english_valid and abbreviation_valid:
        display = ((current.get('abbreviation') + ' ') if current.get('abbreviation') else '')
        display += chinese
        if not _same_name(chinese, current.get('english')):
            display += '（' + current['english'] + '）'
        current['display'] = display

    unique_issues = []
    for issue in issues:
        if issue not in unique_issues:
            unique_issues.append(issue)

    changed = []
    for field in ['english', 'official_spelling', 'display', 'aliases', 'abbreviation', 'components']:
        before_present = field in original
        after_present = field in current
        if original.get(field) != current.get(field) or before_present != after_present:
            changed.append({'field': field, 'before': copy.deepcopy(original.get(field)),
                            'after': copy.deepcopy(current.get(field))})
    for index, (before, after) in enumerate(zip(original.get('components', []), current.get('components', []))):
        if not isinstance(before, dict) or not isinstance(after, dict):
            continue
        for field in ['word', 'symbol']:
            if before.get(field) != after.get(field):
                changed.append({'field': f'components.{index}.{field}',
                                'before': copy.deepcopy(before.get(field)),
                                'after': copy.deepcopy(after.get(field))})
    return current, changed, unique_issues


def normalize_term_names(term):
    """按两个例外位整理一个术语的名称与展示字段，返回副本供 ReadWeave 等调用者复用"""
    return _normalize_term_names(term)[0]


def term_name_findings(term):
    """把尚未整理的名称变化与未能自动确认的字段都交给现有检查路径"""
    current, changes, issues = _normalize_term_names(term)
    findings = [{'field': field, 'message': message} for field, message in issues]
    for change in changes:
        findings.append({'field': change['field'], 'message': '术语名称需要按例外位同步；未确定的其他字段保持原样'})
    unique = []
    for finding in findings:
        if finding not in unique:
            unique.append(finding)
    return unique


def format_term_metadata(terms):
    """只应用能由现有名称文本直接确定的改动，返回副本和逐字段差异"""
    result, changes = [], []
    for authored in terms:
        original = copy.deepcopy(authored)
        current, updates, _issues = _normalize_term_names(original)
        if updates:
            for update in updates:
                changes.append({'term_id': original.get('id') if isinstance(original, dict) else None,
                                **copy.deepcopy(update)})
        result.append(current)
    return result, changes
