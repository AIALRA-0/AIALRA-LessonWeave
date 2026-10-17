"""检查容易导致内容缺漏或重复返修的通用材料情形"""
import sys
from pathlib import Path
import fitz

FRAME=Path(__file__).resolve().parents[1]/'04-framework'
sys.path.insert(0,str(FRAME/'01_tree'))
sys.path.insert(0,str(FRAME/'05_writing'))
from tree_document import parse_native_pdf
from tree_model import TreeBuilder,walk
from book_terminology import format_term_metadata
from build_demo import check_terminology


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
