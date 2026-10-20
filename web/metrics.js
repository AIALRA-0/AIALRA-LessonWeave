import {costText} from './generation-progress.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const seconds=value=>value==null?'未记录':value===0?'0 秒':value<1?Math.round(value*1000)+' 毫秒':value<60?value.toFixed(1)+' 秒':Math.floor(value/60)+' 分 '+Math.round(value%60)+' 秒';
const number=value=>value==null?'未返回':Number(value).toLocaleString();
const count=value=>value==null?'未记录':value;
const stamp=value=>value==null?'—':new Date(value*1000).toLocaleString();
const kinds={initial:'首次生成',repair:'内容返修',retry:'失败后重试'};
const statuses={completed:'调用已返回',running:'正在执行',started:'正在执行',failed:'调用失败',uncertain:'结果待核对',invalid:'格式未通过',cancelled:'已停止',interrupted:'已中断',needs_review:'本阶段待审',queued:'正在排队',cancelling:'正在停止'};
const operations={model:'模型调用',phase:'步骤处理',check:'脚本检查',format:'格式转换与检查',reuse:'复用已有结果',slot_queue:'等待调用名额',job_queue:'等待后台执行',job_run:'后台执行',repair_round:'集中修复批次'};
let dialog,timer,controller,current;

function table(headers,rows){return '<div class="metrics-table"><table><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+row.map(value=>'<td>'+value+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
function render(data){
  const s=data.summary;
  const approximate=value=>value==null?'未记录':(s.historical_estimate_calls&&value>0?'约 ':'')+seconds(value);
  const formats=s.format_operations==null?'历史未记录格式处理次数':'格式处理 '+s.format_operations+' 次，共转换 '+s.converted_items+' 项';
  const cards=[['自提交起经过',seconds(s.elapsed_seconds)],['后台执行经过',seconds(s.execution_seconds)],['首次生成经过',approximate(s.initial_generation_seconds)],['集中修复经过',seconds(s.repair_batch_seconds)],['其中生成返修',approximate(s.repair_generation_seconds)],['独立审查经过',approximate(s.review_seconds)],['失败重试经过',approximate(s.retry_seconds)],['调用累计时间',approximate(s.model_cumulative_seconds)],['等待后台执行',seconds(s.job_queue_seconds)],['API 等价估算',costText(s)]];
  return '<div class="metrics-cards">'+cards.map(([label,value])=>'<div><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong></div>').join('')+'</div>'+
    '<p>模型调用 '+s.calls+' 次 · 生成返修 '+s.repair_calls+' 次 · 独立审查 '+s.review_calls+' 次（其中复核 '+s.review_rechecks+' 次） · 失败重试 '+count(s.retry_calls)+' · 复用 '+count(s.reuse_events)+'</p>'+
    '<p>进入集中修复批次 '+count(s.repair_rounds_entered)+' · 实际有模型调用的修复轮数 '+s.repair_rounds_with_model_calls+' · 审查未通过小节 '+count(s.review_failed_sections)+' · 脚本处理 '+seconds(s.script_seconds)+' · '+formats+'</p>'+
    '<p>已报告输入 '+number(s.input_tokens)+' token · 输出 '+number(s.output_tokens)+' token · 缓存输入 '+number(s.cached_input_tokens)+' token · 尚未取得完整用量 '+s.unknown_usage_calls+' 次 · 缓存数据缺失 '+s.cached_input_tokens_missing_calls+' 次</p>'+
    '<p class="help">'+esc(data.pricing?.notes||'')+'</p><ul class="metrics-notes">'+data.notes.map(note=>'<li>'+esc(note)+'</li>').join('')+'</ul><h3>每个环节花了多久</h3>'+
    table(['环节','开始','结束或本次统计时间','实际经过','调用累计','输入 token','输出 token','缓存输入','API 等价估算','调用次数','返修调用','失败调用','检查失败','复用次数','时间依据'],data.stages.map(row=>[esc(row.label),esc(stamp(row.started_at)),esc(stamp(row.ended_at)),esc(seconds(row.wall_seconds)),row.calls?esc(seconds(row.model_seconds)):'—',esc(number(row.input_tokens)),esc(number(row.output_tokens)),esc(number(row.cached_input_tokens)),esc(costText(row)),row.calls,row.repair_calls,row.failed_calls,count(row.failed_checks),count(row.reuse_count),row.reuse_count&&row.wall_seconds==null?'复用已有结果':row.historical_estimate?'含历史推算':row.wall_seconds==null?'未记录或尚未执行':'直接记录']))+
    '<h3>每次模型调用做了什么</h3>'+table(['任务','用途','模型与推理','修复轮次','开始','结束','等待名额','调用用时','输入 / 输出 / 缓存 token','状态'],data.calls.map(row=>[esc(row.task),row.stage==='review'?(row.kind==='repair'?'独立复核':'独立审查'):esc(kinds[row.kind]||row.kind),esc((row.model||'未记录')+' / '+(row.reasoning_effort||'未记录')),row.round,esc(stamp(row.started_at)),esc(stamp(row.ended_at)),esc(seconds(row.queue_seconds)),esc(seconds(row.elapsed_seconds))+(row.measurement==='historical_file_times'?'（推算）':''),esc([row.input_tokens,row.output_tokens,row.cached_input_tokens].map(number).join(' / ')),esc((statuses[row.status]||row.status)+(row.failure_kind==='output_limit'?' · 输出超限':row.failure_kind?' · '+row.failure_kind:''))]))+
    '<details><summary>查看脚本、排队、复用和修复批次记录</summary>'+table(['步骤','任务','开始','结束','实际用时','结果'],data.steps.map(row=>[esc(operations[row.operation]||row.operation),esc(row.task||'—'),esc(stamp(row.started_at)),esc(stamp(row.ended_at)),esc(seconds(row.elapsed_seconds)),esc((row.operation!=='model'&&row.status==='completed'?'步骤已结束':statuses[row.status]||row.status)+(row.validation_passed===false?' · 审查未通过':'')+(row.converted_items!=null?' · 转换 '+row.converted_items+' 项':''))]))+'</details>'+
    '<p class="help">时间按浏览器时区显示，统计更新于 '+esc(stamp(data.generated_at))+'</p>';
}

export function showMetrics(jobId,title){
  if(!dialog){
    dialog=document.createElement('dialog');dialog.className='metrics-dialog';dialog.innerHTML='<header><h2></h2><button type="button" class="icon" aria-label="关闭耗时明细">×</button></header><div class="metrics-toolbar"><button type="button" data-refresh>刷新记录</button><button type="button" data-export>导出 JSON</button></div><div class="metrics-content"></div>';
    document.body.append(dialog);dialog.querySelector('.icon').onclick=()=>dialog.close();
    dialog.addEventListener('close',()=>{clearTimeout(timer);controller?.abort();current=null;});
    dialog.querySelector('[data-refresh]').onclick=()=>load();
    dialog.querySelector('[data-export]').onclick=()=>{if(!current)return;const blob=new Blob([JSON.stringify(current,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='lessonweave-'+current.job_id+'-metrics.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  }
  dialog.dataset.jobId=jobId;dialog.querySelector('h2').textContent=title+' · 耗时与次数';dialog.querySelector('.metrics-content').textContent='正在读取实际记录';
  if(!dialog.open)dialog.showModal();load();
}

async function load(){
  clearTimeout(timer);controller?.abort();controller=new AbortController();const pending=controller;
  try{
    const response=await fetch('/api/jobs/'+encodeURIComponent(dialog.dataset.jobId)+'/metrics',{signal:pending.signal,cache:'no-store'});const data=await response.json();if(!response.ok)throw Error(data.error||'读取记录失败');
    if(pending!==controller||!dialog.open)return;current=data;const body=dialog.querySelector('.metrics-content'),open=body.querySelector('details')?.open,scroll=dialog.scrollTop;body.innerHTML=render(data);if(open)body.querySelector('details').open=true;dialog.scrollTop=scroll;
    if(['queued','running','cancelling'].includes(data.status))timer=setTimeout(load,3000);
  }catch(error){if(error.name!=='AbortError'&&dialog.open)dialog.querySelector('.metrics-content').textContent=error.message;}
}
