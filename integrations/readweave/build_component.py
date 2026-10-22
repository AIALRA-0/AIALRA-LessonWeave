"""把公共阅读组件编成可挂载模块，演示与交接使用同一份实现"""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[2]
READER=ROOT/'framework/reader'
HERE=Path(__file__).parent


def build():
    html=(READER/'book.html').read_text('utf-8')
    body=html.split('<body',1)[1].split('>',1)[1].split('</body>',1)[0]
    body=re.sub(r'<script\b[^>]*>.*?</script>','',body,flags=re.S)
    styles='\n'.join((READER/name).read_text('utf-8') for name in ['reader.css','writing-demo.css','reading-ui.css','media-renderer.css','reader-polish.css'])
    styles=re.sub(r'(?<![\w-])(?:html|body|:root)(?![\w-])','.lw-reader-root',styles)
    header='''// This module mounts one independent reading view per container
export function mountReader(container, options) {
  const shadow = container.shadowRoot || container.attachShadow({mode:'open'});
  const style = globalThis.document.createElement('style');
  const root = globalThis.document.createElement('div');
  root.className = 'lw-reader-root writing-page demo-page reader-ui book-page'+(options.embedded?' lw-embedded':'');
  root.lang='zh-CN'; root.dataset.theme=options.theme||(globalThis.document.body.classList.contains('dark')?'dark':'light');
  for(const [role,value]of Object.entries(DESIGN_TOKENS[root.dataset.theme]||{}))root.style.setProperty('--'+role.replace(/[A-Z]/g,c=>'-'+c.toLowerCase()),value);
  style.textContent=STYLES; root.innerHTML=TEMPLATE; shadow.replaceChildren(style,root);
  const abort=new AbortController(), timers=new Set(), frames=new Set(), observers=new Set(); let disposed=false;
  const native=globalThis.window;
  const tracked=kind=>class extends native[kind] {constructor(...args){super(...args);observers.add(this)}disconnect(){super.disconnect();observers.delete(this)}};
  const MutationObserver=tracked('MutationObserver'), ResizeObserver=tracked('ResizeObserver'), IntersectionObserver=tracked('IntersectionObserver');
  const config={project_id:options.projectId,base:options.base,legacy:!!options.legacy,sidebarWidth:options.sidebarWidth};
  const path=value=>{let text=String(value||'');const resolved=options.resolveResource?.(text);if(resolved)return resolved;if(/^(https?:|data:|blob:|#)/.test(text))return text;if(text.startsWith(config.base+'/'))return text;return config.base+'/'+text.replace(/^\\/+/,'')};
  const fetch=(value, init)=>value==='/design-tokens.json'?Promise.resolve(new Response(JSON.stringify(DESIGN_TOKENS),{headers:{'Content-Type':'application/json'}})):options.fetch?options.fetch(value,init):native.fetch(typeof value==='string'&&/^\\/(0[0-5]_)/.test(value)?path(value):value,init);
  const location={pathname:'readweave/book.html',search:options.search??'?preview=true',hash:'',get href(){return native.location.origin+config.base+'/book.html'+this.search},set href(value){options.onNavigate?.(new URL(value,native.location.href).search)}};
  const owned={LESSONWEAVE:config,LWPath:path,LESSONWEAVE_THEME:root.dataset.theme};
  const listen=(target,type,handler,settings={})=>target.addEventListener(type,handler,{...(typeof settings==='boolean'?{capture:settings}:settings),signal:abort.signal});
  const document=new Proxy(native.document,{get(target,key){
    if(key==='body'||key==='documentElement')return root;
    if(key==='currentScript')return {src:native.location.origin+'/writing-demo.js'};
    if(key==='head')return {append(...nodes){for(const node of nodes){if(node.tagName==='LINK')shadow.append(node);else native.document.head.append(node)}}};
    if(key==='getElementById')return id=>root.querySelector('#'+CSS.escape(id));
    if(key==='querySelector'||key==='querySelectorAll')return root[key].bind(root);
    if(key==='addEventListener')return (type,handler,settings)=>listen(root,type,handler,settings);
    if(key==='dispatchEvent')return root.dispatchEvent.bind(root);
    const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  }});
  const window=new Proxy(native,{get(target,key){
    if(key in owned)return owned[key];if(key==='document')return document;if(key==='location')return location;
    if(key==='innerWidth')return container.clientWidth;if(key==='innerHeight')return container.clientHeight;
    if(key==='addEventListener')return (type,handler,settings)=>listen(target,type,handler,settings);
    const value=Reflect.get(target,key,target);return typeof value==='function'?value.bind(target):value;
  },set(target,key,value){owned[key]=value;return true}});
  const setTimeout=(callback,delay,...args)=>{const id=native.setTimeout(()=>{timers.delete(id);if(!disposed)callback(...args)},delay);timers.add(id);return id};
  const clearTimeout=id=>{timers.delete(id);native.clearTimeout(id)};
  const requestAnimationFrame=callback=>{const id=native.requestAnimationFrame(time=>{frames.delete(id);if(!disposed)callback(time)});frames.add(id);return id};
  const cancelAnimationFrame=id=>{frames.delete(id);native.cancelAnimationFrame(id)};
  const setInterval=(callback,delay)=>{const id=native.setInterval(()=>{if(!disposed)callback()},delay);timers.add(id);return id};
  const clearInterval=id=>{timers.delete(id);native.clearInterval(id)};
'''
    scripts=(READER/'reading-icons.js').read_text('utf-8')+'\nconst uiIcon=window.uiIcon;\n'+(READER/'math-text.js').read_text('utf8')+'\n'+(READER/'reader-text.js').read_text('utf8')+'\nconst ReaderText=window.ReaderText;\n'+(READER/'media-renderer.js').read_text('utf8')+'\n'+ '\n\n'.join((READER/name).read_text('utf-8') for name in ['reader-search.js','writing-demo.js','reading-ui.js','source-locator.js','source-split.js','generation-settings.js'])
    tail='''
  let shared=null;
  if(options.shared){
    import('./shared-reader.js').then(({mountSharedReader})=>{if(disposed)return;shared=mountSharedReader(root,{...options.shared,onActiveArticle:article=>{owned.ReadWeaveActiveArticle=article;options.onActiveArticle?.(article)},bridge:()=>owned.ReaderSourceBridge?.getState(),updateGlossary:terms=>owned.ReaderSourceBridge?.updateGlossary(terms),hydrateMedia:element=>owned.ReaderSourceBridge?.hydrateSharedMedia(element),hydrateText:element=>owned.ReaderSourceBridge?.hydrateSharedText(element)});}).catch(error=>{if(!disposed)console.error('ReadWeave component',error);});
  }
  if(options.embedded){
    root.querySelector('#toggle-theme').hidden=true;
    const actions=globalThis.document.createElement('div');actions.className='control-group workspace-reader-actions';actions.setAttribute('role','group');actions.setAttribute('aria-label','读本操作');
    for(const action of options.actions||[]){const button=globalThis.document.createElement('button');button.type='button';button.className='icon-button';button.innerHTML=action.icon;button.title=action.label;button.setAttribute('aria-label',action.label);button.disabled=!!action.disabled;listen(button,'click',action.run);actions.append(button)}
    root.querySelector('.demo-header-actions').append(actions);
  }
  listen(root,'reading:layout-reset',()=>options.onResetLayout?.());
  listen(root,'reading:source-selection',event=>options.onSourceSelection?.(event.detail));
  if(options.onNavigate)listen(root,'click',event=>{const link=event.target.closest?.('a[href]');if(!link||event.ctrlKey||event.metaKey||event.shiftKey||link.target==='_blank')return;const url=new URL(link.href,native.location.href);if(/\\/(?:book|readweave)\\.html$/.test(url.pathname)&&url.pathname.startsWith(config.base+'/')){event.preventDefault();options.onNavigate(url.search)}},true);
  const bound=new WeakSet(), noteBindings=new Map();
  const refreshNotes=()=>{for(const [box,binding]of noteBindings){
    if(!box.isConnected){noteBindings.delete(box);continue;}const {input,key}=binding,snapshot=input.value;
    Promise.resolve(options.loadNote?.(key)).then(reply=>{const value=reply&&typeof reply==='object'?reply.value:reply;if(!disposed&&value!==undefined&&!input.hasAttribute('data-note-draft')&&input.value===snapshot&&(options.shared||!input.value)){input.value=value??'';binding.version=reply&&typeof reply==='object'?{revision:reply.revision,linkRevision:reply.linkRevision}:{};}}).catch(()=>{});
  }};
  const connectNotes=()=>root.querySelectorAll('.writing-note').forEach(box=>{
    if(bound.has(box))return;const state=owned.ReaderSourceBridge?.getState();if(!state?.doc)return;
    bound.add(box);const input=box.querySelector('textarea'),button=box.querySelector('button');
    const key=state.doc.section_id+':'+box.dataset.noteId;
    const binding={input,key,version:{}};noteBindings.set(box,binding);refreshNotes();
    listen(button,'click',async()=>{const status=box.querySelector('.help');try{const reply=await options.saveNote?.(key,input.value,binding.version);if(reply&&typeof reply==='object')binding.version={revision:reply.revision,linkRevision:reply.linkRevision};if(status)status.textContent=options.shared?'已保存到共享学习笔记':'已保存到个人笔记';}catch(error){input.dataset.noteDraft='true';if(status)status.textContent=error.message||'笔记暂时没有保存，当前输入仍然保留';}});
  });
  if(options.shared)listen(native,'readweave:shared-change',refreshNotes);
  const observer=new MutationObserver(connectNotes);observer.observe(root,{childList:true,subtree:true});connectNotes();
  return {root, navigate:search=>owned.ReaderSourceBridge.navigate(search), setTheme:name=>owned.ReaderUI?.setTheme(name), getState:()=>({...owned.ReaderSourceBridge?.getState(),sharedArticle:owned.ReadWeaveActiveArticle}),
    focusNotes:()=>root.querySelector('.writing-note textarea')?.focus(),
    toggleGlossary:()=>root.querySelector('[data-toggle-pane="glossary"]')?.click(),
    unmount(){disposed=true;shared?.unmount();abort.abort();for(const item of [...observers])item.disconnect();for(const id of timers){native.clearTimeout(id);native.clearInterval(id)}for(const id of frames)native.cancelAnimationFrame(id);shadow.replaceChildren();}
  };
}
'''
    (HERE/'reader-component.js').write_text('const DESIGN_TOKENS='+(READER/'design-tokens.json').read_text('utf-8')+';\nconst STYLES='+json.dumps(styles,ensure_ascii=False)+';\nconst TEMPLATE='+json.dumps(body,ensure_ascii=False)+';\n'+header+scripts+tail,'utf-8')


if __name__=='__main__':
    build()
