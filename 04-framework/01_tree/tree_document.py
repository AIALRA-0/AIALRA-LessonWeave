import json
import re
import shutil
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from statistics import median

import fitz

from tree_code import file_source


def parse_document(builder, root, path, output):
    import importlib.util
    import os
    if os.environ.get('LESSONWEAVE_PDF_ENGINE') == 'pymupdf' or importlib.util.find_spec('docling') is None:
        return parse_native_pdf(builder, root, path, output)
    cache = root/'01_tree/cache/native-docling'
    info = {'path':str(path),'mtime_ns':path.stat().st_mtime_ns,'size':path.stat().st_size}
    if not (cache/'cache.json').is_file() or json.loads((cache/'cache.json').read_text(encoding='utf-8')) != info:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter,PdfFormatOption
        from docling_core.types.doc import ImageRefMode
        cache.mkdir(parents=True,exist_ok=True)
        options=PdfPipelineOptions(do_ocr=True,generate_page_images=True,generate_picture_images=True,images_scale=1.5)
        options.heading_hierarchy_options.enabled=True
        options.accelerator_options.num_threads=4
        document=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=options)}).convert(path).document
        document.save_as_json(cache/'docling.json',artifacts_dir=cache/'assets',image_mode=ImageRefMode.REFERENCED,ensure_ascii=False)
        (cache/'cache.json').write_text(json.dumps(info),encoding='utf-8')
    native=json.loads((cache/'docling.json').read_text(encoding='utf-8'))
    def freeze_assets(value):
        if isinstance(value,dict):
            if 'uri' in value and isinstance(value['uri'],str) and Path(value['uri']).is_file():
                original=Path(value['uri'])
                target=output/'native-assets'/original.name
                target.parent.mkdir(exist_ok=True)
                if not target.is_file():
                    shutil.copyfile(original,target)
                value['uri']=str(target)
            for child in value.values():
                freeze_assets(child)
        elif isinstance(value,list):
            for child in value:
                freeze_assets(child)
    freeze_assets(native)
    (output/'docling.json').write_text(json.dumps(native,ensure_ascii=False,indent=2),encoding='utf-8')
    pages=[]
    for number,page in native['pages'].items():
        image=Path(page['image']['uri'])
        pages.append({'number':int(number),'width':page['size']['width'],'height':page['size']['height'], 'preview':file_source(root,image)['url']})
    page_map={page['number']:page for page in pages}
    objects={item['self_ref']:item for name in ('texts','pictures','tables','groups') for item in native[name]}
    used=set()
    furniture=[]
    repeated=Counter(item.get('text','') for item in native['texts'] if item.get('label')=='section_header')
    pdf=fitz.open(path)
    def sources(item):
        refs=[]
        for provenance in item.get('prov',[]):
            page=page_map[provenance['page_no']]
            box=provenance['bbox']
            if box.get('coord_origin')=='BOTTOMLEFT':
                bbox=[box['l'],page['height']-box['t'],box['r'],page['height']-box['b']]
            else:
                bbox=[box['l'],box['t'],box['r'],box['b']]
            bbox=[max(0,value) for value in bbox]
            refs.append({**file_source(root,path),'kind':'pdf','page':page['number'],'bbox':bbox,'engine_ref':item['self_ref']})
        return refs or [{**file_source(root,path),'engine_ref':item['self_ref']}]
    def crop(item, name):
        source=sources(item)[0]
        if source['kind']!='pdf':
            return None
        target=output/(name+'.png')
        pdf[source['page']-1].get_pixmap(matrix=fitz.Matrix(2,2),clip=fitz.Rect(source['bbox']),alpha=False).save(target)
        return file_source(root,target)['url']
    floating=[item for name in ('pictures','tables') for item in native[name]]
    caption_owners={}
    for visual in floating:
        for ref in visual.get('captions',[]):
            caption_owners[ref['$ref']]=visual['self_ref']
    caption_pattern=re.compile(r'^(?:Extended Data\s+)?(?:Fig(?:ure)?\.?|Table)\s*\d+\s*[|:]',re.I)
    visual_texts={target['$ref'] for visual in floating for target in visual.get('children',[])}
    for item in native['texts']:
        if item['self_ref'] in caption_owners or item['self_ref'] in visual_texts or not caption_pattern.match(item.get('text','')):
            continue
        source=sources(item)[0]
        candidates=[]
        for visual in floating:
            target=sources(visual)[0]
            if target.get('page')!=source.get('page'):
                continue
            a,b=source['bbox'],target['bbox']
            overlap=min(a[2],b[2])-max(a[0],b[0])
            distance=min(abs(a[1]-b[3]),abs(a[3]-b[1]))
            if overlap>0 and distance<page_map[source['page']]['height']*.25:
                candidates.append((distance,visual['self_ref']))
        if candidates:
            caption_owners[item['self_ref']]=min(candidates)[1]
    continuations={}
    continuation_refs=set()
    for ref in list(caption_owners):
        if ref not in caption_owners or ref in continuation_refs:
            continue
        caption=objects[ref]
        if caption.get('text','').rstrip().endswith(('.', '!', '?')):
            continue
        anchor=sources(caption)[0]
        a=anchor.get('bbox')
        if not a:
            continue
        for candidate in native['texts']:
            text=candidate.get('text','')
            candidate_ref=candidate['self_ref']
            if candidate_ref==ref or candidate_ref in continuation_refs or candidate['label'] not in ('text','caption') or caption_pattern.match(text):
                continue
            if candidate_ref in visual_texts and candidate['label']!='caption':
                continue
            source=sources(candidate)[0]
            b=source.get('bbox')
            horizontal=b and b[0]>a[2] and abs(a[1]-b[1])<2 and abs(a[3]-b[3])<13 and text[:1].islower()
            vertical=b and abs(b[0]-a[0])<4 and 0<=b[1]-a[3]<6 and caption_pattern.match(caption.get('text',''))
            if b and source['page']==anchor['page'] and (horizontal or vertical):
                continuations.setdefault(ref,[]).append(candidate_ref)
                continuation_refs.add(candidate_ref)
                caption_owners.pop(candidate_ref,None)
    moved=continuation_refs
    merged_visuals={}
    secondary_visuals=set()
    pictures=native['pictures']
    for left in pictures:
        if left['self_ref'] in secondary_visuals:
            continue
        a=sources(left)[0]
        owners=[key for key,owner in caption_owners.items() if owner==left['self_ref'] and caption_pattern.match(objects[key].get('text',''))]
        if not owners:
            continue
        for right in pictures:
            b=sources(right)[0]
            if b['page']!=a['page'] or b['bbox'][0]<=a['bbox'][2] or b['bbox'][0]-a['bbox'][2]>30:
                continue
            if abs(a['bbox'][1]-b['bbox'][1])>3 or abs(a['bbox'][3]-b['bbox'][3])>3:
                continue
            if any(owner==right['self_ref'] for owner in caption_owners.values()):
                continue
            merged_visuals.setdefault(left['self_ref'],[]).append(right)
            secondary_visuals.add(right['self_ref'])
    figure_label_owners={}
    for picture in pictures:
        if picture['self_ref'] in secondary_visuals:
            continue
        captions=[objects[key] for key,owner in caption_owners.items() if owner==picture['self_ref']]
        if not captions:
            continue
        source=sources(picture)[0]
        x0,y0,x1,y1=source['bbox']
        for extra in merged_visuals.get(picture['self_ref'],[]):
            box=sources(extra)[0]['bbox']
            x0,y0,x1,y1=min(x0,box[0]),min(y0,box[1]),max(x1,box[2]),max(y1,box[3])
        bottom=min(sources(caption)[0]['bbox'][1] for caption in captions)
        for item in native['texts']:
            ref=item['self_ref']
            if ref in caption_owners or ref in moved:
                continue
            target=sources(item)[0]
            box=target.get('bbox')
            if box and target['page']==source['page'] and box[0]>=x0-8 and box[2]<=x1+8 and box[1]>=y0-2 and box[3]<=max(y1,bottom)+1:
                figure_label_owners[ref]=picture['self_ref']
    repaired_tables=[]
    def descendants(item):
        for child in item.get('children',[]):
            target=objects.get(child['$ref'])
            if target:
                if 'text' in target:
                    yield target
                else:
                    yield from descendants(target)
    def aligned_table(items):
        # 只有表头、首列和其余列的位置能相互印证时，才用 OCR 文字恢复单元格
        located=[(item,sources(item)[0]) for item in items if item.get('text','').strip()]
        if len(located)<6 or any(source['kind']!='pdf' for _,source in located):
            return None
        located.sort(key=lambda pair:(pair[1]['bbox'][1],pair[1]['bbox'][0]))
        top=located[0][1]['bbox'][1]
        headers=sorted([(item,source) for item,source in located if abs(source['bbox'][1]-top)<4],key=lambda pair:pair[1]['bbox'][0])
        if len(headers)<2:
            return None
        xs=[source['bbox'][0] for _,source in headers]
        if min(b-a for a,b in zip(xs,xs[1:]))<40:
            return None
        first_column=sorted([(item,source) for item,source in located if abs(source['bbox'][0]-xs[0])<10],key=lambda pair:pair[1]['bbox'][1])
        ys=[source['bbox'][1] for _,source in first_column]
        if len(ys)<3 or min(b-a for a,b in zip(ys,ys[1:]))<15:
            return None
        cells=[[[] for _ in xs] for _ in ys]
        for item,source in located:
            x,y=source['bbox'][:2]
            column=min(range(len(xs)),key=lambda index:abs(xs[index]-x))
            if abs(xs[column]-x)>12:
                return None
            row=max((index for index,start in enumerate(ys) if y>=start-4),default=0)
            cells[row][column].append(item)
        if any(not cell for row in cells for cell in row):
            return None
        return [[ ' '.join(item['text'] for item in cell) for cell in row] for row in cells],cells
    def plain(item, override=None):
        ref=item['self_ref']
        used.add(ref)
        label=item.get('label','text')
        kind=override or {'text':'paragraph','caption':'caption','page_header':'header','page_footer':'footer',
                          'footnote':'footnote','reference':'reference','list_item':'list_item','code':'code_block','formula':'equation','title':'heading'}.get(label)
        text=item.get('text','')
        content={'text':text} if text.strip() else {}
        if item.get('orig') and item['orig']!=text:
            content['raw_text']=item['orig']
        if ref in continuations:
            extras=[objects[extra] for extra in continuations[ref]]
            used.update(extra['self_ref'] for extra in extras)
            content['text']=' '.join([text]+[extra.get('text','') for extra in extras])
            locations=sources(item)+[source for extra in extras for source in sources(extra)]
        else:
            locations=sources(item)
        if kind=='equation':
            content['asset']=crop(item,ref.replace('#/','').replace('/','-'))
            content['description']='公式字形保留在图像中，尚未转换成 LaTeX'
        if kind=='list_item':
            marker=item.get('marker','')
            details={'marker':marker,'ordered':item.get('enumerated',False)}
            number=re.search(r'\d+',marker)
            if number:details['ordinal']=int(number[0])
            return builder.node('list_item',details,locations,[builder.node('paragraph',content,locations)])
        if not kind or kind in ('paragraph','caption','heading') and not text.strip():
            kind='unknown'
            content['reason']='原解析器没有给出可使用的内容类型或文字，原始对象已保留'
        return builder.node(kind,content,locations)
    def visual(item):
        ref=item['self_ref']
        used.add(ref)
        members=[item]+merged_visuals.get(ref,[])
        used.update(member['self_ref'] for member in members)
        captions=[objects[key] for key,owner in caption_owners.items() if owner==ref]
        is_figure=item.get('label')=='picture' or any(re.match(r'^(?:Extended Data\s+)?Fig',c.get('text',''),re.I) for c in captions)
        asset=crop(item,ref.replace('#/','').replace('/','-'))
        member_sources=[source for member in members for source in sources(member)]
        location=sources(item)[0]
        box=location.get('bbox')
        if is_figure and not captions and box and box[2]-box[0]<30 and box[3]-box[1]<30:
            return builder.node('metadata',{'name':'页边标识图像','asset':asset,'description':'这个小图像没有图注，按页边标识保存，不计入正文图'},sources(item))
        children=[]
        extra_sources=[]
        cell_sources=[]
        inner_map={child['self_ref']:child for member in members for child in descendants(member)}
        inner_map.update({key:objects[key] for key,owner in figure_label_owners.items() if owner==ref})
        inner=[child for key,child in inner_map.items() if key not in caption_owners and key not in moved]
        if is_figure:
            box=fitz.Rect(member_sources[0]['bbox'])
            for source in member_sources[1:]+[source for target in inner for source in sources(target) if source['kind']=='pdf']:
                box |= fitz.Rect(source['bbox'])
            target=output/(ref.replace('#/','').replace('/','-')+'.png')
            pdf[member_sources[0]['page']-1].get_pixmap(matrix=fitz.Matrix(2,2),clip=box,alpha=False).save(target)
            asset=file_source(root,target)['url']
            children.append(builder.node('image',{'asset':asset},member_sources))
        else:
            rows=item.get('data',{}).get('num_rows',0)
            cols=item.get('data',{}).get('num_cols',0)
            matrix=[['' for _ in range(cols)] for _ in range(rows)]
            for cell in item.get('data',{}).get('table_cells',[]):
                row,col=cell['start_row_offset_idx'],cell['start_col_offset_idx']
                if row<rows and col<cols:
                    matrix[row][col]=cell.get('text','')
            if not rows or not cols or not any(any(row) for row in matrix):
                recovered=aligned_table(inner)
                if recovered:
                    matrix,cells=recovered
                    repaired_tables.append(ref)
                    for r,row in enumerate(cells):
                        for c,cell in enumerate(row):
                            refs=[source for target in cell for source in sources(target)]
                            cell_sources.append({'row':r,'column':c,'source':refs})
                            extra_sources.extend(refs)
                            used.update(target['self_ref'] for target in cell)
                else:
                    children.append(builder.node('unknown',{'reason':'表格已经定位，但未识别出可靠的单元格，已保留完整表格图像'},sources(item)))
        for caption in captions:
            children.append(plain(caption,'caption'))
        for target in inner:
            if target['self_ref'] not in used:
                children.append(plain(target,'figure_label') if is_figure else plain(target,'footnote'))
        name=next((caption.get('text','').split('|')[0].strip() for caption in captions), '图' if is_figure else '表格')
        content={'name':name,'asset':asset}
        if not is_figure:
            content.update(rows=matrix)
            if cell_sources:
                content['cell_sources']=cell_sources
                content['reconstruction']='按 OCR 表头、列位置和首列行起点恢复，单元格保留各自来源'
        return builder.node('figure' if is_figure else 'table',content,member_sources+extra_sources,children)
    title=' '.join(item.get('text','') for item in native['texts'] if item.get('label')=='title') or pdf.metadata.get('title') or path.name
    tree=builder.node('document',{'name':title},[file_source(root,path)])
    stack=[]
    extended_section=None
    major_heading=False
    heading_sizes=[sources(item)[0]['bbox'][3]-sources(item)[0]['bbox'][1] for item in native['texts'] if item.get('label')=='section_header' and item.get('text')!=title and repeated[item.get('text','')]<3 and item['self_ref'] not in caption_owners and item['self_ref'] not in figure_label_owners]
    body_heading_size=median(heading_sizes) if heading_sizes else 8
    def append(node):
        (stack[-1][1]['children'] if stack else tree['children']).append(node)
    def visit(ref):
        nonlocal extended_section,major_heading
        if ref in used or ref in caption_owners or ref in moved or ref in secondary_visuals or ref in figure_label_owners:
            return
        item=objects.get(ref)
        if item is None:
            return
        label=item.get('label')
        if label in ('picture','table'):
            extended=any(owner==ref and objects[key].get('text','').startswith('Extended Data') for key,owner in caption_owners.items())
            if extended and extended_section is None:
                extended_section=builder.node('section',{'text':'Extended Data'},sources(item))
                tree['children'].append(extended_section)
            if extended_section is not None:
                stack[:]=[(1,extended_section)]
            append(visual(item))
        elif label in ('list','ordered_list','unordered_list'):
            used.add(ref)
            children=[]
            for child in item.get('children',[]):
                target=objects.get(child['$ref'])
                if target and target['self_ref'] not in used:
                    children.append(plain(target))
            append(builder.node('list',{},sources(item),children))
        elif label=='section_header':
            text=item.get('text','')
            source=sources(item)[0]
            if repeated[text]>=3 and source.get('bbox',[0,999])[1]<page_map[source['page']]['height']*.08:
                furniture.append(plain(item,'header'))
            elif text.strip()==title.strip():
                tree['children'].append(plain(item,'heading'))
            else:
                used.add(ref)
                height=source['bbox'][3]-source['bbox'][1]
                if height>body_heading_size*1.1:
                    level=1
                    major_heading=True
                else:
                    level=2 if major_heading else 1
                while stack and stack[-1][0]>=level:
                    stack.pop()
                section=builder.node('section',{'text':text},sources(item))
                append(section)
                stack.append((level,section))
        elif label in ('page_header','page_footer'):
            furniture.append(plain(item))
        elif 'text' in item or label=='formula':
            append(plain(item))
        else:
            used.add(ref)
            for child in item.get('children',[]):
                visit(child['$ref'])
    for child in native['body']['children']:
        visit(child['$ref'])
    for child in native['furniture']['children']:
        visit(child['$ref'])
    if furniture:
        tree['children'].append(builder.node('section',{'text':'页眉与页脚'},[file_source(root,path)],furniture))
    missing=[]
    for name in ('texts','pictures','tables'):
        for item in native[name]:
            if item['self_ref'] not in used:
                missing.append(builder.node('unknown',{'reason':'原解析器的这个对象尚未匹配到树中的层级','text':item.get('text','')},sources(item)))
    if missing:
        tree['children'].append(builder.node('section',{'text':'待核对的对象'},[file_source(root,path)],missing))
    pdf.close()
    return {'tree':tree,'title':title,'pages':pages,
            'summary':{'pages':len(pages),'native_objects':len(native['texts'])+len(native['pictures'])+len(native['tables']),'unassigned_objects':len(missing)},
            'notes':['正文、图内标注和图注分别归类，公式保留字形与原页位置，空表格保留为待核对节点'],
            'adaptations':[{'rule':'repeated-header','reason':'重复出现在页顶的 Article 归入页眉，不作为正文章节'},
                           {'rule':'caption-continuation','reason':'相同版面高度的双栏图注续文合并，来源仍保留为两个位置','count':len(continuations)},
                           {'rule':'caption-owner','reason':'图注与图内标注归入对应图，标注不再重复出现在正文中'},
                           {'rule':'visual-region-label','reason':'图像与图注之间的坐标轴标题归入图内标注，避免被误当成正文章节'},
                           {'rule':'shared-caption-panels','reason':'左右面板位置对齐并共用一条编号图注时，合为一个图节点，两个原始面板仍分别保留来源','count':len(secondary_visuals)},
                           {'rule':'heading-size','reason':'用标题的实际版面高度补充层级，较小的方法小节放在所属大节下'},
                           {'rule':'mixed-pdf-ocr','reason':'论文含扫描的扩展表格，开启本地 OCR 后再解析单元格'},
                           {'rule':'ocr-table-alignment','reason':'解析器把扫描表格留成一组文字时，用表头、列位置和首列行起点交叉检查后恢复单元格','count':len(repaired_tables)}],
            'engine':{'name':'Docling','version':version('docling'),'profile':'local-ocr-heading-v1'}}



