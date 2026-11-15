import {useEffect,useRef} from 'react';
import {VISUAL_TRANSITION_MS, type VisualMode} from './visualMode';

/** Illustrative artwork. Geometry, colours and timing are never measured predictions. */
export function HomeFlameScene({mode,hintText,compact=false}:{mode:VisualMode;hintText:string;compact?:boolean}){
  const ref=useRef<HTMLCanvasElement>(null), target=useRef(mode);
  useEffect(()=>{target.current=mode;ref.current?.dispatchEvent(new Event('visualmode'));},[mode]);
  useEffect(()=>{
    const canvas=ref.current!,ctx=canvas.getContext('2d');if(!ctx)return;
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    let frame=0,last=performance.now(),mix=target.current==='micro'?1:0,from=mix,to=mix,changed=last;
    let x=0,y=0,vx=0,vy=0,gx=0,gy=0,px=0,py=0,pt=0;
    const rgb=(a:number[],b:number[],m:number,alpha=1)=>`rgba(${a.map((v,i)=>Math.round(v+(b[i]-v)*m)).join(',')},${alpha})`;
    function draw(now:number){
      const c=ctx!,w=canvas.clientWidth,h=canvas.clientHeight,dpr=Math.min(devicePixelRatio||1,2);
      if(!w||!h)return;
      if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
      c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);
      const dt=Math.min((now-last)/1000,.035);last=now;
      const u=Math.min(1,(now-changed)/VISUAL_TRANSITION_MS),ease=u*u*(3-2*u);
      mix=motion.matches?to:from+(to-from)*ease;
      if(motion.matches){x=y=vx=vy=gx=gy=0;}else{
        vx+=(-x*40-vx*9)*dt;vy+=(-y*40-vy*9)*dt;x+=vx*dt;y+=vy*dt;
        gx+=(x-gx)*Math.min(1,dt*5);gy+=(y-gy)*Math.min(1,dt*5);
      }
      const t=motion.matches?0:now/1000,r=Math.min(w*.24,h*(compact?.32:.29)),cx=w/2,cy=h*.51;
      const warm=[240,138,61],cool=[74,112,255];
      const glow=c.createRadialGradient(cx+gx*.5,cy+gy*.5,0,cx+gx*.5,cy+gy*.5,r*(1.7+mix*.7));
      glow.addColorStop(0,rgb(warm,cool,mix,.28));glow.addColorStop(.45,rgb(warm,cool,mix,.13));glow.addColorStop(1,rgb(warm,cool,mix,0));
      c.fillStyle=glow;c.fillRect(0,0,w,h);
      c.save();c.translate(cx,cy);
      // A continuous silhouette morph avoids swapping assets or flashing the canvas.
      const shape=()=>{
        c.beginPath();
        for(let i=0;i<=160;i++){
          const a=i/160*Math.PI*2,top=(1+Math.cos(a))/2;
          const earthWidth=.5*(1-.72*Math.cos(a));
          const ripple=compact?0:Math.sin(a*3-t*(2.7-2*mix))*.012+Math.sin(a*5+t)*.006;
          const xx=Math.sin(a)*r*(earthWidth*(1-mix)+mix)*(1+ripple)+x*top*1.3;
          const yy=-Math.cos(a)*r*(1.38*(1-mix)+mix)*(1+ripple)+y*top*.85+(1-mix)*Math.sin(t*2+a)*r*.012;
          if(i===0)c.moveTo(xx,yy);else c.lineTo(xx,yy);
        }c.closePath();
      };
      // Earth: hot cream/amber upper body and a subtle blue base.
      const earth=c.createLinearGradient(0,-r*1.4,0,r*1.4);
      earth.addColorStop(0,'#F27C3530');earth.addColorStop(.28,'#FFF3BB');earth.addColorStop(.55,'#FFB55B');earth.addColorStop(.8,'#DC714C');earth.addColorStop(.94,'#4A70FF');earth.addColorStop(1,'#78A8FF20');
      c.globalAlpha=1-mix;c.fillStyle=earth;c.shadowColor='#F08A3D';c.shadowBlur=compact?3:24;shape();c.fill();
      if(!compact){
        c.save();shape();c.clip();c.shadowBlur=0;
        for(let j=0;j<4;j++){
          const travel=(t*.55+j*.25)%1,yy=r*.9-travel*r*2.2,xx=Math.sin(t*1.5+j)*r*.1+x*(1-travel)*.3;
          const light=c.createRadialGradient(xx,yy,0,xx,yy,r*.5);
          light.addColorStop(0,'#fff3bb');light.addColorStop(1,'#fff3bb00');
          c.globalAlpha=(1-mix)*Math.sin(travel*Math.PI)*.22;c.fillStyle=light;c.fillRect(-r,-r*1.5,r*2,r*3);
        }c.restore();
      }
      // Microgravity: full spherical blue shell, dark violet centre, cyan rim.
      const micro=c.createRadialGradient(x*.35,y*.25,r*.12,x*.35,y*.25,r*1.04);
      micro.addColorStop(0,'#13166660');micro.addColorStop(.45,'#30257F90');micro.addColorStop(.77,'#182FB9c0');micro.addColorStop(.91,'#3266FF');micro.addColorStop(.97,'#79E5FF');micro.addColorStop(1,'#3266FF10');
      c.globalAlpha=mix;c.fillStyle=micro;c.shadowColor='#3266FF';c.shadowBlur=compact?4:27;shape();c.fill();
      c.globalAlpha=.5;c.shadowBlur=compact?2:14;c.strokeStyle=rgb([255,181,91],[120,168,255],mix);c.lineWidth=compact?.65:1.2;shape();c.stroke();
      // A quiet enclosing arc gives the navbar mark the same circular identity.
      if(compact){c.globalAlpha=.65;c.strokeStyle=rgb([255,201,131],[112,207,255],mix);c.beginPath();c.arc(0,0,r*1.35,-1.3,4.6);c.stroke();}
      c.restore();c.globalAlpha=1;c.shadowBlur=0;
      if(!document.hidden&&!motion.matches)frame=requestAnimationFrame(draw);
    }
    const resume=()=>{cancelAnimationFrame(frame);last=performance.now();draw(last);};
    const change=()=>{from=mix;to=target.current==='micro'?1:0;changed=performance.now();resume();};
    const pointer=(e:PointerEvent)=>{
      if(compact||motion.matches||e.pointerType==='touch')return;
      const now=performance.now(),b=canvas.getBoundingClientRect(),dt=Math.max(12,now-pt);
      const distance=Math.hypot((e.clientX-b.left-b.width/2)/(b.width*.7),(e.clientY-b.top-b.height/2)/(b.height*.7));
      if(pt&&now-pt<100&&distance<1.3){const strength=Math.max(0,1.3-distance);vx+=Math.max(-240,Math.min(240,(e.clientX-px)/dt*90))*strength;vy+=Math.max(-160,Math.min(160,(e.clientY-py)/dt*65))*strength;vx=Math.max(-400,Math.min(400,vx));vy=Math.max(-260,Math.min(260,vy));}
      px=e.clientX;py=e.clientY;pt=now;
    };
    const reset=()=>{pt=0;};
    const resize=new ResizeObserver(resume);resize.observe(canvas);
    window.addEventListener('pointermove',pointer,{passive:true});window.addEventListener('blur',reset);
    canvas.addEventListener('visualmode',change);motion.addEventListener('change',resume);document.addEventListener('visibilitychange',resume);resume();
    return()=>{cancelAnimationFrame(frame);resize.disconnect();window.removeEventListener('pointermove',pointer);window.removeEventListener('blur',reset);canvas.removeEventListener('visualmode',change);motion.removeEventListener('change',resume);document.removeEventListener('visibilitychange',resume);};
  },[compact]);
  return <canvas ref={ref} className="h-full w-full" role={compact?undefined:'img'} aria-label={hintText||undefined} data-flame-mode={mode}/>;
}
