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
    styles='\n'.join((READER/name).read_text('utf-8') for name in ['reader.css','writing-demo.css','reading-ui.css'])
    styles=re.sub(r'(?<![\w-])(?:html|body|:root)(?![\w-])','.lw-reader-root',styles)
    header='''// This module mounts one independent reading view per container
export function mountReader(container, options) {
  const shadow = container.shadowRoot || container.attachShadow({mode:'open'});
  const style = globalThis.document.createElement('style');
  const root = globalThis.document.createElement('div');
  root.className = 'lw-reader-root writing-page demo-page reader-ui book-page';
  root.lang='zh-CN'; root.dataset.theme='light';
  style.textContent=STYLES; root.innerHTML=TEMPLATE; shadow.replaceChildren(style,root);
  const abort=new AbortController(), timers=new Set(), frames=new Set(), observers=new Set(); let disposed=false;
  const native=globalThis.window;
  const tracked=kind=>class extends native[kind] {constructor(...args){super(...args);observers.add(this)}disconnect(){super.disconnect();observers.delete(this)}};
  const MutationObserver=tracked('MutationObserver'), ResizeObserver=tracked('ResizeObserver'), IntersectionObserver=tracked('IntersectionObserver');
  const config={project_id:options.projectId,base:options.base,readweave_demo:true,legacy:!!options.legacy};
  const path=value=>{let text=String(value||'');const resolved=options.resolveResource?.(text);if(resolved)return resolved;if(/^(https?:|data:|blob:|#)/.test(text))return text;if(text.startsWith(config.base+'/'))return text;if(text.startsWith('/book.html')||text.startsWith('book.html'))text=text.replace('book.html','readweave.html');return config.base+'/'+text.replace(/^\\/+/,'')};
  const fetch=(value, init)=>value==='/design-tokens.json'?Promise.resolve(new Response(JSON.stringify(DESIGN_TOKENS),{headers:{'Content-Type':'application/json'}})):options.fetch?options.fetch(value,init):native.fetch(typeof value==='string'&&/^\\/(0[0-5]_)/.test(value)?path(value):value,init);
  const location={pathname:'readweave/book.html',search:options.search??'?preview=true',hash:''};
  const owned={LESSONWEAVE:config,LWPath:path};
  const listen=(target,type,handler,settings={})=>target.addEventListener(type,handler,{...(typeof settings==='boolean'?{capture:settings}:settings),signal:abort.signal});
  const document=new Proxy(native.document,{get(target,key){
    if(key==='body'||key==='documentElement')return root;
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
    scripts=(READER/'reading-icons.js').read_text('utf-8')+'\nconst uiIcon=window.uiIcon;\n'+'\n\n'.join((READER/name).read_text('utf-8') for name in ['writing-demo.js','reading-ui.js','source-locator.js','source-split.js'])
    tail='''
  listen(root,'reading:source-selection',event=>options.onSourceSelection?.(event.detail));
  if(options.onNavigate)listen(root,'click',event=>{const link=event.target.closest?.('a[href]');if(!link||event.ctrlKey||event.metaKey||event.shiftKey||link.target==='_blank')return;const url=new URL(link.href,native.location.href);if(/\\/(?:book|readweave)\\.html$/.test(url.pathname)&&url.pathname.startsWith(config.base+'/')){event.preventDefault();options.onNavigate(url.search)}},true);
  const bound=new WeakSet();
  const connectNotes=()=>root.querySelectorAll('.writing-note').forEach(box=>{
    if(bound.has(box))return;const state=owned.ReaderSourceBridge?.getState();if(!state?.doc)return;
    bound.add(box);const input=box.querySelector('textarea'),button=box.querySelector('button');
    const key=state.doc.section_id+':'+box.dataset.noteId;
    Promise.resolve(options.loadNote?.(key)).then(value=>{if(!disposed&&!input.value&&value)input.value=value});
    listen(button,'click',async()=>{await options.saveNote?.(key,input.value);const status=box.querySelector('.help');if(status)status.textContent='已保存到个人笔记'});
  });
  const observer=new MutationObserver(connectNotes);observer.observe(root,{childList:true,subtree:true});connectNotes();
  return {root, getState:()=>owned.ReaderSourceBridge?.getState(),
    focusNotes:()=>root.querySelector('.writing-note textarea')?.focus(),
    toggleGlossary:()=>root.querySelector('[data-toggle-pane="glossary"]')?.click(),
    unmount(){disposed=true;abort.abort();for(const item of [...observers])item.disconnect();for(const id of timers){native.clearTimeout(id);native.clearInterval(id)}for(const id of frames)native.cancelAnimationFrame(id);shadow.replaceChildren();}
  };
}
'''
    (HERE/'reader-component.js').write_text('const DESIGN_TOKENS='+(READER/'design-tokens.json').read_text('utf-8')+';\nconst STYLES='+json.dumps(styles,ensure_ascii=False)+';\nconst TEMPLATE='+json.dumps(body,ensure_ascii=False)+';\n'+header+scripts+tail,'utf-8')


if __name__=='__main__':
    build()
