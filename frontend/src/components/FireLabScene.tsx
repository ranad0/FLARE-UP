import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import type { FireLabParams, SampleType } from '../types/flare';
import { createCombustionChamber } from '../three/chamberGeometry';
import {
  createFlameMaterial,
  createFlameUniforms,
  createHaloMaterial,
  createParticleSpriteTexture,
} from '../three/flameShaders';

interface FireLabSceneProps {
  params: FireLabParams;
  resetSignal: number;
  cursorHint: string;
}

const SAMPLE_MODE_MAP: Record<SampleType, number> = {
  gaseous: 0,
  liquid: 1,
  fabric: 2,
  polymer: 3,
};

const SAMPLE_BASE_Y: Record<SampleType, number> = {
  gaseous: 0.24,
  liquid: 0.19,
  fabric: 0.26,
  polymer: 0.28,
};


const DEFAULT_CAMERA_POS = new THREE.Vector3(3.15, 2.05, 3.75);
const DEFAULT_TARGET = new THREE.Vector3(0, 0.86, 0);

// Module-scope reusable scratch objects (zero per-frame allocations)
const _camRight = new THREE.Vector3();
const _camUp = new THREE.Vector3();
const _camForward = new THREE.Vector3();
const _flameScreen = new THREE.Vector3();
const _targetFlow = new THREE.Vector3();
const _earthLightCol = new THREE.Color(0xe1b983);
const _microLightCol = new THREE.Color(0x22d3ee);
const _smokeEarthCol = new THREE.Color(0x8e839c);
const _smokeMicroCol = new THREE.Color(0x6e85a8);

