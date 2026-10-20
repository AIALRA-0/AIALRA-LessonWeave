// 材料模式与上下比例分别保存，切换时沿用当前材料、句子和缩放
(() => {
  const pane=document.getElementById('demo-original'),content=document.querySelector('.source-content');
  const text=document.getElementById('source-text-scroll'),locator=document.getElementById('source-locator'),bar=document.getElementById('source-splitter');
  const toggle=document.getElementById('source-view-toggle'),languages=document.getElementById('source-language-tools');
  if(!pane||!content||!text||!locator||!bar||!toggle)return;
  const viewKey='aialra:source-view:v1';
  let view='page-translation',ratio=.58,drag=null;
  const defaultRatio=()=>view==='page-translation'?.58:.5;
  const ratioKey=()=>view==='page-translation'?'aialra:source-split:page-translation:v1':'aialra:source-split:v1';
  const topPane=()=>view==='page-translation'?locator:text;
  const bottomPane=()=>view==='page-translation'?text:locator;
  try{if(localStorage.getItem(viewKey)==='text-original')view='text-original';}catch{}
  function loadRatio(){ratio=defaultRatio();try{const stored=Number(localStorage.getItem(ratioKey()));if(stored>=.1&&stored<=.9)ratio=stored;}catch{}}
  function apply(){content.style.setProperty('--source-upper-fr',(ratio/(1-ratio))+'fr');requestAnimationFrame(updateAria);}
  function limits(){
    const top=topPane(),bottom=bottomPane(),total=top.getBoundingClientRect().height+bottom.getBoundingClientRect().height;
    const minTop=Number.parseFloat(getComputedStyle(top).minHeight)||80,minBottom=Number.parseFloat(getComputedStyle(bottom).minHeight)||80;
    return {total,min:minTop/total,max:Math.max(minTop/total,1-minBottom/total)};
  }
  function updateAria(){
    const bounds=limits();if(!Number.isFinite(bounds.total)||bounds.total<=0)return;
    const actual=topPane().getBoundingClientRect().height/bounds.total;
    bar.setAttribute('aria-valuemin',Math.round(bounds.min*100));bar.setAttribute('aria-valuemax',Math.round(bounds.max*100));bar.setAttribute('aria-valuenow',Math.round(actual*100));
    bar.setAttribute('aria-valuetext',view==='page-translation'?'原页 '+Math.round(actual*100)+'%，中文译文 '+Math.round((1-actual)*100)+'%':'原文与译文 '+Math.round(actual*100)+'%，原文定位 '+Math.round((1-actual)*100)+'%');
  }
  function save(){try{localStorage.setItem(viewKey,view);localStorage.setItem(ratioKey(),String(ratio));}catch{document.getElementById('ui-status').textContent='材料模式和上下比例保留在本次会话中，浏览器存储写入失败';}}
  function setView(next,persist=true){
    if(drag)finish(true);
    view=next==='text-original'?'text-original':'page-translation';
    pane.dataset.sourceView=view;
    const pageFirst=view==='page-translation';
    document.getElementById('demo-original-title').textContent=pageFirst?'原页与译文':'原文与译文';
    toggle.innerHTML=uiIcon(pageFirst?'source':'book');
    toggle.dataset.tooltip=pageFirst?'原文对照':'原页与译文';
    toggle.setAttribute('aria-pressed',String(pageFirst));
    toggle.setAttribute('aria-label',pageFirst?'切换到原文与译文对照模式':'切换到原页与译文模式');
    if(languages)languages.hidden=pageFirst;
    bar.setAttribute('aria-label',pageFirst?'调整上方原页与下方译文的比例':'调整上方原文译文与下方原文定位的比例');
    // 按视觉顺序移动现有区域，保留句子节点和事件，让键盘阅读顺序同步改变
    document.dispatchEvent(new CustomEvent('reading:source-view-changing'));
    content.insertBefore(topPane(),bar);content.append(bottomPane());
    loadRatio();apply();if(persist)save();
    document.dispatchEvent(new CustomEvent('reading:source-view-change',{detail:{view}}));
  }
  function move(next){const bounds=limits();ratio=Math.max(bounds.min,Math.min(bounds.max,next));apply();}
  function finish(cancel){if(!drag)return;const start=drag.ratio;drag=null;document.body.classList.remove('is-source-resizing');if(cancel){ratio=start;apply();}else save();}
  toggle.addEventListener('click',()=>setView(view==='page-translation'?'text-original':'page-translation'));
  bar.addEventListener('pointerdown',event=>{
    if(event.button!==0)return;const bounds=limits();if(!bounds.total)return;
    drag={ratio,y:event.clientY,height:topPane().getBoundingClientRect().height,total:bounds.total};bar.setPointerCapture(event.pointerId);document.body.classList.add('is-source-resizing');event.preventDefault();
  });
  bar.addEventListener('pointermove',event=>{if(drag)move((drag.height+event.clientY-drag.y)/drag.total);});
  bar.addEventListener('pointerup',()=>finish(false));bar.addEventListener('pointercancel',()=>finish(true));
  window.addEventListener('keydown',event=>{if(event.key==='Escape'&&drag){finish(true);event.preventDefault();event.stopImmediatePropagation();}},true);
  bar.addEventListener('keydown',event=>{
    if(!['ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
    event.preventDefault();const bounds=limits(),actual=topPane().getBoundingClientRect().height/bounds.total;
    const step=(event.shiftKey?32:16)/bounds.total;
    move(event.key==='Home'?bounds.min:event.key==='End'?bounds.max:actual+(event.key==='ArrowDown'?step:-step));save();
  });
  bar.addEventListener('dblclick',()=>{ratio=defaultRatio();apply();save();});
  document.getElementById('reset-layout').addEventListener('click',()=>{setView('page-translation',false);ratio=defaultRatio();apply();save();});
  new ResizeObserver(updateAria).observe(content);new ResizeObserver(updateAria).observe(text);
  window.prototypeSourceSplit=()=>({ratio,actual:Number(bar.getAttribute('aria-valuenow')),dragging:!!drag,view});
  setView(view,false);
})();
