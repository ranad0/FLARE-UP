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
      const t=motion.matches?0:now/1000, scale=Math.min(w/580,h/560)*1.28;
      const pulse=1+Math.sin(t*2.1)*.025+Math.sin(t*5.3)*.012;
      const radial=(xx:number,yy:number,r:number,stops:[number,string][])=>{
        const paint=c.createRadialGradient(xx,yy,0,xx,yy,r);
        stops.forEach(([offset,color])=>paint.addColorStop(offset,color));return paint;
      };
      const glow=(xx:number,yy:number,r:number,color:string)=>{c.fillStyle=radial(xx,yy,r,[[0,color],[1,'transparent']]);c.fillRect(xx-r,yy-r,r*2,r*2);};
      c.save();c.translate(w/2,h*.66);c.scale(scale,scale);
      // Original Fireline artwork with smooth mode blending and damped cursor airflow.
      c.save();c.translate(gx*.6/scale,gy*.4/scale);
      c.globalAlpha=1-mix;glow(0,-60,230*pulse,'#d3623a47');glow(0,-20,180*pulse,'#f08a3d55');
      c.globalAlpha=mix;glow(0,-35,250*pulse,'#4a70ff82');glow(0,-10,195*pulse,'#6b8cff85');c.restore();
      c.transform(1,0,-x/260,1,x*.2/scale,y*.3/scale);
      c.globalAlpha=1-mix;
      const tip=Math.sin(t*3.4)*6;
      glow(0,-95,153,'#ee7a344d');
      const paint=c.createLinearGradient(0,-210,0,20);
      ([[0,'#b2401400'],[.19,'#f27c35df'],[.43,'#fff3bb'],[.68,'#ffb55b'],[.85,'#dc714c80'],[1,'#3b73ffdb']] as [number,string][]).forEach(([stop,color])=>paint.addColorStop(stop,color));
      c.fillStyle=paint;c.shadowBlur=30;c.shadowColor='#ff9a49b5';
      c.beginPath();c.moveTo(0,14);c.bezierCurveTo(-49,12,-41,-118,tip,-206);c.bezierCurveTo(38+tip,-124,51,9,0,14);c.fill();
      glow(0,-98,73,'#fff0c443');
      c.save();c.globalAlpha=mix;
      const width=94+Math.sin(t*2.3)*2;
      c.scale(1.2,.96);c.shadowBlur=34;c.shadowColor='#5279ff';
      c.fillStyle=radial(0,0,width,[[0,'#131666'],[.65,'#182fb9'],[.80,'#3266ff'],[.91,'#78a8ff'],[1,'#1c37ff00']]);
      c.beginPath();c.arc(0,0,width,Math.PI,Math.PI*2);c.ellipse(0,0,width,20,0,0,Math.PI);c.fill();
      glow(0,-8,47,'#253bc645');c.restore();
      c.globalAlpha=1;c.shadowBlur=0;c.fillStyle='#110e24c7';
      c.beginPath();c.moveTo(-5,15);c.quadraticCurveTo(-4,-39,6,-33);c.lineTo(5,15);c.fill();
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
