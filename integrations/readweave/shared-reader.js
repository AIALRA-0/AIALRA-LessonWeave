import {mountReadWeave,sanitizeArticle} from './native-panel.js';

// 阅读器保留布局和生成快照，共享正文及交互从同一个原生笔记库读回
export function mountSharedReader(root,options){
 const find=id=>root.querySelector('#'+CSS.escape(id)),abort=new AbortController();
 const listen=(node,type,fn)=>node?.addEventListener(type,fn,{signal:abort.signal});
 const request=options.request??(async(path,init={})=>{
  const url=path.startsWith('lessonweave/')?'/api/shared/'+path.slice(12):'/api/'+path;
  const response=await fetch(url,{...init,credentials:'same-origin'});const value=await response.json();
  if(!response.ok){const error=Error(value.error||value.message||value.code||'这次修改没有保存，请保留输入后重试');error.status=response.status;error.data=value;throw error;}return value;
 });
 const call=(method,path,payload)=>request(path,{method,headers:{'Content-Type':'application/json'},...(payload!==undefined?{body:JSON.stringify(payload)}:{})});
 const style=document.createElement('link');style.rel='stylesheet';style.href=options.styleUrl??'/integrations/readweave/native-panel.css';root.getRootNode().append(style);
 const container=document.createElement('div');container.className='lw-readweave-host';find('glossary-result').append(container);
 const panel=mountReadWeave(container,{root:root.getRootNode(),request});
 let manifest=null,active=null,activeRoot=null,lease=null,edit=null,disposed=false,cursor=0,polling=false,sectionToken=0,leaseRenewedAt=0;
 const draftKey=id=>'lessonweave:shared-draft:'+id;
 let owner;try{owner=sessionStorage.getItem('lessonweave:editor-id')||crypto.randomUUID();sessionStorage.setItem('lessonweave:editor-id',owner);}catch{owner=crypto.randomUUID();}
 const tools=document.createElement('div');tools.className='lw-shared-tools';tools.innerHTML='<span class="lw-shared-state">正在读取共享文章</span><span style="flex:1"></span><button type="button" data-shared="edit" title="编辑当前文章" aria-label="编辑当前文章">✎</button><button type="button" data-shared="delete" title="移入回收站" aria-label="移入回收站">⌫</button>';
 find('demo-content').before(tools);
 const status=text=>tools.querySelector('.lw-shared-state').textContent=text;
 const entry=id=>'lessonweave/articles/'+encodeURIComponent(id);
 const articleCache=new Map(),glossaryBaseline=new Map(),sourceTextHistory=new Map();
 let sourceContext=null;
 const normalizeText=value=>String(value??'').replace(/\s+/g,' ').trim();
 const sentenceHasChinese=value=>/[\u4e00-\u9fff]/u.test(String(value??''));
 function sourceSentences(){
  const values=new Map();for(const source of options.bridge()?.sourcePack?.sources||[])for(const sentence of source.sentences||[])values.set(sentence.id,sentence);return values;
 }
 function clearSourceBindings(){
  for(const node of root.querySelectorAll('[data-readweave-source-projection]')){node.hidden=false;delete node.dataset.readweaveArticleId;delete node.dataset.readweaveContentRoot;delete node.dataset.readweaveSourceProjection;}
  for(const node of root.querySelectorAll('.lw-shared-source-additions'))node.remove();
 }
 function sourceBlocks(row){
  const template=root.ownerDocument.createElement('template');template.innerHTML=sanitizeArticle(row.body||'');
  return [...template.content.children];
 }
 function sourceTarget(pair,kind,sentence,canonicalText,previousText){
  const original=pair.querySelector('.source-original > p, .source-original > pre'),translation=pair.querySelector('.source-translation > p, .source-translation > pre');
  const candidates=[original,translation].filter(Boolean),matches=(node,values)=>values
   .filter(value=>value!==undefined&&value!==null&&String(value).trim()).some(value=>normalizeText(node.textContent)===normalizeText(value));
  if(kind==='translation'){
   const chineseOriginal=sentenceHasChinese(sentence?.original)&&translation&&normalizeText(translation.textContent)===normalizeText(sentence.original)
    &&normalizeText(sentence?.translation||sentence?.zh)!==normalizeText(sentence.original);
   if(chineseOriginal)return null;
   if(translation&&(!sentence||matches(translation,[sentence?.translation,sentence?.zh,canonicalText,previousText])))return translation;
   return null;
  }
  const expected=sentence?.original||sentence?.english;
  const matched=candidates.find(node=>normalizeText(node.textContent)===normalizeText(expected))||candidates.find(node=>matches(node,[canonicalText,previousText]));
  if(matched)return matched;
  if(!sentence)return original||translation||null;
  return sentenceHasChinese(sentence.original)?translation||original||null:original||translation||null;
 }
 function applySourceArticle(row,previousRow){
  if(!sourceContext||![sourceContext.originalId,sourceContext.translationId].includes(row.articleId))return;
  const kind=row.articleId===sourceContext.translationId?'translation':'original';
  const sentences=sourceSentences(),history=sourceTextHistory.get(row.articleId)||new Map(),nextHistory=new Map(),unmatched=[];
  const previous=new Map(sourceBlocks(previousRow||{}).filter(node=>node.matches('p[data-lw-sentence]')).map(node=>[node.dataset.lwSentence,node.textContent]));
  const pairs=new Map([...root.querySelectorAll('.source-sentence-pair[data-sentence-id]')].map(pair=>[pair.dataset.sentenceId,pair]));
  for(const block of sourceBlocks(row)){
   const sentenceId=block.matches('p[data-lw-sentence]')?block.dataset.lwSentence:null;
   if(!sentenceId){unmatched.push(block);continue;}
   const sentence=sentences.get(sentenceId),pair=pairs.get(sentenceId);
   if(!sentence){unmatched.push(block);continue;}
   if(!pair)continue;
   const oldText=previous.get(sentenceId)||history.get(sentenceId)||'';
   const target=sourceTarget(pair,kind,sentence,block.textContent,oldText);
   if(!target){unmatched.push(block);continue;}
   if(!row.deleted){target.hidden=false;target.innerHTML=block.innerHTML;}else target.hidden=true;
   target.dataset.readweaveArticleId=row.articleId;target.dataset.readweaveContentRoot='readonly';target.dataset.readweaveSourceProjection=kind;
   nextHistory.set(sentenceId,block.textContent);
  }
  for(const node of root.querySelectorAll('[data-readweave-source-projection]'))if(node.dataset.readweaveArticleId===row.articleId&&row.deleted)node.hidden=true;
  for(const [sentenceId,text]of history)if(!nextHistory.has(sentenceId))nextHistory.set(sentenceId,text);
  sourceTextHistory.set(row.articleId,nextHistory);
  const additionsId='lw-shared-free-'+row.articleId;
  let additions=[...root.querySelectorAll('[data-readweave-free-id]')].find(node=>node.dataset.readweaveFreeId===additionsId);
  if(additions)additions.remove();
  if(row.deleted){
   additions=root.ownerDocument.createElement('section');additions.className='lw-shared-source-additions';additions.dataset.readweaveFreeId=additionsId;
   const heading=root.ownerDocument.createElement('h3');heading.textContent=kind==='original'?'共享原文已删除':'共享译文已删除';
   const restore=root.ownerDocument.createElement('button');restore.type='button';restore.textContent=kind==='original'?'恢复共享原文':'恢复共享译文';
   restore.onclick=async()=>{restore.disabled=true;try{const result=await call('POST',entry(row.articleId)+'/restore',{expectedRevision:row.revision,operationId:crypto.randomUUID()});articleCache.delete(row.articleId);await refreshArticle(result.articleId,null,true);}catch(error){status(error.message);}finally{restore.disabled=false;}};
   additions.append(heading,restore);(find('source-text-scroll')||find('demo-original'))?.append(additions);
  }else if(unmatched.length){
   additions=root.ownerDocument.createElement('section');additions.className='lw-shared-source-additions';additions.dataset.readweaveFreeId=additionsId;
   const heading=root.ownerDocument.createElement('h3');heading.textContent=kind==='original'?'ReadWeave 原文补充':'ReadWeave 译文补充';additions.append(heading);
   for(const block of unmatched){const copy=block.cloneNode(true);copy.dataset.readweaveArticleId=row.articleId;copy.dataset.readweaveContentRoot='readonly';copy.dataset.readweaveSourceProjection=kind;additions.append(copy);}
   (find('source-text-scroll')||find('demo-original'))?.append(additions);
  }
 }
 const showDeleted=(element,row)=>{element.replaceChildren();const box=document.createElement('div');box.className='lw-shared-deleted';box.textContent='这篇文章已在共享笔记库中删除，原始生成快照仍然保留';const restore=document.createElement('button');restore.textContent='恢复文章';restore.onclick=async()=>{try{const result=await call('POST',entry(row.articleId)+'/restore',{expectedRevision:row.revision,operationId:crypto.randomUUID()});articleCache.delete(row.articleId);await refreshArticle(result.articleId,element,true);}catch(error){status(error.message);}};box.append(document.createElement('br'),restore);element.append(box);};
 async function syncGlossary(row){
  const bridge=options.bridge(),doc=bridge?.doc,sectionId=row.source?.section_id||doc?.section_id;
  if(row.kind!=='explanation'||!row.readweave||!Array.isArray(doc?.glossary)||!sectionId)return;
  if(!glossaryBaseline.has(sectionId))glossaryBaseline.set(sectionId,doc.glossary.map(term=>({...term,explanation:[...(term.explanation||[])]})));
  const baseline=glossaryBaseline.get(sectionId),key=term=>String(term.id||term.display),baselineKeys=new Set(baseline.map(key));
  const additions=doc.glossary.filter(term=>!baselineKeys.has(key(term))),terms=[...baseline,...additions];
  const objects=new Map((row.readweave.objects||[]).map(item=>[item.objectId,item]));
  const mapped=new Map();for(const link of row.readweave.links||[]){const item={...objects.get(link.objectId),...link};if(link.articleId===row.articleId&&item.contentType==='definition')mapped.set(link.anchorId,item);}
  const updated=[];
  for(const term of terms){const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(term.id||term.display))),b=>b.toString(16).padStart(2,'0')).join('').slice(0,24);const item=mapped.get('lwdef_'+hash);if(!item){if(!baselineKeys.has(key(term)))updated.push(term);continue;}const paragraphs=(item.displayBody??item.body??'').split(/\n\s*\n/);updated.push({...term,display:item.displayTitle||item.title||term.display,definition:paragraphs.shift()||'',explanation:paragraphs});}
  options.updateGlossary?.(updated);
 }
 async function refreshArticle(id,element,force=false){
  const row=await call('GET',entry(id));if(disposed)return row;
  const previous=articleCache.get(id);articleCache.set(id,row);
  const changed=force||!previous||previous.revision!==row.revision;
  if(row.kind==='explanation'){
   if(row.key?.startsWith('explanation:')&&row.key!=='explanation:'+options.bridge()?.doc?.section_id)return row;
   if(!element?.isConnected||element.dataset.readweaveArticleId!==id)return row;
   if(row.deleted)showDeleted(element,row);
   else if(row.revision>1&&changed&&!(edit&&active?.articleId===id)){
    element.innerHTML=sanitizeArticle(row.body||'');element.classList.add('lw-shared-body');
    options.hydrateMedia?.(element);
   }
   await syncGlossary(row);
  }else if(row.kind==='original'||row.kind==='translation'){
   if(changed)applySourceArticle(row,previous);
  }
  if(active?.articleId===id){active=row;status(row.deleted?'已移入回收站':lease?'正在编辑，草稿会留在当前浏览器':'已同步 · 版本 '+row.revision);}
  return row;
 }
 function activate(row,element){if(!row||!element||edit&&active?.articleId!==row.articleId)return;active=row;activeRoot=element;element.dataset.readweaveContentRoot='readonly';element.dataset.readweaveArticleId=row.articleId;panel.update(row,element);status(row.deleted?'已移入回收站':'已同步 · 版本 '+row.revision);}
 async function loadSection(){
  const token=++sectionToken,state=options.bridge(),sid=state?.doc?.section_id;if(!sid)return;
  if(edit){if(sid===sourceContext?.sectionId)return;await endEdit();}
  try{
   manifest=await options.manifest();if(disposed||token!==sectionToken)return;
   const article=find('demo-content'),id=manifest.section_articles[sid];
   if(!id){status('当前小节尚未保存到共享笔记库');return;}
   clearSourceBindings();sourceContext={sectionId:sid,originalId:manifest.original_articles?.[sid]||null,translationId:manifest.translation_articles?.[sid]||null};
   article.dataset.readweaveArticleId=id;const row=await refreshArticle(id,article);if(disposed||token!==sectionToken)return;activate(row,article);
   for(const sourceId of [sourceContext.originalId,sourceContext.translationId])if(sourceId)refreshArticle(sourceId,null,true).catch(()=>{});
   status('已同步 · 版本 '+row.revision);
  }catch(error){if(!disposed)status(error.message);}
 }
 async function release(){const owned=lease;lease=null;if(owned)try{await call('DELETE','lessonweave/edit-sessions/'+owned.leaseId,{token:owned.token,fence:owned.fence});}catch{}}
 async function endEdit(saved=false){edit?.remove();edit=null;await release();if(active&&activeRoot)await refreshArticle(active.articleId,activeRoot,true);status(saved?'修改已同步到 ReadWeave':'已退出编辑，未保存的草稿仍留在当前浏览器');}
 async function beginEdit(){
  if(edit)return;
  try{
   const row=await refreshArticle(active.articleId,activeRoot);if(row.deleted)return;
   lease=await call('POST','lessonweave/edit-sessions',{articleId:row.articleId,ownerId:'LessonWeave-'+owner});
   leaseRenewedAt=Date.now();
   edit=document.createElement('div');const textarea=document.createElement('div');textarea.className='lw-shared-edit';textarea.contentEditable='true';textarea.setAttribute('role','textbox');textarea.setAttribute('aria-multiline','true');textarea.setAttribute('aria-label','编辑共享文章');let draft;try{draft=localStorage.getItem(draftKey(row.articleId));}catch{}textarea.innerHTML=sanitizeArticle(draft??row.body);
   textarea.oninput=()=>{try{localStorage.setItem(draftKey(row.articleId),textarea.innerHTML);}catch{}};
   const save=document.createElement('button');save.textContent='保存并同步';save.onclick=async()=>{save.disabled=true;try{const result=await call('PUT',entry(row.articleId),{body:sanitizeArticle(textarea.innerHTML),expectedRevision:row.revision,operationId:crypto.randomUUID(),leaseToken:lease?.token,fence:lease?.fence});try{localStorage.removeItem(draftKey(row.articleId));}catch{}active=result;await endEdit(true);}catch(error){status(error.status===409?'另一处已更新，当前草稿已保留，请退出编辑后对照最新版本':error.message);}finally{save.disabled=false;}};
   const cancel=document.createElement('button');cancel.textContent='退出编辑';cancel.onclick=()=>endEdit();edit.append(textarea,save,cancel);activeRoot.before(edit);status('正在编辑，另一处暂时无法覆盖这篇文章');textarea.focus();
  }catch(error){status(error.status===423?'这篇文章正在另一处编辑，可以继续阅读，稍后再改':error.message);}
 }
 listen(tools,'click',async event=>{
  const command=event.target.closest('[data-shared]')?.dataset.shared;if(!command||!active)return;
  if(command==='edit')return beginEdit();
  try{if(edit)await endEdit();const row=await call('GET',entry(active.articleId));await call('DELETE',entry(row.articleId),{expectedRevision:row.revision,operationId:crypto.randomUUID()});await refreshArticle(row.articleId,activeRoot,true);}catch(error){status(error.message);}
 });
 listen(root,'pointerdown',async event=>{const element=event.target.closest?.('[data-readweave-article-id]');if(element&&element!==activeRoot){const row=articleCache.get(element.dataset.readweaveArticleId)||await refreshArticle(element.dataset.readweaveArticleId,element);activate(row,element);}});
 const sourceCards=find('source-cards'),sourceObserver=typeof MutationObserver==='function'&&sourceCards?new MutationObserver(()=>{if(!sourceContext)return;for(const id of [sourceContext.originalId,sourceContext.translationId]){const row=id&&articleCache.get(id);if(row)applySourceArticle(row,null);}}):null;
 sourceObserver?.observe(sourceCards,{childList:true});
 listen(root,'reading:document-ready',loadSection);
 const timer=setInterval(async()=>{
  if(disposed||polling||!manifest)return;polling=true;
  try{
   if(lease&&Date.now()-leaseRenewedAt>30000){lease=await call('PUT','lessonweave/edit-sessions/'+lease.leaseId,{token:lease.token,fence:lease.fence});leaseRenewedAt=Date.now();}
   const changes=await call('GET','lessonweave/changes?after='+cursor+'&editionId='+encodeURIComponent(manifest.editionId));cursor=changes.nextCursor;
   if(changes.changes?.some(item=>!item.kind.startsWith('edit-lease'))&&activeRoot&&active){
    const sid=options.bridge()?.doc?.section_id,ids=[manifest.section_articles?.[sid],sourceContext?.originalId,sourceContext?.translationId].filter(Boolean);
    for(const id of [...new Set(ids)]){
     if(edit&&active.articleId===id)continue;
     const element=active.articleId===id?activeRoot:id===manifest.section_articles?.[sid]?find('demo-content'):null;
     const row=await refreshArticle(id,element);
     if(active?.articleId===id){active=row;panel.update(active,activeRoot);}
    }
    window.dispatchEvent(new CustomEvent('readweave:shared-change',{detail:{articleId:active.articleId,articleIds:[...new Set(ids)]}}));
   }
  }catch(error){if(!disposed)status(error.message);}finally{polling=false;}
 },900);
 loadSection();
 return{unmount(){disposed=true;abort.abort();clearInterval(timer);sourceObserver?.disconnect();release();panel.unmount();style.remove();container.remove();tools.remove();}};
}
