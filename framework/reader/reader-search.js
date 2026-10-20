/* 输入后搜索全书，索引只读取已有产物，正文与用户笔记保持原样 */
(() => {
 const header=document.querySelector('.demo-masthead');if(!header)return;
 const form=document.createElement('form');form.className='reader-search';form.setAttribute('role','search');
 form.innerHTML='<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></svg><input type="search" role="combobox" aria-label="搜索全书正文" placeholder="搜索全书正文" autocomplete="off" aria-autocomplete="list" aria-expanded="false" aria-controls="reader-search-list"><kbd>Ctrl K</kbd><div class="reader-search-results" hidden><p class="reader-search-status" role="status"></p><div id="reader-search-list" role="listbox" aria-label="搜索结果"></div></div>';
 header.insertBefore(form,header.querySelector('.demo-header-actions'));
 const input=form.querySelector('input'),panel=form.querySelector('.reader-search-results'),list=form.querySelector('[role=listbox]'),status=form.querySelector('[role=status]');
 const cache=new Map();let ready,sequence=0,timer,bookPromise,active=-1,buttons=[];
 const path=value=>window.LWPath?window.LWPath(value):value;
 function entries(doc){const rows=[],add=(text,block)=>{if(typeof text==='string'&&text.trim())rows.push({text,lower:text.toLocaleLowerCase(),block})};
  function walk(value,block=null){if(!value||typeof value!=='object')return;if(value.id)block=value.id;
   if(value.kind==='heading'||value.kind==='paragraph'){add(value.text,block);return}
   if(value.kind==='list'){for(const text of value.items||[])add(text,block);return}
   if(value.kind==='table')add([...(value.headers||[]),...(value.rows||[]).flat()].join(' '),block);
   if(['code','formula','mermaid'].includes(value.kind))add(value.text,block);
   for(const [key,child]of Object.entries(value)){
    if(['glossary','source_links','bindings','coverage','preview_provenance','grounding','catalog_path','source_refs','local_notations'].includes(key))continue;
    if(typeof child==='object')Array.isArray(child)?child.forEach(c=>walk(c,block)):walk(child,block);
    else if(['caption','reading_guide','explanation','takeaway','conclusion','relation_to_whole','premise','action','result','meaning','purpose','sentence','answer','collaboration','title_premise','title_question'].includes(key))add(child,block);
   }
  }walk(doc);return rows;
 }
 function index(section,doc){if(!cache.has(section.id))cache.set(section.id,{...section,rows:entries(doc)})}
 async function documents(){
  if(!bookPromise)bookPromise=(async()=>{
   const r=await fetch(path('05_writing/preview-book.json')),book=r.ok?await r.json():await(await fetch(path('05_writing/book.json'))).json();
   const sections=book.chapters.flatMap(c=>c.sections);let at=0;
   await Promise.all(Array.from({length:4},async()=>{while(at<sections.length){const section=sections[at++];if(cache.has(section.id))continue;const response=await fetch(path(section.path));if(response.ok)index(section,await response.json())}}));
   return sections;
  })().catch(e=>{bookPromise=null;throw e});
  await bookPromise;return [...cache.values()];
 }
 function show(value){panel.hidden=!value;input.setAttribute('aria-expanded',String(value));if(!value){active=-1;input.removeAttribute('aria-activedescendant')}}
 function activate(n){active=Math.max(0,Math.min(buttons.length-1,n));buttons.forEach((b,i)=>b.setAttribute('aria-selected',String(i===active)));if(buttons[active]){input.setAttribute('aria-activedescendant',buttons[active].id);buttons[active].scrollIntoView({block:'nearest'})}}
 function locate(block,query){
  window.ReaderUI?.openPane('lesson');const target=block?document.getElementById('block-'+block):document.getElementById('demo-content');if(!target)return;
  target.scrollIntoView({block:'center',behavior:'instant'});target.classList.add('reader-search-target');setTimeout(()=>target.classList.remove('reader-search-target'),2200);
  if(window.Highlight&&CSS.highlights){const ranges=[],walker=document.createTreeWalker(target,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest('button,textarea,.reader-math,.katex')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
   while(walker.nextNode()){const n=walker.currentNode,text=n.nodeValue.toLocaleLowerCase();let start=0,i;while((i=text.indexOf(query.toLocaleLowerCase(),start))>=0){const range=document.createRange();range.setStart(n,i);range.setEnd(n,i+query.length);ranges.push(range);start=i+query.length}}CSS.highlights.set('reader-search',new Highlight(...ranges));
  }
 }
 async function search(){const mine=++sequence,query=input.value.trim();list.replaceChildren();buttons=[];active=-1;show(Boolean(query));if(!query){CSS.highlights?.delete('reader-search');return}
  if(!ready){status.textContent='正文载入后开始查找';return}status.textContent='正在搜索全书';
  try{const docs=await documents();if(mine!==sequence)return;let total=0;const needle=query.toLocaleLowerCase();
   for(const d of docs)for(const row of d.rows){const at=row.lower.indexOf(needle);if(at<0)continue;total++;if(buttons.length>=60)continue;
    const button=document.createElement('button');button.type='button';button.id='reader-hit-'+buttons.length;button.setAttribute('role','option');button.setAttribute('aria-selected','false');
    const title=document.createElement('span');title.textContent=d.title;const excerpt=document.createElement('span'),begin=Math.max(0,at-24),end=at+query.length;
    excerpt.append(document.createTextNode((begin?'…':'')+row.text.slice(begin,at)));const mark=document.createElement('mark');mark.textContent=row.text.slice(at,end);excerpt.append(mark,document.createTextNode(row.text.slice(end,end+80)));button.append(title,excerpt);
    button.onclick=()=>{show(false);if(d.id===ready.doc.section_id)locate(row.block,query);else{const url=new URL(location.href);url.searchParams.set('section',d.id);url.searchParams.set('find',query);if(row.block)url.searchParams.set('block',row.block);location.href=url.href}};
    buttons.push(button);list.append(button);
   }status.textContent=total?(total>60?'找到 '+total+' 处，先显示前 60 处':'找到 '+total+' 处'):'全书没有匹配内容';if(buttons.length)activate(0);
  }catch(error){if(mine===sequence)status.textContent='本次搜索未完成，再输入即可重试';console.error(error)}
 }
 form.onsubmit=e=>{e.preventDefault();if(active>=0)buttons[active]?.click();else search()};
 input.oninput=()=>{++sequence;clearTimeout(timer);timer=setTimeout(search,160)};
 input.onfocus=()=>{if(input.value.trim())show(true)};
 input.onkeydown=e=>{if(e.key==='Escape'){show(false);input.blur()}else if(['ArrowDown','ArrowUp'].includes(e.key)&&buttons.length){e.preventDefault();show(true);activate(active+(e.key==='ArrowDown'?1:-1))}};
 document.addEventListener('pointerdown',e=>{if(!form.contains(e.target))show(false)});
 document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();input.focus();input.select()}});
 document.addEventListener('reading:document-ready',event=>{ready=event.detail;index({id:ready.doc.section_id,title:ready.doc.title},ready.doc);const params=new URLSearchParams(location.search);if(params.get('find')){input.value=params.get('find');setTimeout(()=>locate(params.get('block'),input.value),150)}else if(location.hash.startsWith('#heading-')){const target=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(target)setTimeout(()=>(target.matches('figcaption')?target.closest('.lw-media'):target).scrollIntoView({block:'start'}),150)}});
})();