def parse_native_pdf(builder, root, path, output):
    """直接保存 PDF 的文本、原图和页面坐标，图内信息交给后续视觉清点"""
    pages = []
    title = path.stem
    tree = builder.node('document', {'text': title}, [file_source(root, path)])
    with fitz.open(path) as pdf:
        for number, page in enumerate(pdf, 1):
            preview = output / f'page-{number:04d}.png'
            page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(preview)
            pages.append({'number': number, 'width': page.rect.width, 'height': page.rect.height, 'preview': file_source(root, preview)['url']})
            refs = lambda box: [{**file_source(root, path), 'kind': 'pdf', 'page': number, 'bbox': list(box)}]
            branch = builder.node('section', {'text': str(number)}, refs(page.rect))
            tree['children'].append(branch)
            for index, block in enumerate(page.get_text('dict')['blocks']):
                box = block['bbox']
                if block['type'] == 0:
                    text = '\n'.join(''.join(span['text'] for span in line['spans']) for line in block['lines'])
                    if text.strip():
                        branch['children'].append(builder.node('paragraph', {'text': text}, refs(box)))
                elif block['type'] == 1:
                    image = output / f'image-{number:04d}-{index:04d}.png'
                    page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(box), alpha=False).save(image)
                    branch['children'].append(builder.node('image', {'asset': file_source(root, image)['url'], 'alt': ''}, refs(box)))
            if page.get_drawings():
                branch['children'].append(builder.node('image', {'asset': file_source(root, preview)['url'], 'alt': '', 'role':'visual_page'}, refs(page.rect)))
            if not branch['children']:
                branch['children'].append(builder.node('image', {'asset': file_source(root, preview)['url'], 'alt': ''}, refs(page.rect)))
    return {'tree': tree, 'title': title, 'pages': pages,
            'summary': {'pages': len(pages), 'native_objects': builder.count},
            'notes': ['保留 PDF 中的实际文本、图像和页面坐标，视觉内容继续按原图清点'],
            'adaptations': [], 'engine': {'name': 'PyMuPDF', 'version': fitz.VersionBind, 'profile': 'native-page-objects-v1'}}
