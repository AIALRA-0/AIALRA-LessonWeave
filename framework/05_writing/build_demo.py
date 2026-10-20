"""检查小节样稿、逐问回答、练习与独立清点的术语"""
import argparse
import copy
import importlib.util
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

# 成书检查也会按文件路径加载本模块，因此同目录检查器不能依赖调用者的 sys.path
_coverage_spec=importlib.util.spec_from_file_location('writing_teaching_coverage',Path(__file__).with_name('teaching_coverage.py'))
_coverage_module=importlib.util.module_from_spec(_coverage_spec)
_coverage_spec.loader.exec_module(_coverage_module)
check_grounding=_coverage_module.check_grounding
_style_spec=importlib.util.spec_from_file_location('writing_positive_style',Path(__file__).with_name('positive_writing.py'))
_style_module=importlib.util.module_from_spec(_style_spec)
_style_spec.loader.exec_module(_style_module)
check_positive_writing=_style_module.check_positive_writing
_notation_spec=importlib.util.spec_from_file_location('writing_local_notations',Path(__file__).with_name('local_notations.py'))
_notation_module=importlib.util.module_from_spec(_notation_spec)
_notation_spec.loader.exec_module(_notation_module)
check_local_notations=_notation_module.check_local_notations


def walk(n):
    yield n
    for c in n['children']:yield from walk(c)


def section_number(tree,section_id,path=()):
    if tree['id']==section_id:return '.'.join(map(str,path))
    for index,child in enumerate(tree['children'],1):
        found=section_number(child,section_id,path+(index,))
        if found:return found
    return ''


def blocks(doc):
    yield doc['opening']
    if doc.get('opening_forward'):
        yield doc['opening_forward']
    for u in doc['units']:
        yield u['problem'];yield from u['explanation'];yield u['synthesis']
    for row in doc['summary']:yield row['answer']
    for row in doc['pitfalls']:yield row['body']
    for row in doc['quiz']:
        yield row['prompt'];yield row['explanation']


def block_text(block):
    if 'guide' in block:
        from media_contract import authored_texts
        return block.get('caption', '') + ' ' + ' '.join(value for _, value in authored_texts(block['guide']))
    if block['kind']=='table':text=' '.join(block['headers']+[cell for row in block['rows'] for cell in row])
    elif block['kind']=='list':text=' '.join(block['items'])
    elif block['kind'] in ['code','formula','image']:text=block.get('caption','')
    else:text=block['text']
    return block.get('lead_in','')+' '+text


def chunks(doc):
    yield 'title',doc['title'];yield 'next-title',doc['next_title']
    yield 'opening-title',doc['opening_title']
    if doc.get('book_introduction'):yield 'book-introduction',doc['book_introduction']
    for goal in doc.get('context_goals',[]):yield 'context-goal:'+goal['question_id'],goal['text']+' '+goal['answer']
    for q in doc['core_questions']:yield 'core:'+q['question_id'],q['text']
    for u in doc['units']:yield 'unit-title:'+u['question_id'],u['title']
    for b in blocks(doc):yield b['id'],block_text(b)
    for p in doc['pitfalls']:yield p['id']+':title',p['premise']+p['question']
    for q in doc['quiz']:
        for i,choice in enumerate(q.get('options',[])):yield q['id']+f':option:{i}',choice
        if q['kind']=='short_answer':
            yield q['id']+':reference',q['reference_answer']
            for i,point in enumerate(q['rubric']):yield q['id']+f':rubric:{i}',point


