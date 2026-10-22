"""在真实浏览器检查各阅读位置的公式，并确认代码和原始文字没有被改写"""
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright

from lessonweave import legacy
import math_syntax

READER = Path(__file__).resolve().parents[1] / 'framework/reader'


@pytest.fixture
def math_page():
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        def route(request):
            path = urlsplit(request.request.url).path
            if path == '/':
                request.fulfill(body='''<!doctype html><meta charset="utf-8"><main id="reading"></main>
                <script src="/math-text.js"></script><script src="/reader-text.js"></script>''', content_type='text/html')
            elif (READER / path.lstrip('/')).is_file():
                request.fulfill(path=str(READER / path.lstrip('/')))
            else:
                request.fulfill(status=404, body='')
        page.route('http://reader.test/**', route)
        page.goto('http://reader.test/')
        yield page
        assert errors == []
        browser.close()


def test_tables_options_terms_tooltips_headings_and_dynamic_articles(math_page):
    examples = {
        'paragraph': ('p', '截面满足 p∘s=id_Z'),
        'heading': ('h4', 'z、w、X_z 与 Ω_z'),
        'table': ('td', r'\(z=(z_1,\ldots,z_n)\)'),
        'quiz': ('label', r'A · \(s\circ p=\operatorname{id}_X\)'),
        'term': ('summary', r'法丛 \(N_{Y/X}\)'),
        'tooltip': ('p', 'Ω_z 是 X_z 中落在 Ω 内的点，逆映射写作 p⁻¹(z)'),
        'answer': ('li', r'\[p\circ s=\operatorname{id}_Z\]'),
    }
    result = math_page.evaluate(r'''async rows=>{
      const root=document.querySelector('#reading'),original={};
      for(const[id,[tag,text]]of Object.entries(rows)){const node=document.createElement(tag);node.id=id;node.textContent=text;root.append(node);original[id]=text;}
      await ReaderText.renderIn(root,['z','w','Ω']);
      const first=root.querySelectorAll('.katex').length;
      await ReaderText.renderIn(root,['z','w','Ω']);
      const result={count:first,again:root.querySelectorAll('.katex').length,audit:ReaderText.audit(root),rows:{}};
      for(const id of Object.keys(rows)){const node=document.getElementById(id);result.rows[id]={rendered:node.querySelectorAll('.katex').length,plain:ReaderText.plain(node),original:original[id]};}
      root.innerHTML='<p id="updated">\\(X_z=p^{-1}(z)\\)</p>';
      await ReaderText.renderIn(root);result.updated=root.querySelectorAll('.katex').length;result.updatedAudit=ReaderText.audit(root);
      return result;
    }''', examples)
    assert result['count'] == result['again']
    assert result['audit']['errors'] == result['updatedAudit']['errors'] == []
    assert result['updated'] == 1
    for row in result['rows'].values():
        assert row['rendered'] > 0
        assert row['plain'] == row['original']


def test_explicit_math_wins_over_identifier_protection_and_code_stays_verbatim(math_page):
    result = math_page.evaluate(r'''async()=>{
      const root=document.querySelector('#reading');
      const source='user_name | https://example.test/x_y | /src/file_name.py | C:\\data\\file_name.py | $20 | ${USER}';
      const node=document.createElement('p');node.id='safe';node.textContent=source;root.append(node);
      const code=document.createElement('code');code.textContent='p∘s=id_Z \\(x_1\\)';root.append(code);
      const math=document.createElement('p');math.textContent='\\(\\operatorname{id}_Z\\)';root.append(math);
      await ReaderText.renderIn(root);
      return {safe:node.textContent,source,safeMath:node.querySelectorAll('.katex').length,code:code.textContent,codeMath:code.querySelectorAll('.katex').length,math:math.querySelectorAll('.katex').length,audit:ReaderText.audit(root)};
    }''')
    assert result['safe'] == result['source'] and result['safeMath'] == 0
    assert result['codeMath'] == 0 and result['math'] == 1
    assert result['audit']['errors'] == []


