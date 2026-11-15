import {useEffect,useRef} from 'react';
import type {VisualMode} from './visualMode';
type Particle={x:number;y:number;vx:number;vy:number;age:number;life:number;size:number;phase:number};
/** One lightweight, bounded, demand-driven overlay; never intercepts input. */
export function CursorAtmosphere({mode}:{mode:VisualMode}){
  const ref=useRef<HTMLCanvasElement>(null),modeRef=useRef(mode);
  useEffect(()=>{modeRef.current=mode;},[mode]);
  useEffect(()=>{
    const canvas=ref.current!,ctx=canvas.getContext('2d');if(!ctx)return;
    const motion=matchMedia('(prefers-reduced-motion: reduce)'),fine=matchMedia('(hover: hover) and (pointer: fine)');
    let particles:Particle[]=[],frame=0,last=0,emitted=0,mix=modeRef.current==='micro'?1:0;
    const clear=()=>{cancelAnimationFrame(frame);frame=0;particles=[];ctx.clearRect(0,0,innerWidth,innerHeight);};
    const resize=()=>{const d=Math.min(devicePixelRatio||1,2);canvas.width=innerWidth*d;canvas.height=innerHeight*d;ctx.setTransform(d,0,0,d,0,0);};
    const draw=(now:number)=>{
      const dt=Math.min((now-last)/1000,.04);last=now;ctx.clearRect(0,0,innerWidth,innerHeight);
      mix+=(Number(modeRef.current==='micro')-mix)*Math.min(1,dt*6);
      particles=particles.filter(p=>p.age<p.life);
      for(const p of particles){
        p.age+=dt;const age=p.age/p.life;
        p.x+=(p.vx+Math.sin(p.phase+p.age*9)*(1-mix)*5)*dt;
        p.y+=(p.vy*mix-(30+18*(1-age))*(1-mix))*dt;
        const r=p.size*(mix*(.7+age*.6)+(1-mix)*(1-age*.8)),alpha=(1-age)*.42;
        const red=Math.round(255+(90-255)*mix),green=Math.round(174+(176-174)*mix),blue=Math.round(70+(255-70)*mix);
        ctx.save();ctx.translate(p.x,p.y);ctx.scale(1,1+(1-mix)*.6);
        const g=ctx.createRadialGradient(0,0,0,0,0,Math.max(.01,r));g.addColorStop(0,`rgba(${red},${green},${blue},${alpha})`);g.addColorStop(1,`rgba(${red},${green},${blue},0)`);ctx.fillStyle=g;ctx.beginPath();ctx.arc(0,0,Math.max(.01,r),0,Math.PI*2);ctx.fill();ctx.restore();
      }
      frame=particles.length?requestAnimationFrame(draw):0;
    };
    const move=(e:PointerEvent)=>{
      if(motion.matches||!fine.matches||document.hidden||e.pointerType==='touch')return;
      const now=performance.now();if(now-emitted<18)return;emitted=now;
      if(!frame){last=now;mix=Number(modeRef.current==='micro');}
      for(let i=0;i<3&&particles.length<100;i++){const a=Math.random()*Math.PI*2;particles.push({x:e.clientX,y:e.clientY,vx:Math.cos(a)*22,vy:Math.sin(a)*22,age:0,life:.65+Math.random()*.4,size:5+Math.random()*5,phase:a});}
      if(!frame)frame=requestAnimationFrame(draw);
    };
    const visibility=()=>{if(document.hidden)clear();};resize();
    window.addEventListener('resize',resize);window.addEventListener('pointermove',move,{passive:true});window.addEventListener('blur',clear);motion.addEventListener('change',clear);fine.addEventListener('change',clear);document.addEventListener('visibilitychange',visibility);
    return()=>{clear();window.removeEventListener('resize',resize);window.removeEventListener('pointermove',move);window.removeEventListener('blur',clear);motion.removeEventListener('change',clear);fine.removeEventListener('change',clear);document.removeEventListener('visibilitychange',visibility);};
  },[]);
  return <canvas ref={ref} className="cursor-atmosphere" aria-hidden="true" data-particle-mode={mode}/>;
}
