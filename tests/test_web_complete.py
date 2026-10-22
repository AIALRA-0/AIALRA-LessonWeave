"""用不同页头和陌生控件检查原页内容是否会在解析时消失"""
import json
from pathlib import Path

from PIL import Image

from lessonweave import pipeline
from build_tree import build_tree
from content_checks import source_inventory
from tree_model import walk
import book_sources


def parse(tmp_path, html):
    pipeline.scaffold(tmp_path)
    folder=tmp_path/'00_source/materials/page';folder.mkdir(parents=True)
    (folder/'original.html').write_text(html,encoding='utf-8')
    (folder/'dom.json').write_text('{}',encoding='utf-8')
    Image.new('RGB',(100,200),'white').save(folder/'original.png')
    source={'status':'acquired','material':'https://example.com/article','entry':'00_source/materials/page/original.html',
            'positions':'00_source/materials/page/dom.json','images':[],'resources':[],
            'snapshot':{'image':'/00_source/materials/page/original.png','html':'/00_source/materials/page/original.html','width':100,'height':200}}
    payload={'kind':'url','material':source['material'],'mode':'one_shot','system_prompt':'解释全部有用材料'}
    return build_tree(tmp_path,payload,source),source


def test_metadata_is_extracted_without_a_site_specific_byline(tmp_path):
    html='''<html><head><title>A study</title><meta name="author" content="Example Writer">
    <meta property="article:published_time" content="2026-01-02"><link rel="canonical" href="https://example.com/article">
    <script type="application/ld+json">{"@type":"BlogPosting","headline":"A study","author":{"name":"Example Writer"},"dateModified":"2026-01-03","unknownField":"retain this too"}</script>
    </head><body><header><h1>A study</h1><span class="new-person-widget">Example Writer</span></header><main><p>Full explanation</p></main></body></html>'''
    result,source=parse(tmp_path,html)
    fields={(n['content'].get('field'),n['content'].get('value'))for n in walk(result['tree'])}
    assert ('author','Example Writer')in fields and ('published_time','2026-01-02')in fields
    assert ('modified_time','2026-01-03')in fields and ('canonical_url','https://example.com/article')in fields
    assert result['coverage']['content']['ratio']==1 and result['coverage']['objects']['ratio']==1
    inventory=source_inventory(tmp_path,result,source)
    assert any('unknownField'in u.get('text','')for u in inventory['units'])


def test_inventory_includes_text_outside_main_and_unrecognized_media(tmp_path):
    html='''<html><head><meta name="custom-tag" content="custom information"></head><body>
    <nav>Locate chapter</nav><main><h1>Subject</h1><p>Main text</p><button>Change the measurement</button>
    <canvas data-value="42"></canvas><svg><text>Diagram label</text></svg></main>
    <aside>Unusual appendix<input placeholder="Type a measurement" value="42"></aside><footer>License and attribution</footer></body></html>'''
    result,source=parse(tmp_path,html)
    inventory=source_inventory(tmp_path,result,source)
    text=' '.join(u.get('text','')for u in inventory['units'])
    assert all(value in text for value in ['custom information','Locate chapter','Change the measurement','Diagram label','Unusual appendix','Type a measurement','42','License and attribution'])
    fragments=[n for n in walk(result['tree'])if n['content'].get('representation')=='original_dom_fragment']
    assert len(fragments)==2 and any('data-value="42"'in n['content']['html_fragment']for n in fragments)
    assert result['coverage']['content']['ratio']==1 and result['validation']['passed']


def test_metadata_bundle_reaches_the_title_question_without_other_body():
    nodes={'title':{'content':{}},'author':{'content':{'metadata_for':'title'}},'body':{'content':{}}}
    selected={'title'};owners={'title':['q.0.1'],'body':['q.1.1']};required=['title']
    book_sources.complete_metadata(nodes,selected,owners,required)
    assert selected=={'title','author'} and owners['author']==['q.0.1']
    assert required==['title','author'] and owners['body']==['q.1.1']
def test_hidden_infrastructure_frame_does_not_hide_visible_teaching_media():
    from bs4 import BeautifulSoup
    from web_metadata import hidden_control_frame
    soup=BeautifulSoup('<iframe width="0" height="0" src="/channel"></iframe><iframe width="0" height="0" title="互动实验"></iframe><iframe width="600" height="400"></iframe>','html.parser')
    assert [hidden_control_frame(n) for n in soup.find_all('iframe')]==[True,False,False]
