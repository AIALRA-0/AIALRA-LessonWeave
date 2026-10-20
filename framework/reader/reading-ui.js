// 布局和外观沿用已确认的 UI-04，正文、来源和笔记继续读取当前案例
(() => {
  const $ = id => document.getElementById(id);
  const names = {directory:'目录',source:'原文与译文',glossary:'术语表'};
  const panes = Object.fromEntries([...document.querySelectorAll('[data-pane]')].map(el=>[el.dataset.pane,el]));
  const defaults = {version:1,theme:'light',widths:{directory:224,source:420,glossary:272},visible:{directory:true,source:true,glossary:true},body:17,line:1.95,focus:false};
  const key = 'aialra:reader-ui:v1';
  let state = structuredClone(defaults), tokens, current = {}, drawer = null, trigger = null, dragging = null, initialized = false, frame = 0;
  let tooltipTimer, peekOpenTimer, peekCloseTimer, peekTarget = null, pinnedDrawer = false, restoringDrawerFocus=false;
  try { const old=JSON.parse(localStorage.getItem(key)); if(old?.version===1) state={...state,...old,widths:{...state.widths,...old.widths},visible:{...state.visible,...old.visible}}; } catch {}
  if(['light','dark'].includes(window.LESSONWEAVE_THEME))state.theme=window.LESSONWEAVE_THEME;
  for(const name of Object.keys(names)) state.widths[name]=Math.max(180,Math.min(name==='source'?840:560,Number(state.widths[name])||defaults.widths[name]));
  state.body=Math.max(16,Math.min(21,Number(state.body)||17));
  state.line=Math.max(1.65,Math.min(2.2,Number(state.line)||1.95));
  state.focus=false;
  document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=uiIcon(el.dataset.icon));
  function message(text){$('ui-status').textContent=text;}
  function save(){try{localStorage.setItem(key,JSON.stringify(state));message('布局已保存到此浏览器')}catch{message('当前设置保留在本次会话中，浏览器存储写入失败')}}
  function theme(){
    const name=state.theme==='dark'?'dark':'light';document.documentElement.dataset.theme=name;
    for(const [role,value] of Object.entries(tokens?.[name]||{})) document.documentElement.style.setProperty('--'+role.replace(/[A-Z]/g,c=>'-'+c.toLowerCase()),value);
    $('toggle-theme').innerHTML=uiIcon(name==='dark'?'sun':'moon');$('toggle-theme').setAttribute('aria-label',name==='dark'?'切换浅色主题':'切换深色主题');
    document.documentElement.style.setProperty('--body-size',state.body+'px');document.documentElement.style.setProperty('--body-line',state.line);
    $('body-size').value=state.body;$('body-size-value').value=state.body+' px';$('line-height').value=state.line;$('line-height-value').value=state.line.toFixed(2);
  }
  function queueLayout(){cancelAnimationFrame(frame);frame=requestAnimationFrame(layout);}
  function layout(){
    const available=$('reader-shell').clientWidth;current={...state.visible};
    if(state.focus||innerWidth<900) Object.keys(current).forEach(p=>current[p]=false);
    const gap=parseFloat(getComputedStyle($('reader-shell')).columnGap)||0;
    const budget=()=>Object.entries(current).reduce((n,[p,on])=>n+(on?state.widths[p]+gap:0),0)+560;
    for(const p of ['directory','glossary','source'])if(budget()>available)current[p]=false;
    const cols=[];
    for(const p of ['directory','source'])if(current[p])cols.push(state.widths[p]+'px');
    cols.push('minmax(0,1fr)');if(current.glossary)cols.push(state.widths.glossary+'px');
    $('reader-shell').style.setProperty('--columns',cols.join(' '));
    for(const [p,el]of Object.entries(panes)) el.dataset.uiVisible=p==='lesson'||!!current[p];
    for(const button of document.querySelectorAll('[data-toggle-pane]')){
      const p=button.dataset.togglePane;const visible=!!current[p]||drawer===p;
      button.setAttribute('aria-pressed',visible);button.setAttribute('aria-label',(visible?'隐藏':'打开')+names[p]);
    }
    $('focus-reading').setAttribute('aria-pressed',state.focus);$('focus-reading').setAttribute('aria-label',state.focus?'恢复对照阅读':'进入专注阅读');
    $('layout-status').textContent=state.focus?'专注阅读':`${1+Object.values(current).filter(Boolean).length} 栏阅读`;
    positionResizers();
  }
  function positionResizers(){
    const base=$('reader-shell').getBoundingClientRect();
    for(const el of document.querySelectorAll('[data-resize-pane]')){
      const p=el.dataset.resizePane;el.hidden=!current[p]||!!drawer;
      if(el.hidden)continue;const r=panes[p].getBoundingClientRect();
      el.style.left=(p==='glossary'?r.left-base.left-14:r.right-base.left+2)+'px';
      el.setAttribute('aria-valuemin',p==='directory'?180:240);el.setAttribute('aria-valuemax',Math.floor(maxWidth(p)));el.setAttribute('aria-valuenow',Math.round(r.width));
    }
  }
  function maxWidth(p){
    const others=Object.entries(current).reduce((n,[name,on])=>n+(on&&name!==p?state.widths[name]+16:0),0);
    return Math.min(p==='source'?840:600,$('reader-shell').clientWidth-others-16-560);
  }
  function closeDrawer(restore=true){
    clearTimeout(peekOpenTimer);clearTimeout(peekCloseTimer);peekTarget=null;
    if(!drawer)return;const p=drawer;panes[p].classList.remove('ui-drawer');panes[p].removeAttribute('role');panes[p].removeAttribute('aria-modal');
    drawer=null;pinnedDrawer=false;$('drawer-backdrop').hidden=true;
    for(const el of [...Object.values(panes),document.querySelector('.demo-masthead')])el.inert=false;
    layout();const returnTo=trigger;trigger=null;if(restore&&returnTo?.isConnected){restoringDrawerFocus=true;returnTo.focus({preventScroll:true});restoringDrawerFocus=false;}
    document.dispatchEvent(new CustomEvent('reading:clear-preview',{detail:{pane:p}}));
  }
  function openDrawer(p,modal=false,source=null){
    if(current[p])return;
    if(drawer&&drawer!==p)closeDrawer(false);
    const wasPinned=drawer===p&&pinnedDrawer;
    drawer=p;pinnedDrawer=modal||wasPinned;trigger=source||trigger;
    panes[p].classList.add('ui-drawer');
    if(modal){
      $('drawer-backdrop').hidden=false;panes[p].setAttribute('role','dialog');panes[p].setAttribute('aria-modal','true');
      for(const [name,el] of Object.entries(panes))el.inert=name!==p;
      document.querySelector('.demo-masthead').inert=true;
      (panes[p].querySelector('button,input,select,a')||panes[p]).focus({preventScroll:true});
    }
    layout();
  }
  document.querySelectorAll('[data-toggle-pane]').forEach(button=>button.addEventListener('click',()=>{
    const p=button.dataset.togglePane;
    if(drawer===p){closeDrawer();return;}
    if(current[p]){state.visible[p]=false;layout();save();return;}
    if(!state.visible[p]){state.visible[p]=true;layout();save();if(current[p])return;}
    openDrawer(p,true,button);
  }));
  document.querySelectorAll('[data-close-pane]').forEach(button=>button.addEventListener('click',()=>{
    const p=button.dataset.closePane;if(drawer===p)closeDrawer();else{state.visible[p]=false;layout();save();}
  }));
  $('drawer-backdrop').onclick=()=>closeDrawer();
  $('focus-reading').onclick=()=>{closeDrawer(false);state.focus=!state.focus;layout();save();};
  $('toggle-theme').onclick=()=>{state.theme=state.theme==='light'?'dark':'light';theme();save();};
  $('open-settings').onclick=()=>{$('ui-tooltip').hidden=true;$('reading-settings').showModal();$('body-size').focus();};
  $('reading-settings').addEventListener('close',()=>{$('open-settings').focus({preventScroll:true});save();});
  $('body-size').oninput=event=>{state.body=Number(event.target.value);theme();};
  $('line-height').oninput=event=>{state.line=Number(event.target.value);theme();};
  $('reset-layout').onclick=()=>{state={...structuredClone(defaults),theme:state.theme};closeDrawer(false);theme();layout();save();};
  // 拖动与方向键使用同一份宽度状态，取消拖动时恢复起点，完成后才保存
  for(const el of document.querySelectorAll('[data-resize-pane]')){
    const p=el.dataset.resizePane;
    el.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;el.setPointerCapture(event.pointerId);dragging={p,el,x:event.clientX,width:state.widths[p],saved:{...state.widths}};document.body.classList.add('is-resizing');event.preventDefault();
    });
    el.addEventListener('pointermove',event=>{if(dragging?.el!==el)return;const change=(event.clientX-dragging.x)*(p==='glossary'?-1:1);state.widths[p]=Math.round(Math.max(p==='directory'?180:240,Math.min(maxWidth(p),dragging.width+change)));queueLayout();});
    const finish=cancel=>{if(dragging?.el!==el)return;if(cancel)state.widths=dragging.saved;dragging=null;document.body.classList.remove('is-resizing');layout();if(!cancel)save();};
    el.addEventListener('pointerup',()=>finish(false));el.addEventListener('pointercancel',()=>finish(true));
    el.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const min=p==='directory'?180:240;let amount=(event.shiftKey?32:16)*(event.key==='ArrowRight'?1:-1)*(p==='glossary'?-1:1);state.widths[p]=event.key==='Home'?min:event.key==='End'?maxWidth(p):Math.max(min,Math.min(maxWidth(p),state.widths[p]+amount));layout();save();});
    el.addEventListener('dblclick',()=>{state.widths[p]=defaults.widths[p];layout();save();});
  }
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'){
      if(dragging){state.widths=dragging.saved;dragging=null;document.body.classList.remove('is-resizing');layout();event.preventDefault();event.stopImmediatePropagation();return;}
      if(!$('ui-tooltip').hidden){$('ui-tooltip').hidden=true;event.preventDefault();event.stopImmediatePropagation();return;}
      if(drawer){closeDrawer();event.preventDefault();event.stopImmediatePropagation();}
    }
    if(event.key==='Tab'&&drawer&&pinnedDrawer){
      const els=[...panes[drawer].querySelectorAll('button,a[href],input,select,textarea,summary,[tabindex="0"]')].filter(el=>el.getClientRects().length&&!el.disabled);
      const first=els[0],last=els.at(-1);if(event.shiftKey&&document.activeElement===first){last.focus();event.preventDefault();}else if(!event.shiftKey&&document.activeElement===last){first.focus();event.preventDefault();}
    }
  },true);
  // 临时面板只响应有停留意图的鼠标，关闭计时只在回到对应入口或面板时取消
  const peekEntry=target=>target instanceof Element?target.closest('.inline-term,.source-marker'):null;
  const entryPane=el=>el?.classList.contains('inline-term')?'glossary':'source';
  function schedulePeekClose(){
    clearTimeout(peekCloseTimer);
    peekCloseTimer=setTimeout(()=>{
      if(!drawer||pinnedDrawer)return;
      const hovered=[...document.querySelectorAll('.inline-term:hover,.source-marker:hover')].some(el=>entryPane(el)===drawer);
      const focused=document.activeElement?.matches(':focus-visible')&&(panes[drawer].contains(document.activeElement)||peekEntry(document.activeElement)&&entryPane(document.activeElement)===drawer);
      if(!panes[drawer].matches(':hover')&&!hovered&&!focused)closeDrawer(false);
    },300);
  }
  document.addEventListener('pointerover',event=>{
    if(event.pointerType!=='mouse'||!matchMedia('(hover:hover) and (pointer:fine)').matches)return;
    const entry=peekEntry(event.target);
    if(drawer&&panes[drawer].contains(event.target)){clearTimeout(peekCloseTimer);return;}
    if(!entry)return;
    const p=entryPane(entry);if(current[p])return;
    if(entry.contains(event.relatedTarget))return;
    if(drawer===p)clearTimeout(peekCloseTimer);
    clearTimeout(peekOpenTimer);peekTarget=entry;
    peekOpenTimer=setTimeout(()=>{if(entry===peekTarget&&entry.matches(':hover')&&!pinnedDrawer)openDrawer(p,false,entry);},240);
  });
  document.addEventListener('pointerout',event=>{
    const entry=peekEntry(event.target);
    if(entry&&!entry.contains(event.relatedTarget)){clearTimeout(peekOpenTimer);peekTarget=null;}
    if(drawer)schedulePeekClose();
  });
  document.addEventListener('focusin',event=>{
    const entry=peekEntry(event.target);
    if(!restoringDrawerFocus&&entry&&entry.matches(':focus-visible')){clearTimeout(peekCloseTimer);openDrawer(entryPane(entry),false,entry);}
  });
  document.addEventListener('focusout',()=>{if(drawer)schedulePeekClose();});
  document.addEventListener('click',event=>{
    const entry=peekEntry(event.target);if(!entry)return;
    clearTimeout(peekOpenTimer);
    // 阅读器先更新查询内容，再把点击打开的窄屏面板保持为可明确关闭的对话框
    queueMicrotask(()=>openDrawer(entryPane(entry),true,entry));
  },true);
  const tooltip=$('ui-tooltip');
  function showTooltip(el){
    clearTimeout(tooltipTimer);const text=el.dataset.tooltip;if(!text||el.matches('select:open'))return;
    const host=el.closest('dialog[open]')||document.body;if(tooltip.parentElement!==host)host.append(tooltip);
    const pane=el.closest('.demo-reading-pane,dialog[open]'),bounds=pane?.getBoundingClientRect();
    const left=Math.max(8,bounds?.left||8),right=Math.min(innerWidth-8,bounds?.right||innerWidth-8);
    tooltip.style.width=Math.max(100,Math.min(440,right-left-12))+'px';tooltip.style.maxWidth=tooltip.style.width;
    tooltip.textContent=text;tooltip.hidden=false;const r=el.getBoundingClientRect(),t=tooltip.getBoundingClientRect();
    tooltip.style.left=Math.max(left,Math.min(right-t.width,r.left))+'px';tooltip.style.top=Math.max(8,Math.min(innerHeight-t.height-8,r.bottom+7))+'px';el.setAttribute('aria-describedby','ui-tooltip');
  }
  document.addEventListener('pointerover',event=>{const el=event.target.closest('[data-tooltip]');if(el)showTooltip(el);});
  function preparePicker(select){
    closedLabel(select);
    tooltip.hidden=true;
    const pane=select.closest('.demo-reading-pane,dialog[open]'),rect=pane?.getBoundingClientRect();
    select.style.setProperty('--reader-picker-width',Math.max(100,Math.min(innerWidth-24,rect?rect.width-16:560))+'px');
    select.style.setProperty('--reader-picker-left',Math.max(8,rect?rect.left+8:8)+'px');
    const choice=select.getBoundingClientRect(),below=innerHeight-choice.bottom-12,above=choice.top-12;
    const height=Math.min(330,Math.max(below,above));
    select.style.setProperty('--reader-picker-top',(below>=Math.min(180,above)?choice.bottom+4:Math.max(8,choice.top-height-4))+'px');
    select.style.setProperty('--reader-picker-height',Math.max(80,height)+'px');
  }
  function closedLabel(select){
    if(!CSS.supports('appearance','base-select')||select.querySelector(':scope>button'))return;
    const button=document.createElement('button'),label=document.createElement('selectedcontent');
    button.type='button';button.append(label);select.prepend(button);
  }
  document.addEventListener('pointerdown',event=>{const select=event.target.closest('select');if(select)preparePicker(select);},true);
  document.addEventListener('focusin',event=>{const select=event.target.closest('select');if(select)preparePicker(select);const el=event.target.closest('[data-tooltip]');if(el&&el.matches(':focus-visible'))showTooltip(el);});
  function hideTooltip(){tooltipTimer=setTimeout(()=>{if(!tooltip.matches(':hover'))tooltip.hidden=true;},120);}
  document.addEventListener('pointerout',event=>{if(event.target.closest('[data-tooltip]'))hideTooltip();});
  document.addEventListener('focusout',hideTooltip);tooltip.onpointerenter=()=>clearTimeout(tooltipTimer);tooltip.onpointerleave=hideTooltip;
  document.querySelectorAll('dialog').forEach(dialog=>dialog.addEventListener('close',()=>{if(dialog.contains(tooltip)){tooltip.hidden=true;document.body.append(tooltip);}}));
  document.addEventListener('click',event=>{
    if(event.target.closest('.icon-button'))tooltip.hidden=true;
    const media=event.target.closest('.writing-source-figure img,.demo-source-figure img,.source-region-image');
    if(!media)return;
    event.preventDefault();event.stopPropagation();const img=media.matches('img')?media:media.querySelector('image');const url=img?.src||img?.getAttribute('href');
    if(!url)return;const full=new Image();full.src=url;full.alt=img.alt||'完整原图';$('image-stage').replaceChildren(full);$('image-viewer').showModal();
  },true);
  $('image-viewer').querySelector('button').onclick=()=>$('image-viewer').close();
  $('image-viewer').addEventListener('click',event=>{if(event.target===$('image-viewer'))$('image-viewer').close();});
  function updateDocumentStatus(detail=window.ReaderSourceBridge?.getState()){
    if(!detail?.doc)return;
    const doc=detail.doc;
    $('current-section-context').textContent=doc.section_number+' · '+doc.core_questions.length+' 个核心问题';
    $('reading-location').textContent=doc.section_number;
    $('preview-indicator').hidden=!detail.preview;
    $('preview-indicator').textContent=doc.validation?.passed?'稿件预览':'待审预览';
    message((detail.preview?'完整稿预览 · ':'')+(doc.validation?.passed?'本节检查通过':doc.validation?.passed===false?'本节检查未通过':'本节审查待完成')+' · '+doc.core_questions.length+' 个核心问题');
  }
  function enhance(){
    if(initialized||!document.querySelector('.writing-unit')||!window.ReaderSourceBridge?.getState()?.ready)return;initialized=true;
    $('demo-title').dataset.tooltip=$('demo-title').textContent;
    
    
    const sourceChoice=$('source-unit-select');
    closedLabel(sourceChoice);
    const describeChoice=()=>{sourceChoice.dataset.tooltip=sourceChoice.selectedOptions[0]?.textContent||'';};
    sourceChoice.addEventListener('change',describeChoice);describeChoice();
    for(const el of document.querySelectorAll('.demo-outline-question,.demo-outline-section'))el.dataset.tooltip=el.textContent;
    const units=[...document.querySelectorAll('.writing-unit')];
    const unitLinks=[...document.querySelectorAll('.demo-outline-question')];
    const observer=new IntersectionObserver(entries=>{
      const active=entries.filter(e=>e.isIntersecting).sort((a,b)=>a.boundingClientRect.top-b.boundingClientRect.top)[0];if(!active)return;
      const index=units.indexOf(active.target);$('reading-location').textContent=active.target.querySelector('h3')?.textContent.split(' ')[0]||'';
      unitLinks.forEach((el,i)=>{el.classList.toggle('is-reading-current',i===index);if(i===index)el.setAttribute('aria-current','location');else el.removeAttribute('aria-current');});
    },{root:panes.lesson,rootMargin:'-55px 0px -60% 0px',threshold:0});units.forEach(el=>observer.observe(el));
    $('demo-outline').addEventListener('click',()=>{if(drawer==='directory')closeDrawer(false);});
    updateDocumentStatus();layout();
  }
  document.addEventListener('reading:document-ready',event=>{enhance();updateDocumentStatus(event.detail);});
  new ResizeObserver(queueLayout).observe($('reader-shell'));
  window.addEventListener('resize',queueLayout);
  fetch('/design-tokens.json').then(r=>r.json()).then(value=>{tokens=value;theme();layout();enhance();}).catch(()=>{theme();layout();message('已使用本地默认样式，设计参数文件读取失败');});
  window.readerUIState=()=>({preferences:structuredClone(state),visible:{...current},drawer});
  window.prototypeState=window.readerUIState;
  window.ReaderUI={setTheme:name=>{state.theme=name==='dark'?'dark':'light';theme();save();},openPane:(name,options={})=>{if(name==='lesson'){if(drawer)closeDrawer(false);}else if(panes[name])openDrawer(name,!!options.modal,options.trigger||null);},closeDrawer};
  theme();layout();enhance();
})();
