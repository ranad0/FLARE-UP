import type {CSSProperties} from 'react';
// Stable, tiny stars in three depth layers; no random remounts when modes change.
const layers=[{count:120,duration:110,size:1},{count:80,duration:80,size:1.3},{count:34,duration:55,size:1.7}];
export function StarfieldBackground(){
  return <div className="visual-sky" aria-hidden="true"><div className="sky-earth"/><div className="sky-cool-halo"/><div className="sky-warm-halo"/>{layers.map((layer,l)=><div className="star-depth" key={l} style={{'--drift-time':`${layer.duration}s`,'--drift-x':`${l===1?2:-2}%`} as CSSProperties}>{Array.from({length:layer.count},(_,i)=><i key={i} style={{left:`${(i*61.803+l*17)%100}%`,top:`${(i*37.719+l*23)%100}%`,width:layer.size,height:layer.size,background:['#fff3d7','#ffffff','#c7b5e7'][i%3],'--star-alpha':.28+(i%5)*.085,animationDuration:`${7+i%7}s`,animationDelay:`-${i%11}s`} as CSSProperties}/>)}</div>)}</div>;
}