def terminology_inventory(doc,catalog):
    found={};unknown=[];patterns=[]
    notations=check_local_notations(doc);notation_occurrences=[]
    counts={'english_token_occurrences':0,'professional_term_token_occurrences':0,
            'local_notation_token_occurrences':0,'unknown_token_occurrences':0}
    # 同一份术语清单先编译一次匹配规则，避免逐段反复编译大量别名
    for term in catalog['entries']:
        for alias in term['aliases']:
            pattern=re.escape(alias)
            if re.fullmatch(r'[A-Za-z0-9 -]+',alias):pattern=r'(?<![A-Za-z0-9])'+pattern+r'(?![A-Za-z0-9])'
            patterns.append((term['id'],re.compile(pattern,re.I)))
    for location,text in [*chunks(doc),*_notation_module.formula_chunks(doc)]:
        spans=[]
        local_spans=_notation_module.notation_spans(notations,location,text)
        notation_occurrences.extend(local_spans)
        # 只遮住完整定位编号的匹配跨度，原文和实际阅读位置保持原样
        locator_spans=[match.span() for match in re.finditer(
            r'(?<![A-Za-z0-9_])(?:n\d{6}(?:\.s\d+)?|q(?:\.\d+)+|c\d{2}\.s\d{2})(?![A-Za-z0-9_])',text)]
        locator_spans.extend(_notation_module.formula_markup_spans(location,text))
        visible=list(text)
        for start,end in locator_spans:visible[start:end]=' '*(end-start)
        token_text=''.join(visible)
        for row in local_spans:visible[row['start']:row['end']]=' '*(row['end']-row['start'])
        match_text=''.join(visible)
        for term_id,pattern in patterns:
            for match in pattern.finditer(match_text):
                found.setdefault(term_id,set()).add(location);spans.append((match.start(),match.end()))
        professional_covered=[False]*len(text)
        for start,end in spans:
            professional_covered[start:end]=[True]*(end-start)
        # 材料、问题和小节的完整定位编号只用于回到来源，独立字母与其他英文仍需登记
        # 英文与缩写单独扫描，不从已经生成的术语表反推检查分母
        for token in re.finditer(r'(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*',token_text):
            if any(a<=token.start() and b>=token.end() for a,b in locator_spans):continue
            counts['english_token_occurrences']+=1
            if any(row['start']<=token.start() and row['end']>=token.end() for row in local_spans):
                counts['local_notation_token_occurrences']+=1
            elif all(professional_covered[index] or token_text[index] in '/-'
                     for index in range(token.start(),token.end())):
                counts['professional_term_token_occurrences']+=1
            else:
                unknown.append({'token':token.group(),'location':location})
                counts['unknown_token_occurrences']+=1
    notations['occurrences']=notation_occurrences
    counts['covered_token_occurrences']=counts['professional_term_token_occurrences']+counts['local_notation_token_occurrences']
    return {'terms':[{'term_id':key,'locations':sorted(value)} for key,value in sorted(found.items())],
            'unknown_tokens':unknown,'local_notations':notations,'token_coverage':counts,
            'scope':'正文、标题、核心问题、总结、易错点、题目、选项、答案与公式，专业术语和就地定义的局部符号分别核对，术语表自身不计入分母'}


def split_numeric_value(term):
    abbreviation=term.get('abbreviation') or ''
    spans=[];start=0
    for component in term.get('components',[]):
        end=start+len(component.get('symbol',''))
        spans.append((start,end));start=end
    return any(sum(left<match.end() and right>match.start() for left,right in spans)>1
               for match in re.finditer(r'\d{2,}',abbreviation))