@pytest.mark.parametrize('label', [r'$\exists N$ 与 $\forall N$', r'$a_1$ and $b_2$', 'W₀ 与 W₋₁'])
def test_media_math_labels_keep_separate_formulas_and_the_words_between_them(math_page, label):
    resources = json.loads((READER.parent/'examples/media/resources.json').read_text('utf-8'))
    resource = next(row for row in resources if row['kind'] == 'formula')
    resource['guide']['components'] = [{'label':label, 'math_label':True, 'explanation':'逐个读取两个记号'}]
    math_page.add_script_tag(url='/reading-icons.js')
    math_page.add_script_tag(url='/media-renderer.js')
    result = math_page.evaluate('''async resource=>{
      const root=document.querySelector('#reading');root.append(LessonMedia.render(resource));
      await ReaderText.renderIn(root);
      const label=root.querySelector('.lw-media-components li > span');
      return {plain:ReaderText.plain(label),formulas:label.querySelectorAll('.katex').length,audit:ReaderText.audit(root)};
    }''', resource)
    assert result['plain'] == label and result['formulas'] == 2
    assert result['audit']['errors'] == []
    assert math_syntax.check_documents({'reader':resource}) == []


def test_marked_math_with_chinese_text_is_not_silently_skipped(math_page):
    value = r'\(x=1\text{，成立}\)'
    result = math_page.evaluate('''async text=>{
      const root=document.querySelector('#reading');root.textContent=text;await ReaderText.renderIn(root);
      return {plain:ReaderText.plain(root),formulas:root.querySelectorAll('.katex').length,audit:ReaderText.audit(root)};
    }''', value)
    assert result['plain'] == value and result['formulas'] == 1
    assert result['audit']['errors'] == []
    invalid = r'\(\unknowncommand{x}\text{，条件}\)'
    assert math_syntax.check_documents({'reader':{'kind':'formula','text':invalid}})


def test_syntax_checker_covers_saved_reader_fields_and_only_repairs_valid_proposals():
    invalid = r'\(\unknowncommand{x}\)'
    doc = {'quiz': [{'options': [invalid], 'reference_answer': invalid}],
           'glossary': [{'definition': invalid, 'explanation': [invalid]}],
           'units': [{'explanation': [{'kind': 'table', 'headers': [invalid], 'rows': [[invalid]]},
                                      {'kind': 'code', 'text': invalid}]}]}
    issues = math_syntax.check_documents({'reader': doc})
    paths = {row['path'] for row in issues}
    assert paths == {'/quiz/0/options/0', '/quiz/0/reference_answer', '/glossary/0/definition',
                     '/glossary/0/explanation/0', '/units/0/explanation/0/headers/0', '/units/0/explanation/0/rows/0/0'}
    assert not any('script_value' in row for row in issues)
    fixed = math_syntax.check_documents({'reader': {'definition': r'使用 \(\texttt{signal_name}\) 读取结果'}})
    assert len(fixed) == 1 and r'\texttt{signal\_name}' in fixed[0]['script_value']


def test_syntax_checker_accepts_unicode_and_does_not_treat_source_or_code_as_math():
    value = {'definition': 'p∘s=id_Z，Ω_z，p⁻¹(z)', 'source': {'text': r'\(\badsource\)'},
             'units': [{'explanation': [{'kind': 'code', 'text': r'\(\badcode\)'}]}],
             'quiz': [{'options': [r'\(p\circ s=\operatorname{id}_Z\)']}],
             'explanation': '读取 user_name 和 https://example.test/x_y'}
    assert math_syntax.check_documents({'reader': value}) == []


def test_syntax_checker_covers_structured_term_explanations_names_and_openings():
    invalid = r'\(\unknowncommand{x}\)'
    term = {'abbreviation': invalid, 'official_spelling': invalid, 'aliases': [invalid],
            'professional_definition': {'genus': invalid},
            'intuitive_explanation': {key: invalid for key in ['anchor', 'mapping', 'intuition']},
            'typical_example': {key: invalid for key in ['initial_conditions', 'mechanism', 'outcome']}}
    document = {'appendix': {'terms': [term]}, 'opening': invalid, 'opening_forward': invalid}
    paths = {issue['path'] for issue in math_syntax.check_documents({'reader': document})}
    expected = {'/opening', '/opening_forward', '/appendix/terms/0/abbreviation',
                '/appendix/terms/0/official_spelling', '/appendix/terms/0/aliases/0',
                '/appendix/terms/0/professional_definition/genus'}
    expected.update('/appendix/terms/0/intuitive_explanation/' + key for key in ['anchor', 'mapping', 'intuition'])
    expected.update('/appendix/terms/0/typical_example/' + key for key in ['initial_conditions', 'mechanism', 'outcome'])
    assert paths == expected


