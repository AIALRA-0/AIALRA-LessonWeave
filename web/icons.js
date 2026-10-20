const paths={
 menu:'M4 6h16M4 12h16M4 18h16',plus:'M12 4v16M4 12h16',
 folder:'M3 7V5h6l2 2h10v13H3Z',file:'M6 3h8l4 4v14H6ZM14 3v5h4M9 12h6M9 16h6',
 chevron:'m9 5 7 7-7 7',search:'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
 trash:'M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7',
 edit:'m4 16-1 5 5-1L20 8l-4-4ZM14 6l4 4',move:'M12 3v18M3 12h18M8 7l4-4 4 4M8 17l4 4 4-4M7 8l-4 4 4 4M17 8l4 4-4 4',
 theme:'M12 3a9 9 0 1 0 0 18V3ZM12 3a9 9 0 0 1 0 18',close:'M5 5l14 14M19 5 5 19',
 book:'M12 5C7 2 3 4 3 4v15s4-2 9 1c5-3 9-1 9-1V4s-4-2-9 1ZM12 5v15',
 download:'M12 3v12m-5-5 5 5 5-5M4 15v6h16v-6',external:'M14 3h7v7M21 3 10 14M10 3H3v18h18v-7',
 progress:'M4 5h3m3 0h10M4 12h3m3 0h10M4 19h3m3 0h10',
 flow:'M3 3h6v6H3ZM15 15h6v6h-6ZM15 3h6v6h-6ZM9 6h6M6 9v9h9',
 chart:'M4 3v18h17M8 17v-5M13 17V7M18 17V4',stop:'M5 5h14v14H5Z',play:'m7 4 14 8-14 8Z',refresh:'M20 7a8 8 0 1 0 1 8M20 3v5h-5'
};
export const icon=name=>'<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+(paths[name]||paths.file)+'"/></svg>';
export function iconControl(node,name,label){if(!node)return;node.innerHTML=icon(name);node.setAttribute('aria-label',label);node.title=label;node.classList.add('icon-control');}
