"""检查容易导致内容缺漏或重复返修的通用材料情形"""
import sys
from pathlib import Path
import fitz

FRAME=Path(__file__).resolve().parents[1]/'framework'
sys.path.insert(0,str(FRAME/'01_tree'))
sys.path.insert(0,str(FRAME/'05_writing'))
from tree_document import parse_native_pdf
from tree_model import TreeBuilder,walk
from book_terminology import format_term_metadata
from build_demo import check_terminology
from book_sources import generated_pdf_container_sentence


def test_pdf_vector_figures_keep_actual_page(tmp_path):
    # PDF 中的矢量图也必须进入视觉材料，正文提取成功时仍保留完整原页
    path=tmp_path/'source.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page()
        page.insert_text((40,50),'Observed counts')
        page.draw_rect(fitz.Rect(60,100,120,200),fill=(0,0.5,0.2))
        pdf.save(path)
    output=tmp_path/'out'
    output.mkdir()
    result=parse_native_pdf(TreeBuilder(),tmp_path,path,output)
    figures=[node for node in walk(result['tree']) if node['type']=='image']
    assert figures and figures[0]['content']['role']=='visual_page'
    assert (tmp_path/figures[0]['content']['asset'].lstrip('/')).is_file()


def test_unit_name_is_kept_once_with_its_alias():
    # 单位名称与其英文相同时保留别名，展示名称省去重复的伪缩写
    term={'id':'light','kind':'unit','abbreviation':'lux','chinese':'勒克斯','english':'Lux','aliases':['lux'],
          'components':[{'symbol':'lux','word':'Lux'}],'display':'lux 勒克斯（Lux）'}
    terms,changes=format_term_metadata([term])
    assert terms[0]['abbreviation'] is None
    assert terms[0]['components']==[]
    assert any(alias.casefold()=='lux' for alias in terms[0]['aliases'])
    assert not check_terminology(terms[0])
    assert changes


def test_generated_pdf_labels_keep_body_and_heading_in_coverage(tmp_path):
    # 仅排除经过原文件和整页坐标核对的结构标签，同字正文和局部标题继续逐句核对
    path=tmp_path/'notes.pdf'
    with fitz.open() as pdf:
        page=pdf.new_page()
        page.insert_text((40,50),'notes 1')
        rect=list(page.rect)
        pdf.save(path)
    root={'id':'root','type':'document','child_ids':['page'],'raw_content':{'text':'notes','source_text':[]},'source':{'kind':'file','path':'notes.pdf'},'sentences':[{'id':'root.s1','original':'notes'}]}
    assert generated_pdf_container_sentence(tmp_path,root)
    root['type']='paragraph'
    assert generated_pdf_container_sentence(tmp_path,root) is None
    source={'id':'page','type':'section','child_ids':['text'],'raw_content':{'text':'1'},'source':{'kind':'pdf','path':'notes.pdf','page':1,'bbox':rect},'sentences':[{'id':'page.s1','original':'1'}]}
    assert generated_pdf_container_sentence(tmp_path,source)
    source['source']['bbox']=[40,40,90,60]
    assert generated_pdf_container_sentence(tmp_path,source) is None
