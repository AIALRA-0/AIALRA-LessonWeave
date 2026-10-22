"""正式默认调度：材料直接进入问题规划，逐问写作合并附加内容，末尾只做脚本检查"""
import concurrent.futures as futures
import copy
import os
import json
import re
import time
from pathlib import Path

from .agents import Backend
from .storage import read, save
from .findings import record
from .metrics import span
from .progress import begin
import lean_contract as contract
import writing_contract as authoring
import book_sources
from .concurrency import options


def catalog(pack, root=None):
    rows = {}
    visuals={v['source_id']:v for v in pack.get('visual_assets',[])}
    for source in pack['sources']:
        if 'question_ids'in source and not source['question_ids']:
            continue
        if source.get('evidence_kind') == 'material_index':
            continue
        if source.get('raw_content',{}).get('reading_role')=='hidden_control':continue
        if source.get('asset'):
            from reader_repairs import file_role
            if file_role(source['asset'])=='system_metadata':continue
        if source.get('coverage_scope')=='file_role':
            key=source['id']+'.file'
            rows[key]={'id':key,'source_id':source['id'],'kind':'file','scope':'file_role',
                       'original':contract.dumps(source.get('file_metadata')or{'path':source.get('asset','')}),
                       'question_ids':source.get('question_ids',[])}
            continue
        for sentence in source.get('sentences', []):
            if sentence.get('evidence_kind') == 'material_index':
                continue
            rows[sentence['id']] = {'id':sentence['id'],'source_id':source['id'],'kind':'code' if source.get('verbatim_code') or sentence.get('verbatim_code') or source.get('type')=='code' else 'text',
                'original':sentence['original'],'question_ids':sentence.get('question_ids',source.get('question_ids',[]))}
            if source.get('raw_content',{}).get('field'):rows[sentence['id']]['metadata_field']=source['raw_content']['field']
            if source.get('dependency_definition'):rows[sentence['id']]['dependency_definition']=True
            if source.get('source',{}).get('kind')=='code':
                rows[sentence['id']]['source_path']=source['source']['path']
                for field in ['start_line','end_line']:
                    if field in sentence:rows[sentence['id']][field]=sentence[field]
        if source.get('asset') and book_sources._is_image(source['asset']):
            key=source['id']+'.image'
            rows[key]={'id':key,'source_id':source['id'],'kind':'image','asset':source['asset'],'question_ids':source.get('question_ids',[])}
            preview=visuals.get(source['id'],{}).get('model_path') or source.get('image_preview',{}).get('path')
            if preview:rows[key]['model_asset']=preview
        elif source.get('asset') and not any(s.get('evidence_kind')!='material_index' for s in source.get('sentences',[])) and not source.get('file_fragments'):
            import mimetypes
            asset=source['asset'];details={'path':asset,'format':Path(asset).suffix,'role':'original_attachment'}
            if root is not None:
                path=(Path(root)/asset.lstrip('/')).resolve()
                if path.is_relative_to(Path(root).resolve()) and path.is_file():details.update(bytes=path.stat().st_size,mime=mimetypes.guess_type(path)[0]or'application/octet-stream')
            rows[source['id']+'.file']={'id':source['id']+'.file','source_id':source['id'],'kind':'file','scope':'file_role',
                                      'original':contract.dumps(details),'question_ids':source.get('question_ids',[])}
        for file_index,fragment in enumerate(source.get('file_fragments',[]),1):
            if fragment.get('role') not in book_sources.TEXT_ROLES or fragment.get('read_policy')=='original_attachment':
                from reader_repairs import file_role
                fragment_path=fragment.get('source',{}).get('path','') if isinstance(fragment.get('source'),dict) else fragment.get('source','')
                if file_role(fragment_path)=='system_metadata':continue
                if source.get('asset') and book_sources._is_image(source['asset']):continue
                key=source['id']+'.file'+str(file_index)
                details={k:fragment[k] for k in ['source','file_bytes','mime','role','read_policy'] if k in fragment}
                rows[key]={'id':key,'source_id':source['id'],'kind':'file','original':contract.dumps(details),
                           'scope':'file_role','question_ids':source.get('question_ids',[])}
                continue
            storage=fragment.get('text_storage')
            if storage and fragment.get('read_policy')=='indexed_complete':
                stored=read(storage['path'])
                for i,chunk in enumerate(stored.get('chunks',[]),1):
                    key=source['id']+'.chunk'+str(i)
                    rows[key]={'id':key,'source_id':source['id'],'kind':'code','original':chunk['text'],
                        'question_ids':source.get('question_ids',[]),'start_line':chunk['start_line'],'end_line':chunk['end_line']}
    return list(rows.values())


