"""完成生成后集中检查一次，有问题时执行一次批量修复，再保存实际检查状态"""
import copy
import concurrent.futures as futures
import json
import re
import time
from pathlib import Path
from jsonschema import Draft202012Validator
from . import legacy as flow
import independent_checks as rules
import lean_contract as contract
from .storage import read,save
from .metrics import span


def scan(root):
    from . import lean,legacy as flow
    started=time.monotonic();findings=[];checks=[]
    def add(document,errors,rule):
        checks.append({'document':document,'rule':rule,'passed':not errors})
        findings.extend(dict(error,document=document) if isinstance(error,dict) else
                        dict(rules.issue(rule,'/',str(error)),document=document) for error in errors)
    from tree_model import check_tree
    from build_questions import check_questions
    from build_chapters import check_chapters
    for name,check in [('01_tree/tree.json',lambda v:check_tree(v,read(root/'01_tree/tree.schema.json'),root)),
                       ('02_questions/questions.json',lambda v:check_questions(v,root)),
                       ('03_chapters/chapters.json',lambda v:check_chapters(v,root))]:
        try:add(name,check(read(root/name)),name.split('/')[0])
        except (OSError,KeyError,TypeError,ValueError) as error:add(name,[str(error)],'stage_complete')
    contexts,_,_,_=flow.runtime.contexts(root);all_resources={};expected_units=0;math_documents={}
    for context in contexts:
        folder=root/'05_writing/work/sections'/context['section_id'];resources=read(folder/'resources.json',[])
        all_resources.update({r['id']:r for r in resources})
        for i,spec in enumerate(context['units']):
            name=(folder/('unit-'+spec['question_id']+'.json')).relative_to(root).as_posix();value=read(root/name)
            errors=rules.unit_findings(value,resources,lean.quota(i,len(context['units'])),spec['question_id'],root) if value else [rules.issue('unit_complete','/','分配的问题缺少生成结果')]
            add(name,errors,'unit_contract');expected_units+=1
            if value:math_documents[name]=value
    import math_syntax
    math_findings=math_syntax.check_documents(math_documents)
    findings.extend(math_findings)
    checks.append({'document':'05_writing','rule':'math_syntax','passed':not math_findings})
    translations='05_writing/translations.json'
    add(translations,rules.translation_findings(read(root/translations,{}),list(all_resources.values())),'translation_complete')
    bridges='05_writing/work/bridges.json';value=read(root/bridges,{'bridges':[]})
    errors=[rules.issue('schema',rules.pointer(e.path),e.message) for e in Draft202012Validator(contract.schema('c-bridges')).iter_errors(value)]
    expected={c['section_id'] for c in contexts};actual=[b['section_id'] for b in value['bridges']]
    if expected!=set(actual) or len(actual)!=len(set(actual)):errors.append(rules.issue('bridge_complete','/bridges','每节需要且只需要一份承接'))
    for i,b in enumerate(value['bridges']):
        for key in ['carryover','premise','question']:
            for match in rules.LINT.finditer(b.get(key,'')):
                errors.append(rules.issue('lint',f'/bridges/{i}/{key}','需要调整作者句式或内部编号：'+match.group()))
    add(bridges,errors,'bridge_contract')
    from positive_writing import WRITING_RULES_VERSION
    return {'profile':'lightweight-independent-check-v1','writing_rules_version':WRITING_RULES_VERSION,'passed':not findings,'semantic_quality_review':'not_run',
            'checks':checks,'findings':findings,'expected_units':expected_units,'expected_translations':sum(r['kind']=='text' for r in all_resources.values()),
            'elapsed_seconds':round(time.monotonic()-started,3)}


def get(value,path):
    if path=='/':return value
    for part in path.lstrip('/').split('/'):
        key=part.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
    return value


def put(value,path,new):
    if path=='/':return new
    parts=path.lstrip('/').split('/');parent=value
    for part in parts[:-1]:
        key=part.replace('~1','/').replace('~0','~');parent=parent[int(key)] if isinstance(parent,list) else parent[key]
    key=parts[-1].replace('~1','/').replace('~0','~')
    if isinstance(parent,list):parent[int(key)]=new
    else:parent[key]=new
    return value


