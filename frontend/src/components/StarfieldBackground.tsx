import type {CSSProperties} from 'react';
// Fireline v17 depth, palette and drift, with stable placement across mode changes.
const layers=[{count:120,duration:95,shift:-4,size:1.6},{count:80,duration:65,shift:5,size:2.3},{count:34,duration:42,shift:-7,size:3.2}];
const noise=(seed:number)=>{const n=Math.sin(seed*127.1+311.7)*43758.5453;return n-Math.floor(n);};
export function StarfieldBackground(){
  return <div className="visual-sky" aria-hidden="true"><div className="sky-earth"/><div className="sky-cool-halo"/><div className="sky-warm-halo"/>{layers.map((layer,l)=><div className="star-depth" key={l} style={{'--drift-time':`${layer.duration}s`,'--drift-x':`${layer.shift}%`} as CSSProperties}>{Array.from({length:layer.count},(_,i)=>{
    const seed=i+l*173,diameter=layer.size*(.55+noise(seed+7)*.6);
    return <i key={i} className={i%19===0?'star-bright':undefined} style={{left:`${noise(seed+1)*100}%`,top:`${noise(seed+2)*100}%`,width:diameter,height:diameter,'--star-color':['#E1B983','#faf5ff','#ad87c7'][i%3],'--star-alpha':.56+noise(seed+3)*.24,animationDuration:`${3+noise(seed+4)*7}s`,animationDelay:`-${noise(seed+5)*12}s`} as CSSProperties}/>;
  })}</div>)}</div>;
}
