const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const duration=s=>s==null?'未记录':s===0?'0 秒':s<1?Math.round(s*1000)+' 毫秒':s<60?s.toFixed(1)+' 秒':Math.floor(s/60)+' 分 '+Math.round(s%60)+' 秒';
const states={done:'已完成',skipped:'已完成，无需执行',running:'正在生成',waiting:'等待执行',failed:'生成失败',interrupted:'已中断'};
const taskStates={waiting:'等待调用',running:'正在生成',completed:'已返回',reused:'复用已有结果',failed:'正在自动恢复'};
const taskLabel=name=>{
 const q=String(name).match(/-c-(q\.[0-9.]+)$/);if(q)return '生成问题 '+q[1]+' 的讲解';
 if(name.startsWith('02_questions-initial'))return '首次规划问题';
 if(name.startsWith('02_questions-fill'))return '补齐问题与材料去向';
 if(name==='03_chapters')return '编排章节';
 for(const [prefix,label]of [['c_translation','生成中文译文'],['c_bridges','生成承上启下'],['c_repair','按问题批量修复']])if(name.startsWith(prefix))return label+(name.match(/(?:batch-)?([0-9]+)$/)?.[1]?' · 第 '+Number(name.match(/([0-9]+)$/)[1])+' 批':'');
 if(name.startsWith('attachment:'))return '保存文件 '+name.split('/').at(-1).replace('attachment:','');
 return name;
};
export const stagePercent=s=>['done','skipped'].includes(s.status)?100:s.total>0?Math.min(100,Math.round(100*(s.done||0)/s.total)):0;
export const progressPercent=p=>p.stages?.length?Math.floor(p.stages.reduce((n,s)=>n+stagePercent(s),0)/p.stages.length):0;
export function progressMarkup(p,selected){
 const stages=p.stages||[],row=stages.find(r=>r.id===selected)||stages.find(r=>r.status==='running')||stages.find(r=>['failed','interrupted'].includes(r.status))||stages.find(r=>r.status==='waiting')||stages.at(-1);
 if(!row)return '<p class="help">没有可展开的阶段记录</p>';
 const tasks=p.tasks||[],active=tasks.filter(t=>t.status==='running'),finished=tasks.filter(t=>['completed','reused'].includes(t.status));
 const percent=stagePercent(row),indeterminate=row.status==='running'&&!row.total;
 return '<div class="generation-layout"><nav class="generation-stages" aria-label="生成阶段">'+stages.map((s,i)=>'<button type="button" data-stage="'+esc(s.id)+'" data-state="'+esc(s.status)+'" aria-current="'+(s.id===row.id?'step':'false')+'"><span class="stage-mark" aria-hidden="true">'+(['done','skipped'].includes(s.status)?'✓':['failed','interrupted'].includes(s.status)?'⚠':s.status==='running'?'◌':'')+'</span><span class="stage-number">'+String(i+1).padStart(2,'0')+'</span><span class="stage-copy">'+esc(s.label)+'<small>'+esc(states[s.status]||s.status)+' · '+(s.execution_seconds==null&&s.status==='waiting'?'尚未执行':duration(s.execution_seconds))+'</small></span><span class="stage-percent">'+stagePercent(s)+'%</span></button>').join('')+'</nav><section class="generation-detail"><h3>'+esc(row.label)+'</h3><p>'+esc(row.detail||'进度随实际保存的结果更新')+'</p><div class="generation-count">'+percent+'%'+(row.total!=null?'<span>'+row.done+' / '+row.total+' 项已完成</span>':'<span>'+esc(states[row.status]||row.status)+'</span>')+'</div><progress '+(indeterminate?'':'value="'+percent+'"')+' max="100" aria-label="'+esc(row.label)+'进度"></progress>'+(indeterminate?'<p class="help">当前步骤尚未返回，百分比按已完成的步骤计算</p>':'')+'<div class="generation-facts"><span class="stage-clock">本阶段执行 '+(row.execution_seconds==null&&row.status==='waiting'?'尚未执行':duration(row.execution_seconds))+'</span><span title="各阶段分别计时后相加，并行阶段的时间可能重叠">阶段执行累计 '+duration(p.stage_execution_seconds)+'</span><span>自提交起 '+duration(p.elapsed_seconds||0)+'</span><span>正在调用 '+active.length+' 项</span><span>已返回或复用 '+finished.length+' 项</span><span>最近更新 '+(p.updated?new Date(p.updated*1000).toLocaleTimeString():'等待记录')+'</span></div><p class="help">当前动作：'+esc(p.phase||'等待执行')+'</p>'+(active.length?'<div class="generation-active">'+active.map(t=>'<div title="'+esc(t.name)+'">'+esc(taskLabel(t.name))+' · '+duration(t.elapsed_seconds||0)+'</div>').join('')+'</div>':'')+'<details class="generation-requests"><summary>调用记录（'+tasks.length+'）</summary><div class="generation-table"><table><thead><tr><th>任务</th><th>状态</th><th>用时</th></tr></thead><tbody>'+tasks.map(t=>'<tr><td title="'+esc(t.name)+'">'+esc(taskLabel(t.name))+'</td><td>'+esc(taskStates[t.status]||t.status)+'</td><td>'+duration(t.elapsed_seconds||0)+'</td></tr>').join('')+'</tbody></table></div></details></section></div>';
}
export function systemMarkup(s){
 const gb=n=>n==null?'未记录':(n/1024**3).toFixed(1)+' GB',p=s.profile;
 return '<strong>当前执行环境</strong><span>'+esc(s.platform)+' · Python '+esc(s.python)+' · '+s.cpu_count+' CPU</span><span>可用内存 '+gb(s.memory.available_bytes)+' / '+gb(s.memory.total_bytes)+'</span><span>可用磁盘 '+gb(s.disk.free_bytes)+'</span><span>写作 '+esc(s.models.writing.model)+' '+esc(s.models.writing.effort)+' · 并发 '+p.writing_calls+'</span><span>翻译 Flash 非推理 · 并发 '+p.translation_calls+'</span><span>承接 '+p.bridge_batch_sections+' 节/批 × '+p.bridge_calls+' 路 · 修复 '+p.repair_calls+' 路</span><span>'+esc(s.project_scheduling)+'</span>';
}
