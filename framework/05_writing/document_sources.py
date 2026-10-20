"""保留文档中的代码与公式边界，翻译只接收自然语言，不改变材料归属"""
import re
from functools import lru_cache

PROTECTED = re.compile(
    r'(`{3,}|~{3,})[^\n]*\n[\s\S]*?\1|(`+)(?!`)[\s\S]*?\2(?!`)|'
    r'<(?:pre|code|math)\b[^>]*>[\s\S]*?</(?:pre|code|math)>|'
    r'\$\$[\s\S]*?\$\$|(?<![\\$])\$(?!\$)[^$\n]+\$|'
    r'\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|'
    r'\\begin\{(equation\*?|align\*?|aligned|gather\*?|matrix|pmatrix|bmatrix|cases)\}[\s\S]*?\\end\{\3\}|'
    r'https?://[^\s<>]+|</?[A-Za-z][^>\n]*>', re.IGNORECASE)
BOUNDARY = re.compile(r'(?<=[.!?。！？])\s+(?=[A-Z\d\u4e00-\u9fff(\[“\"])')


def protect(original):
    fragments = []

    def replace(match):
        index=len(fragments)
        token = '⟦LW_KEEP_' + str(index).zfill(4) + '⟧'
        while token in original or any(token==known for known,_ in fragments):
            index+=1
            token='⟦LW_KEEP_'+str(index).zfill(4)+'⟧'
        fragments.append((token, match.group()))
        return token

    return PROTECTED.sub(replace, original), fragments


@lru_cache(maxsize=1)
def markdown_parser():
    from markdown_it import MarkdownIt
    return MarkdownIt('commonmark')


def is_requirements(text):
    """使用 PEP 508 语法确认整个配置，不根据文件名或 generated 字样删减内容"""
    from packaging.requirements import Requirement, InvalidRequirement
    count = 0
    explicit = False
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith('#'):
            continue
        value = value.rstrip('\\').strip()
        if re.match(r'^(?:--[A-Za-z][\w-]*|-[cerif])(?:[=\s]|$)', value):
            explicit = True
            continue
        try:
            requirement = Requirement(value)
        except InvalidRequirement:
            return False
        count += 1
        explicit |= bool(requirement.specifier or requirement.url or requirement.marker)
    return bool(count and explicit)


def is_named_code(path):
    """用语言词法器识别有标准文件名的代码和配置，普通文本与文档继续按正文处理"""
    return _named_code(str(path).replace('\\','/').rsplit('/',1)[-1])


@lru_cache(maxsize=None)
def _named_code(path):
    from pygments.lexers import get_lexer_for_filename
    from pygments.lexers.special import TextLexer
    from pygments.util import ClassNotFound
    if str(path).lower().endswith(('.md','.markdown','.mdx','.rst','.rest')):return False
    try:lexer=get_lexer_for_filename(str(path))
    except ClassNotFound:return False
    return not isinstance(lexer,TextLexer) and not set(lexer.aliases)&{'text','rst','rest','md','markdown','textile','rdoc'}


def sentences(source_id, text, start_line=1):
    """先隔离完整代码块，再拆普通句子，代码和数学表达式不会在中间断开"""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans = []
    for token in markdown_parser().parse(text):
        if token.type in {'fence', 'code_block'} and token.map:
            first, last = token.map
            spans.append((offsets[first], offsets[min(last, len(lines))]))
    for match in re.finditer(r'<(?:pre|code)\b[^>]*>[\s\S]*?</(?:pre|code)>', text, re.IGNORECASE):
        spans.append(match.span())
    merged = []
    for first, last in sorted(spans):
        if merged and first < merged[-1][1]:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    result = []
    count = 0

    def prose(first, last):
        nonlocal count
        part = text[first:last]
        protected = [m.span() for m in PROTECTED.finditer(part)]
        previous = 0
        cuts = [m.end() for m in BOUNDARY.finditer(part) if not any(a < m.start() < b for a, b in protected)]
        for end in cuts + [len(part)]:
            original = part[previous:end]
            if original.strip():
                count += 1
                result.append({'id': source_id + '.s' + str(count), 'original': original, 'translation': ''})
            previous = end

    previous = 0
    for first, last in merged:
        prose(previous, first)
        line = start_line + text[:first].count('\n')
        end_line = line + max(0, len(text[first:last].splitlines()) - 1)
        result.append({'id': f'{source_id}.L{line}-L{end_line}', 'original': text[first:last],
            'translation': '', 'start_line': line, 'end_line': end_line, 'verbatim_code': True,
            '_start_column':first-text.rfind('\n',0,first)-1,'_end_column':last-text.rfind('\n',0,last)-1})
        previous = last
    prose(previous, len(text))
    from collections import Counter
    repeated=Counter(row['id']for row in result)
    for row in result:
        if '_start_column'in row:
            first=row.pop('_start_column');last=row.pop('_end_column')
            if repeated[row['id']]>1:row['id']+=f'.C{first}-{last}'
    return result
