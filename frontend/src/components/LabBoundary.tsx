import {Component,type ReactNode} from 'react';
export class LabBoundary extends Component<{children:ReactNode},{failed:boolean}>{
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){return this.state.failed?<section role="alert" className="relative z-10 mx-auto my-16 max-w-lg rounded-xl border border-[#78a8ff55] bg-[#151529] p-8 text-center"><h1 className="text-xl">The Fire Lab could not load</h1><p className="my-4 text-sm text-[#cfd1e8]">The app may have been updated, or your browser could not initialize the 3D view. Reload to get the current version. Search and Evidence remain available in the navigation.</p><button className="rounded-lg bg-[#8fbaff] px-5 py-2 text-[#151529]" onClick={()=>window.location.reload()}>Reload FLARE UP</button></section>:this.props.children;}
}
