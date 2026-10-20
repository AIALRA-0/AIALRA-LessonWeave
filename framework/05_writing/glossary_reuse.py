"""按明确词义复用完整三段，任务只返回引用，当前正文仍保留自己的来源对应"""
import copy,json,os,re
from pathlib import Path
import lean_contract as contract
from functools import lru_cache

def library_path():
    from lessonweave.storage import data_root
    return Path(os.environ.get('LESSONWEAVE_GLOSSARY_LIBRARY',data_root()/'glossary-library.json'))

@lru_cache(maxsize=1)
def load():
    entries={}
    for path in [Path(__file__).with_name('glossary-common.json'),library_path()]:
        if path.is_file():
            entries.update({row['key']:row for row in json.loads(path.read_text('utf8')).get('entries',[])})
    return list(entries.values())


def remember(terms):
    """保存已经生成的通用实例，下一次写作再按实际词义选择，不重复生成三段"""
    from lessonweave.storage import read,save,WRITE_LOCK
    from jsonschema import Draft202012Validator
    import time
    if not terms:return {'added':0,'model_calls':0,'seconds':0,'policy':'本次没有新词条，词库保持原样'}
    started=time.perf_counter();validator=Draft202012Validator(contract.schema('c-unit')['properties']['appendix']['properties']['terms']['items'])
    def identity(term):
        definition=term['professional_definition']
        return (term['english'].strip().casefold(),term['chinese'].strip(),
            *(str(definition[key]).strip()for key in ['genus','differentia','boundary']))
    with WRITE_LOCK:
        entries={row['key']:row for row in load()}
        entries.update({row['key']:row for row in read(library_path(),{}).get('entries',[])})
        known={identity(row['term'])for row in entries.values()};added=0;skipped=0;duplicates=0;before=len(entries)
        for term in terms:
            if term.get('case_source')is not None or not validator.is_valid(term):skipped+=1;continue
            key=identity(term)
            if key in known:duplicates+=1;continue
            index=len(entries)+1
            while 'learned-'+str(index).zfill(6)in entries:index+=1
            name='learned-'+str(index).zfill(6)
            entries[name]={'key':name,'term':copy.deepcopy(term)};known.add(key);added+=1
        save(library_path(),{'version':1,'entries':list(entries.values())})
    return {'before':before,'added':added,'after':len(entries),'duplicates':duplicates,'skipped':skipped,
        'seconds':time.perf_counter()-started,'model_calls':0,
        'policy':'三段完整保留；仅合并名称和专业定义完全相同的词条，不同边界保留为候选，由后续写作按当前材料选择；这一步不节省本轮已经生成的token'}

def prepare(prompt,schema,entries):
    payload=json.loads(prompt)
    text=contract.dumps({'question':payload['question'],'materials':payload['materials']}).casefold()
    chosen=[]
    for entry in entries:
        term=entry['term'];names=[term['chinese'],term['english'],term.get('abbreviation')or'',*term.get('aliases',[])]
        if any(name and (name.casefold() in text if re.search('[\u4e00-\u9fff]',name) else re.search(r'(?<![a-z0-9_])'+re.escape(name.casefold())+r'(?![a-z0-9_])',text))for name in names):chosen.append(entry)
    if not chosen:return prompt,schema,{}
    payload['common_terms']=[{'key':e['key'],'chinese':e['term']['chinese'],'english':e['term']['english'],'abbreviation':e['term'].get('abbreviation'),'genus':e['term']['professional_definition']['genus'],'differentia':e['term']['professional_definition']['differentia'],'boundary':e['term']['professional_definition']['boundary']}for e in chosen]
    payload['glossary_rules']+=['已登记词义与当前用法一致时，terms 只返回 common_key、当前 id 和 aliases，脚本完整复用原有定义、生活类比和简短通用实例，不缩短或改写三段；只有当前材料引入特殊词义或边界时，才返回新词条的完整字段并明确该边界；其他新术语仍在本次调用中完整生成，不漏掉正文中的术语']
    schema=copy.deepcopy(schema);field=schema['properties']['appendix']['properties']['terms']
    field['items']={'anyOf':[field['items'],contract.obj({'common_key':{'type':'string','enum':[e['key']for e in chosen]},'id':contract.TEXT,'aliases':contract.STRINGS})]}
    return contract.dumps(payload),schema,{e['key']:e['term']for e in chosen}

def expand(value,selected):
    value=copy.deepcopy(value);hits=[];terms=[]
    for term in value['appendix']['terms']:
        if 'common_key' not in term:terms.append(term);continue
        common=copy.deepcopy(selected[term['common_key']]);common['id']=term['id'];common['aliases']=list(dict.fromkeys(common.get('aliases',[])+term['aliases']))
        terms.append(common);hits.append({'key':term['common_key'],'id':term['id'],'three_paragraphs':'copied_complete','material_sources':'current_body_mapping'})
    value['appendix']['terms']=terms
    return value,hits
