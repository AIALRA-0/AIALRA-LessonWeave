// Trilium executes this trusted frontend code note through its renderNote relation
const config=/*LESSONWEAVE_CONFIG*/null;
const host=document.createElement('div');
host.style.cssText='height:max(650px,calc(100vh - 180px));width:100%;min-width:0';
api.$container.append(host);
const absolute=path=>new URL(path,document.baseURI).href;
const edition=await api.startNote.getRelationTarget('lessonweaveEdition');
const noteParent=await api.startNote.getRelationTarget('lessonweaveUserNotes');
if(!edition||!noteParent)throw Error('阅读组件缺少对应的版本或学习笔记目录');
const attachments=await edition.getAttachments();
const resources=Object.fromEntries(attachments.map(item=>[item.title,'/api/attachments/'+item.attachmentId+'/open']));
for(const item of attachments)if(item.title.startsWith('.lessonweave-preview/'))resources[item.title.slice('.lessonweave-preview/'.length,-4)]='/api/attachments/'+item.attachmentId+'/open';
const sections=Object.fromEntries((await edition.getSubtreeNotes()).map(note=>[note.getLabelValue('lessonweaveSectionId'),note.noteId]).filter(([id])=>id));
const resource=value=>{
  let path=String(value).split('#')[0].split('?')[0];
  if(path.startsWith(config.base+'/'))path=path.slice(config.base.length+1);
  else path=path.replace(/^\/+/, '');
  return resources[path]?absolute(resources[path]):null;
};
const noteCache=new Map((await noteParent.getChildNotes()).map(note=>[note.title,note]));
const notes=async(key,value)=>{
  let note=noteCache.get(key);
  if(value===null)return note?JSON.parse(await note.getContent()).text||'':'';
  if(!note){note=(await api.createNote(noteParent.noteId,{title:key,type:'code',mime:'application/json',content:JSON.stringify({text:value}),activate:false})).note;noteCache.set(key,note);}
  else{
    const response=await fetch(absolute('api/notes/'+note.noteId+'/data'),{method:'PUT',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':globalThis.glob.csrfToken},body:JSON.stringify({content:JSON.stringify({text:value})})});
    if(!response.ok)throw Error('学习笔记保存失败，请保留输入内容后重试');
    await api.reloadNotes([note.noteId]);noteCache.set(key,await api.getNote(note.noteId));
  }
  return value;
};
const {mountReader}=await import(absolute(resources[config.moduleTitle]));
let reader;
const open=search=>{reader?.unmount();reader=mountReader(host,{projectId:config.projectId,base:config.base,search,onNavigate:open,resolveResource:resource,loadNote:key=>notes(key,null),saveNote:(key,text)=>notes(key,text),onSourceSelection:selection=>{
  host.dispatchEvent(new CustomEvent('lessonweave:source-selection',{bubbles:true,detail:selection}));
}});};
open(config.preview?'?preview=true':'');
const nativeChapter=document.createElement('button');nativeChapter.textContent='在原生章节中提问';nativeChapter.onclick=()=>{const id=reader.getState()?.doc?.section_id;if(sections[id])api.activateNote(sections[id]);};api.$container.prepend(nativeChapter);
// Native text chapter notes remain available to ReadWeave's existing selection and question tools
const cleanup=new MutationObserver(()=>{if(!host.isConnected){reader.unmount();cleanup.disconnect();}});
cleanup.observe(document.body,{childList:true,subtree:true});
