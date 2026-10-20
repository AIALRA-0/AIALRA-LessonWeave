import re
from importlib.metadata import version
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from content_checks import web_origin

from tree_code import file_source


def original_image_url(value):
    # 回放地址和原站地址表示同一资源，移除回放前缀但保留尺寸、格式和查询参数
    return re.sub(r'^https?://[^/]+/archive/replay/.*?/\d{1,14}[a-z]*_/(?=https?://)','',value or '')


def image_asset(record,anchor,*addresses):
    items=record.get('images',[])
    direct=next((item['path'] for item in items if anchor and item.get('anchor')==anchor),None)
    if direct:return direct
    aliases={original_image_url(item['url']):item['path'] for item in items}
    return next((aliases[original_image_url(address)] for address in addresses if original_image_url(address) in aliases),None)


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
        return [web_origin(root,source_record,element,positions)]
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
        images.append((node,address,element))
        return node
    def emit(element, target):
        if isinstance(element,Comment):
            return
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
    image_issues=[]
    for node,address,element in images:
        anchor=element.get('data-iqa-source')
        path=image_asset(source_record,anchor,address,urljoin(url,element.get('src','')),element.get('data-src',''))
        if not path:
            # 原站未交付图片时保留原页中的实际区域，单个资源不再让整篇材料中断
            screenshot=root/source_record['snapshot']['image'].lstrip('/')
            bbox=positions.get(anchor,{}).get('bbox')
            if screenshot.is_file() and bbox and bbox[2]>bbox[0] and bbox[3]>bbox[1]:
                from PIL import Image
                cropped=output/('image-'+anchor+'.png')
                with Image.open(screenshot) as page:
                    box=(max(0,int(bbox[0])),max(0,int(bbox[1])),min(page.width,int(bbox[2])),min(page.height,int(bbox[3])))
                    if box[2]>box[0] and box[3]>box[1]:page.crop(box).save(cropped)
                if cropped.is_file():
                    path=cropped.relative_to(root).as_posix();node['content']['representation']='original_page_region'
            image_issues.append({'anchor':anchor,'original_url':address,'reason':'使用原页区域' if path else '原站未提供可读取的图片，保留位置、链接与替代文字'})
        if path:node['content']['asset']=file_source(root,root/path)['url']
        else:
            node['type']='unknown';node['content']['text']=node['content'].get('alt') or '原站图片暂不可读取'
    return {'tree':tree,'title':title,'pages':[],
            'snapshot':source_record['snapshot'],
            'summary':{'downloaded_images':len(images),'image_issues':image_issues},
            'notes':['正文按 DOM 层级组织，图像和图注归在 figure 中，导航和评论仍保留在原始页面快照中'],
            'adaptations':[{'rule':'figure-ownership','reason':'按 figure 容器绑定图片与图注，图片不再与图注平铺'},
                           {'rule':'independent-original','reason':'原文对照使用浏览器直接截取的原页，DOM 快照在提取前保存，不再由解析树重建'}],
            'engine':{'name':'Playwright + DOM','version':version('playwright'),'profile':'rendered-dom-figure-v1'}}
