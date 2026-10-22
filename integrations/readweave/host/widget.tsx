import { useState } from 'preact/hooks';

// 宿主只提供卡片外框，选择、提问、定义和编辑都由原生组件完成
export default function RightPanelWidget({id,title,children,buttons}:any){
 const [expanded,setExpanded]=useState(true);
 return <section id={id} class={'card widget'+(expanded?'':' collapsed')}>
  <header class="card-header"><button type="button" aria-label={expanded?'收起 ReadWeave':'展开 ReadWeave'} onClick={()=>setExpanded(!expanded)}>{expanded?'▾':'▸'}</button><span class="card-header-title">{title}</span>{buttons}</header>
  <div class="body-wrapper" hidden={!expanded}><div class="card-body">{children}</div></div>
 </section>;
}