def targets(rows):
    paths={f['target'] for f in rows}
    if any(f['rule'] in {'material_coverage','plan_coverage','source_exists'} for f in rows):paths.update(['/plan/items','/explanation'])
    return sorted(p for p in paths if not any(q!=p and (q=='/' or p.startswith(q+'/')) for q in paths))


def file_role_context(root,resources):
    """按材料树已声明的读取范围传递资源文件，完整原文件继续留在本地"""
    import book_sources
    tree=read(root/'01_tree/tree.json',{}).get('tree',{})
    nodes={n['id']:n for n in flow.walk(tree) if n.get('id')}
    result=[];groups={}
    for row in resources:
        node=nodes.get(row['source_id'],{});content=node.get('content',{})
        name=content.get('local_path') or content.get('path','')
        if content.get('role') not in {'resource','attachment'} or book_sources._is_image(name,content.get('mime','')):
            result.append(row);continue
        sid=row['source_id']
        if sid not in groups:
            groups[sid]={'source_id':sid,'resource_ids':[],'kind':'file','scope':'file_role',
                'file':{k:content[k] for k in ['name','path','local_path','bytes','mime','role','detail_state'] if k in content}}
            result.append(groups[sid])
        groups[sid]['resource_ids'].append(row['id'])
    return result


def namespace_blocks(root):
    """各问可以使用局部 ID，装配前统一加上问题前缀，避免来源标识串到其他问题"""
    changed=[]
    for path in (root/'05_writing/work/sections').glob('*/unit-*.json'):
        value=read(path);qid=value.get('question_id')
        if not qid:continue
        renames={};source_changes=[];syntax_changes=[];resources=read(path.parent/'resources.json',[])
        import plan_sync
        syntax_changes+=plan_sync.align(value,resources)
        corrected=[]
        for resource in resources:
            if resource.get('kind')=='text' and re.search(r'\.L\d+-L\d+$',resource['id']):
                resource['kind']='code';corrected.append(resource['id'])
        if corrected:
            save(path.parent/'resources.json',resources);syntax_changes.append({'resources':corrected,'action':'源码行片段保持源码，不作为自然语言送去翻译'})
        task=re.sub(r'[^\w.-]','_',path.parent.name+'-c-'+qid)
        raw_media={}
        for response in sorted((root/'runtime/calls'/task).glob('*/response.json'),key=lambda p:p.stat().st_mtime):
            raw=read(response,{})
            if (raw.get('question_id')==qid or 'p' in raw):
                raw_media.update({m['id']:m for g in raw.get('explanation',[]) for m in g.get('resources',[])})
        known={r['id'] for r in resources};by_source={}
        for resource in resources:by_source.setdefault(resource['source_id'],[]).append(resource['id'])
        def resolve(ref):
            if ref in known:return [ref]
            if ref in by_source:return by_source[ref]
            match=re.fullmatch(r'(.+)\.L(\d+)-L(\d+)',ref)
            if match:
                source,start,end=match[1],int(match[2]),int(match[3]);pieces=[]
                for rid in known:
                    part=re.fullmatch(re.escape(source)+r'\.L(\d+)-L(\d+)',rid)
                    if part and start<=int(part[1])<=int(part[2])<=end:pieces.append((int(part[1]),int(part[2]),rid))
                pieces.sort();next_line=start
                for first,last,_ in pieces:
                    if first>next_line:return [ref]
                    next_line=max(next_line,last+1)
                if pieces and next_line==end+1:return [p[2] for p in pieces]
            return [ref]
        for group in value.get('explanation',[]):
            title=group.get('title_question')
            if isinstance(title,str) and title.strip() and not title.endswith('？'):
                group['title_question']=title.rstrip('？? ')+'？';syntax_changes.append({'group':group.get('id'),'action':'统一问题标题的问号'})
            for media in group.get('resources',[]):
                local=media['id'].removeprefix(qid+'-');raw=raw_media.get(local) or raw_media.get(media['id'])
                if media.get('kind')=='mermaid' and raw and raw.get('kind')=='mermaid':
                    original=raw['text'];flattened=re.sub(r'[\r\n\u2028\u2029]+',' ',original).replace('。','；').rstrip('；')
                    if media['text']!=original and media['text']==flattened:
                        media['text']=original;syntax_changes.append({'media':media['id'],'action':'保留原始 Mermaid 语法换行'})
                previous=media.get('source_refs',[])
                resolved=list(dict.fromkeys(rid for ref in previous for rid in resolve(ref)))
                if resolved!=previous:media['source_refs']=resolved;source_changes.append({'media':media.get('id'),'from':previous,'to':resolved})
        def collect(node):
            if isinstance(node,list):
                for child in node:collect(child)
            elif isinstance(node,dict):
                old=node.get('id')
                if old and not old.startswith(qid+'-'):
                    node['id']=qid+'-'+old;renames[old]=node['id']
                for child in node.values():collect(child)
        collect(value)
        if not renames and not source_changes and not syntax_changes:continue
        references={'plan_ids','definition_block_id','scope_block_ids','component_ids'}
        def rewrite(node,key=None):
            if isinstance(node,str):
                if key in references:
                    if node in renames:return renames[node]
                    for old,new in renames.items():
                        if any(node==old+'-'+role for role in ('claim','body','reasoning','grounding','supplement','heading')):
                            return new+node[len(old):]
                    return node
                for old,new in renames.items():node=node.replace('{{media:'+old+'}}','{{media:'+new+'}}')
                return node
            if isinstance(node,list):return [rewrite(v,key) for v in node]
            if isinstance(node,dict):return {k:rewrite(v,k) for k,v in node.items()}
            return node
        save(path,rewrite(value));changed.append({'document':path.relative_to(root).as_posix(),'action':'为生成块添加所属问题前缀，并保留材料引用与媒体语法','renames':renames,'source_refs':source_changes,'syntax':syntax_changes})
    return changed


