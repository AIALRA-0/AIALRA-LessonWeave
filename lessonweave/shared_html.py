"""把已经生成的文字完整导入共享文章，媒体说明也保留，不调用模型"""
import html
from .trilium import section_html,block_html,resolve_resource_html


def paragraph(value):
    if isinstance(value,dict):return ''.join(paragraph(part)for part in value.values())
    if isinstance(value,list):return ''.join(paragraph(part)for part in value)
    return '<p>'+html.escape(str(value or ''))+'</p>'


def media_guide(block):
    guide=block.get('guide',{})
    if not guide:return ''
    output=[]
    if block['kind']=='code':
        output.append('<h4>综合综述</h4>'+paragraph(guide.get('overview')))
        for run in block.get('runs',[]):output.append('<p>'+html.escape(str(run.get('inputs','')))+' → '+html.escape(str(run.get('outputs','')))+'</p>')
        for segment in guide.get('segments',[]):
            output.append('<h4>'+html.escape(segment.get('title_premise','').rstrip('，,；;？? ')+'，'+segment.get('title_question',''))+'</h4>'+paragraph(segment.get('overview')))
            for component in segment.get('components',[]):
                output.append(paragraph(' · '.join(str(component.get(k,''))for k in ['owner','name','kind','type','default','purpose'] if component.get(k) is not None)))
            for step in segment.get('core_logic',[]):
                output.extend([paragraph(step.get('explanation')),paragraph(step.get('example'))] if step.get('example') else [paragraph(step.get('explanation'))])
            takeaway=segment.get('takeaway',{});output.extend([paragraph(takeaway.get('conclusion')),paragraph(takeaway.get('relation_to_whole'))])
        summary=guide.get('summary',{});output.extend([paragraph(summary.get('answer')),paragraph(summary.get('collaboration'))])
        for line in guide.get('line_annotations',[]):output.append(paragraph(str(line.get('line_start',''))+' '+line.get('sentence','')))
    else:
        output.append('<h4>阅读指引</h4>'+paragraph(guide.get('reading_guide')))
        for component in guide.get('components',[]):output.append(paragraph(component.get('label','')+'，'+component.get('explanation','')))
        for step in guide.get('explanation',[]):
            if step.get('formula'):output.append('<div class="math-tex">'+html.escape(step['formula'])+'</div>')
            output.append(paragraph(step.get('text')))
        output.append(paragraph(guide.get('takeaway')))
    return ''.join(output)


def article_html(doc,resources):
    body=section_html(doc,resources).split('<h2>术语表</h2>',1)[0]
    placeholders={}
    for unit in doc.get('units',[]):
        for block in unit.get('explanation',[]):
            if not block.get('guide'):continue
            old=resolve_resource_html(block_html(block),resources)
            key='LWSHAREDMEDIA'+str(len(placeholders))+'END'
            visual=old
            if block['kind']=='table':
                visual='<table><thead><tr>'+''.join('<th>'+html.escape(str(value))+'</th>'for value in block.get('headers',[]))+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(value))+'</td>'for value in row)+'</tr>'for row in block.get('rows',[]))+'</tbody></table>'
            elif block['kind']=='formula':
                visual='<div class="math-tex" data-lw-formula="true">'+html.escape(block.get('text',''))+'</div>'
            elif block['kind']=='mermaid':
                visual='<pre>'+html.escape(block.get('text',''))+'</pre>'
            elif block.get('asset')and block['kind']!='image':
                visual='<a href="'+html.escape(resources.get(block['asset'].lstrip('/'),block['asset']))+'">'+html.escape(block.get('caption',block['asset']))+'</a>'
            visual+='<p>'+html.escape(block.get('caption',''))+'</p>'
            payload='<section class="lw-media" data-media-id="'+html.escape(block['id'])+'"><div data-shared-media="'+html.escape(block['id'])+'">'+visual+'</div>'+media_guide(block)+'</section>'
            if old in body:body=body.replace(old,key,1)
            else:body+=key
            placeholders[key]=payload
    for key,payload in placeholders.items():body=body.replace(key,payload)
    for notation in doc.get('local_notations',[]):
        body+='<aside>'+paragraph(notation.get('symbol'))+paragraph(notation.get('definition',notation.get('meaning','')))+'</aside>'
    return body