def _is_preface_context(context):
    """识别第 0 章的导读节，避免把导读答案当作首正文的前置结论。"""
    chapter_id = str(context.get('chapter_id') or '')
    match = re.search(r'(?:^|[-_])(?:ch|chapter)[-_]?(\d+)(?:[-_]|$)', chapter_id, re.I)
    if match:
        return int(match.group(1)) == 0
    section_number = str(context.get('section_number') or '')
    match = re.match(r'^\s*(\d+)(?:\.|$)', section_number)
    if match:
        return int(match.group(1)) == 0
    section_id = str(context.get('section_id') or '')
    return bool(re.search(r'(?:^|[-_])ch0+(?:[-_]|$)', section_id, re.I))


def _project_background(chapters, questions):
    tree = chapters.get('tree', {}) if isinstance(chapters, dict) else {}
    root_questions = []
    for question_id in tree.get('question_ids', []):
        question = questions.get(question_id)
        if not isinstance(question, dict):
            continue
        text = str(question.get('premise') or '') + str(question.get('question') or '')
        root_questions.append({'question_id': question_id, 'text': text})
    result = {'root_questions': root_questions}
    if isinstance(tree.get('title'), str) and tree['title'].strip():
        result['title'] = tree['title']
    return result


def build_bridge_boundaries(section_values, chapters, questions):
    """首正文从全书背景起笔，后续正文只承接前一正文节的实际结果。"""
    boundaries = []
    previous_preface = None
    previous_body = None
    first_body = True
    background = _project_background(chapters, questions)
    for context, values in section_values:
        preface = _is_preface_context(context)
        previous = previous_preface if preface else previous_body
        row = {
            'section_id': context['section_id'],
            'prior_actual_results': previous,
            'current': {
                'title': context.get('title', ''),
                'questions': context.get('core_questions', []),
                'results': [value['result'] for value in values if isinstance(value, dict) and 'result' in value],
            },
        }
        row['is_preface'] = preface
        if not preface and first_body:
            row['is_first_main_body'] = True
            row['project_background'] = copy.deepcopy(background)
            first_body = False
        boundaries.append(row)
        current = {
            'section_id': context['section_id'],
            'title': context.get('title', ''),
            'answers': [value['result']['answer'] for value in values
                        if isinstance(value, dict) and isinstance(value.get('result'), dict)
                        and isinstance(value['result'].get('answer'), str)],
        }
        if preface:
            previous_preface = current
        else:
            previous_body = current
    return boundaries


def generate_first_opening_candidate(backend, boundaries):
    """只为首个正文节生成可审阅的开场候选，不写入正式章节文件。"""
    boundary = next((row for row in boundaries if row.get('is_first_main_body')), None)
    if boundary is None:
        return {'status': 'no_first_main_body', 'candidate': None, 'records': []}
    import bridge_batches
    generated = bridge_batches.generate(backend, [copy.deepcopy(boundary)])
    bridge = next((row for row in generated.get('bridges', [])
                   if row.get('section_id') == boundary['section_id']), None)
    candidate = None if bridge is None else {
        'section_id': boundary['section_id'],
        'carryover': bridge.get('carryover', ''),
        'premise': bridge.get('premise', ''),
        'question': bridge.get('question', ''),
    }
    return {'status': 'proposed_only' if candidate else 'recorded_error',
            'candidate': candidate, 'records': copy.deepcopy(generated.get('records', []))}


