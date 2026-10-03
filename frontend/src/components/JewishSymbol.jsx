export default function JewishSymbol({name='star',className=''}) {
 return <svg className={className} width="30" height="30" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{name==='star'?<><path d="M24 5 42 36H6Z"/><path d="M24 43 6 12h36Z"/></>:<><path d="M24 9v31M8 14v7a16 16 0 0 0 32 0v-7M14 12v9a10 10 0 0 0 20 0v-9M19 10v11a5 5 0 0 0 10 0V10M16 42h16M20 39h8"/>{[8,14,19,24,29,34,40].map((x,i)=><path key={x} d={`M${x} ${[9,7,5,3,5,7,9][i]}v2`} stroke="#f9d795" strokeWidth="3"/>)}</>}</svg>;
}
