/* 新媒体只读取 guide 与素材字段，旧正文和用户笔记继续沿用原来的读取方式 */
window.LessonMedia=(()=>{
 const scriptBase=new URL('.',document.currentScript.src),loads=new Map();let diagramSerial=0,diagramQueue=Promise.resolve(),diagramInitialized=false;
 const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
 function describe(node,text){node.setAttribute('aria-label',text);node.dataset.tooltip=text;return node}
 function icon(tag,name,text){const node=describe(make(tag,undefined,'icon-button lw-media-action'),text);node.dataset.icon=name;node.innerHTML=window.uiIcon(name);if(tag==='button')node.type='button';return node}
 let activePin=null;
 function pinFigure(fig,button){
  if(activePin?.fig===fig){activePin.stop();return}
  activePin?.stop();
  const media=fig.closest('.lw-media'),article=media.closest('article,main')||document.body,pane=media.closest('.demo-explanation');
  const placeholder=make('div',undefined,'lw-media-pin-placeholder');placeholder.style.height=fig.getBoundingClientRect().height+'px';fig.before(placeholder);
  // 素材留在原来的 DOM 中，交互状态不变，占位块让后面的文字继续正常滚动
  let frame=0,stopped=false;
  const next=[...article.querySelectorAll('.lw-media,.writing-block[data-media-kind]')].find(node=>!node.contains(media)&&!media.contains(node)&&(media.compareDocumentPosition(node)&Node.DOCUMENT_POSITION_FOLLOWING)&&node.getBoundingClientRect().height>0);
  const stop=()=>{
   if(stopped)return;stopped=true;cancelAnimationFrame(frame);observer.disconnect();removed.disconnect();
   (pane||window).removeEventListener('scroll',schedule);window.removeEventListener('resize',schedule);window.removeEventListener('scroll',schedule,true);
   fig.classList.remove('is-pinned');for(const name of ['top','left','width'])fig.style.removeProperty(name);
   placeholder.remove();button.setAttribute('aria-pressed','false');describe(button,'固定素材，读后面的文字时保持置顶');if(activePin?.fig===fig)activePin=null;
  };
  const update=()=>{
   frame=0;if(!fig.isConnected||!placeholder.isConnected){stop();return}
   const bounds=pane?.getBoundingClientRect()||{top:0,bottom:innerHeight},head=pane?.querySelector('.pane-head');
   const top=Math.max(0,bounds.top)+(head?.offsetHeight||0)+6,box=placeholder.getBoundingClientRect();
   fig.style.top=top+'px';fig.style.left=box.left+'px';fig.style.width=box.width+'px';
   placeholder.style.height=fig.getBoundingClientRect().height+'px';
   // 下一份素材进入固定区下方时交还阅读空间，向回滚动到上一份素材也解除固定
   if(bounds.bottom<=top||box.top>=bounds.bottom||next?.getBoundingClientRect().top<=top+fig.getBoundingClientRect().height+18)stop();
  };
  const schedule=()=>{if(!frame&&!stopped)frame=requestAnimationFrame(update)};
  const observer=new ResizeObserver(schedule),removed=new MutationObserver(()=>{if(!fig.isConnected)stop()});
  observer.observe(placeholder);observer.observe(fig);if(pane)observer.observe(pane);removed.observe(article,{childList:true,subtree:true});
  fig.classList.add('is-pinned');button.setAttribute('aria-pressed','true');describe(button,'取消固定素材');activePin={fig,stop};
  (pane||window).addEventListener('scroll',schedule,{passive:true});window.addEventListener('resize',schedule);window.addEventListener('scroll',schedule,{capture:true,passive:true});update();
 }
 document.addEventListener('reading:document-ready',()=>activePin?.stop());
 const assetLabel={image:'图',table:'表',mermaid:'图',formula:'式',code:'代码',model:'模型',video:'视频',audio:'音频',interactive:'交互'};
 function load(name,path){if(!loads.has(name))loads.set(name,new Promise((resolve,reject)=>{if(window[name])return resolve();const s=make('script');s.src=new URL('media-vendor/'+path,scriptBase);s.onload=resolve;s.onerror=reject;document.head.append(s)}));return loads.get(name)}
 async function math(node,text,display=true){if(window.ReaderText)return ReaderText.math(node,text,display);await load('katex','katex/dist/katex.min.js');window.katex.render(text,node,{displayMode:display,throwOnError:false,trust:false,strict:'ignore'})}
 function rich(node,text){if(window.ReaderText)return ReaderText.rich(node,text);node.append(document.createTextNode(String(text??'')))}
 function p(text){const n=make('p');rich(n,String(text));return n}
 function par(value,node){for(const field of ['premise','action','result'])node.append(p(value[field]))}
 function section(title,parent){const s=make('section',undefined,'lw-media-part');s.append(make(parent.classList.contains('lw-media-code-segment')?'h6':'h5',title));parent.append(s);return s}
 function table(headers,rows){const wrap=make('div',undefined,'lw-media-table'),t=make('table'),head=make('tr');headers.forEach(x=>head.append(make('th',x)));const thead=make('thead');thead.append(head);t.append(thead);const body=make('tbody');rows.forEach(values=>{const row=make('tr');values.forEach(v=>row.append(make('td',v===null?'':String(v))));body.append(row)});t.append(body);wrap.append(t);return wrap}
 function genericBody(r,options){
  if(r.kind==='image'){const img=options.image?options.image(r):make('img');if(!options.image){img.src=options.path(r.asset);img.alt=r.alt}img.draggable=false;return img}
  if(r.kind==='formula'){const n=make('div',undefined,'lw-media-math');n.mediaReady=math(n,r.text);return n}
    if(r.kind==='table'){
      const content=table(r.headers,r.rows);
      if(r.attachment_asset){const link=icon('a','download','打开附件');link.href=options.path(r.attachment_asset);link.target='_blank';content.append(link);}
      return content;
    }
  if(r.kind==='mermaid'){const n=make('div',undefined,'lw-media-mermaid'),source=String(r.text);n.textContent=source;n.mediaReady=load('mermaid','mermaid.min.js').then(()=>{
   const job=diagramQueue.catch(()=>{}).then(async()=>{if(!diagramInitialized){mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',flowchart:{htmlLabels:false}});diagramInitialized=true}const result=await mermaid.render('lw-diagram-'+(++diagramSerial),source);n.innerHTML=result.svg;result.bindFunctions?.(n)});diagramQueue=job;return job;
  }).catch(()=>{n.replaceChildren(make('pre',source));n.dataset.renderError='true'});return n}
  if(r.kind==='audio'||r.kind==='video'){const group=make('div',undefined,'lw-media-playback'),player=make(r.kind);player.controls=true;player.preload='metadata';player.src=options.path(r.asset);if(r.kind==='video'){player.playsInline=true;if(r.poster)player.poster=options.path(r.poster)}group.append(player);if(r.cues?.length){const cues=make('div',undefined,'lw-media-cues');for(const cue of r.cues){const button=icon('button','play',cue.label);button.onclick=()=>{player.currentTime=cue.time;player.play()};cues.append(button)}group.append(cues)}return group}
  if(r.kind==='interactive'){const frame=make('iframe');frame.src=options.path(r.asset);frame.title=r.caption;frame.setAttribute('sandbox','allow-scripts');return frame}
  if(r.kind==='model')return model(r,options);
  // 历史稿中的附件继续使用原路径下载，界面保留真实检查状态
  if(r.asset){const link=make('a',String(r.asset).split('/').pop(),'lw-media-attachment');link.href=options.path(r.asset);link.download='';return link}
  return make('pre',r.text||'');
 }
 function model(r,options){const wrap=make('div',undefined,'lw-media-model'),canvas=make('canvas');canvas.tabIndex=0;canvas.setAttribute('aria-label',r.caption+'，拖动旋转，方向键调整视角');wrap.append(canvas);let yaw=-.6,pitch=.65,chosen=-1;
  const controls=make('div',undefined,'lw-media-model-controls'),select=make('select');select.setAttribute('aria-label','选择模型部件');select.append(new Option('完整模型','-1'));(r.parts||[]).forEach((part,i)=>select.append(new Option(part.label,String(i))));select.onchange=()=>{chosen=Number(select.value);draw()};controls.append(select,make('span','单位 '+r.unit));if(r.asset){const a=icon('a','external','打开原始模型');a.href=options.path(r.asset);a.target='_blank';controls.append(a)}wrap.append(controls);
  const points=r.vertices,center=[0,1,2].map(i=>(Math.min(...points.map(v=>v[i]))+Math.max(...points.map(v=>v[i])))/2),extent=Math.max(...points.map(v=>Math.hypot(...v.map((x,i)=>x-center[i]))),1);
  function draw(){const b=canvas.getBoundingClientRect();if(!b.width||!b.height)return;const d=devicePixelRatio||1;canvas.width=b.width*d;canvas.height=b.height*d;const c=canvas.getContext('2d');c.scale(d,d);const scale=Math.min(b.width,b.height)*.43/extent;
   const projected=points.map(v=>{const[x,y,z]=v.map((x,i)=>x-center[i]),a=x*Math.cos(yaw)-y*Math.sin(yaw),b=x*Math.sin(yaw)+y*Math.cos(yaw);return [canvas.clientWidth/2+a*scale,canvas.clientHeight/2+(Math.sin(pitch)*b-Math.cos(pitch)*z)*scale,Math.cos(pitch)*b+Math.sin(pitch)*z]});
   r.faces.map((face,index)=>({points:face.map(i=>projected[i]),index})).sort((a,b)=>a.points.reduce((s,p)=>s+p[2],0)/a.points.length-b.points.reduce((s,p)=>s+p[2],0)/b.points.length).forEach(face=>{c.beginPath();face.points.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.closePath();const selected=chosen<0||r.parts[chosen].face_indices.includes(face.index);c.globalAlpha=selected?1:.28;c.fillStyle=chosen>=0&&selected?'#91adbb':'#c9d3cd';c.fill();c.strokeStyle='#4a5c52';c.lineWidth=.8;c.stroke()});c.globalAlpha=1}
  let dragging;canvas.onpointerdown=e=>{dragging={x:e.clientX,y:e.clientY,yaw,pitch};canvas.setPointerCapture(e.pointerId)};canvas.onpointermove=e=>{if(dragging){yaw=dragging.yaw+(e.clientX-dragging.x)*.012;pitch=Math.max(-1.3,Math.min(1.3,dragging.pitch+(e.clientY-dragging.y)*.008));draw()}};canvas.onpointerup=canvas.onpointercancel=()=>dragging=null;canvas.onkeydown=e=>{if(e.key.startsWith('Arrow')){e.preventDefault();yaw+=e.key==='ArrowLeft'?-.12:e.key==='ArrowRight'?.12:0;pitch+=e.key==='ArrowUp'?-.1:e.key==='ArrowDown'?.1:0;draw()}};new ResizeObserver(draw).observe(canvas);return wrap}
 function codeBody(r){const outer=make('div',undefined,'lw-media-code-lines');r.text.trimEnd().split(/\r?\n/).forEach((line,i)=>{const row=make('div',undefined,'lw-media-code-row');row.dataset.line=i+1;row.append(make('span',String(i+1),'lw-media-line-number'),make('code',line));const note=r.guide.line_annotations.find(a=>a.line_start===i+1);row.append(make('span',note?.sentence||'','lw-media-line-note'));outer.append(row)});return outer}
 function viewer(r,options,body){
  const fig=make('figure',undefined,'lw-media-figure'),toolbar=make('div',undefined,'lw-media-toolbar'),stage=make('div',undefined,'lw-media-stage'),label=make('span','', 'lw-media-range'),expand=icon('button','expand','放大素材'),pin=icon('button','pin','固定素材，读后面的文字时保持置顶'),handle=make('div',undefined,'lw-media-height');
  pin.setAttribute('aria-pressed','false');pin.onclick=()=>pinFigure(fig,pin);
  handle.tabIndex=0;handle.setAttribute('role','separator');handle.setAttribute('aria-label','调整素材高度');stage.append(body);toolbar.append(label);
  const visual=['image','formula','mermaid'].includes(r.kind);let zoom=100,manual=false,fitOnce=()=>{};
  if(visual){
   const surface=make('div',undefined,'lw-media-surface'),spacer=make('div',undefined,'lw-media-spacer');surface.append(body);spacer.append(surface);stage.replaceChildren(spacer);
   const intrinsic=()=>{const svg=body.querySelector('svg[viewBox]');if(svg){const box=svg.viewBox.baseVal;svg.setAttribute('width',box.width);svg.setAttribute('height',box.height);svg.style.width=box.width+'px';svg.style.height=box.height+'px';svg.style.maxWidth='none'}};
   const scale=make('select');scale.setAttribute('aria-label','素材缩放比例');for(let i=10;i<=300;i+=10)scale.append(new Option(i+'%',i));scale.value='100';
   const apply=()=>{surface.style.transform='scale('+zoom/100+')';spacer.style.width=surface.offsetWidth*zoom/100+'px';spacer.style.height=surface.offsetHeight*zoom/100+'px';scale.value=String(zoom);fig.dataset.zoom=zoom};
   scale.onchange=()=>{manual=true;zoom=Number(scale.value);apply()};
   fitOnce=(resize=false)=>{
    intrinsic();const w=surface.offsetWidth,h=surface.offsetHeight,available=stage.clientWidth-16;
    if(!w||!h||available<=0)return false;
    if(resize){const chrome=toolbar.offsetHeight+caption.offsetHeight+handle.offsetHeight+18;const wanted=h*Math.min(3,available/w)+chrome;fig.style.setProperty('--lw-media-height',Math.max(136,Math.min(innerHeight*.58,450,wanted))+'px')}
    zoom=Math.max(10,Math.min(300,Math.floor(Math.min((stage.clientWidth-16)/w,(stage.clientHeight-16)/h)*100/10)*10));apply();stage.scrollLeft=0;stage.scrollTop=0;fig.dataset.fitted='true';return true;
   };
   const fit=icon('button','fit','适配素材大小');fit.onclick=()=>{manual=true;fitOnce(false)};toolbar.append(scale,fit);stage.classList.add('lw-media-visual');
   // 本体加载后只自动适配一次，后续缩放、拖动和高度调整交给读者
   const images=[...(body.matches('img')?[body]:[]),...body.querySelectorAll('img')];images.forEach(img=>img.loading='eager');
   Promise.all([body.mediaReady||Promise.resolve(),...images.map(img=>img.decode().catch(()=>{}))]).then(()=>document.fonts.ready).then(()=>requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(manual)return;if(fitOnce(true))return;
    const observer=new ResizeObserver(()=>{if(manual||fitOnce(true))observer.disconnect()});observer.observe(stage);
   })));
   let pan;stage.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse'&&e.button===0){manual=true;pan={x:e.clientX,y:e.clientY,left:stage.scrollLeft,top:stage.scrollTop};stage.setPointerCapture(e.pointerId)}});
   stage.addEventListener('pointermove',e=>{if(pan){stage.scrollLeft=pan.left+pan.x-e.clientX;stage.scrollTop=pan.top+pan.y-e.clientY}});stage.addEventListener('pointerup',()=>pan=null);stage.addEventListener('pointercancel',()=>pan=null);
  }
  if(r.kind==='code'){const notes=icon('button','notes','显示或隐藏行注');notes.setAttribute('aria-pressed','true');notes.onclick=()=>{const hidden=stage.classList.toggle('lw-hide-notes');notes.setAttribute('aria-pressed',String(!hidden))};toolbar.append(notes)}
  toolbar.append(pin,expand);const caption=make('figcaption',(assetLabel[r.kind]||'素材')+' '+options.prefix+'-'+(options.index||1)+'. '+r.caption);fig.append(toolbar,stage,caption,handle);fig.style.setProperty('--lw-media-height',r.kind==='code'?'310px':'290px');let drag;
  const resize=value=>{manual=true;fig.style.setProperty('--lw-media-height',Math.max(128,Math.min(innerHeight*.6,value))+'px')};
  handle.onpointerdown=e=>{e.preventDefault();manual=true;drag={y:e.clientY,height:fig.getBoundingClientRect().height};handle.setPointerCapture(e.pointerId)};handle.onpointermove=e=>{if(drag)resize(drag.height+e.clientY-drag.y)};handle.onpointerup=handle.onpointercancel=()=>drag=null;
  handle.onkeydown=e=>{if(['ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();resize(fig.getBoundingClientRect().height+(e.key==='ArrowUp'?-20:20))}};
  expand.onclick=()=>{activePin?.stop();const dialog=make('dialog',undefined,'lw-media-dialog'),bar=make('div',undefined,'lw-media-dialog-bar'),back=icon('button','close','返回阅读'),placeholder=make('div');
   const saved={zoom,left:stage.scrollLeft,top:stage.scrollTop,height:fig.style.getPropertyValue('--lw-media-height'),manual};
   placeholder.style.height=fig.getBoundingClientRect().height+'px';fig.replaceWith(placeholder);expand.hidden=true;pin.hidden=true;bar.append(toolbar,back);dialog.append(bar,fig);document.body.append(dialog);dialog.showModal();
   requestAnimationFrame(()=>{if(dialog.open)fitOnce(false)});
   const close=()=>{dialog.close();fig.prepend(toolbar);expand.hidden=false;pin.hidden=false;placeholder.replaceWith(fig);dialog.remove();fig.style.setProperty('--lw-media-height',saved.height);manual=saved.manual;
    if(visual){const select=toolbar.querySelector('select');select.value=String(saved.zoom);select.dispatchEvent(new Event('change'));manual=saved.manual}
    stage.scrollLeft=saved.left;stage.scrollTop=saved.top;expand.focus({preventScroll:true})};back.onclick=close;dialog.oncancel=e=>{e.preventDefault();close()}};
  return {fig,stage,label}
 }
 function render(resource,settings={}){const r=resource,options={prefix:'1',index:1,path:x=>x,...settings},root=make('section',undefined,'lw-media '+(r.kind==='code'?'lw-media-code':''));root.dataset.mediaId=r.id;root.dataset.mediaNumber=(assetLabel[r.kind]||'素材')+' '+options.prefix+'-'+options.index;
   if(r.attachment_role==='system_metadata'){root.classList.add('debug-only');const link=make('a','系统元数据：'+r.rows[0][0]);link.href=options.path(r.attachment_asset);root.append(link);return root;}
  const v=viewer(r,options,r.kind==='code'?codeBody(r):genericBody(r,options));root.append(v.fig);
  if(r.kind==='code'){
   const intro=section('综合综述',root);par(r.guide.overview,intro);
   if(r.runs.length)section('实际运行',root).append(table(['输入','输出'],r.runs.map(run=>[run.inputs,run.outputs])));
   const sections=[];r.guide.segments.forEach((segment,i)=>{const area=make('section',undefined,'lw-media-code-segment');area.dataset.start=segment.line_start;area.dataset.end=segment.line_end;const title=segment.title_premise.replace(/[，,；;？?\s]+$/,'')+'，'+segment.title_question;area.append(make('h5',title));par(segment.overview,section('综合讲解',area));
    const group=section('关键组分',area),componentTable=table(['所属对象','关键组分','类型','作用'],segment.components.map(item=>[item.owner,item.name+(item.default?'（默认 '+item.default+'）':''),item.type||'',item.purpose]));[...componentTable.querySelectorAll('tbody tr')].forEach((row,index)=>{const item=segment.components[index];row.tabIndex=0;row.onclick=()=>mark(item.line_start,item.line_end);row.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();mark(item.line_start,item.line_end)}}});group.append(componentTable);
    const logic=section('核心逻辑',area);segment.core_logic.forEach(item=>{logic.append(p(item.explanation));if(item.example)logic.append(p(item.example))});const takeaway=section('理解结论',area);takeaway.append(p(segment.takeaway.conclusion),p(segment.takeaway.relation_to_whole));root.append(area);sections.push(area)});
   section('综合总结',root).append(p(r.guide.summary.answer),p(r.guide.summary.collaboration));
   function mark(start,end){root.querySelectorAll('.lw-media-code-row').forEach(row=>row.classList.toggle('is-current',Number(row.dataset.line)>=start&&Number(row.dataset.line)<=end));v.label.textContent='第 '+start+(start!==end?'–'+end:'')+' 行';const first=root.querySelector('[data-line="'+start+'"]');if(first)v.stage.scrollTop+=first.getBoundingClientRect().top-v.stage.getBoundingClientRect().top-8}
   let active,frame;const track=()=>{frame=0;if(!root.isConnected||v.fig.closest('dialog'))return;const point=v.fig.getBoundingClientRect().bottom+22,chosen=sections.find(s=>{const box=s.getBoundingClientRect();return box.top<=point+35&&box.bottom>point});if(chosen&&chosen!==active){active=chosen;mark(Number(chosen.dataset.start),Number(chosen.dataset.end))}};root.addEventListener('scroll',()=>{if(!frame)frame=requestAnimationFrame(track)},true);document.addEventListener('scroll',()=>{if(root.isConnected&&!frame)frame=requestAnimationFrame(track)},true);
  }else{const guide=r.guide;section('阅读指引',root).append(p(guide.reading_guide));const list=make('ul',undefined,'lw-media-components');guide.components.forEach(component=>{const item=make('li'),label=make('span');if(component.math_label)math(label,component.label,false);else label.textContent=component.label;item.append(label,document.createTextNode('：'));rich(item,component.explanation);list.append(item)});section('关键组分',root).append(list);const explanation=section('具体讲解',root);guide.explanation.forEach(item=>{if(item.formula){const n=make('div',undefined,'lw-media-math');math(n,item.formula);explanation.append(n)}explanation.append(p(item.text))});section('理解结论',root).append(p(guide.takeaway))}
  return root}
 return {render,label:kind=>assetLabel[kind]||'素材'};
})();
