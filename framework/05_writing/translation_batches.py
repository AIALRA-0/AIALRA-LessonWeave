"""翻译只生成缺少的中文，原句、保护片段与重复映射由脚本处理"""
import concurrent.futures as futures
import collections,copy,json,os,re
import lean_contract as contract
from reader_repairs import is_chinese

DEFAULT_PAYLOAD_BYTES=24_000
PROTECTED=re.compile(r'```[\s\S]*?```|`[^`\n]+`|\$\$[\s\S]*?\$\$|(?<!\$)\$[^$\n]+\$|https?://[^\s<>]+')

def batches(resources,budget=None):
 budget=budget or __import__('lessonweave.concurrency',fromlist=['options']).options()['translation_bytes'];result=[];current=[];size=0
 for row in resources:
  cost=len(contract.dumps({'id':row['id'],'original':row['original']}).encode('utf8'))
  if current and size+cost>budget:result.append(current);current=[];size=0
  current.append(row);size+=cost
 if current:result.append(current)
 return result

from document_sources import protect


def generate(backend,resources,name='c_translation',budget=None):
 completed={};unique={};aliases=collections.defaultdict(list)
 for row in resources:
  original=row['original'];rid=row['id']
  if is_chinese(original):completed[rid]={'resource_id':rid,'chinese':original,'english':''};continue
  masked,fragments=protect(original)
  if not re.search('[A-Za-z]',re.sub(r'⟦LW_KEEP_\d+⟧','',masked)):
   completed[rid]={'resource_id':rid,'chinese':original,'english':original};continue
  # 短标签可能有多义，保留来源上下文；完整相同段落才跨来源复用
  context=row.get('translation_context',row.get('source_id','') if len(original)<80 else '')
  key=(original,context);aliases[key].append(rid)
  if key not in unique:unique[key]=dict(row,masked=masked,protected=fragments)
 groups=batches(list(unique.values()),budget);records=[];errors=[]
 from lessonweave.storage import read,save
 live=backend.root/'runtime/translation-live.json' if hasattr(backend,'root') else None
 initial=read(live,{}) if live else {}
 schema=contract.obj({'translations':{'type':'array','items':contract.obj({'resource_id':contract.TEXT,'translation':contract.TEXT})}})
 def call(pair):
  index,rows=pair;task=name if len(groups)==1 else name+'-batch-'+str(index+1).zfill(3)
  payload={'task':'把英文自然语言忠实流畅地译为中文，只生成译文并输出紧凑 JSON，逐项保留 resource_id','rules':['保留数字、单位、专名、否定、限定、语气和标点，不添加解释','⟦LW_KEEP_数字⟧ 是脚本保留的代码、公式或 URL，逐字原样保留这些标记','每个条目完整翻译，不重写原句，不为中文补英文'],'resources':[{'id':r['id'],'original':r['masked']}for r in rows]}
  value=backend._call_once(task,contract.dumps(payload),schema);expected={r['id']:r for r in rows};result=[];problems=[];seen=set()
  for row in value['translations']:
   rid=row['resource_id']
   if rid not in expected or rid in seen:problems.append('本批次译文编号不匹配或重复：'+rid);continue
   seen.add(rid);source=expected[rid];text=row['translation']
   if any(text.count(token)!=1 for token,_ in source['protected']):problems.append('译文中的保护标记不完整：'+rid);continue
   for token,fragment in source['protected']:text=text.replace(token,fragment)
   context=source.get('translation_context',source.get('source_id','')if len(source['original'])<80 else '')
   for target in aliases[(source['original'],context)]:result.append({'resource_id':target,'chinese':text,'english':source['original']})
  for rid in set(expected)-seen:problems.append('本批次缺少中文译文：'+rid)
  return task,result,problems
 with futures.ThreadPoolExecutor(max_workers=__import__('lessonweave.concurrency',fromlist=['options']).options()['translation_calls'])as pool:
  pending={pool.submit(call,pair):pair for pair in enumerate(groups)}
  for future in futures.as_completed(pending):
   index,rows=pending[future];task=name if len(groups)==1 else name+'-batch-'+str(index+1).zfill(3)
   try:
    _,values,problems=future.result();completed.update({r['resource_id']:r for r in values});errors.extend(problems);records.append({'task':task,'resources':len(rows),'returned':len(values),'status':'completed'})
   except Exception as error:errors.append(task+': '+str(error));records.append({'task':task,'resources':len(rows),'returned':0,'status':'recorded'})
   if live:save(live,{**initial,'completed':initial.get('completed',0)+len(completed),'batches_completed':len(records),'batches_total':len(groups)})
 return {'translations':[completed[r['id']]for r in resources if r['id']in completed],'calls':len(groups),'records':records,'errors':errors,'originals_regenerated':False,'english_policy':'on_demand_for_chinese','unique_requests':len(unique),'reused_rows':sum(len(v)-1 for v in aliases.values()),'payload_budget_bytes':budget or __import__('lessonweave.concurrency',fromlist=['options']).options()['translation_bytes']}
