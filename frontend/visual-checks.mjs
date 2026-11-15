// Behavioral tests for canvas geometry, spring recovery and reduced-motion scheduling.
// Compile the two components into .visual-test first (see docs/VISUAL_STATE.md).
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
function mount(name,props,reduced=false){
  const refs=[],effects=[],frames=new Map(),events={},mediaEvents={};let now=100,id=0,path=[],centers=[],draws=0;
  const gradient={addColorStop(){}};
  const ctx=new Proxy({clearRect(){centers=[];},translate(x,y){centers.push([x,y]);},beginPath(){path=[];},moveTo(x,y){path.push([x,y]);},lineTo(x,y){path.push([x,y]);},fill(){draws++;},createRadialGradient(){return gradient;},createLinearGradient(){return gradient;}},{get:(o,k)=>k in o?o[k]:()=>{}});
  const canvas={clientWidth:420,clientHeight:310,width:0,height:0,getContext:()=>ctx,getBoundingClientRect:()=>({left:0,top:0,width:420,height:310}),addEventListener:(k,f)=>events[k]=f,removeEventListener:(k)=>delete events[k],dispatchEvent:e=>events[e.type]?.(e)};
  const doc={hidden:false,addEventListener:(k,f)=>events[k]=f,removeEventListener:k=>delete events[k]};
  const media={matches:reduced,addEventListener:(k,f)=>mediaEvents[k]=f,removeEventListener:k=>delete mediaEvents[k]};
  const context={useRef:v=>{const r={current:v===null?canvas:v};refs.push(r);return r;},useEffect:f=>effects.push(f),_jsx:()=>null,VISUAL_TRANSITION_MS:800,Event,Math,performance:{now:()=>now},devicePixelRatio:1,innerWidth:1000,innerHeight:800,document:doc,matchMedia:q=>q.includes('reduced')?media:{matches:true,addEventListener(){},removeEventListener(){}},ResizeObserver:class{observe(){}disconnect(){}},requestAnimationFrame:f=>{frames.set(++id,f);return id;},cancelAnimationFrame:i=>frames.delete(i)};
  context.window={addEventListener:(k,f)=>events[k]=f,removeEventListener:k=>delete events[k]};
  vm.createContext(context);
  let source=readFileSync(new URL(`.visual-test/${name}.js`,import.meta.url),'utf8').replace(/^import .*;$/gm,'').replace(/export function /g,'function ');
  vm.runInContext(source,context);context[name==='OrbScene'?'HomeFlameScene':'CursorAtmosphere'](props);const cleanups=effects.map(f=>f());
  return {canvas,frames,media,events,get path(){return path;},get draws(){return draws;},get centers(){return centers;},mode(mode){refs[1].current=mode;canvas.dispatchEvent(new Event('visualmode'));},step(n=1){for(let i=0;i<n;i++){now+=16;const batch=[...frames.values()];frames.clear();batch.forEach(f=>f(now));}},pointer(x,y){now+=16;events.pointermove?.({clientX:x,clientY:y,pointerType:'mouse'});},reduce(){media.matches=true;mediaEvents.change?.({matches:true});},close(){cleanups.forEach(f=>f?.());}};
}
function bounds(path){const xs=path.map(p=>p[0]),ys=path.map(p=>p[1]);return {w:Math.max(...xs)-Math.min(...xs),h:Math.max(...ys)-Math.min(...ys),center:(Math.max(...xs)+Math.min(...xs))/2};}
for(const mode of ['earth','micro']){
  const h=mount('OrbScene',{mode,hintText:'test'},true),b=bounds(h.path);
  assert.ok(mode==='earth'?b.h/b.w>2:b.h/b.w>.9&&b.h/b.w<1.1);
  assert.equal(h.frames.size,0);h.pointer(150,150);h.pointer(280,150);assert.equal(h.frames.size,0);h.close();
  console.log('PASS',mode,'geometry and static reduced-motion rendering');
}
const spring=mount('OrbScene',{mode:'earth',hintText:'test'});spring.pointer(170,100);spring.pointer(240,100);spring.step(10);assert.ok(Math.abs(bounds(spring.path).center)>3);spring.step(220);assert.ok(Math.abs(bounds(spring.path).center)<2);spring.reduce();assert.equal(spring.frames.size,0);spring.close();console.log('PASS visible directional spring response, recovery, live motion preference change');
for(const mode of ['earth','micro']){const c=mount('CursorAtmosphere',{mode},true);c.pointer(20,20);assert.equal(c.frames.size,0);assert.equal(c.draws,0);c.close();}
const c=mount('CursorAtmosphere',{mode:'micro'});c.pointer(20,20);c.step();assert.ok(c.draws>0);c.reduce();assert.equal(c.frames.size,0);c.close();console.log('PASS cursor emission, reduced-motion suppression and cleanup');

const morph=mount('OrbScene',{mode:'earth',hintText:'test'});morph.mode('micro');morph.step(25);let b=bounds(morph.path);assert.ok(b.h/b.w>1.1&&b.h/b.w<2.2);morph.step(30);b=bounds(morph.path);assert.ok(Math.abs(b.h/b.w-1)<.05);morph.close();console.log('PASS continuous 800ms geometry transition');
for(const mode of ['earth','micro']){const trail=mount('CursorAtmosphere',{mode});trail.pointer(200,200);trail.step(20);const ys=trail.centers.map(p=>p[1]-200);assert.ok(ys.length>0);if(mode==='earth')assert.ok(ys.every(y=>y< -10));else assert.ok(ys.every(y=>Math.abs(y)<9));trail.close();}console.log('PASS Earth rising particles versus microgravity radial diffusion');
