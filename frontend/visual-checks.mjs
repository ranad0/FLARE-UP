// Behavioral tests for canvas geometry, spring recovery and reduced-motion scheduling.
// Compile the two components into .visual-test first (see docs/VISUAL_STATE.md).
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
function mount(name,props,reduced=false){
  const refs=[],effects=[],frames=new Map(),events={},mediaEvents={};let now=100,id=0,path=[],centers=[],draws=0,transforms=[],strokes=0,alphas=[];
  const gradient={addColorStop(){}};
  const ctx=new Proxy({clearRect(){centers=[];transforms=[];alphas=[];},translate(x,y){centers.push([x,y]);},beginPath(){path=[];},moveTo(x,y){path.push([x,y]);},lineTo(x,y){path.push([x,y]);},fill(){draws++;alphas.push(ctx.globalAlpha);},stroke(){strokes++;},transform(...v){transforms.push(v);},createRadialGradient(){return gradient;},createLinearGradient(){return gradient;}},{get:(o,k)=>k in o?o[k]:()=>{}});
  const canvas={clientWidth:420,clientHeight:310,width:0,height:0,getContext:()=>ctx,getBoundingClientRect:()=>({left:0,top:0,width:420,height:310}),addEventListener:(k,f)=>events[k]=f,removeEventListener:(k)=>delete events[k],dispatchEvent:e=>events[e.type]?.(e)};
  const doc={hidden:false,addEventListener:(k,f)=>events[k]=f,removeEventListener:k=>delete events[k]};
  const media={matches:reduced,addEventListener:(k,f)=>mediaEvents[k]=f,removeEventListener:k=>delete mediaEvents[k]};
  const context={useRef:v=>{const r={current:v===null?canvas:v};refs.push(r);return r;},useEffect:f=>effects.push(f),_jsx:()=>null,VISUAL_TRANSITION_MS:800,Event,Math,performance:{now:()=>now},devicePixelRatio:1,innerWidth:1000,innerHeight:800,document:doc,matchMedia:q=>q.includes('reduced')?media:{matches:true,addEventListener(){},removeEventListener(){}},ResizeObserver:class{observe(){}disconnect(){}},requestAnimationFrame:f=>{frames.set(++id,f);return id;},cancelAnimationFrame:i=>frames.delete(i)};
  context.window={addEventListener:(k,f)=>events[k]=f,removeEventListener:k=>delete events[k]};
  vm.createContext(context);
  let source=readFileSync(new URL(`.visual-test/${name}.js`,import.meta.url),'utf8').replace(/^import .*;$/gm,'').replace(/export function /g,'function ');
  vm.runInContext(source,context);context[name==='OrbScene'?'HomeFlameScene':'CursorAtmosphere'](props);const cleanups=effects.map(f=>f());
  return {canvas,frames,media,events,get path(){return path;},get draws(){return draws;},get strokes(){return strokes;},get transforms(){return transforms;},get alphas(){return alphas;},get centers(){return centers;},mode(mode){refs[1].current=mode;canvas.dispatchEvent(new Event('visualmode'));},step(n=1){for(let i=0;i<n;i++){now+=16;const batch=[...frames.values()];frames.clear();batch.forEach(f=>f(now));}},pointer(x,y){now+=16;events.pointermove?.({clientX:x,clientY:y,pointerType:'mouse'});},reduce(){media.matches=true;mediaEvents.change?.({matches:true});},close(){cleanups.forEach(f=>f?.());}};
}

for(const mode of ['earth','micro']){
  const h=mount('OrbScene',{mode,hintText:'test'},true);
  assert.ok(h.draws>0);assert.equal(h.frames.size,0);
  h.pointer(150,150);h.pointer(280,150);assert.equal(h.frames.size,0);h.close();
}
console.log('PASS both modes render once with reduced motion');
const spring=mount('OrbScene',{mode:'earth',hintText:'test'});
spring.pointer(170,100);spring.pointer(240,100);spring.step(10);
assert.ok(Math.abs(spring.transforms[0][2])>.01);
spring.step(220);assert.ok(Math.abs(spring.transforms[0][2])<.005);
spring.reduce();assert.equal(spring.frames.size,0);spring.close();
console.log('PASS directional airflow response, spring recovery, and live reduced-motion change');
const blend=mount('OrbScene',{mode:'earth',hintText:'test'});
blend.mode('micro');blend.step(25);assert.ok(blend.alphas.some(a=>a>.2&&a<.8));
blend.step(30);assert.ok(blend.alphas.every(a=>a===0||a===1));blend.close();
console.log('PASS smooth mode crossfade completes within the 800ms transition');
for(const mode of ['earth','micro']){
  const trail=mount('CursorAtmosphere',{mode});trail.pointer(100,100);trail.step();trail.pointer(180,130);trail.step(6);
  assert.ok(trail.strokes>0);trail.step(40);assert.equal(trail.frames.size,0);
  trail.pointer(200,200);trail.reduce();assert.equal(trail.frames.size,0);trail.close();
  const reduced=mount('CursorAtmosphere',{mode},true);reduced.pointer(20,20);assert.equal(reduced.frames.size,0);assert.equal(reduced.strokes,0);reduced.close();
}
console.log('PASS continuous trail rendering, short fade-out, idle shutdown, and reduced-motion suppression');