export function FireLabScene({ params, resetSignal, cursorHint }: FireLabSceneProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const paramsRef = useRef<FireLabParams>(params);
  paramsRef.current = params;

  const resetFnRef = useRef<(() => void) | null>(null);
  const [webglUnavailable, setWebglUnavailable] = useState(false);

  useEffect(() => {
    if (resetSignal > 0 && resetFnRef.current) {
      resetFnRef.current();
    }
  }, [resetSignal]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    // Software WebGL probe (cost-only adaptation, never changes scene content)
    const isSoftwareGl = (() => {
      try {
        const probe = document.createElement('canvas').getContext('webgl2');
        if (!probe) return true;
        const ext = probe.getExtension('WEBGL_debug_renderer_info');
        const param = ext ? ext.UNMASKED_RENDERER_WEBGL : probe.RENDERER;
        const gpu = String(probe.getParameter(param) || '');
        probe.getExtension('WEBGL_lose_context')?.loseContext();
        return /SwiftShader|llvmpipe|softpipe|Software|Basic Render/i.test(gpu);
      } catch {
        return true;
      }
    })();

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: !isSoftwareGl,
        alpha: true,
        powerPreference: 'high-performance',
      });
    } catch {
      setWebglUnavailable(true);
      return;
    }

    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = !isSoftwareGl;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.setClearColor(0x000000, 0);

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;
    renderer.setSize(width, height);
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();

    // Procedural RoomEnvironment for crisp metallic & borosilicate glass reflections
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const envRT = pmremGenerator.fromScene(new RoomEnvironment(), 0.04);
    scene.environment = envRT.texture;
    pmremGenerator.dispose();

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 40);
    camera.position.copy(DEFAULT_CAMERA_POS);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(DEFAULT_TARGET);
    controls.enableDamping = !isSoftwareGl;
    controls.dampingFactor = 0.055;
    controls.enablePan = false;
    controls.minDistance = 2.6;
    controls.maxDistance = 6.2;
    controls.minPolarAngle = Math.PI * 0.18;
    controls.maxPolarAngle = Math.PI * 0.54;
    controls.rotateSpeed = 0.65;
    controls.zoomSpeed = 0.7;
    controls.update();

    // 3-point studio lighting + dynamic flame light
    const hemiLight = new THREE.HemisphereLight(0xb89ee8, 0x160c24, 0.68);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight(0xffe9cc, 1.55);
    keyLight.position.set(3.8, 5.4, 4.2);
    keyLight.castShadow = !isSoftwareGl;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    keyLight.shadow.camera.near = 1;
    keyLight.shadow.camera.far = 16;
    const d = 2.6;
    keyLight.shadow.camera.left = -d;
    keyLight.shadow.camera.right = d;
    keyLight.shadow.camera.top = d;
    keyLight.shadow.camera.bottom = -d;
    keyLight.shadow.bias = -0.0005;
    keyLight.shadow.normalBias = 0.02;
    scene.add(keyLight);

    const rimLight = new THREE.DirectionalLight(0x7a5498, 0.95);
    rimLight.position.set(-4.0, 2.8, -3.5);
    scene.add(rimLight);

    const flameLight = new THREE.PointLight(0xe1b983, 2.2, 7.5, 1.8);
    flameLight.position.set(0, 0.72, 0);
    scene.add(flameLight);

    // Composite Combustion Chamber
    const chamber = createCombustionChamber(renderer, isSoftwareGl);
    scene.add(chamber.root);

    // Volumetric 3D Flame Group (Outer Envelope + Inner Core + Glow Halo)
    const flameGroup = new THREE.Group();
    flameGroup.position.set(0, SAMPLE_BASE_Y[paramsRef.current.sampleType], 0);
    scene.add(flameGroup);

    const flameGeo = new THREE.SphereGeometry(0.32, 44, 44);
    const outerUniforms = createFlameUniforms(false);
    const outerMat = createFlameMaterial(outerUniforms);
    const outerFlame = new THREE.Mesh(flameGeo, outerMat);
    outerFlame.renderOrder = 6;
    flameGroup.add(outerFlame);

    const innerUniforms = createFlameUniforms(true);
    const innerMat = createFlameMaterial(innerUniforms);
    const innerFlame = new THREE.Mesh(flameGeo, innerMat);
    innerFlame.renderOrder = 7;
    flameGroup.add(innerFlame);

    const haloGeo = new THREE.PlaneGeometry(2.1, 2.4);
    const haloMat = createHaloMaterial();
    const haloMesh = new THREE.Mesh(haloGeo, haloMat);
    haloMesh.position.set(0, 0.5, 0);
    haloMesh.renderOrder = 5;
    flameGroup.add(haloMesh);

    // Illustrative smoke tracers only; no inferred soot yield or sparks.
    const spriteTex = createParticleSpriteTexture();

    const SMOKE_COUNT = 32;
    const smokePositions = new Float32Array(SMOKE_COUNT * 3);
    const smokeVel = new Float32Array(SMOKE_COUNT * 3);
    const smokeLife = new Float32Array(SMOKE_COUNT);
    const smokeMaxLife = new Float32Array(SMOKE_COUNT);

    const resetSmokeParticle = (i: number, randomAge = false) => {
      const angle = Math.random() * Math.PI * 2;
      const rad = Math.random() * 0.08;
      smokePositions[i * 3] = Math.cos(angle) * rad;
      smokePositions[i * 3 + 1] = 0.25 + Math.random() * 0.25;
      smokePositions[i * 3 + 2] = Math.sin(angle) * rad;
      smokeVel[i * 3] = (Math.random() - 0.5) * 0.08;
      smokeVel[i * 3 + 1] = (Math.random() - 0.5) * 0.08;
      smokeVel[i * 3 + 2] = (Math.random() - 0.5) * 0.08;
      smokeMaxLife[i] = 1.6 + Math.random() * 1.4;
      smokeLife[i] = randomAge ? Math.random() * smokeMaxLife[i] : 0;
    };
    for (let i = 0; i < SMOKE_COUNT; i++) resetSmokeParticle(i, true);

    const smokeGeo = new THREE.BufferGeometry();
    smokeGeo.setAttribute('position', new THREE.BufferAttribute(smokePositions, 3));
    const smokeMat = new THREE.PointsMaterial({
      map: spriteTex,
      color: 0x8e839c,
      size: 0.18,
      transparent: true,
      opacity: 0.07,
      depthWrite: false,
      blending: THREE.NormalBlending,
      sizeAttenuation: true,
    });
    const smokePoints = new THREE.Points(smokeGeo, smokeMat);
    smokePoints.renderOrder = 8;
    flameGroup.add(smokePoints);

    if (!isSoftwareGl) {
      renderer.compile(scene, camera);
    }

    // Smoothly damped state + second-order spring cursor disturbance
    let smoothGravity = paramsRef.current.gravity === 'microgravity' ? 1 : 0;
    let smoothOxygen = 0.24;
    let smoothPressure = 0.7;
    let smoothAirflow = paramsRef.current.airflow;
    let smoothDirRad = THREE.MathUtils.degToRad(paramsRef.current.airflowDirectionDegrees);
    let smoothBaseY = SAMPLE_BASE_Y[paramsRef.current.sampleType];

    // Cursor disturbance spring state
    const cursorPos = new THREE.Vector3(0, 0, 0);
    const cursorVel = new THREE.Vector3(0, 0, 0);
    const cursorImpulse = new THREE.Vector3(0, 0, 0);
    let lastPointerX = 0;
    let lastPointerY = 0;
    let hasLastPointer = false;
    let isOrbitDragging = false;
    let parallaxTargetX = 0;
    let parallaxTargetY = 0;
    let currentParallaxX = 0;
    let currentParallaxY = 0;

    // Camera reset animation state
    let resettingCamera = false;
    resetFnRef.current = () => {
      resettingCamera = true;
    };

    const onControlsStart = () => {
      isOrbitDragging = true;
      resettingCamera = false;
    };
    const onControlsEnd = () => {
      isOrbitDragging = false;
    };
    controls.addEventListener('start', onControlsStart);
    controls.addEventListener('end', onControlsEnd);

    const onPointerMove = (e: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;

      const ndcX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ndcY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      parallaxTargetX = ndcX * 0.08;
      parallaxTargetY = ndcY * 0.05;

      if (!hasLastPointer) {
        lastPointerX = ndcX;
        lastPointerY = ndcY;
        hasLastPointer = true;
        return;
      }

      const dx = ndcX - lastPointerX;
      const dy = ndcY - lastPointerY;
      lastPointerX = ndcX;
      lastPointerY = ndcY;

      if (isOrbitDragging) return;

      // Project flame center to screen NDC to compute proximity weighting
      _flameScreen.set(0, 0.72, 0).project(camera);
      const distToFlame = Math.hypot(ndcX - _flameScreen.x, ndcY - _flameScreen.y);
      const proximity = THREE.MathUtils.smoothstep(1.25 - distToFlame, 0.0, 1.05);

      if (proximity > 0.02) {
        camera.updateMatrixWorld();
        _camRight.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
        _camUp.setFromMatrixColumn(camera.matrixWorld, 1).normalize();

        // Map screen velocity into world disturbance vector
        const strength = 3.0 * proximity;
        const ix = THREE.MathUtils.clamp((_camRight.x * dx + _camUp.x * dy) * strength, -0.18, 0.18);
        const iy = THREE.MathUtils.clamp((_camRight.y * dx + _camUp.y * dy) * strength * 0.25, -0.05, 0.05);
        const iz = THREE.MathUtils.clamp((_camRight.z * dx + _camUp.z * dy) * strength, -0.18, 0.18);

        cursorImpulse.x = THREE.MathUtils.clamp(cursorImpulse.x + ix, -0.20, 0.20);
        cursorImpulse.y = THREE.MathUtils.clamp(cursorImpulse.y + iy, -0.06, 0.06);
        cursorImpulse.z = THREE.MathUtils.clamp(cursorImpulse.z + iz, -0.20, 0.20);
      }
    };

    const onPointerLeave = () => {
      hasLastPointer = false;
      parallaxTargetX = 0;
      parallaxTargetY = 0;
    };

    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);

    // ResizeObserver for crisp layout transitions (e.g. Evidence Panel opening)
    const handleResize = () => {
      const w = container.clientWidth || 1;
      const h = container.clientHeight || 1;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // Context loss resilience
    const onContextLost = (ev: Event) => {
      ev.preventDefault();
    };
    renderer.domElement.addEventListener('webglcontextlost', onContextLost);

    // Motion & visibility governance
    const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let prefersReduced = reducedMotionQuery.matches;

    let frameId = 0;
    let elapsed = 0;
    let lastNow = performance.now();
    let disposed = false;

    const afterDraw = (cb: () => void) => {
      const gl = renderer.getContext() as WebGL2RenderingContext;
      const sync = gl.fenceSync ? gl.fenceSync(gl.SYNC_GPU_COMMANDS_COMPLETE, 0) : null;
      if (!sync) {
        frameId = window.setTimeout(cb, 80);
        return;
      }
      gl.flush();
      const poll = () => {
        if (disposed || document.hidden) {
          gl.deleteSync(sync);
          return;
        }
        const state = gl.getSyncParameter(sync, gl.SYNC_STATUS);
        if (state === gl.UNSIGNALED) {
          frameId = window.setTimeout(poll, 5);
        } else {
          gl.deleteSync(sync);
          frameId = window.setTimeout(cb, 80);
        }
      };
      frameId = window.setTimeout(poll, 5);
    };

    let lastSampleType: SampleType | null = null;

    const tick = () => {
      if (disposed || document.hidden) return;

      const now = performance.now();
      const rawDt = Math.min((now - lastNow) / 1000, 0.05);
      lastNow = now;
      const dt = Math.max(rawDt, 0.001);
      elapsed += prefersReduced ? 0 : dt;

      const p = paramsRef.current;

      if (lastSampleType !== p.sampleType) {
        chamber.setSampleType(p.sampleType);
        lastSampleType = p.sampleType;
      }

      // Smooth parameter damping
      const targetG = p.gravity === 'microgravity' ? 1 : 0;
      // No validated pressure/oxygen-to-appearance mapping: keep artistic reference values.
      const targetOx = 0.24;
      const targetPr = 0.7;
      const targetAir = THREE.MathUtils.clamp(p.airflow, 0, 1);
      const targetDir = THREE.MathUtils.degToRad(p.airflowDirectionDegrees);

      smoothGravity = THREE.MathUtils.damp(smoothGravity, targetG, 4.8, dt);
      smoothOxygen = THREE.MathUtils.damp(smoothOxygen, targetOx, 5.2, dt);
      smoothPressure = THREE.MathUtils.damp(smoothPressure, targetPr, 5.2, dt);
      smoothAirflow = THREE.MathUtils.damp(smoothAirflow, targetAir, 5.0, dt);

      // Shortest-angle wrap for airflow direction
      let dirDiff = targetDir - smoothDirRad;
      while (dirDiff > Math.PI) dirDiff -= Math.PI * 2;
      while (dirDiff < -Math.PI) dirDiff += Math.PI * 2;
      smoothDirRad += dirDiff * (1 - Math.exp(-6.5 * dt));

      smoothBaseY = THREE.MathUtils.damp(smoothBaseY, SAMPLE_BASE_Y[p.sampleType], 7.0, dt);
      flameGroup.position.y = smoothBaseY;

      chamber.setAirflowDirection(THREE.MathUtils.radToDeg(smoothDirRad), smoothAirflow);

      // Second-order spring-damper for cursor disturbance
      cursorImpulse.multiplyScalar(Math.exp(-5.4 * dt));
      const stiffness = 38.0;
      const damping = 12.4;

      cursorVel.x += ((cursorImpulse.x - cursorPos.x) * stiffness - cursorVel.x * damping) * dt;
      cursorVel.y += ((cursorImpulse.y - cursorPos.y) * stiffness - cursorVel.y * damping) * dt;
      cursorVel.z += ((cursorImpulse.z - cursorPos.z) * stiffness - cursorVel.z * damping) * dt;
      cursorPos.addScaledVector(cursorVel, dt);
      if(prefersReduced){cursorImpulse.set(0,0,0);cursorVel.set(0,0,0);cursorPos.set(0,0,0);}

      // Steady airflow vector from 0-360° dial
      const steadyAirMag = smoothAirflow * 0.92;
      const airX = Math.sin(smoothDirRad) * steadyAirMag;
      const airZ = Math.cos(smoothDirRad) * steadyAirMag;

      _targetFlow.set(airX + cursorPos.x, cursorPos.y, airZ + cursorPos.z);

      // Update flame uniforms
      const sampleIndex = SAMPLE_MODE_MAP[p.sampleType];
      outerUniforms.uTime.value = elapsed;
      outerUniforms.uGravityMix.value = smoothGravity;
      outerUniforms.uOxygenNorm.value = smoothOxygen;
      outerUniforms.uPressureNorm.value = smoothPressure;
      outerUniforms.uAirflowMag.value = smoothAirflow;
      outerUniforms.uFlowVec.value.copy(_targetFlow);
      outerUniforms.uSampleMode.value = sampleIndex;

      innerUniforms.uTime.value = elapsed;
      innerUniforms.uGravityMix.value = smoothGravity;
      innerUniforms.uOxygenNorm.value = smoothOxygen;
      innerUniforms.uPressureNorm.value = smoothPressure;
      innerUniforms.uAirflowMag.value = smoothAirflow;
      innerUniforms.uFlowVec.value.copy(_targetFlow);
      innerUniforms.uSampleMode.value = sampleIndex;

      // Billboard halo plane toward camera
      haloMesh.quaternion.copy(camera.quaternion);
      haloMat.uniforms.uGravityMix.value = smoothGravity;
      haloMat.uniforms.uOxygenNorm.value = smoothOxygen;
      haloMat.uniforms.uFlowOffset.value.set(_targetFlow.x, _targetFlow.y);

      // Dynamic flame illumination on chamber metal & sample
      flameLight.color.copy(_earthLightCol).lerp(_microLightCol, smoothGravity);
      const flicker = prefersReduced ? 1 : 0.94 + 0.06 * Math.sin(elapsed * 9.5) + 0.04 * Math.cos(elapsed * 14.3);
      flameLight.intensity = (1.5 + smoothOxygen * 1.9) * flicker;
      flameLight.position.set(_targetFlow.x * 0.14, smoothBaseY + 0.36, _targetFlow.z * 0.14);

      // Update smoke particles (buoyancy vs airflow-driven in microgravity + cursor swirl)
      const upwardBuoyancy = THREE.MathUtils.lerp(0.48, 0, smoothGravity);
      // Fixed artistic visibility, not smoke concentration inferred from the controls.
      smokeMat.opacity = 0.07;
      smokeMat.color.copy(_smokeEarthCol).lerp(_smokeMicroCol, smoothGravity);

      for (let i = 0; !prefersReduced && i < SMOKE_COUNT; i++) {
        smokeLife[i] += dt;
        if (smokeLife[i] >= smokeMaxLife[i]) {
          resetSmokeParticle(i, false);
        } else {
          const i3 = i * 3;
          const swirl = Math.sin(elapsed * 2.2 + i) * 0.025;
          const vx = _targetFlow.x * (0.85 + smoothGravity * 0.45) + swirl + smokeVel[i3] * 0.4;
          const vy = upwardBuoyancy + _targetFlow.y * 0.45 + smokeVel[i3 + 1] * 0.35;
          const vz = _targetFlow.z * (0.85 + smoothGravity * 0.45) + Math.cos(elapsed * 1.9 + i) * 0.025 + smokeVel[i3 + 2] * 0.4;

          smokePositions[i3] += vx * dt;
          smokePositions[i3 + 1] += vy * dt;
          smokePositions[i3 + 2] += vz * dt;

          // Keep smoke contained smoothly within chamber radius
          const rSq = smokePositions[i3] ** 2 + smokePositions[i3 + 2] ** 2;
          if (rSq > 1.32 * 1.32 || smokePositions[i3 + 1] > 1.88 || smokePositions[i3 + 1] < 0.04) {
            resetSmokeParticle(i, false);
          }
        }
      }
      smokeGeo.attributes.position.needsUpdate = true;

      // Camera reset glide + subtle parallax
      if (resettingCamera) {
        camera.position.lerp(DEFAULT_CAMERA_POS, 1 - Math.exp(-6.0 * dt));
        controls.target.lerp(DEFAULT_TARGET, 1 - Math.exp(-6.0 * dt));
        if (camera.position.distanceTo(DEFAULT_CAMERA_POS) < 0.015) {
          camera.position.copy(DEFAULT_CAMERA_POS);
          controls.target.copy(DEFAULT_TARGET);
          resettingCamera = false;
        }
      }

      controls.update();

      // Subtle parallax without drifting camera target permanently
      if (!isOrbitDragging && !prefersReduced) {
        currentParallaxX = THREE.MathUtils.damp(currentParallaxX, parallaxTargetX, 4.5, dt);
        currentParallaxY = THREE.MathUtils.damp(currentParallaxY, parallaxTargetY, 4.5, dt);
        camera.updateMatrixWorld();
        _camRight.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
        _camUp.setFromMatrixColumn(camera.matrixWorld, 1).normalize();
        _camForward.copy(camera.position);
        camera.position.addScaledVector(_camRight, currentParallaxX * 0.45);
        camera.position.addScaledVector(_camUp, currentParallaxY * 0.35);
        camera.lookAt(controls.target);
        renderer.render(scene, camera);
        camera.position.copy(_camForward);
      } else {
        renderer.render(scene, camera);
      }

      if (isSoftwareGl) {
        afterDraw(tick);
      } else {
        frameId = window.requestAnimationFrame(tick);
      }
    };

    const startLoop = () => {
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(frameId);
      if (disposed || document.hidden) return;
      lastNow = performance.now();
      tick();
    };

    const onVisibilityChange = () => {
      if (!document.hidden) startLoop();
    };

    const onMotionChange = (e: MediaQueryListEvent) => {
      prefersReduced = e.matches;
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    reducedMotionQuery.addEventListener('change', onMotionChange);
    startLoop();

    return () => {
      disposed = true;
      window.cancelAnimationFrame(frameId);
      window.clearTimeout(frameId);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      reducedMotionQuery.removeEventListener('change', onMotionChange);
      resizeObserver.disconnect();
      controls.removeEventListener('start', onControlsStart);
      controls.removeEventListener('end', onControlsEnd);
      controls.dispose();
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
      renderer.domElement.removeEventListener('webglcontextlost', onContextLost);

      chamber.dispose();
      flameGeo.dispose();
      outerMat.dispose();
      innerMat.dispose();
      haloGeo.dispose();
      haloMat.dispose();
      smokeGeo.dispose();
      smokeMat.dispose();
      spriteTex.dispose();
      envRT.dispose();
      renderer.dispose();

      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  if (webglUnavailable) {
    return (
      <div className="flex h-full w-full items-center justify-center rounded-xl border border-[#7A5498]/25 bg-[#120B1F]/80 p-8 text-center">
        <div className="max-w-sm space-y-3">
          <div className="mx-auto h-16 w-16 rounded-full bg-gradient-to-tr from-[#3B82F6]/40 via-[#22D3EE]/40 to-[#E1B983]/50" />
          <p className="text-sm text-[#D6CBE8]">
            3D WebGL viewport is unavailable on this browser context. You can still adjust conditions and analyze NASA evidence.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full select-none">
      <div
        ref={mountRef}
        className="h-full w-full cursor-crosshair"
        aria-label="3D Combustion Chamber interactive viewport"
      />
      <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center px-4">
        <p className="rounded-md bg-[#0E0818]/75 px-3 py-1 text-center text-xs text-[#C7B9DC] border border-[#7A5498]/20">
          {cursorHint}
        </p>
      </div>
    </div>
  );
}
