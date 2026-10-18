(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data, timer, loading = false, generation = 0, graphs = Promise.resolve();
  const previous = new Map();
  let dark = false;
  try { dark = (localStorage.getItem('lessonweave:theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark'; } catch {}
  document.body.classList.toggle('dark', dark);
  const labels = {'opening_title':'承上启下','problem.text':'问题段','explanation':'讲解段','synthesis.text':'升华段','glossary':'术语表','core_questions':'核心问题','premise':'前提','question':'问题','title':'标题','content':'材料','source':'来源位置','description':'应讲信息点','checks':'需要讲清的细节','explained':'已讲清标记','block_ids':'对应正文位置'};
  async function api(url) {
    const response = await fetch(url, {cache:'no-store'});
    if (!response.headers.get('content-type')?.includes('application/json')) throw Error('请重新登录后查看流程与架构');
    const value = await response.json();
    if (!response.ok) throw Error(value.error || '读取项目结果时遇到问题');
    return value;
  }
  function readable(text) {
    if (text === null) return '<span class="muted">尚未生成</span>';
    let value = text;
    try { value = JSON.parse(text); } catch {}
    function content(v) {
      if (v === null) return '空值';
      if (typeof v === 'boolean') return v ? '是' : '否';
      if (Array.isArray(v)) return v.length ? '<ul>' + v.slice(0,5).map(x=>'<li>'+content(x)+'</li>').join('') + '</ul>' + (v.length>5?'<p class="muted">另有 '+(v.length-5)+' 项，可打开完整产物查看</p>':'') : '<span class="muted">当前列表为空</span>';
      if (typeof v === 'object') {
        const main = v.text || v.display || v.title || v.description || v.name;
        if (main) return esc(main);
        return Object.entries(v).slice(0,6).map(([k,x])=>'<span class="value-item"><span class="muted">'+esc(k)+'：</span>'+content(x)+'</span>').join('');
      }
      return esc(v);
    }
    return content(value);
  }
  const part = (field, short=false) => '<span class="render-part" tabindex="0" data-field="'+esc(field.key)+'">'+(short && field.value?.length>200 ? esc(field.value.slice(0,200))+'…' : readable(field.value))+'</span>';
  const fixed = text => '<span class="render-part" tabindex="0" data-fixed>'+esc(text)+'</span>';
  function table(stage) {
    return '<div class="table-wrap"><table class="fields"><thead><tr><th>字段</th><th>类型</th><th>解释</th><th>案例</th><th>规则</th></tr></thead><tbody>'+stage.fields.map(f=>'<tr class="field-row" tabindex="0" data-field="'+esc(f.key)+'"><td><code>'+esc(f.path)+'</code>'+(f.file?'<small class="artifact-file">'+esc(f.file)+'</small>':'')+'</td><td>'+esc(f.type)+'</td><td>'+esc(f.description)+'</td><td>'+part(f,true)+'</td><td>'+esc(f.rule)+'</td></tr>').join('')+'</tbody></table></div>';
  }
  function preview(stage) {
    const fields = stage.fields.filter(f=>f.value !== null);
    if (!fields.length) return '<div class="render-box"><div class="render-label">'+fixed('实际渲染')+'</div><div class="render-body muted">'+(data.project?'本阶段尚无可展示的产物':'选择项目后，这里显示实际材料和生成结果')+'</div></div>';
    if (stage.id === '07') {
      const get = (sid, ending) => data.stages.find(s=>s.id===sid)?.fields.find(f=>f.key.endsWith(':'+ending));
      const columns = [['目录',get('03','title')],['原文与译文',get('01','content')],['讲解',get('05','explanation')],['术语表',get('05','glossary')]];
      return '<div class="reader-wrap"><div class="render-label">当前数据在四栏阅读器中的位置</div><div class="reader-grid">'+columns.map(([name,f])=>'<div class="reader-cell"><h4>'+fixed(name)+'</h4>'+(f?part(f):'<span class="muted">尚未生成</span>')+'</div>').join('')+'</div></div>'+(data.reader_url?'<p class="reader-link"><a href="'+esc(data.reader_url)+'" target="_blank" rel="noopener">打开这个版本的完整读本 ↗</a></p>':'');
    }
    return '<div class="render-box"><div class="render-label">'+fixed('实际渲染')+'</div><div class="render-body">'+fields.map(f=>'<div class="preview-field"><h4>'+fixed(labels[f.key.split(':').slice(2).join(':')]||f.description)+'</h4>'+part(f)+'</div>').join('')+(stage.id==='01' && data.material_image?'<img class="live-material" loading="lazy" src="'+esc(data.material_image)+'" alt="当前项目保存的原材料预览">':'')+'</div></div>';
  }
  function runtime(stage) {
    const measured = stage.metrics.filter(m=>m.wall_seconds !== null || m.calls);
    return '<span class="stage-status">'+esc(stage.status)+'</span>'+stage.coverage.map(c=>'<span>'+esc(c.label)+'：'+(c.numerator===null||c.numerator===undefined?'未记录':esc(c.numerator))+' / '+(c.denominator===null||c.denominator===undefined?'未记录':esc(c.denominator))+(c.percentage===null?'':' · '+esc(c.percentage)+'%')+' · 目标 '+esc(c.target)+'</span>').join('')+measured.map(m=>'<span>'+esc(m.label)+'：'+(m.wall_seconds===null?'用时未记录':Math.round(m.wall_seconds)+' 秒')+' · 调用 '+m.calls+' 次 · 修复 '+m.repair_calls+' 次'+(m.historical_estimate?' · 时间按旧文件推算':'')+'</span>').join('');
  }
  async function renderGraphs() {
    graphs = graphs.then(async()=>{
      window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',fontFamily:'system-ui, Microsoft YaHei, sans-serif',themeVariables:{primaryColor:dark?'#303030':'#eeeeec',primaryTextColor:dark?'#eeeeee':'#232321',primaryBorderColor:dark?'#686868':'#aaa9a4',lineColor:dark?'#b8b8b8':'#72726c',edgeLabelBackground:dark?'#1b1b1b':'#f7f7f5'},flowchart:{htmlLabels:false,curve:'linear',useMaxWidth:true}});
      await window.mermaid.run({nodes:document.querySelectorAll('.mermaid:not([data-processed])')});
      document.documentElement.dataset.ready='true';
    }).catch(error=>{$('update').textContent='流程图读取失败：'+error.message;});
    return graphs;
  }
  function render(value, reset=false) {
    data = value;
    if (reset || !$('stage-00')) {
      previous.clear();
      $('flow-nav').innerHTML=data.stages.map(s=>'<button type="button" data-stage="'+s.id+'"><span class="num">'+s.id+'</span><span>'+esc(s.name)+'</span></button>').join('');
      $('flow-main').innerHTML=data.stages.map(s=>'<section class="stage" id="stage-'+s.id+'"><div class="stage-heading"><span>'+s.id+'</span><h2>'+esc(s.name)+'</h2></div><p class="stage-note">'+esc(s.note)+'</p><p class="implementation"><code>'+esc(s.directory)+'</code><a href="/api/architecture/rule?stage='+s.id+'" target="_blank" rel="noopener">查看实际规则与实现 ↗</a></p><div class="diagram"><pre class="mermaid">'+esc(s.diagram)+'</pre></div><div class="stage-runtime" id="runtime-'+s.id+'"></div><div class="stage-content" id="content-'+s.id+'"></div><div class="field-hint" aria-live="polite"></div></section>').join('');
      renderGraphs();
    }
    for (const stage of data.stages) {
      const signature=JSON.stringify([stage.fields,stage.id==='01'?data.material_image:null,stage.id==='07'?data.reader_url:null]);
      if(previous.get(stage.id)!==signature){$('content-'+stage.id).innerHTML=table(stage)+preview(stage);previous.set(stage.id,signature);}
      const node=$('runtime-'+stage.id),html=runtime(stage);if(node.innerHTML!==html)node.innerHTML=html;
    }
    $('version').textContent='模板 v'+data.template_version+' · '+data.framework_release+(data.version?' · '+data.version:'')+(data.preview?' · 待审预览':'');
    $('update').textContent=(data.project?data.project.name+' · ':'')+(data.active?'任务运行中，每 3 秒读取进度':'已读取当前结果')+' · '+new Date(data.generated_at*1000).toLocaleTimeString();
    $('back').href='/workspace'+(data.project?'?project='+encodeURIComponent(data.project.id):'');
    markStage();
  }
  async function refresh(reset=false) {
    if(loading)return;
    loading=true;clearTimeout(timer);const mine=generation;
    try{const value=await api('/api/architecture'+($('project').value?'?project='+encodeURIComponent($('project').value):''));if(mine===generation)render(value,reset);}
    catch(error){$('update').textContent=error.message;}
    finally{loading=false;if(mine===generation&&data?.active&&!document.hidden)timer=setTimeout(()=>refresh(),3000);}
  }
  function resetHover(){document.querySelectorAll('.active-field,.is-active').forEach(el=>el.classList.remove('active-field','is-active'));document.querySelectorAll('.field-hint').forEach(el=>el.textContent='');}
  function inspect(el){resetHover();if(!el)return;const stage=el.closest('.stage'),hint=stage?.querySelector('.field-hint');if(el.hasAttribute('data-fixed')){el.classList.add('is-active');if(hint)hint.textContent='模板固定文字';return;}document.querySelectorAll('[data-field]').forEach(part=>{if(part.dataset.field===el.dataset.field)part.classList.add(part.matches('tr')?'active-field':'is-active');});if(hint)hint.textContent=el.dataset.field;}
  $('flow-main').addEventListener('mouseover',event=>inspect(event.target.closest('[data-field],[data-fixed]')));
  $('flow-main').addEventListener('mouseout',event=>{if(!event.relatedTarget?.closest?.('[data-field],[data-fixed]'))resetHover();});
  $('flow-main').addEventListener('focusin',event=>inspect(event.target.closest('[data-field],[data-fixed]')));
  $('flow-main').addEventListener('focusout',resetHover);
  $('flow-nav').addEventListener('click',event=>{const button=event.target.closest('[data-stage]');if(button)$('stage-'+button.dataset.stage).scrollIntoView({block:'start'});});
  let tick=false;
  function markStage(){tick=false;let id='00';document.querySelectorAll('.stage').forEach(s=>{if(s.getBoundingClientRect().top<=105)id=s.id.slice(6);});document.querySelectorAll('[data-stage]').forEach(b=>{if(b.dataset.stage===id)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current');});}
  addEventListener('scroll',()=>{if(!tick){tick=true;requestAnimationFrame(markStage);}},{passive:true});
  $('project').onchange=async()=>{generation++;clearTimeout(timer);while(loading)await new Promise(resolve=>setTimeout(resolve,30));const url=new URL(location.href);if($('project').value)url.searchParams.set('project',$('project').value);else url.searchParams.delete('project');history.replaceState(null,'',url);await refresh(true);};
  $('refresh').onclick=()=>refresh();
  $('theme').onclick=()=>{dark=!dark;document.body.classList.toggle('dark',dark);try{localStorage.setItem('lessonweave:theme',dark?'dark':'light');}catch{}if(data){for(const s of data.stages)$('stage-'+s.id).querySelector('.diagram').innerHTML='<pre class="mermaid">'+esc(s.diagram)+'</pre>';renderGraphs();}};
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else refresh();});
  (async()=>{try{const projects=await api('/api/projects');for(const p of projects){const option=document.createElement('option');option.value=p.id;option.textContent=p.name;$('project').append(option);}const requested=new URL(location.href).searchParams.get('project');if(requested&&projects.some(p=>p.id===requested))$('project').value=requested;await refresh();}catch(error){$('update').textContent=error.message;}})();
})();
