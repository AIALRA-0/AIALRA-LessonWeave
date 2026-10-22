import { render } from 'preact';
import Panel from '@readweave/Panel';
import { HostContext } from './hooks';
import { setRoot } from './globals';
import { setTransport } from './server';
import DOMPurify from 'dompurify';
import './host.css';
import 'boxicons/css/boxicons.min.css';
import iconFontUrl from 'boxicons/fonts/boxicons.woff2';

// 浏览器不会从 Shadow DOM 的样式中登记字体，先把同一份图标字体交给文档
const iconFontUrlFromBundle=new URL(iconFontUrl,import.meta.url).href;
const iconFont=new FontFace('boxicons',`url(${iconFontUrlFromBundle})`);
const iconFontReady=iconFont.load().then(font=>{document.fonts.add(font);return font;}).catch(error=>{console.warn('ReadWeave icon font',error);return null;});

export const sanitizeArticle=(body:string)=>DOMPurify.sanitize(body,{FORBID_TAGS:['script','style','iframe','object','form','input','button'],FORBID_ATTR:['contenteditable']});

export function mountReadWeave(container:HTMLElement,options:any){
 setRoot(options.root);setTransport(options.request);
 let article:any=null,contentElement:HTMLElement|null=null;
 let context:any=null;
 const draw=()=>{
  if(!context||context.noteId!==article?.articleId||context.contentElement!==contentElement){
   const element=contentElement;
   context={noteId:article?.articleId,contentElement:element,noteContext:{contentElement:element,getTextEditor:async()=>null,getContentElement:async()=>element?[element]:[]}};
  }
  const state={...context,note:article?{title:article.title,type:'text',isContentAvailable:()=>!article.deleted}:null};
  render(<HostContext.Provider value={state}><Panel/></HostContext.Provider>,container);
 };
 const contextMenu=(event:MouseEvent)=>{
  if(!contentElement)return;
  const owner=contentElement.ownerDocument,selection=contentElement.getRootNode() instanceof ShadowRoot?(contentElement.getRootNode() as ShadowRoot).getSelection?.():owner.getSelection();
  if(!selection?.rangeCount||selection.isCollapsed)return;
  const range=selection.getRangeAt(0);if(!contentElement.contains(range.startContainer)||!contentElement.contains(range.endContainer))return;
  event.preventDefault();owner.dispatchEvent(new Event('selectionchange'));event.target?.dispatchEvent(new (owner.defaultView?.MouseEvent||MouseEvent)('mouseup',{bubbles:true,composed:true}));
 };
 options.root.addEventListener('contextmenu',contextMenu,true);
 let externalDocument:Document|null=null;
 return {update(next:any,element:HTMLElement){
  const nextDocument=element.ownerDocument===container.ownerDocument?null:element.ownerDocument;
  if(nextDocument!==externalDocument){externalDocument?.removeEventListener('contextmenu',contextMenu,true);externalDocument=nextDocument;externalDocument?.addEventListener('contextmenu',contextMenu,true);if(nextDocument)iconFontReady.then(font=>{if(font)nextDocument.fonts.add(font);});}
  article=next;contentElement=element;draw();
 },unmount(){options.root.removeEventListener('contextmenu',contextMenu,true);externalDocument?.removeEventListener('contextmenu',contextMenu,true);render(null,container);}};
}