def test_adjacent_factors_keep_their_own_subscripts_and_equation_tags_are_display_math(math_page):
    value = r'\(a_bc_d\)，\[A_{LA}A_R^*\tag{1}\]，\(a=c_id_i\)，\(1ᵐⁿ=1\)'
    result=math_page.evaluate(r'''async text=>{const node=document.querySelector('#reading');node.textContent=text;await ReaderText.renderIn(node);return {plain:ReaderText.plain(node),audit:ReaderText.audit(node),sources:[...node.querySelectorAll('[data-math-source]')].map(span=>span.dataset.mathSource)}}''',value)
    assert result['plain']==value and result['audit']['errors']==[]
    assert result['sources'][0]=='a_bc_d'
    assert math_syntax.check_documents({'reader': {'definition': value}})==[]


def test_literal_braces_get_a_matching_escape_but_no_mathematical_operator_is_invented():
    value = {'kind':'formula','text':r'S\{a,b}'}
    issues=math_syntax.check_documents({'reader':value})
    assert len(issues)==1 and issues[0]['script_value']==r'S\{a,b\}'
    assert 'setminus' not in issues[0]['script_value']


def test_prose_math_repair_preserves_display_layout():
    value = {'definition': r'计算结果为 \[\texttt{signal_name}\]'}
    issues = math_syntax.check_documents({'reader': value})
    assert len(issues) == 1
    assert issues[0]['script_value'] == r'计算结果为 \[\texttt{signal\_name}\]'


def test_dollar_code_tokens_do_not_swallow_the_prose_between_them(math_page):
    source = r'进程调用 $finish 结束，另一个进程在 #100_000 后调用 $display 报告结果，读取 ${STATE}，再检查 $set_isolation 的参数；匹配 {^VDD$} 或 {^u_sram.*$}'+'\n    $ git show $commit | awk \'{print $3}\'\n'
    result = math_page.evaluate('''async text=>{
      const root=document.querySelector('#reading');root.textContent=text;await ReaderText.renderIn(root);
      return {plain:ReaderText.plain(root),formulas:root.querySelectorAll('.katex').length,audit:ReaderText.audit(root)};
    }''', source)
    assert result['plain'] == source and result['formulas'] == 0
    assert result['audit']['errors'] == []
    assert math_syntax.check_documents({'reader':{'definition':source}}) == []
    assert math_syntax.check_documents({'reader':{'definition':r'读取 $f(x)$、$x_i$ 和 $x + y$'}}) == []
    normalized=math_page.evaluate("() => [LessonMath.normalize('W₋₁'),LessonMath.normalize(LessonMath.normalize('W₋₁'))]")
    assert normalized == ['W_{-1}','W_{-1}']


def test_display_math_keeps_its_delimiters_when_reading_paragraphs_are_split(math_page):
    text = '先看这个式子\n\\[\na=b+c\n\\]\n再读下一段'
    result=math_page.evaluate('''async text=>{
      const parts=ReaderText.paragraphs(text),root=document.querySelector('#reading');
      for(const part of parts){const paragraph=document.createElement('p');ReaderText.rich(paragraph,part);root.append(paragraph);}
      await ReaderText.renderIn(root);
      return {parts,formulas:root.querySelectorAll('.katex-display').length,audit:ReaderText.audit(root),plain:[...root.children].map(node=>ReaderText.plain(node)).join('\\n')};
    }''',text)
    assert result['parts'] == ['先看这个式子','\\[\na=b+c\n\\]','再读下一段']
    assert result['formulas'] == 1 and result['audit']['errors'] == []
    assert result['plain'] == text
    code='```python\nx = 1\ny = 2\n```'
    assert math_page.evaluate('text=>ReaderText.paragraphs(text)',code) == [code]
