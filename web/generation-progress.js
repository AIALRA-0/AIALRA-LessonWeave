const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const duration=s=>s<60?Math.round(s)+' 秒':Math.floor(s/60)+' 分 '+Math.round(s%60)+' 秒';
const states={done:'已完成',skipped:'无需执行',running:'正在处理',waiting:'等待处理'};
const taskStates={waiting:'等待调用',running:'正在生成',completed:'已返回',reused:'复用已有结果',failed:'已记录问题'};

export function progressMarkup(p,selected){
 const stages=p.stages||[],row=stages.find(r=>r.id===selected)||stages.find(r=>r.status==='running')||stages.find(r=>r.status==='waiting')||stages.at(-1);
 if(!row)return '<p class="help">正在读取阶段记录</p>';
 const tasks=p.tasks||[],active=tasks.filter(t=>t.status==='running'),finished=tasks.filter(t=>['completed','reused'].includes(t.status));
 const rows=tasks.map(t=>'<tr><td>'+esc(t.name)+'</td><td>'+esc(taskStates[t.status]||t.status)+'</td><td>'+duration(t.elapsed_seconds||0)+'</td></tr>').join('');
 return '<div class="generation-layout"><nav class="generation-stages" aria-label="生成阶段">'+stages.map((s,i)=>'<button type="button" data-stage="'+esc(s.id)+'" data-state="'+esc(s.status)+'" aria-current="'+(s.id===row.id?'step':'false')+'"><span class="stage-number">'+String(i+1).padStart(2,'0')+'</span><span>'+esc(s.label)+'<small>'+esc(states[s.status]||s.status)+(s.total!=null?' · '+s.done+' / '+s.total:'')+'</small></span></button>').join('')+'</nav><section class="generation-detail"><h3>'+esc(row.label)+'</h3><p>'+esc(row.detail||'按实际保存的产物更新进度')+'</p>'+(row.total!=null?'<p class="generation-count">'+row.done+' / '+row.total+' <span>项已完成</span></p><progress value="'+row.done+'" max="'+Math.max(1,row.total)+'" aria-label="'+esc(row.label)+'完成数"></progress>':'<p class="generation-state">'+esc(states[row.status]||row.status)+'</p>')+'<div class="generation-facts"><span>自提交起 '+duration(p.elapsed_seconds||0)+'</span><span>正在调用 '+active.length+' 项</span><span>已返回或复用 '+finished.length+' 项</span><span>最近收到记录 '+(p.updated?new Date(p.updated*1000).toLocaleTimeString():'等待记录')+'</span></div><p class="help">当前动作：'+esc(p.phase||'等待执行')+'</p>'+(active.length?'<p class="generation-active">'+active.map(t=>esc(t.name)+' · '+duration(t.elapsed_seconds||0)).join('<br>')+'</p>':'')+'<details class="generation-requests"><summary>查看全部 '+tasks.length+' 项调用记录</summary><div class="generation-table"><table><thead><tr><th>任务</th><th>状态</th><th>调用用时</th></tr></thead><tbody>'+rows+'</tbody></table></div></details></section></div>';
}

export function systemMarkup(s){
 const gb=n=>n==null?'未记录':(n/1024**3).toFixed(1)+' GB',p=s.profile;
 return '<strong>当前执行环境</strong><span>'+esc(s.platform)+' · Python '+esc(s.python)+' · '+s.cpu_count+' CPU</span><span>可用内存 '+gb(s.memory.available_bytes)+' / '+gb(s.memory.total_bytes)+'</span><span>可用磁盘 '+gb(s.disk.free_bytes)+'</span><span>写作 '+esc(s.models.writing.model)+' '+esc(s.models.writing.effort)+' · 并发 '+p.writing_calls+'</span><span>翻译 Flash 非推理 · 并发 '+p.translation_calls+'</span><span>承接 '+p.bridge_batch_sections+' 节/批 × '+p.bridge_calls+' 路 · 修复 '+p.repair_calls+' 路</span><span>'+esc(s.project_scheduling)+'</span>';
}
