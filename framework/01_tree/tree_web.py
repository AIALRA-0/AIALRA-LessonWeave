import re
from importlib.metadata import version
from urllib.parse import urljoin

from bs4 import BeautifulSoup, NavigableString, Tag

from tree_code import file_source


def parse_webpage(builder, root, source_record, output):
    import json
    original=root/source_record['entry']
    url=source_record['material']
    html=original.read_text(encoding='utf-8')
    positions=json.loads((root/source_record['positions']).read_text(encoding='utf-8'))
    soup=BeautifulSoup(html,'html.parser')
    body=soup.select_one('.body.markup') or soup.find('article') or soup.find('main') or soup.body
    if body is None:
        raise ValueError('没有找到网页正文区域')
    def source(element):
        anchor=element.get('data-iqa-source')
        return [{**file_source(root,original),'kind':'html','dom_path':f'[data-iqa-source="{anchor}"]',
                 'bbox':positions[anchor]['bbox'],'url':url}]
    title_tag=soup.select_one('h1.post-title') or soup.find('h1') or soup.find('title')
    title=title_tag.get_text(' ',strip=True) if title_tag else url
    tree=builder.node('webpage',{'name':title},[file_source(root,original)])
    if title_tag and title_tag.get('data-iqa-source'):
        tree['children'].append(builder.node('heading',{'text':title},source(title_tag)))
    for element in soup.select('.subtitle,.byline-names time,.byline-names .author-name'):
        text=element.get_text(' ',strip=True)
        if text and element.get('data-iqa-source'):
            tree['children'].append(builder.node('metadata',{'text':text},source(element)))
    images=[]
    sections=[]
    skipped_tags={'script','style','noscript','button','form'}
    def image(element):
        anchor=element['data-iqa-source']
        address=positions[anchor]['src'] or urljoin(url,element.get('src',''))
        node=builder.node('image',{'original_url':address,'alt':element.get('alt','')},source(element))
        images.append((node,address))
        return node
    def emit(element, target):
        if isinstance(element,NavigableString):
            text=str(element).strip()
            if text and isinstance(element.parent,Tag):
                target.append(builder.node('paragraph',{'text':text},source(element.parent)))
            return
        if not isinstance(element,Tag) or element.name in skipped_tags:
            return
        if element.name=='figure':
            children=[]
            seen=set()
            for picture in element.find_all('img'):
                address=positions[picture['data-iqa-source']]['src'] or picture.get('src')
                if address and address not in seen:
                    children.append(image(picture))
                    seen.add(address)
            for caption in element.find_all('figcaption'):
                text=caption.get_text(' ',strip=True)
                if text:
                    children.append(builder.node('caption',{'text':text},source(caption)))
            target.append(builder.node('figure',{},source(element),children))
        elif element.name=='img':
            target.append(builder.node('figure',{},source(element),[image(element)]))
        elif element.name in ('ul','ol'):
            node=builder.node('list',{'ordered':element.name=='ol','start':int(element.get('start',1))},source(element))
            for child in element.find_all('li',recursive=False):
                number=int(child.get('value',len(node['children'])+node['content']['start']))
                item=builder.node('list_item',{'ordinal':number,'marker':str(number) if element.name=='ol' else '•'},source(child))
                for content in child.children:
                    emit(content,item['children'])
                node['children'].append(item)
            target.append(node)
        elif element.name=='table':
            rows=[[cell.get_text(' ',strip=True) for cell in row.find_all(['th','td'])] for row in element.find_all('tr')]
            target.append(builder.node('table',{'rows':rows},source(element)))
        elif element.name=='pre':
            target.append(builder.node('code_block',{'text':element.get_text(),'language':'text'},source(element)))
        elif element.name=='math' or 'katex' in element.get('class',[]):
            annotation=element.find('annotation',attrs={'encoding':'application/x-tex'})
            target.append(builder.node('equation',{'text':annotation.get_text() if annotation else element.get_text(' ',strip=True),'mathml':str(element)},source(element)))
        elif element.name in ('p','figcaption','blockquote'):
            text=element.get_text(' ',strip=True)
            if text:
                target.append(builder.node('caption' if element.name=='figcaption' else 'paragraph',{'text':text},source(element)))
            for embedded in element.find_all(['img','math']):
                emit(embedded,target)
        elif element.name in ('hr','br'):
            return
        else:
            for child in element.children:
                emit(child,target)
    # 按实际 DOM 顺序建立标题层级，容器 div 不生成无意义的空章节
    def traverse(element):
        if isinstance(element,Tag) and re.fullmatch(r'h[1-6]',element.name):
            text=element.get_text(' ',strip=True)
            level=int(element.name[1:])
            while sections and sections[-1][0]>=level:
                sections.pop()
            node=builder.node('section',{'text':text},source(element))
            (sections[-1][1]['children'] if sections else tree['children']).append(node)
            sections.append((level,node))
        elif isinstance(element,Tag) and element.name not in ('figure','p','pre','table','ul','ol','math','figcaption','blockquote','img') and element.name not in skipped_tags:
            for child in element.children:
                traverse(child)
        else:
            emit(element,sections[-1][1]['children'] if sections else tree['children'])
    for element in body.children:
        traverse(element)
    assets={item['url']:item['path'] for item in source_record['images']}
    for node,address in images:
        if address not in assets:raise ValueError('原材料清单中没有这张图像')
        node['content']['asset']=file_source(root,root/assets[address])['url']
    return {'tree':tree,'title':title,'pages':[],
            'snapshot':source_record['snapshot'],
            'summary':{'downloaded_images':len(images)},
            'notes':['正文按 DOM 层级组织，图像和图注归在 figure 中，导航和评论仍保留在原始页面快照中'],
            'adaptations':[{'rule':'figure-ownership','reason':'按 figure 容器绑定图片与图注，图片不再与图注平铺'},
                           {'rule':'independent-original','reason':'原文对照使用浏览器直接截取的原页，DOM 快照在提取前保存，不再由解析树重建'}],
            'engine':{'name':'Playwright + DOM','version':version('playwright'),'profile':'rendered-dom-figure-v1'}}
