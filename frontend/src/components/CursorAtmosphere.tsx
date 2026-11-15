import {useEffect,useRef} from 'react';
import type {VisualMode} from './visualMode';
type TrailPoint={x:number;y:number;born:number};
/** A short, low-opacity ribbon; bounded, demand-driven, and never intercepting input. */
export function CursorAtmosphere({mode}:{mode:VisualMode}){
  const ref=useRef<HTMLCanvasElement>(null),modeRef=useRef(mode);
  useEffect(()=>{modeRef.current=mode;},[mode]);
  useEffect(()=>{
    const canvas=ref.current!,ctx=canvas.getContext('2d');if(!ctx)return;
    const motion=matchMedia('(prefers-reduced-motion: reduce)'),fine=matchMedia('(hover: hover) and (pointer: fine)');
    let points:TrailPoint[]=[],frame=0,last=0,moved=0,tx=0,ty=0,sx=0,sy=0,mix=modeRef.current==='micro'?1:0;
    const clear=()=>{cancelAnimationFrame(frame);frame=0;points=[];moved=0;ctx.clearRect(0,0,innerWidth,innerHeight);};
    const resize=()=>{clear();const d=Math.min(devicePixelRatio||1,2);canvas.width=innerWidth*d;canvas.height=innerHeight*d;ctx.setTransform(d,0,0,d,0,0);};
    const draw=(now:number)=>{
      const dt=Math.min((now-last)/1000,.04);last=now;ctx.clearRect(0,0,innerWidth,innerHeight);
      mix+=(Number(modeRef.current==='micro')-mix)*Math.min(1,dt*5);
      const follow=1-Math.exp(-24*dt);sx+=(tx-sx)*follow;sy+=(ty-sy)*follow;
      if(now-moved<100&&(!points.length||Math.hypot(sx-points[points.length-1].x,sy-points[points.length-1].y)>.8))points.push({x:sx,y:sy,born:now});
      points=points.filter(p=>now-p.born<420).slice(-36);
      const color=`${Math.round(225-120*mix)},${Math.round(185+5*mix)},${Math.round(131+124*mix)}`;
      ctx.lineCap='round';ctx.lineJoin='round';
      for(let i=1;i<points.length;i++){
        const a=points[i-1],b=points[i],fade=Math.max(0,1-(now-a.born)/420);
        const lift=(p:TrailPoint)=>(now-p.born)/1000*9*(1-mix);
        ctx.beginPath();ctx.moveTo(a.x,a.y-lift(a));ctx.lineTo(b.x,b.y-lift(b));
        ctx.strokeStyle=`rgba(${color},${fade*.055})`;ctx.lineWidth=5;ctx.stroke();
        ctx.strokeStyle=`rgba(${color},${fade*.23})`;ctx.lineWidth=.6+fade*.65;ctx.stroke();
      }
      frame=points.length||now-moved<100?requestAnimationFrame(draw):0;
    };
    const move=(e:PointerEvent)=>{
      if(motion.matches||!fine.matches||document.hidden||e.pointerType==='touch')return;
      const now=performance.now();tx=e.clientX;ty=e.clientY;
      if(!frame||now-moved>150){sx=tx;sy=ty;points=[];}
      moved=now;if(!frame){last=now;frame=requestAnimationFrame(draw);}
    };
    const visibility=()=>{if(document.hidden)clear();};resize();
    window.addEventListener('resize',resize);window.addEventListener('pointermove',move,{passive:true});window.addEventListener('blur',clear);motion.addEventListener('change',clear);fine.addEventListener('change',clear);document.addEventListener('visibilitychange',visibility);
    return()=>{clear();window.removeEventListener('resize',resize);window.removeEventListener('pointermove',move);window.removeEventListener('blur',clear);motion.removeEventListener('change',clear);fine.removeEventListener('change',clear);document.removeEventListener('visibilitychange',visibility);};
  },[]);
  return <canvas ref={ref} className="cursor-atmosphere" aria-hidden="true" data-particle-mode={mode}/>;
}
