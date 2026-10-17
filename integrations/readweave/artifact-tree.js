export function mountArtifactTree(container, document, options={}) {
  const controller=new AbortController();
  const root=window.document.createElement('section');root.style.cssText='font:14px/1.9 system-ui;padding:24px;overflow:auto;height:100%;background:#fafaf7;color:#263a2c';
  const details=window.document.createElement('pre');details.style.cssText='white-space:pre-wrap;font:12px/1.8 monospace;border-top:1px solid #ddd;padding-top:15px';details.hidden=true;
  const debug=window.document.createElement('label'),toggle=window.document.createElement('input');toggle.type='checkbox';debug.append(toggle,' Debug');root.append(debug);
  toggle.addEventListener('change',()=>details.hidden=!toggle.checked,{signal:controller.signal});
  function node(value){const group=window.document.createElement('details');group.open=true;group.style.marginLeft='14px';const title=window.document.createElement('summary');const text=value.title||value.text||((value.premise||'')+(value.question||''))||value.content?.text||value.content?.name||value.id;title.textContent=text;title.style.cursor='pointer';title.addEventListener('click',()=>{details.textContent=JSON.stringify(value,null,2);options.onSelect?.(value)},{signal:controller.signal});group.append(title);for(const child of value.children||[])group.append(node(child));return group}
  if(document?.tree)root.append(node(document.tree));else root.append(window.document.createTextNode('这个阶段尚未生成'));
  root.append(details);container.replaceChildren(root);
  return {unmount(){controller.abort();container.replaceChildren()}};
}
