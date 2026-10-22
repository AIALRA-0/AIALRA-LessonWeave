import {mountReadWeave,sanitizeArticle} from './native-panel.js';

// 阅读器保留布局和生成快照，共享正文及交互从同一个原生笔记库读回
export function mountSharedReader(root,options){
 const find=id=>root.querySelector('#'+CSS.escape(id)),abort=new AbortController();
 const listen=(node,type,fn)=>node?.addEventListener(type,fn,{signal:abort.signal});
 const rawRequest=options.request??(async(path,init={})=>{
  const url=path.startsWith('lessonweave/')?'/api/shared/'+path.slice(12):'/api/'+path;
  const response=await fetch(url,{...init,credentials:'same-origin'});const value=await response.json();
  if(!response.ok){const error=Error(value.error||value.message||value.code||'这次修改没有保存，请保留输入后重试');error.status=response.status;error.data=value;throw error;}return value;
 });
 const pendingGets=new Map();
 const request=(path,init={})=>{
  const method=(init.method||'GET').toUpperCase();
  if(method!=='GET'){
   if(method==='HEAD'||method==='OPTIONS')return rawRequest(path,init);
   pendingGets.clear();return Promise.resolve().then(()=>rawRequest(path,init)).finally(()=>pendingGets.clear());
  }
  if(pendingGets.has(path))return pendingGets.get(path);
  const pending=Promise.resolve().then(()=>rawRequest(path,init)).finally(()=>{if(pendingGets.get(path)===pending)pendingGets.delete(path);});
  pendingGets.set(path,pending);return pending;
 };
 const call=(method,path,payload)=>request(path,{method,headers:{'Content-Type':'application/json'},...(payload!==undefined?{body:JSON.stringify(payload)}:{})});
 const style=document.createElement('link');style.rel='stylesheet';style.href=options.styleUrl??'/integrations/readweave/native-panel.css';const surface=root.getRootNode();(surface.nodeType===9?surface.head:surface).append(style);
 const container=document.createElement('div');container.className='lw-readweave-host';find('glossary-result').append(container);
 const panel=mountReadWeave(container,{root:root.getRootNode(),request});
 let manifest=null,active=null,activeRoot=null,disposed=false,cursor=0,polling=false,sectionToken=0,renderingSectionId=null,menu=null;
 const icon=path=>'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+path+'</svg>';
 const tools=document.createElement('div');tools.className='lw-shared-tools';tools.innerHTML='<span class="lw-shared-state">正在读取共享文章</span><span style="flex:1"></span><a data-shared="edit" target="_blank" rel="noopener" title="在 ReadWeave 编辑当前文章" aria-label="在 ReadWeave 编辑当前文章">'+icon('<path d="m15 4 5 5M4 20l5-1 12-12a2 2 0 0 0-5-5L4 15z"/>')+'</a><a data-shared="open" target="_blank" rel="noopener" title="在 ReadWeave 打开当前文章" aria-label="在 ReadWeave 打开当前文章">'+icon('<path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6"/>')+'</a>';
 find('demo-content').before(tools);
 const status=text=>tools.querySelector('.lw-shared-state').textContent=text;
 const entry=id=>'lessonweave/articles/'+encodeURIComponent(id);
 const articleCache=new Map(),glossaryBaseline=new Map();
 let sourceContext=null;
 function sourceSentences(){
  const values=new Map();for(const source of options.bridge()?.sourcePack?.sources||[])for(const sentence of source.sentences||[])values.set(sentence.id,{...sentence,source_id:source.id});return values;
 }
 function clearSourceBindings(){
  for(const node of root.querySelectorAll('[data-readweave-source-projection]')){node.hidden=false;delete node.dataset.readweaveArticleId;delete node.dataset.readweaveContentRoot;delete node.dataset.readweaveSourceProjection;}
  for(const node of root.querySelectorAll('.lw-shared-source-additions,.lw-shared-source-documents'))node.remove();
  for(const node of root.querySelectorAll('[data-shared-source-hidden]')){node.hidden=false;delete node.dataset.sharedSourceHidden;}
 }
 function applySourceArticle(row){
  if(!sourceContext)return;
  if(row.articleId===sourceContext.translationId)renderSourceDocument(row,'translation');
  else if(row.articleId===(sourceContext.displayOriginalId||sourceContext.originalId))renderSourceDocument(row,'original');
 }
 function renderSourceDocument(row,kind){
  const cards=find('source-cards');if(!cards)return;
  let documents=cards.querySelector(':scope > .lw-shared-source-documents');
  if(!documents){documents=root.ownerDocument.createElement('div');documents.className='lw-shared-source-documents';cards.prepend(documents);}
  let section=documents.querySelector('[data-shared-source-document="'+kind+'"]');
  if(!section){section=root.ownerDocument.createElement('section');section.dataset.sharedSourceDocument=kind;section.className=kind==='original'?'source-original':'source-translation';const heading=root.ownerDocument.createElement('h3');heading.textContent=kind==='original'?'原文':'译文';const body=root.ownerDocument.createElement('div');section.append(heading,body);documents.append(section);}
  const body=section.lastElementChild;if(body.dataset.readweaveArticleId===row.articleId&&body.dataset.sharedRevision===String(row.revision)&&body.dataset.sharedDeleted===String(row.deleted))return;
  body.dataset.sharedRevision=String(row.revision);body.dataset.sharedDeleted=String(row.deleted);body.dataset.readweaveArticleId=row.articleId;body.dataset.readweaveContentRoot='readonly';body.dataset.readweaveMultiblock='true';
  if(row.deleted)showDeleted(body,row);else body.innerHTML=sanitizeArticle(row.body||'');
  const sentences=sourceSentences();for(const paragraph of body.querySelectorAll('[data-lw-sentence]')){const sentence=sentences.get(paragraph.dataset.lwSentence);paragraph.dataset.sentenceId=paragraph.dataset.lwSentence;paragraph.classList.add('source-sentence-pair');if(sentence)paragraph.dataset.sourceId=sentence.source_id;}
  for(const pair of cards.querySelectorAll('.source-sentence-pair'))if(!documents.contains(pair)){pair.hidden=true;pair.dataset.sharedSourceHidden='true';}
  options.hydrateText?.(body);
 }
 const showDeleted=(element,row)=>{element.replaceChildren();const box=document.createElement('div');box.className='lw-shared-deleted';box.textContent='这篇文章已在共享笔记库中删除，原始生成快照仍然保留';const restore=document.createElement('button');restore.textContent='恢复文章';restore.onclick=async()=>{try{const result=await call('POST',entry(row.articleId)+'/restore',{expectedRevision:row.revision,operationId:crypto.randomUUID()});articleCache.delete(row.articleId);await refreshArticle(result.articleId,element,true);}catch(error){status(error.message);}};box.append(document.createElement('br'),restore);element.append(box);};
 async function syncGlossary(row,token=sectionToken){
  const bridge=options.bridge(),doc=bridge?.doc,sectionId=row.source?.section_id||doc?.section_id;
  if(row.kind!=='explanation'||!row.readweave||!Array.isArray(doc?.glossary)||!sectionId)return;
  if(!glossaryBaseline.has(sectionId))glossaryBaseline.set(sectionId,doc.glossary.map(term=>({...term,explanation:[...(term.explanation||[])]})));
  const baseline=glossaryBaseline.get(sectionId),key=term=>String(term.id||term.display),baselineKeys=new Set(baseline.map(key));
  const additions=doc.glossary.filter(term=>!baselineKeys.has(key(term))),terms=[...baseline,...additions];
  const objects=new Map((row.readweave.objects||[]).map(item=>[item.objectId,item]));
  const mapped=new Map();for(const link of row.readweave.links||[]){const item={...objects.get(link.objectId),...link};if(link.articleId===row.articleId&&item.contentType==='definition')mapped.set(link.anchorId,item);}
  const updated=[];
  for(const term of terms){const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(term.id||term.display))),b=>b.toString(16).padStart(2,'0')).join('').slice(0,24);const item=mapped.get('lwdef_'+hash);if(!item){if(!baselineKeys.has(key(term)))updated.push(term);continue;}const paragraphs=(item.displayBody??item.body??'').split(/\n\s*\n/);updated.push({...term,display:item.displayTitle||item.title||term.display,definition:paragraphs.shift()||'',explanation:paragraphs});}
  if(!disposed&&token===sectionToken&&doc===options.bridge()?.doc)options.updateGlossary?.(updated);
 }
 async function refreshArticle(id,element,force=false,token=sectionToken){
  const row=await call('GET',entry(id));if(disposed||token!==sectionToken)return row;
  const previous=articleCache.get(id);articleCache.set(id,row);
  const changed=force||!previous||previous.revision!==row.revision;
  if(row.kind==='explanation'){
   if(row.key?.startsWith('explanation:')&&row.key!=='explanation:'+options.bridge()?.doc?.section_id)return row;
   if(!element?.isConnected||element.dataset.readweaveArticleId!==id)return row;
   if(row.deleted)showDeleted(element,row);
   else if(row.revision>1&&changed){
    element.innerHTML=sanitizeArticle(row.body||'');element.classList.add('lw-shared-body');
    options.hydrateMedia?.(element);options.hydrateText?.(element);
   }
   await syncGlossary(row,token);
  }else if(row.kind==='original'||row.kind==='translation'||row.kind==='source'){
   if(changed)applySourceArticle(row,previous);
  }
  if(!disposed&&token===sectionToken&&active?.articleId===id){active=row;status(row.deleted?'已移入回收站':'已同步 · 版本 '+row.revision);}
  return row;
 }
 function activate(row,element){if(!row||!element)return;active=row;activeRoot=element;element.dataset.readweaveContentRoot='readonly';element.dataset.readweaveMultiblock='true';element.dataset.readweaveArticleId=row.articleId;panel.update(row,element);updateLinks();options.onActiveArticle?.({articleId:row.articleId,kind:row.kind,title:row.title});status(row.deleted?'已移入回收站':'已同步 · 版本 '+row.revision);}
 function clearCurrentBindings(){
  sourceContext=null;active=null;activeRoot=null;closeMenu();
  const nodes=new Set([...root.querySelectorAll('[data-readweave-article-id]'),...externalSurfaces.keys()]);
  for(const node of nodes){delete node.dataset.readweaveArticleId;delete node.dataset.readweaveContentRoot;delete node.dataset.readweaveMultiblock;}
  clearSourceBindings();
  const article=find('demo-content');
  panel.update(null,article);updateLinks();options.onActiveArticle?.(null);
  status('正在读取当前章节的共享文章');
 }
 function clearSectionContext(){++sectionToken;renderingSectionId=null;clearCurrentBindings();}
 async function loadSection(){
  const token=++sectionToken,state=options.bridge(),sid=state?.doc?.section_id;if(!sid||state?.ready===false)return;
  const article=find('demo-content');
  if(renderingSectionId!==sid){
   renderingSectionId=sid;clearCurrentBindings();
  }
  try{
   manifest=await options.manifest();if(disposed||token!==sectionToken)return;
   const id=manifest.section_articles[sid];
   if(!id){status('当前小节尚未保存到共享笔记库');return;}
   clearSourceBindings();sourceContext={sectionId:sid,originalId:manifest.original_articles?.[sid]||null,translationId:manifest.translation_articles?.[sid]||null};
   article.dataset.readweaveArticleId=id;const row=await refreshArticle(id,article);if(disposed||token!==sectionToken)return;activate(row,article);
   for(const sourceId of [sourceContext.originalId,sourceContext.translationId])if(sourceId)refreshArticle(sourceId,null,true).catch(()=>{});
   const surfaces=[...root.querySelectorAll('.locator-selectable-text')];try{const body=find('locator-dom')?.contentDocument?.body;if(body)surfaces.push(body);}catch{}
   for(const element of surfaces)if(element.__lessonweaveSourceSurface)externalSurfaces.set(element,element.__lessonweaveSourceSurface);
   for(const [element,detail]of externalSurfaces)if(element.isConnected)bindSourceSurface(detail).catch(()=>{});else externalSurfaces.delete(element);
   status('已同步 · 版本 '+row.revision);
  }catch(error){if(!disposed)status(error.message);}
 }
 function nativeUrl(id){return options.nativeUrl?.(id)||('/p/'+encodeURIComponent(manifest?.project_id||options.projectId||'')+'/open-readweave?article='+encodeURIComponent(id));}
 function updateLinks(){for(const link of tools.querySelectorAll('a[data-shared]')){if(active)link.href=nativeUrl(active.articleId);else link.removeAttribute('href');}}
 function closeMenu(){menu?.remove();menu=null;}
 listen(root,'contextmenu',event=>{
  const element=event.target.closest?.('[data-readweave-article-id]');if(!element)return;
  const selected=element.ownerDocument.defaultView.getSelection?.();
  const shadowSelected=element.getRootNode().getSelection?.();if((shadowSelected||selected)?.toString().trim())return;
  event.preventDefault();closeMenu();const articleId=element.dataset.readweaveArticleId;
  menu=root.ownerDocument.createElement('div');menu.className='lw-shared-context-menu';menu.setAttribute('role','menu');
  Object.assign(menu.style,{position:'fixed',left:event.clientX+'px',top:event.clientY+'px',zIndex:2000});
  for(const [name,label]of [['open','在 ReadWeave 打开'],['edit','在 ReadWeave 编辑'],['delete','移入回收站']]){
   const button=root.ownerDocument.createElement('button');button.type='button';button.textContent=label;button.setAttribute('role','menuitem');
   button.onclick=async()=>{closeMenu();if(name!=='delete'){root.ownerDocument.defaultView.open(nativeUrl(articleId),'_blank','noopener');return;}
    const target=articleCache.get(articleId),kind={explanation:'讲解',original:'原文',translation:'译文',source:'原文件'}[target?.kind]||'文章';
    if(!root.ownerDocument.defaultView.confirm('将'+kind+'“'+(target?.title||'未命名文章')+'”移入回收站？原始生成快照会保留，可以恢复'))return;
    try{const row=await call('GET',entry(articleId));await call('DELETE',entry(articleId),{expectedRevision:row.revision,operationId:crypto.randomUUID()});await refreshArticle(articleId,element,true);}catch(error){status(error.message);}
   };menu.append(button);
  }(surface.nodeType===9?surface.body:surface).append(menu);
 });
 listen(root,'click',event=>{if(!event.target.closest?.('.lw-shared-context-menu'))closeMenu();});
 listen(root,'keydown',event=>{if(event.key==='Escape')closeMenu();});
 const externalSurfaces=new Map(),boundSurfaces=new WeakSet();
 function surfaceId(detail){
  if(!sourceContext||sourceContext.sectionId!==renderingSectionId||renderingSectionId!==options.bridge()?.doc?.section_id)return null;
  const identity=[detail.materialRun||'',detail.materialPath||'',detail.pageId||''].join('\n');
  return manifest?.page_articles?.[identity]||manifest?.page_articles?.[detail.pageId]||manifest?.source_articles?.[String(detail.filePath||'').replace(/^\//,'')]||sourceContext?.originalId;
 }
 async function bindSourceSurface(detail){
  const element=detail.element,id=surfaceId(detail);if(!element||!id)return;
  element.dataset.readweaveArticleId=id;element.dataset.readweaveContentRoot='readonly';element.dataset.readweaveMultiblock='true';
  if(!articleCache.has(id))await refreshArticle(id,null);
  if(boundSurfaces.has(element))return;boundSurfaces.add(element);
  const select=()=>{if(!element.isConnected)return;const current=surfaceId(externalSurfaces.get(element)||detail),row=current&&articleCache.get(current);if(row&&sourceContext){sourceContext.displayOriginalId=row.articleId;renderSourceDocument(row,'original');activate(row,element);}};
  element.addEventListener('pointerdown',select,{capture:true,signal:abort.signal});element.addEventListener('contextmenu',select,{capture:true,signal:abort.signal});
 }
 listen(root,'reading:source-surface',event=>{if(event.detail?.element){externalSurfaces.set(event.detail.element,event.detail);bindSourceSurface(event.detail).catch(error=>status(error.message));}});
 listen(root,'pointerdown',async event=>{if(!sourceContext||sourceContext.sectionId!==options.bridge()?.doc?.section_id)return;const element=event.target.closest?.('[data-readweave-article-id]');if(element&&element!==activeRoot){const token=sectionToken,id=element.dataset.readweaveArticleId,row=articleCache.get(id)||await refreshArticle(id,element);if(token===sectionToken&&element.isConnected&&element.dataset.readweaveArticleId===id)activate(row,element);}});
 const sourceCards=find('source-cards'),sourceObserver=typeof MutationObserver==='function'&&sourceCards?new MutationObserver(()=>{if(!sourceContext)return;for(const id of [sourceContext.originalId,sourceContext.translationId]){const row=id&&articleCache.get(id);if(row)applySourceArticle(row,null);}}):null;
 sourceObserver?.observe(sourceCards,{childList:true});
 listen(root,'reading:document-ready',loadSection);
 listen(root,'reading:document-changing',clearSectionContext);
 const timer=setInterval(async()=>{
  if(disposed||polling||!manifest)return;const token=sectionToken,editionId=manifest.editionId;polling=true;
  try{
   const changes=await call('GET','lessonweave/changes?after='+cursor+'&editionId='+encodeURIComponent(editionId));
   if(disposed||token!==sectionToken||manifest?.editionId!==editionId)return;
   if(changes.changes?.some(item=>!item.kind.startsWith('edit-lease'))&&activeRoot&&active){
    const articleId=active.articleId,surface=activeRoot,sid=options.bridge()?.doc?.section_id,explanationId=manifest.section_articles?.[sid];
    const current=()=>!disposed&&token===sectionToken&&active?.articleId===articleId&&activeRoot===surface;
    const ids=[explanationId,sourceContext?.originalId,sourceContext?.translationId,sourceContext?.displayOriginalId,articleId].filter(Boolean);
    for(const id of [...new Set(ids)]){
     if(!current())return;
     const element=articleId===id?surface:id===explanationId?find('demo-content'):null;
     const row=await refreshArticle(id,element,false,token);
     if(!current())return;
     if(articleId===id){active=row;panel.update(row,surface);}
    }
    window.dispatchEvent(new CustomEvent('readweave:shared-change',{detail:{articleId,articleIds:[...new Set(ids)]}}));
   }
   cursor=changes.nextCursor;
  }catch(error){if(!disposed&&token===sectionToken)status(error.message);}finally{polling=false;}
 },900);
 loadSection();
 return{unmount(){disposed=true;abort.abort();clearInterval(timer);sourceObserver?.disconnect();closeMenu();panel.unmount();style.remove();container.remove();tools.remove();}};
}