def check_terminology(term):
    errors=[];key=term['id'];abbr=term['abbreviation'];english=term['english']
    display=(abbr+' ' if abbr else '')+term['chinese']+'（'+english+'）'
    if term['display']!=display:errors.append(key+' 的中英文排列或括号内容不正确')
    if any(c in english for c in '（）()“”"`'):errors.append(key+' 的英文全称混入了额外符号')
    words=re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*",english);small={'of','and','the','in','to','for','on','at','a','an','per','per'}
    if term['kind']=='official_name':
        if english!=term.get('official_spelling') or not term.get('case_source','').strip():errors.append(key+' 没有保留有来源的正式大小写')
    else:
        for i,word in enumerate(words):
            expected=word.lower() if i and word.lower() in small else word[0].upper()+word[1:].lower()
            if word!=expected:errors.append(key+' 的英文名称没有使用规定的大小写')
    if abbr:
        if re.search(r'(?<![A-Za-z0-9])'+re.escape(abbr)+r'(?![A-Za-z0-9])',english,re.I):errors.append(key+' 在英文全称中重复了缩写')
        if ''.join(p['symbol'] for p in term['components'])!=abbr:errors.append(key+' 的缩写没有逐项拆开')
        if split_numeric_value(term):errors.append(key+' 的缩写中连续数字需要作为一个实际数值整体拆解，请保留原材料的数值与名称')
        parts=[p['word'] for p in term['components']]
        if term['kind']=='initialism':
            significant=[w for w in words if w.lower() not in small]
            compounds=re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)*",english)
            compound_significant=[w for w in compounds if w.lower() not in small]
            if parts not in [significant,words,compound_significant,compounds] or any(p['symbol']!=p['word'][0].upper() for p in term['components']):
                errors.append(key+' 的缩写拆解与完整英文名称不一致')
        elif term['kind']=='unit':
            # 多词单位忽略词间空白再核对，具体词语、符号与其他大小写规则仍逐项检查
            if re.sub(r'\s+','',''.join(parts)).lower()!=re.sub(r'\s+','',english).lower():errors.append(key+' 的单位拆解与名称不一致')
    elif term['components']:errors.append(key+' 没有缩写却添加了缩写拆解')
    return errors


