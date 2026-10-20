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
    return '<div class="table-wrap"><table class="fields"><thead><tr><th>字段</th><th>类型</th><th>解释</th><th>案例</th><th>规则</th><th>路径</th></tr></thead><tbody>'+stage.fields.map(f=>'<tr class="field-row" tabindex="0" data-side="'+esc(f.side)+'" data-field="'+esc(f.key)+'"><td><small>'+esc(f.side)+'</small><code>'+esc(f.path)+'</code></td><td>'+esc(f.type)+'</td><td>'+esc(f.description)+'</td><td>'+part(f,true)+'</td><td>'+esc(f.rule)+'</td><td><code>$.'+esc(f.path)+'</code><small class="artifact-file">'+esc(f.file)+'</small></td></tr>').join('')+'</tbody></table></div>';
  }
  function preview(stage) {
    const fields = stage.fields;
    if (stage.id === '09') {
      const get = (sid, ending) => data.stages.find(s=>s.id===sid)?.fields.find(f=>f.key.endsWith(':'+ending));
      const columns = [['目录',get('03','title')],['原文与译文',get('01.1','content')],['讲解',get('04','explanation[0].claim')],['术语表',get('06','professional_definition.genus')]];
      return '<div class="reader-wrap"><div class="render-label">当前数据在四栏阅读器中的位置</div><div class="reader-grid">'+columns.map(([name,f])=>'<div class="reader-cell"><h4>'+fixed(name)+'</h4>'+(f?part(f):'<span class="muted">尚未生成</span>')+'</div>').join('')+'</div></div>'+(data.reader_url?'<p class="reader-link"><a href="'+esc(data.reader_url)+'" target="_blank" rel="noopener">打开这个版本的完整读本 ↗</a></p>':'');
    }
    return '<div class="render-row">'+['输入','输出'].map(side=>'<div class="render-box"><div class="render-label" tabindex="0" data-group="'+side+'">'+side+'怎样显示</div><div class="render-body">'+fields.filter(f=>f.side===side).map(f=>'<div class="preview-field" data-side="'+side+'"><h4>'+fixed(f.label)+'</h4>'+part(f)+'</div>').join('')+'</div></div>').join('')+'</div>'+(stage.id==='01.1'&&data.material_image?'<img class="live-material" loading="lazy" src="'+esc(data.material_image)+'" alt="当前项目保存的原材料预览">':'')+(stage.id==='04'&&data.legacy_unit?'<p class="legacy-notice">当前书稿使用旧结构，正文没有重写，新字段保留未生成状态，可在阅读入口审核现有正文</p>':'');
  }
  function runtime(stage) {
    const measured = stage.metrics.filter(m=>m.wall_seconds !== null || m.calls);
    return '<span class="stage-status">'+esc(stage.status)+'</span>'+stage.coverage.map(c=>'<span>'+esc(c.label)+'：'+(c.numerator===null||c.numerator===undefined?'未记录':esc(c.numerator))+' / '+(c.denominator===null||c.denominator===undefined?'未记录':esc(c.denominator))+(c.percentage===null?'':' · '+esc(c.percentage)+'%')+' · 目标 '+esc(c.target)+'</span>').join('')+measured.map(m=>'<span>'+esc(m.label)+'：'+(m.wall_seconds===null?'用时未记录':Math.round(m.wall_seconds)+' 秒')+' · 调用 '+m.calls+' 次 · 修复 '+m.repair_calls+' 次'+(m.historical_estimate?' · 时间按旧文件推算':'')+'</span>').join('');
  }
  async function renderGraphs() {
    graphs = graphs.then(async()=>{
      window.mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',fontFamily:'system-ui, Microsoft YaHei, sans-serif',themeVariables:{primaryColor:dark?'#303030':'#eeeeec',primaryTextColor:dark?'#eeeeee':'#232321',primaryBorderColor:dark?'#686868':'#aaa9a4',lineColor:dark?'#b8b8b8':'#72726c',edgeLabelBackground:dark?'#1b1b1b':'#f7f7f5'},flowchart:{htmlLabels:false,curve:'linear',useMaxWidth:true}});
      await window.mermaid.run({nodes:document.querySelectorAll('.mermaid:not([data-processed])')});
      for (const stage of data.stages) {
        const section=$('stage-'+stage.id);
        for(const node of stage.nodes||[]) {
          const el=[...section.querySelectorAll('.node')].find(el=>el.id.startsWith('flowchart-'+node.id+'-'));
          if(el){el.dataset.fields=JSON.stringify(node.field_keys);el.setAttribute('tabindex','0');el.setAttribute('role','img');el.setAttribute('aria-label',node.label);}
        }
      }
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
      const signature=JSON.stringify([stage.fields,stage.id==='01.1'?data.material_image:null,stage.id==='09'?data.reader_url:null]);
      if(previous.get(stage.id)!==signature){$('content-'+stage.id).innerHTML=table(stage)+preview(stage);previous.set(stage.id,signature);}
      const node=$('runtime-'+stage.id),html=runtime(stage);if(node.innerHTML!==html)node.innerHTML=html;
    }
    $('version').textContent='架构 v'+data.template_version+' · '+(data.using_example?'框架内的真实生成案例':!data.project?'后续生成使用当前约定':data.writing_contract_version==='legacy'?'现有正文保留旧版':'正文 v'+data.writing_contract_version)+(data.version?' · '+data.version:'')+(data.preview?' · 待审预览':'');
    $('project').options[0].textContent=data.using_example?'框架内置真实案例':'框架说明';
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
  function inspect(el){resetHover();if(!el)return;const section=el.closest('.stage'),hint=section?.querySelector('.field-hint');if(el.hasAttribute('data-fixed')){el.classList.add('is-active');if(hint)hint.textContent='模板固定文字';return;}const spec=data.stages.find(s=>'stage-'+s.id===section?.id);let keys=el.dataset.fields?JSON.parse(el.dataset.fields):el.dataset.group?spec.fields.filter(f=>f.side===el.dataset.group).map(f=>f.key):[el.dataset.field];section?.querySelectorAll('[data-field],[data-fields]').forEach(part=>{const own=part.dataset.fields?JSON.parse(part.dataset.fields):[part.dataset.field];if(own.some(k=>keys.includes(k)))part.classList.add(part.matches('tr')?'active-field':'is-active');});if(hint)hint.textContent=el.dataset.group?el.dataset.group+'字段与渲染同步高亮':keys.join(' ↔ ');}
  const inspectSelector='[data-field],[data-fields],[data-fixed],[data-group]';
  $('flow-main').addEventListener('mouseover',event=>inspect(event.target.closest(inspectSelector)));
  $('flow-main').addEventListener('mouseout',event=>{if(!event.relatedTarget?.closest?.(inspectSelector))resetHover();});
  $('flow-main').addEventListener('focusin',event=>inspect(event.target.closest(inspectSelector)));
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
