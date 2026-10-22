(async()=>{
 const config=window.LESSONWEAVE;if(!config)return;
 const request=async(path,options)=>{const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw Error(data.error||data.message||'共享内容暂时无法读取');return data;};
 const bridge=()=>window.ReaderSourceBridge?.getState();
 if(config.readweave_shared){
  const {mountSharedReader}=await import('/integrations/readweave/shared-reader.js');
  mountSharedReader(document.body,{bridge,updateGlossary:terms=>window.ReaderSourceBridge?.updateGlossary(terms),hydrateMedia:element=>window.ReaderSourceBridge?.hydrateSharedMedia(element),manifest:()=>request('/api/readweave-projects/'+config.project_id)});
 }
 const bound=new WeakSet(),bindings=new Map();
 const refresh=()=>{for(const [box,binding]of bindings){const {field,path}=binding;if(!box.isConnected){bindings.delete(box);continue;}const snapshot=field.value;request(path).then(data=>{if(!field.hasAttribute('data-note-draft')&&field.value===snapshot&&(config.readweave_shared||!field.value)){field.value=data.value??'';binding.version={revision:data.revision,linkRevision:data.linkRevision};}}).catch(()=>{});}};
 const bind=()=>document.querySelectorAll('.writing-note').forEach(box=>{
  if(bound.has(box))return;const state=bridge();if(!state?.doc)return;bound.add(box);
  const field=box.querySelector('textarea'),button=box.querySelector('button'),path='/api/notes/'+config.project_id+'/'+encodeURIComponent(state.doc.section_id+':'+box.dataset.noteId);
  const binding={field,path,version:{}};bindings.set(box,binding);refresh();
  button.addEventListener('click',async()=>{const status=box.querySelector('.help');try{const reply=await request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({value:field.value,...binding.version})});binding.version={revision:reply.revision,linkRevision:reply.linkRevision};if(status)status.textContent='已保存到共享学习笔记';}catch(error){field.dataset.noteDraft='true';if(status)status.textContent=error.message;}});
 });
 window.addEventListener('readweave:shared-change',refresh);
 new MutationObserver(bind).observe(document.querySelector('#demo-content'),{childList:true,subtree:true});bind();
})();