def repair(root,report,backend):
    """集中处理全部剩余问题，按容量并行请求，只返回受影响字段的改动"""
    documents={};conversions=[]
    for row in report['findings']:
        name=row['document'];value=documents.setdefault(name,read(root/name))
        if value is None:continue
        if row['rule']=='math_syntax' and 'script_value'in row and get(value,row['path'])==row.get('original_value'):
            put(value,row['path'],row['script_value'])
            conversions.append({'document':name,'path':row['path'],'action':'采用 KaTeX 已确认有效的确定性排版修正'})
        elif row['rule']=='question_owner':
            put(value,row['path'],Path(name).stem.removeprefix('unit-'))
            conversions.append({'document':name,'path':row['path'],'action':'按任务文件恢复所属问题编号'})
        elif row['rule']=='question_title':
            previous=get(value,row['path']);put(value,row['path'],previous.rstrip('？?')+'？')
            conversions.append({'document':name,'path':row['path'],'action':'补齐标题问号'})
    for name,value in documents.items():
        if value is not None:save(root/name,value)
    converted={(row['document'],row['path']) for row in conversions}
    remaining=dict(report,findings=[f for f in report['findings'] if (f['document'],f['path']) not in converted])
    by_doc={}
    for finding in remaining['findings']:by_doc.setdefault(finding['document'],[]).append(finding)
    translation_calls=0
    if '05_writing/translations.json' in by_doc:
        from .agents import Backend
        import translation_batches
        resources=list({r['id']:r for p in (root/'05_writing/work/sections').glob('*/resources.json') for r in read(p,[]) if r['kind']=='text'}.values())
        existing=read(root/'05_writing/translations.json',{}).get('translations',[])
        cache={r['resource_id']:r for r in existing if isinstance(r,dict) and 'resource_id' in r}
        pending=[r for r in resources if r['id'] not in cache or not all(cache[r['id']].get(k) for k in ['chinese','english']) or r['original'] not in [cache[r['id']].get(k) for k in ['chinese','english']]]
        # 原文始终由脚本回填，缺少的中文统一交给已经选定的翻译模型
        from reader_repairs import is_chinese
        pending=[]
        for resource in resources:
            rid=resource['id'];original=resource['original'];prior=cache.get(rid,{})
            if is_chinese(original):
                cache[rid]={'resource_id':rid,'chinese':original,'english':prior.get('english','')if prior.get('chinese')==original else''}
            elif prior.get('english')==original and str(prior.get('chinese','')).strip():pass
            else:pending.append(resource)
        by_doc.pop('05_writing/translations.json')
        if pending:
            translated=translation_batches.generate(Backend(root,role='lean_translation_repair'),pending,'c_repair-translation')
            translation_calls=translated['calls'];cache.update({r['resource_id']:r for r in translated['translations']})
            save(root/'05_writing/checks/translation-repair.json',{k:v for k,v in translated.items()if k!='translations'})
        save(root/'05_writing/translations.json',{'translations':[cache[r['id']]for r in resources if r['id']in cache]})
        save(root/'05_writing/translation-originals.json',{r['id']:r['original']for r in resources})
    tasks=[];allowed={};input_adaptations=[]
    for name,rows in by_doc.items():
        value=read(root/name)
        rows=copy.deepcopy(rows)
        for finding in rows:
            if finding['rule']!='media_contract' or value is None:continue
            try:media=get(value,finding['path'])
            except (KeyError,IndexError,TypeError):continue
            if media.get('kind')!='code':continue
            message=finding['message']
            if any(word in message for word in ['代码缺少行注','代码行注的范围','line_annotations']):
                finding['target']=finding['path']+'/guide/line_annotations'
            elif any(word in message for word in ['代码缺少讲解归属','代码行重复归属','代码讲解分段','组分或功能说明','segments']):
                finding['target']=finding['path']+'/guide/segments'
        paths=targets(rows);allowed[name]=paths
        fragments=[]
        for path in paths:
            try:current=get(value,path)
            except (KeyError,TypeError,IndexError):current=None
            fragments.append({'path':path,'current':current})
        task={'document':name,'findings':rows,'fragments':fragments}
        if '/unit-' in name:
            qid=Path(name).stem.removeprefix('unit-')
            task['question_id']=qid;task['actual_answer']=(value or {}).get('result')
            context=read((root/name).parent/'context.json',{})
            task['question']=next((u for u in context.get('units',[]) if u['question_id']==qid),None)
            local_context={}
            for path in paths:
                match=re.match(r'/appendix/(terms|quiz)/(\d+)(?:/|$)',path)
                if match:
                    parent='/appendix/'+match[1]+'/'+match[2]
                    try:local_context[parent]=get(value,parent)
                    except (KeyError,IndexError,TypeError):pass
            for path in paths:
                match=re.match(r'(/explanation/\d+)(/resources/\d+)?',path)
                if not match:continue
                parent=match[1]+(match[2]or'')
                try:
                    local=copy.deepcopy(get(value,parent))
                    if match[2]:
                        guide=local.get('guide',{})
                        for target in paths:
                            if target.startswith(parent+'/guide/'):
                                key=target[len(parent+'/guide/'):].split('/')[0]
                                guide.pop(key,None)
                    else:local.pop('resources',None)
                    local_context[parent]=local
                except (KeyError,IndexError,TypeError):pass
            if local_context:task['local_context']=local_context
            if any(f['rule'] in {'unit_complete','material_coverage','source_exists'} for f in rows):
                original_resources=[r for r in read((root/name).parent/'resources.json',[]) if qid in r.get('question_ids',[])]
                if all(f['rule']not in {'unit_complete','source_exists'}for f in rows):
                    missing={rid for f in rows if f['rule']=='material_coverage'for rid in f.get('resource_ids',[])}
                    if missing:original_resources=[r for r in original_resources if r['id']in missing]
                task['materials']=file_role_context(root,original_resources)
                if task['materials']!=original_resources:
                    input_adaptations.append({'document':name,'scope':'declared_file_role',
                        'before_characters':len(contract.dumps(original_resources)),'after_characters':len(contract.dumps(task['materials'])),
                        'resource_ids':len(original_resources),'retained_reference_ids':sum(len(r.get('resource_ids',[r.get('id')])) for r in task['materials'])})
                task['material_scope_rule']='scope=file_role 的条目沿用材料树已声明的保留状态，只解释已提供的名称、类型、路径、大小及项目用途，resource_ids 完整列出原任务的引用编号，完整原文件继续保存在本地，不声称已经逐字符读懂资源文件内部数据'
            if value is None:
                from .lean import quota
                index=next(i for i,u in enumerate(context['units']) if u['question_id']==qid)
                task['quiz_quota']=quota(index,len(context['units']));task['schema_name']='c-unit'
        elif name.endswith('translations.json'):
            ids=set()
            for row in rows:ids.update(row.get('resource_ids',[]))
            task['originals']=list({r['id']:r for file in (root/'05_writing/work/sections').glob('*/resources.json') for r in read(file,[]) if r['id'] in ids}.values())
            existing=(value or {}).get('translations',[])
            task['translation_context']={'existing_count':len(existing),
                'rows_to_correct':[{'index':i,'value':r} for i,r in enumerate(existing) if r['resource_id'] in ids]}
            if '/translations' in paths:task['fragments']=[{'path':'/translations','current':task['translation_context']}]
        elif name.endswith('bridges.json'):
            boundaries=read(root/'05_writing/work/bridge-boundaries.json',[])
            present={b['section_id']for b in (value or{}).get('bridges',[])}
            if any(f['rule']=='bridge_complete'for f in rows):
                task['boundaries']=[b for b in boundaries if b['section_id']not in present]
                task['fragments']=[{'path':'/bridges','current':{'completed_sections':sorted(present)}}]
            else:task['boundaries']=boundaries
        tasks.append(task)
    model_calls=translation_calls;applied=[];errors=[];request_records=[];content_calls=0
    if tasks:
        rules=['保留原有事实、数值、条件、三段定义和未受影响的文字，不重新审查或评价内容',
                '只能修改 fragments 指定路径或其子路径，value_json 是新值的合法 JSON 字符串，保持既有字段和结构',
                'local_context 提供受影响术语或练习的完整局部上下文，改写术语时保留三段含义，改写练习时保留答案索引和各选项的正误性质，只修具体违规字段',
                'operation=replace 替换指定字段，operation=append 向指定数组追加一批新条目，补译只追加缺少的行，已有译文保持原样，不重复返回全部已完成译文',
                '补译条目仍使用 resource_id、chinese、english 三个字段，原文所在的显示字段填写 null，脚本按 resource_id 复制原句，另一个字段填写完整译文，每行至少一个字段需要包含实际译文，避免再次生成输入中已有的原句',
                '材料映射缺漏时把缺少的内容接入实际讲解并补齐规划，同一内容的多个来源切片可以对应同一段实际解释，相关材料可以共同展开，正文围绕当前问题推进',
                '已有段落继续保留，优先通过 append 补充必要规划或讲解，通过 replace 调整具体字段，只有原有推理需要整体调整时才替换整个数组',
                'material_refs 在 material_pool 中查找实际材料，输出引用继续使用材料自身的 id 或 resource_ids，文件作用范围保持 file_role，不把输入池索引写进正文',
                '已有问题、章节与小节 ID 和单位归属保持不变，修复字段、遗漏和明确 lint 违规',
                '返回本批全部改动，其他批次处理其他文档，所有批次属于同一轮修复，不返回未修改的整篇正文','输出紧凑 JSON，保留必要空字段与可空拓展字段']
        import repair_batches
        import book_sources
        groups=repair_batches.split(tasks,rules)
        def call(pair):
            index,group=pair;name='c_repair-batch' if len(groups)==1 else 'c_repair-batch-'+str(index+1).zfill(3)
            payload=repair_batches.pack(group,rules);prompt=contract.dumps(payload)
            documents=[t['document'] for t in group]
            schema=contract.obj({'changes':{'type':'array','items':contract.obj({'document':{'type':'string','enum':documents},'path':{'type':'string'},
                'operation':{'type':'string','enum':['replace','append']},'value_json':{'type':'string'}})}})
            images=list(dict.fromkeys(r.get('model_asset',r['asset']) for task in group for r in task.get('materials',[]) if r['kind']=='image' and book_sources._is_image(r['asset'])))
            complete_bytes=len(prompt.encode('utf8'))
            import writing_input
            folder=root/'05_writing/work/repair-inputs'/name
            folder.mkdir(parents=True,exist_ok=True)
            prompt,read_tools,input_mode=writing_input.prepare(root,folder,name,prompt,getattr(backend,'model','gpt-6.1-sol'))
            save(folder/'input-mode.json',input_mode)
            if read_tools:value=backend._call_once(name,prompt,schema,images or[],read_only_tools=True)
            else:value=backend._call_once(name,prompt,schema,images)if images else backend._call_once(name,prompt,schema)
            return value,{'task':name,'documents':documents,'input_utf8_bytes':len(prompt.encode('utf-8')),'complete_input_utf8_bytes':complete_bytes,'input_mode':input_mode,
                'material_occurrences':sum(len(t.get('materials',[])) for t in group),'unique_materials':len(payload['material_pool'])}
        results=[]
        from .concurrency import options
        with futures.ThreadPoolExecutor(max_workers=options()['repair_calls']) as pool:
            pending={pool.submit(call,pair):pair[0] for pair in enumerate(groups)}
            for future in futures.as_completed(pending):
                try:
                    value,receipt=future.result();results.append((pending[future],value));request_records.append(receipt)
                except Exception as error:errors.append('修复批次 '+str(pending[future]+1)+': '+str(error))
        content_calls=len(groups);model_calls+=content_calls
        value={'changes':[change for _,item in sorted(results) for change in item['changes']]};patches={}
        for change in value['changes']:
            name,path=change['document'],change['path']
            if not any(p=='/' or path==p or path.startswith(p+'/') for p in allowed.get(name,[])):
                errors.append('改动路径未被本次检查授权：'+name+path);continue
            try:
                candidate=patches.setdefault(name,copy.deepcopy(read(root/name)))
                replacement=json.loads(change['value_json'])
                if change.get('operation','replace')=='append':
                    target=get(candidate,path)
                    if not isinstance(target,list) or not isinstance(replacement,list):raise ValueError('追加操作需要指向数组，并返回新增条目数组')
                    target.extend(replacement);patches[name]=candidate
                else:patches[name]=put(candidate,path,replacement)
                applied.append({'document':name,'path':path,'operation':change.get('operation','replace')})
            except (ValueError,KeyError,IndexError,TypeError) as error:errors.append(name+path+': '+str(error))
        for name,candidate in patches.items():
            old=read(root/name)
            if '/unit-' in name and candidate.get('question_id')!=Path(name).stem.removeprefix('unit-'):
                errors.append(name+' 的问题归属发生变化，保留原结果');continue
            if name.endswith('translations.json'):
                originals=read(root/'05_writing/translation-originals.json',{})
                for row in candidate.get('translations',[]):
                    rid=row.get('resource_id')
                    if row.get('chinese') is None and row.get('english') is None:
                        errors.append('补译同时缺少两个显示字段：'+str(rid));continue
                    for field in ('chinese','english'):
                        if row.get(field) is None and rid in originals:row[field]=originals[rid]
            if '/unit-' in name:
                formatted,term_changes,term_errors=repair_batches.format_document_terms(candidate)
                if term_changes:
                    candidate=formatted
                    conversions.append({'document':name,'path':'/appendix/terms',
                        'action':'按术语例外位同步名称、拆解、显示和别名','changes':term_changes})
                for error in term_errors:
                    errors.append(name+' 的术语名称整理失败，已保留本次修复结果：'+error)
            save(root/name,candidate)
    return {'rounds':int(bool(report['findings'])),'model_calls':model_calls,'translation_calls':translation_calls,'content_calls':content_calls,
        'script_conversions':conversions,'applied':applied,'patch_errors':errors,'input_adaptations':input_adaptations,'requests':request_records}


def run(root,backend):
    folder=root/'05_writing/checks';started=time.monotonic()
    with span(root,'writing','format'):namespaces=namespace_blocks(root)
    with span(root,'review','check'):before=scan(root)
    save(folder/'independent-before.json',before)
    if before['findings']:
        with span(root,'repair','phase'):result=repair(root,before,backend)
        with span(root,'writing','format'):namespaces+=namespace_blocks(root)
        with span(root,'review','check'):after=scan(root)
    else:result={'rounds':0,'model_calls':0,'script_conversions':[],'applied':[],'patch_errors':[]};after=before
    result['script_conversions']=namespaces+result['script_conversions']
    save(folder/'independent-after.json',after)
    result.update(passed=after['passed'],before_findings=len(before['findings']),after_findings=len(after['findings']),
                  elapsed_seconds=round(time.monotonic()-started,3),semantic_quality_review='not_run')
    save(folder/'batch-repair.json',result)
    return result