def quota(index, count):
    return {'single_choice':4//count+(index<4%count),'short_answer':int(index==count-1)}


def reader_unit(value):
    qid=value['question_id']
    blocks=[]
    for group in value['explanation']:
        blocks.append({'id':group['id']+'-heading','kind':'heading',
            'text':group['title_premise'].rstrip('，,；;？? ')+'，'+group['title_question']})
        for role in (['claim','body','supplement'] if 'body' in group else ['claim','reasoning','grounding','supplement']):
            if group.get(role):blocks.append(authoring.paragraph(group['id']+'-'+role,group[role]))
        for resource in group['resources']:
            item=copy.deepcopy(resource)
            if 'guide' not in item:
                item['guide']={k:item.pop(k) for k in ['reading_guide','components','explanation','takeaway'] if k in item}
            blocks.append(item)
    return {'question_id':qid,'problem':authoring.paragraph(qid+'-problem',value['premise']), 'explanation':blocks,
        'synthesis':authoring.paragraph(qid+'-synthesis',authoring.compose(value['result'][key] for key in ['answer','generalization'])),
        'summary':authoring.paragraph(qid+'-summary',value['result']['answer']),'bindings':[]}


def coverage(units, resources):
    by_id={r['id']:r for r in resources}
    links,results={},[]
    for value in units:
        expected=[r['id'] for r in resources if value['question_id'] in r.get('question_ids',[])]
        if not expected:expected=list({r for group in value['explanation'] for r in group['resource_ids']})
        result=contract.mappings(value,expected)
        result['unknown']=[rid for rid in result['unknown'] if rid not in by_id]
        result['errors']=[e for e in result['errors'] if not e.startswith('材料引用不存在')]
        if result['unknown']:result['errors'].append('材料引用不存在：'+', '.join(result['unknown']))
        results.append(dict(result,question_id=value['question_id']))
        for group in value['explanation']:
            refs={}
            for rid in group['resource_ids']:
                if rid not in by_id:continue
                row=by_id[rid]
                ref=refs.setdefault(row['source_id'],{'source_id':row['source_id'],'sentence_ids':[],'region_ids':[]})
                if row['kind'] in {'text','code'}:ref['sentence_ids'].append(rid)
            # 讲解组保存组级对应，原始生成结果没有逐自然段证据时，不伪造更细的来源精度
            for block_id in [group['id']+'-'+role for role in (['claim','body','supplement'] if 'body' in group else ['claim','reasoning','grounding','supplement']) if group.get(role)]:
                links[block_id]=list(copy.deepcopy(refs).values())
            for media in group['resources']:
                own={}
                for rid in media.get('source_refs',group['resource_ids']):
                    if rid in by_id:
                        row=by_id[rid];ref=own.setdefault(row['source_id'],{'source_id':row['source_id'],'sentence_ids':[],'region_ids':[]})
                        if row['kind']=='text':ref['sentence_ids'].append(rid)
                links[media['id']]=list(own.values())
    expected=set(by_id)
    used={rid for unit in units for group in unit['explanation'] for rid in group['resource_ids']}
    return {'passed':all(not r['errors'] for r in results),'items':[], 'block_sources':links,'questions':results,
        'covered':len(used&expected),'expected':len(expected),'percentage':100*len(used&expected)/len(expected) if expected else 100,
        'semantic_review':'not_run','source_precision':'explanation_group'},links


def translate(root, backend, resources, packs):
    translation_started=time.time()
    existing=read(root/'05_writing/translations.json',{'translations':[]})
    cache={row['resource_id']:row for row in existing['translations']}
    originals=read(root/'05_writing/translation-originals.json',{})
    version=sorted({str(pack.get('material_run',''))+'|'+str(pack.get('material_path','')) for pack in packs})
    same_version=read(root/'05_writing/translation-version.json',version)==version
    unique={r['id']:r for r in resources if r['kind']=='text'}
    from reader_repairs import is_chinese
    pending=[r for rid,r in unique.items() if not same_version or rid not in cache or originals.get(rid)!=r['original']
             or cache[rid].get('chinese' if is_chinese(r['original']) else 'english')!=r['original']
             or not cache[rid].get('chinese')]
    save(root/'runtime/translation-live.json',{'total':len(unique),'completed':len(unique)-len(pending),'reused':len(unique)-len(pending)})
    if pending and backend is not None:
        import translation_batches
        value=translation_batches.generate(backend,pending)
        save(root/'05_writing/work/translation-batches.json',{k:v for k,v in value.items() if k!='translations'})
        for error in value['errors']:record(root,'c_translation',error)
        cache.update({row['resource_id']:row for row in value['translations']})
    save(root/'05_writing/translations.json',{'translations':[cache[rid] for rid in unique if rid in cache]})
    save(root/'05_writing/translation-originals.json',{rid:r['original'] for rid,r in unique.items()})
    save(root/'05_writing/translation-version.json',version)
    for pack in packs:
        for source in pack['sources']:
            for sentence in source.get('sentences',[]):
                if sentence['id'] in cache:
                    sentence.update(translation=cache[sentence['id']]['chinese'],english=cache[sentence['id']]['english'])
    save(root/'runtime/translation-stage.json',{'started':translation_started,'ended':time.time(),'seconds':time.time()-translation_started})
    save(root/'runtime/translation-live.json',{'total':len(unique),'completed':sum(rid in cache for rid in unique),'reused':len(unique)-len(pending)})
    return cache


def assemble(root, context, folder, pack, units, appendix, bridge, resources=None):
    from . import legacy as flow
    appendix=copy.deepcopy(appendix)
    for item in appendix['pitfalls']:
        item['question']=item['question'].rstrip('？?')+'？'
    rendered=[reader_unit(unit) for unit in units]
    terms,conflicts=contract.merge_terms(appendix['terms'])
    extras={**appendix,'terms':[authoring.reader_term(t) for t in terms],
        'summary':[{'question_id':u['question_id'],'answer':authoring.paragraph(u['question_id']+'-summary',u['result']['answer'])} for u in units],
        'opening':authoring.paragraph(context['section_id']+'-opening',bridge['carryover']),
        'opening_forward':authoring.paragraph(context['section_id']+'-forward',bridge['premise'].rstrip('，,；;：:？? ')+'，'+bridge['question'].lstrip('，,；; '))}
    context=copy.deepcopy(context);context['opening_title']=''
    for spec in context['units']:
        generated=next((u for u in units if u['question_id']==spec['question_id']),{})
        if generated.get('reader_title'):
            spec['title']=generated['reader_title']
            for core in context['core_questions']:
                if core['question_id']==spec['question_id']:core['text']=generated['reader_title']
    doc,_,catalog_doc=flow.generation.assemble_section(context,pack,{'points':[]},rendered,extras)
    specs={u['question_id']:u for u in context['units']}
    for unit in doc['units']:
        spec=specs[unit['question_id']]
        index=0
        for block in unit['explanation']:
            if block['kind']=='heading':
                index+=1;block['text']=spec['number'].rstrip('.')+'.'+str(index+1)+'. '+block['text']
        unit['problem_heading']=spec['number'].rstrip('.')+'.1. 核心问题'
        unit['summary_heading']=spec['number'].rstrip('.')+'.'+str(index+2)+'. 本段总结'
    doc['writing_contract_version']=authoring.VERSION
    doc['validation_scope']='format_and_references'
    doc['local_notations']=copy.deepcopy(appendix['local_notations'])
    save(folder/'source-pack.json',pack)
    report,_=coverage(units,resources if resources is not None else catalog(pack))
    save(folder/'coverage.json',report)
    doc['grounding']={k+'_path':(folder/v).relative_to(root).as_posix() for k,v in [('source_pack','source-pack.json'),('coverage','coverage.json')]}
    save(folder/'terminology.catalog.json',catalog_doc)
    doc['catalog_path']=(folder/'terminology.catalog.json').relative_to(root).as_posix()
    issues=[error for item in report['questions'] for error in item['errors']]
    missing=set(specs)-{u['question_id'] for u in units}
    if missing:issues.append('本节仍缺少已分配问题的生成结果：'+', '.join(sorted(missing)))
    from jsonschema import Draft202012Validator
    issues.extend(error.json_path+': '+error.message for error in Draft202012Validator(authoring.schema('demo')).iter_errors(doc))
    if not 3<=sum(q['kind']=='single_choice' for q in doc['quiz'])<=5 or sum(q['kind']=='short_answer' for q in doc['quiz'])!=1:
        issues.append('每节需要三至五道单选与恰好一道简答')
    for row in doc['quiz']:
        if row['kind']=='single_choice' and not 0<=row['answer']<len(row['options']):issues.append(row['id']+' 的答案选项不存在')
    known_questions={u['question_id'] for u in units}
    if any(set(q['question_ids'])-known_questions for q in doc['quiz']):issues.append('练习引用了本节以外的问题')
    doc['validation']={'passed':not issues,'errors':issues}
    save(folder/'checks.json',{'scope':'format_and_references','semantic_review':'not_run','errors':issues,'term_conflicts':conflicts})
    save(folder/'bridge.json',bridge);save(folder/'glossary.json',{'terms':terms,'local_notations':appendix['local_notations']})
    save(folder/'extras.json',extras);save(folder/'candidate.json',doc)
    return doc


def write_sections(root,backend,reuse_only=False,inspect=False):
    from . import pipeline,legacy as flow
    contexts,plan,chapters,questions=flow.runtime.contexts(root)
    prepare_started=time.perf_counter()
    source_session=book_sources.prepare_session(root)
    prepared=[]
    for context in contexts:
        folder=root/'05_writing/work/sections'/context['section_id'];folder.mkdir(parents=True,exist_ok=True)
        save(folder/'context.json',context)
        pack_path=folder/'source-pack.json'
        pack=read(pack_path) if pack_path.exists() else book_sources.prepare_sources(root,context['section_id'],folder,**({'session':source_session}if source_session is not None else{}))
        resource_path=folder/'resources.json'
        resources=read(resource_path) if reuse_only and resource_path.exists() else catalog(pack,root)
        if not reuse_only or not resource_path.exists():save(resource_path,resources)
        prepared.append((context,folder,pack,resources))
    save(root/'runtime/writing-preparation.json',{'seconds':time.perf_counter()-prepare_started,'sections':len(prepared),'model_calls':0})
    jobs=[(row,index) for row in prepared for index in range(len(row[0]['units']))]
    begin(root,'一次规划并写出正文、媒体与阅读组件',[row[0]['section_id']+'-c-'+row[0]['units'][index]['question_id'] for row,index in jobs]+['c_translation'])
    def write(task):
        (context,folder,pack,resources),index=task
        spec=context['units'][index];qid=spec['question_id'];path=folder/('unit-'+qid+'.json')
        if path.exists():return read(path)
        if reuse_only:raise ValueError('重新装配时缺少已有正文：'+spec['question_id'])
        selected=[r for r in resources if qid in r.get('question_ids',[])]
        images=[r.get('model_asset',r['asset']) for r in selected if r['kind']=='image']
        prompt=contract.writer_prompt(context,spec,[{k:v for k,v in r.items() if k!='question_ids'} for r in selected],quota(index,len(context['units'])))
        import glossary_reuse
        prompt,wire_schema,shared=glossary_reuse.prepare(prompt,contract.writer_schema(quota(index,len(context['units']))),glossary_reuse.load())
        import writing_input
        prompt,read_tools,input_mode=writing_input.prepare(root,folder,qid,prompt,getattr(backend,'model','gpt-6.1-sol'))
        save(folder/('input-mode-'+qid+'.json'),input_mode)
        call_options={'read_only_tools':True}if read_tools else{}
        value=contract.reader_quiz(backend._call_once(context['section_id']+'-c-'+qid,prompt,wire_schema,images,**call_options),qid)
        value,hits=glossary_reuse.expand(value,shared)
        import repair_batches
        value,term_changes,term_errors=repair_batches.format_document_terms(value,include_legacy=True)
        value,shared_format=flow.author_format(value)
        save(folder/('term-format-'+qid+'.json'),{
            'scope':'按术语例外位整理本次新生成的名称，并同步展示字段，不改定义内容',
            'changes':term_changes,'errors':term_errors})
        if term_errors:
            record(root,qid,['术语名称整理失败，已保留生成内容并交独立检查：'+error for error in term_errors])
        save(folder/('glossary-reuse-'+qid+'.json'),{'hits':hits,'available':len(shared),'special_senses':'完整新词条保留在本问正文产物中'})
        record(root,qid,contract.findings(value,'c-unit'));save(path,value);return value
    all_resources=list({r['id']:r for row in prepared for r in row[3]}.values())
    writing_started=time.time()
    with futures.ThreadPoolExecutor(max_workers=options()['writing_calls']+1) as pool:
        translation=pool.submit(translate,root,None if reuse_only else Backend(root,role='lean_translation'),all_resources,[row[2] for row in prepared])
        pending=[pool.submit(write,job) for job in sorted(jobs,key=lambda task:sum(len(r.get('original','')) for r in task[0][3] if task[0][0]['units'][task[1]]['question_id'] in r.get('question_ids',[])),reverse=True)]
        for result in pending:
            try:result.result()
            except Exception as error:
                if not inspect:raise
                record(root,'c_generation',str(error))
        save(root/'runtime/writing-requests.json',{'started':writing_started,'ended':time.time(),'seconds':time.time()-writing_started,'scheduled_units':len(jobs)})
        try:translation.result()
        except Exception as error:
            if not inspect:raise
            record(root,'c_translation',str(error))
    section_values=[]
    for context,folder,pack,resources in prepared:
        values=[v for unit in context['units'] if (v:=read(folder/('unit-'+unit['question_id']+'.json'))) and 'result' in v]
        section_values.append((context,values))
    boundary=build_bridge_boundaries(section_values,chapters,questions)
    pipeline.update_state(root,stage='05_writing/bridges')
    begin(root,'根据实际答案集中生成两段承接',[])
    bridge_path=root/'05_writing/work/bridges.json'
    save(root/'05_writing/work/bridge-boundaries.json',boundary)
    if bridge_path.exists():bridges=read(bridge_path)
    else:
        import bridge_batches
        generated=bridge_batches.generate(Backend(root,role='lean_bridge'),boundary)
        bridges={'bridges':generated['bridges']}
        save(root/'05_writing/work/bridge-batches.json',{'records':generated['records']})
    save(bridge_path,bridges);by_sid={b['section_id']:b for b in bridges['bridges']}
    for _,folder,pack,_ in prepared:save(folder/'source-pack.json',pack)
    if not inspect and not reuse_only:
        from .checks import namespace_blocks
        namespace_blocks(root)
    if inspect:
        from .checks import run as independent_check
        pipeline.update_state(root,stage='05_writing/independent-check')
        independent_check(root,Backend(root,role='lean_repair'))
        bridges=read(bridge_path);by_sid={b['section_id']:b for b in bridges['bridges']}
        cache={row['resource_id']:row for row in read(root/'05_writing/translations.json',{'translations':[]})['translations']}
        for _,_,pack,_ in prepared:
            for source in pack['sources']:
                for sentence in source.get('sentences',[]):
                    if sentence['id'] in cache:sentence.update(translation=cache[sentence['id']]['chinese'],english=cache[sentence['id']]['english'])
    pipeline.update_state(root,stage='05_writing/assembly')
    assembly_started=time.perf_counter()
    sections={}
    for context,folder,pack,resources in prepared:
        values=[value for u in context['units'] if (value:=read(folder/('unit-'+u['question_id']+'.json')))]
        appendix={key:[item for u in values for item in u['appendix'][key]] for key in ['pitfalls','quiz','terms','local_notations']}
        sections[context['section_id']]=assemble(root,context,folder,pack,values,appendix,by_sid.get(context['section_id'],{'section_id':context['section_id'],'carryover':'','premise':'','question':''}),resources)
    save(root/'runtime/section-assembly.json',{'seconds':time.perf_counter()-assembly_started,'sections':len(sections),'model_calls':0})
    answers={row['question_id']:row['answer']['text'] for doc in sections.values() for row in doc['summary']}
    for qid in reversed(list(questions)):
        if qid not in answers:
            answers[qid]='；'.join(answers[c['id']] for c in questions[qid].get('children',[]) if c['id'] in answers)
    reader_started=time.perf_counter()
    book=flow.make_preview(root,sections,chapters,questions,answers,'',review=False)
    save(root/'05_writing/work/sections.json',sections)
    # 格式结果与语义审查分开保存，完整内容始终可以进入阅读
    errors=[e for doc in sections.values() for e in doc['validation']['errors']]
    findings=read(root/'05_writing/checks/independent-after.json',{}).get('findings',[]) if inspect else []
    book['validation']={'passed':not errors and not findings,'errors':errors+[f['document']+f['path']+': '+f['message'] for f in findings]}
    save(root/'05_writing/book.json',book)
    if (root/'05_writing/preview-book.json').exists():save(root/'05_writing/preview-book.json',book)
    from reader_repairs import build as prepare_reader_repairs
    prepare_reader_repairs(root)
    save(root/'runtime/reader-assembly.json',{'seconds':time.perf_counter()-reader_started,'model_calls':0})
    if not reuse_only:
        import glossary_reuse
        collected=[term for context,folder,_,_ in prepared for unit in context['units']
            for term in read(folder/('unit-'+unit['question_id']+'.json'),{}).get('appendix',{}).get('terms',[])]
        save(root/'runtime/glossary-library-increment.json',glossary_reuse.remember(collected))
    return sections,not errors,errors


def run(root,maximum=1):
    from . import pipeline,legacy as flow
    root=Path(root).resolve()
    if root.name=='05-test' or '05-test' in root.parts:
        raise ValueError('05-test 由用户保留，本入口不执行该目录')
    pipeline.scaffold(root)
    state=read(root/'runtime/state.json',{})
    if state.get('status')=='completed':return state
    started=time.monotonic()
    pipeline.update_state(root,status='running',round=0,maximum=1,workflow=contract.VERSION,stage='00_source',issues=[])
    pipeline.prepare(root)
    pipeline.update_state(root,stage='02_questions–03_chapters')
    flow.tree_stages(root,Backend(root,role='lean_planning'))
    pipeline.update_state(root,stage='05_writing/c')
    _,passed,issues=write_sections(root,Backend(root,role='lean_writing'),inspect=True)
    checked=read(root/'05_writing/checks/batch-repair.json')
    generation_seconds=time.monotonic()-started-checked['elapsed_seconds']
    passed=passed and checked['passed']
    final_report=read(root/'05_writing/checks/independent-after.json')
    issues += [f['document']+f['path']+': '+f['message'] for f in final_report['findings']]
    from prepare_source_locations import prepare_locations
    pipeline.update_state(root,stage='05_writing/locations')
    with span(root,'locations','phase'):
        prepare_locations(root,list((root/'05_writing/work/sections').glob('*/source-pack.json')))
    pipeline.update_state(root,stage='05_writing/package')
    from .package import export_package
    with span(root,'package','phase'):
        export_package(root)
    return pipeline.update_state(root,status='completed',workflow=contract.VERSION,quality_status='format_checked' if passed else 'findings_recorded',
        semantic_review='not_run',issues=issues,independent_check=checked,generation_seconds=round(generation_seconds,3),
        check_repair_ratio=round(checked['elapsed_seconds']/generation_seconds,4) if generation_seconds else 0,
        usage=pipeline.usage(root),elapsed_seconds=round(time.monotonic()-started,3))
