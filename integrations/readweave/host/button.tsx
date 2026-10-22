export default function Button({text,buttonRef,children,onClick,className,disabled,kind,icon,title,...props}:any){
 return <button ref={buttonRef} type={onClick?'button':'submit'} class={'btn '+(kind==='primary'?'btn-primary ':'btn-secondary ')+(className||'')} disabled={disabled} onClick={onClick} title={title} style={props.style}>{icon&&<i class={icon}/ >}{text??children}</button>;
}
