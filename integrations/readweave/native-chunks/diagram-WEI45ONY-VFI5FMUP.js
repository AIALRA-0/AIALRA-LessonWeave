import{a as F}from"./chunk-2KZLJ3MZ.js";import{a as _}from"./chunk-4T4VSO2B.js";import{a as D}from"./chunk-SYB3J72Q.js";import"./chunk-ENGTSJDD.js";import"./chunk-TAEUGFPI.js";import"./chunk-2TCOFK2F.js";import"./chunk-KKXHN4H7.js";import"./chunk-DUEXTXBX.js";import"./chunk-4JVBCYMY.js";import"./chunk-POO24QG3.js";import"./chunk-HDWBKE3E.js";import"./chunk-2YZRN676.js";import"./chunk-KAL3PKK5.js";import"./chunk-2E3B4Z7V.js";import"./chunk-YGTB62VF.js";import"./chunk-TWI7BP3O.js";import"./chunk-BSPR3HME.js";import"./chunk-WJTLWZK6.js";import"./chunk-C5SO5IYD.js";import{o as y}from"./chunk-2NSFK2MV.js";import"./chunk-HDEC2OZ7.js";import{N as L,S as T,T as S,U as O,V as k,W as R,X as I,Y as E,h as A,j as M,t as C}from"./chunk-HNBZIBMT.js";import{a as b}from"./chunk-A4UI2OWC.js";import"./chunk-QLTNP2JE.js";import{a as i}from"./chunk-I5VDREFL.js";import"./chunk-N75YSNYA.js";import"./chunk-LUUESNYC.js";import{i as w}from"./chunk-JDSUVWEQ.js";w();var x={showLegend:!0,ticks:5,max:null,min:0,graticule:"circle"},P={axes:[],curves:[],options:x},g=structuredClone(P),N=M.radar,U=i(()=>y({...N,...C().radar}),"getConfig"),z=i(()=>g.axes,"getAxes"),X=i(()=>g.curves,"getCurves"),Y=i(()=>g.options,"getOptions"),Z=i(a=>{g.axes=a.map(t=>({name:t.name,label:t.label??t.name}))},"setAxes"),q=i(a=>{g.curves=a.map(t=>({name:t.name,label:t.label??t.name,entries:J(t.entries)}))},"setCurves"),J=i(a=>{if(a[0].axis==null)return a.map(e=>e.value);let t=z();if(t.length===0)throw new Error("Axes must be populated before curves for reference entries");return t.map(e=>{let r=a.find(n=>n.axis?.$refText===e.name);if(r===void 0)throw new Error("Missing entry for axis "+e.label);return r.value})},"computeCurveEntries"),K=i(a=>{let t=a.reduce((e,r)=>(e[r.name]=r,e),{});g.options={showLegend:t.showLegend?.value??x.showLegend,ticks:t.ticks?.value??x.ticks,max:t.max?.value??x.max,min:t.min?.value??x.min,graticule:t.graticule?.value??x.graticule}},"setOptions"),Q=i(()=>{T(),g=structuredClone(P)},"clear"),f={getAxes:z,getCurves:X,getOptions:Y,setAxes:Z,setCurves:q,setOptions:K,getConfig:U,clear:Q,setAccTitle:S,getAccTitle:O,setDiagramTitle:I,getDiagramTitle:E,getAccDescription:R,setAccDescription:k},tt=i(a=>{_(a,f);let{axes:t,curves:e,options:r}=a;f.setAxes(t),f.setCurves(e),f.setOptions(r)},"populate"),et={parse:i(async a=>{let t=await D("radar",a);b.debug(t),tt(t)},"parse")},at=i((a,t,e,r)=>{let n=r.db,l=n.getAxes(),c=n.getCurves(),s=n.getOptions(),o=n.getConfig(),d=n.getDiagramTitle(),p=F(t),u=rt(p,o),m=s.max??Math.max(...c.map($=>Math.max(...$.entries))),h=s.min,v=Math.min(o.width,o.height)/2;nt(u,l,v,s.ticks,s.graticule),st(u,l,v,o),G(u,l,c,h,m,s.graticule,o),V(u,c,s.showLegend,o),u.append("text").attr("class","radarTitle").text(d).attr("x",0).attr("y",-o.height/2-o.marginTop)},"draw"),rt=i((a,t)=>{let e=t.width+t.marginLeft+t.marginRight,r=t.height+t.marginTop+t.marginBottom,n={x:t.marginLeft+t.width/2,y:t.marginTop+t.height/2};return L(a,r,e,t.useMaxWidth??!0),a.attr("viewBox",`0 0 ${e} ${r}`).attr("overflow","visible"),a.append("g").attr("transform",`translate(${n.x}, ${n.y})`)},"drawFrame"),nt=i((a,t,e,r,n)=>{if(n==="circle")for(let l=0;l<r;l++){let c=e*(l+1)/r;a.append("circle").attr("r",c).attr("class","radarGraticule")}else if(n==="polygon"){let l=t.length;for(let c=0;c<r;c++){let s=e*(c+1)/r,o=t.map((d,p)=>{let u=2*p*Math.PI/l-Math.PI/2,m=s*Math.cos(u),h=s*Math.sin(u);return`${m},${h}`}).join(" ");a.append("polygon").attr("points",o).attr("class","radarGraticule")}}},"drawGraticule"),st=i((a,t,e,r)=>{let n=t.length;for(let l=0;l<n;l++){let c=t[l].label,s=2*l*Math.PI/n-Math.PI/2,o=Math.cos(s),d=Math.sin(s);a.append("line").attr("x1",0).attr("y1",0).attr("x2",e*r.axisScaleFactor*o).attr("y2",e*r.axisScaleFactor*d).attr("class","radarAxisLine");let p=o>.01?"start":o<-.01?"end":"middle",u=d>.01?"hanging":d<-.01?"auto":"central",m=4;a.append("text").text(c).attr("x",e*r.axisLabelFactor*o+m*o).attr("y",e*r.axisLabelFactor*d+m*d).attr("text-anchor",p).attr("dominant-baseline",u).attr("class","radarAxisLabel")}},"drawAxes");function G(a,t,e,r,n,l,c){let s=t.length,o=Math.min(c.width,c.height)/2;e.forEach((d,p)=>{if(d.entries.length!==s)return;let u=d.entries.map((m,h)=>{let v=2*Math.PI*h/s-Math.PI/2,$=B(m,r,n,o),H=$*Math.cos(v),j=$*Math.sin(v);return{x:H,y:j}});l==="circle"?a.append("path").attr("d",W(u,c.curveTension)).attr("class",`radarCurve-${p}`):l==="polygon"&&a.append("polygon").attr("points",u.map(m=>`${m.x},${m.y}`).join(" ")).attr("class",`radarCurve-${p}`)})}i(G,"drawCurves");function B(a,t,e,r){let n=Math.min(Math.max(a,t),e);return r*(n-t)/(e-t)}i(B,"relativeRadius");function W(a,t){let e=a.length,r=`M${a[0].x},${a[0].y}`;for(let n=0;n<e;n++){let l=a[(n-1+e)%e],c=a[n],s=a[(n+1)%e],o=a[(n+2)%e],d={x:c.x+(s.x-l.x)*t,y:c.y+(s.y-l.y)*t},p={x:s.x-(o.x-c.x)*t,y:s.y-(o.y-c.y)*t};r+=` C${d.x},${d.y} ${p.x},${p.y} ${s.x},${s.y}`}return`${r} Z`}i(W,"closedRoundCurve");function V(a,t,e,r){if(!e)return;let n=(r.width/2+r.marginRight)*3/4,l=-(r.height/2+r.marginTop)*3/4,c=20;t.forEach((s,o)=>{let d=a.append("g").attr("transform",`translate(${n}, ${l+o*c})`);d.append("rect").attr("width",12).attr("height",12).attr("class",`radarLegendBox-${o}`),d.append("text").attr("x",16).attr("y",0).attr("class","radarLegendText").text(s.label)})}i(V,"drawLegend");var ot={draw:at},it=i((a,t)=>{let e="";for(let r=0;r<a.THEME_COLOR_LIMIT;r++){let n=a[`cScale${r}`];e+=`
		.radarCurve-${r} {
			color: ${n};
			fill: ${n};
			fill-opacity: ${t.curveOpacity};
			stroke: ${n};
			stroke-width: ${t.curveStrokeWidth};
		}
		.radarLegendBox-${r} {
			fill: ${n};
			fill-opacity: ${t.curveOpacity};
			stroke: ${n};
		}
		`}return e},"genIndexStyles"),lt=i(a=>{let t=A(),e=C(),r=y(t,e.themeVariables),n=y(r.radar,a);return{themeVariables:r,radarOptions:n}},"buildRadarStyleOptions"),ct=i(({radar:a}={})=>{let{themeVariables:t,radarOptions:e}=lt(a);return`
	.radarTitle {
		font-size: ${t.fontSize};
		color: ${t.titleColor};
		dominant-baseline: hanging;
		text-anchor: middle;
	}
	.radarAxisLine {
		stroke: ${e.axisColor};
		stroke-width: ${e.axisStrokeWidth};
	}
	.radarAxisLabel {
		font-size: ${e.axisLabelFontSize}px;
		color: ${e.axisColor};
	}
	.radarGraticule {
		fill: ${e.graticuleColor};
		fill-opacity: ${e.graticuleOpacity};
		stroke: ${e.graticuleColor};
		stroke-width: ${e.graticuleStrokeWidth};
	}
	.radarLegendText {
		text-anchor: start;
		font-size: ${e.legendFontSize}px;
		dominant-baseline: hanging;
	}
	${it(t,e)}
	`},"styles"),Ct={parser:et,db:f,renderer:ot,styles:ct};export{Ct as diagram};