def load_context(doc,root):
    root=Path(root).resolve();path=(root/doc['transitions_path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('样稿没有对应的承接计划')
    transitions=json.loads(path.read_text(encoding='utf-8'))
    if transitions['transition_run']!=doc['transition_run'] or not transitions['validation']['passed']:raise ValueError('样稿与承接计划版本不一致')
    spec=importlib.util.spec_from_file_location('writing_transitions',root/'04_transitions/build_transitions.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    errors=m.check_transitions(transitions,root)
    if errors:raise ValueError('承接计划需要先修复：'+'；'.join(errors))
    chapters,questions=m.load_chapters(transitions,root)
    section=next((n for n in walk(chapters['tree']) if n['id']==doc['section_id'] and n['kind']=='section'),None)
    if not section:raise ValueError('样稿引用的章节不存在')
    bridge=next(n for n in walk(transitions['tree']) if n['title_id']==section['id'])
    return transitions,chapters,questions,section,bridge


def check_demo(doc,root):
    root=Path(root);schema=json.loads((root/'05_writing/demo.schema.json').read_text(encoding='utf-8'))
    errors=[str(e.message) for e in Draft202012Validator(schema).iter_errors(doc)]
    if errors:return errors
    errors.extend(check_positive_writing(doc))
    try:transitions,chapters,questions,section,bridge=load_context(doc,root)
    except (ValueError,KeyError,OSError) as e:return [str(e)]
    qnodes={n['id']:n for n in walk(questions['tree'])}
    expected=section['question_ids'];concrete=[key for key in expected if not qnodes[key]['children']]
    if [q['question_id'] for q in doc['core_questions']]!=expected:errors.append('核心问题列表与章节分配不一致')
    for q in doc['core_questions']:
        if q['question_id'] in qnodes and q['text']!=qnodes[q['question_id']]['premise']+qnodes[q['question_id']]['question']:errors.append('核心问题的文字被改动')
    if doc['title']!=section['title']:errors.append('样稿标题与成书目录不一致')
    number=section_number(chapters['tree'],section['id'])
    if doc['section_number']!=number:errors.append('小节编号与成书目录中的位置不一致')
    if not doc.get('writing_contract_version') and doc['opening_title']!=bridge['premise']+bridge['question']:errors.append('承上启下标题与 04 中的完整问句不一致')
    if doc['scope']=='book_section':
        chapter=next(c for c in chapters['tree']['children'] if any(s['id']==section['id'] for s in c['children']))
        expected_goals=[]
        if section['id']==chapter['children'][0]['id']:
            if chapter['id']==chapters['tree']['children'][0]['id']:expected_goals.extend(chapters['tree']['question_ids'])
            expected_goals.extend(chapter['question_ids'])
        if [g['question_id'] for g in doc.get('context_goals',[])]!=expected_goals:errors.append('节前整体目标与原有归属不一致')
        for g in doc.get('context_goals',[]):
            q=qnodes.get(g['question_id'])
            if not q or g['text']!=q['premise']+q['question'] or g['source_nodes']!=q['source_nodes']:errors.append('节前整体目标的文字或材料映射不一致')
    if [u['question_id'] for u in doc['units']]!=concrete:errors.append('具体问题必须按分配顺序各讲解一次')
    for index,u in enumerate(doc['units'],1):
        if u['number']!=f'{number}.{index}':errors.append('讲解单元编号必须按小节顺序连续排列')
        source=qnodes.get(u['question_id'])
        if 'source_nodes' in u and source and u['source_nodes']!=source['source_nodes']:errors.append('讲解单元的材料映射与问题不一致')
        if 'source_nodes' in u and source and u['source_nodes']!=source['source_nodes']:errors.append('讲解单元的材料映射与问题不一致')
        if source and u['title']!=source['premise']+source['question']:errors.append('讲解单元标题必须使用对应的完整核心问题')
    if [q['question_id'] for q in doc['summary']]!=expected:errors.append('内容总结必须按核心问题一一实际回答')
    if doc['next_section_id']!=bridge['next_section_id']:errors.append('样稿结尾没有接到计划中的下一节')
    next_title=next((n['title'] for n in walk(chapters['tree']) if n['id']==doc['next_section_id']),'')
    if doc['next_title']!=next_title:errors.append('下一节标题与目录不一致')
    seen=set()
    for b in blocks(doc):
        if b['id'] in seen:errors.append('内容块 ID 重复，无法准确定位原段落与单元笔记')
        seen.add(b['id'])
        if 'guide' in b:
            from media_contract import check as check_media
            errors.extend(check_media(b, root))
        if b.get('lead_in','').endswith(('：',':')):errors.append('lead_in 不重复保存由页面添加的冒号')
        if b['kind']=='image':
            asset=(root/b['asset'].lstrip('/')).resolve()
            if not asset.is_relative_to(root.resolve()) or not asset.is_file():errors.append('正文引用的本地图像不存在')
    for i,u in enumerate(doc['units']):
        following=doc['units'][i+1]['problem']['text'] if i+1<len(doc['units']) else ''
        if following and re.sub(r'\W','',u['synthesis']['text'])==re.sub(r'\W','',following):errors.append('升华段重复了下一问题段')
    quiz_covered=set()
    for q in doc['quiz']:
        if set(q['question_ids'])-set(expected):errors.append('练习引用了本节以外的问题')
        quiz_covered.update(q['question_ids'])
        if q['kind']=='single_choice' and not 0<=q['answer']<len(q['options']):errors.append('单选答案没有对应选项')
    if 'grounding' in doc:
        valid_quiz = 3 <= sum(q['kind']=='single_choice' for q in doc['quiz']) <= 5 if doc.get('writing_contract_version') else 3<=len(doc['quiz'])<=5
        if not valid_quiz or sum(q['kind']=='short_answer' for q in doc['quiz'])!=1:
            errors.append('新版每节需要三至五道单选和恰好一道简答，旧稿保留原检查范围')
        errors.extend(check_grounding(doc,root))
    if set(concrete)-quiz_covered:errors.append('还有核心知识没有对应练习')
    for p in doc['pitfalls']:
        if not p['question'].endswith('？') or '\n' in p['premise']+p['question']:errors.append('易错点标题必须是同一行的前提与问句')
    catalog_path=(root/doc['catalog_path']).resolve()
    if not catalog_path.is_relative_to(root.resolve()) or not catalog_path.is_file():return errors+['术语清单不存在']
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'));inventory=terminology_inventory(doc,catalog)
    errors.extend(inventory['local_notations']['errors'])
    if inventory['unknown_tokens']:errors.append('还有未登记的专业英文、缩写或缺少就地定义的局部符号：'+', '.join(sorted({p['token'] for p in inventory['unknown_tokens']})))
    expected_terms={r['term_id'] for r in inventory['terms']};actual_terms=[t['id'] for t in doc['glossary']]
    if set(actual_terms)!=expected_terms or len(actual_terms)!=len(set(actual_terms)):errors.append('术语表没有恰好覆盖独立清点出的全部术语')
    for term in doc['glossary']:
        errors.extend(check_terminology(term))
        if len(set(term['explanation']))!=len(term['explanation']):errors.append(term['id']+' 的术语解释重复了同一段')
        for text in [term['definition']]+term['explanation']:
            if '。' in text:errors.append(term['id']+' 的术语解释使用了中文句号')
    if 'coverage' in doc:
        expected_coverage={'questions':len(expected),'units':len(concrete),'answered':len(doc['summary']),
                           'quiz':len(doc['quiz']),'terms':len(expected_terms),'covered_terms':len(actual_terms),'term_percentage':100.0}
        if {k:v for k,v in doc['coverage'].items() if k!='report'}!=expected_coverage:errors.append('写作覆盖数字与逐项核对的结果不一致')
    for location,text in chunks(doc):
        if '。' in text:errors.append(location+' 使用了中文句号')
    return errors


def publish_demo(root,candidate):
    root=Path(root);doc=copy.deepcopy(candidate);doc.pop('writing_run',None);doc.pop('coverage',None)
    doc['validation']={'passed':False,'errors':[]}
    if 'grounding' in doc and doc.get('writing_rules_version')!=2:
        raise ValueError('新发布的讲解需要按第 2 版写作规则完成检查')
    catalog_source=(root/doc['catalog_path']) if 'grounding' in doc else root/'05_writing/terminology.catalog.json'
    catalog=json.loads(catalog_source.read_text(encoding='utf-8'))
    doc['catalog_path']=catalog_source.relative_to(root).as_posix()
    inventory=terminology_inventory(doc,catalog);required={r['term_id'] for r in inventory['terms']}
    doc['glossary']=[copy.deepcopy(t) for t in catalog['entries'] if t['id'] in required]
    errors=check_demo(doc,root)
    if errors:raise ValueError('\n'.join(errors))
    stage=root/'05_writing';nums=[int(p.name[9:]) for p in (stage/'history').glob('revision-*') if p.name[9:].isdigit()]
    revision=f'revision-{max(nums,default=0)+1:04d}';dest=stage/'history'/revision;dest.mkdir(parents=True)
    if 'grounding' in doc:
        # 本版正文与材料、对应表、审查结果一起冻结，旧版原文定位不会随新一轮变化
        for key,path in list(doc['grounding'].items()):
            filename=key.removesuffix('_path').replace('_','-')+'.json'
            frozen=dest/filename
            frozen.write_text((root/path).read_text(encoding='utf-8'),encoding='utf-8')
            doc['grounding'][key]=frozen.relative_to(root).as_posix()
    (dest/'terminology.catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    doc['catalog_path']=f'05_writing/history/{revision}/terminology.catalog.json';doc['writing_run']=revision
    doc['coverage']={'questions':len(doc['core_questions']),'units':len(doc['units']),'answered':len(doc['summary']),
                     'quiz':len(doc['quiz']),'terms':len(required),'covered_terms':len(doc['glossary']),
                     'term_percentage':100.0,'report':f'05_writing/history/{revision}/term-inventory.json'}
    doc['validation']={'passed':True,'errors':[]}
    for name,obj in [('demo.json',doc),('term-inventory.json',inventory)]:
        (dest/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp=stage/'demo.tmp';temp.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(stage/'demo.json')
    return doc


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='检查一个小节的写作结构、材料映射与术语')
    parser.add_argument('candidate',type=Path);args=parser.parse_args()
    result=publish_demo(Path(__file__).resolve().parent.parent,json.loads(args.candidate.read_text(encoding='utf-8')))
    print(json.dumps(result['coverage'],ensure_ascii=False))
