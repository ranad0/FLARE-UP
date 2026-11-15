import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import {
  createFlameMaterial,
  createFlameUniforms,
  createHaloMaterial,
  createParticleSpriteTexture,
} from '../three/flameShaders';

interface HomeFlameSceneProps {
  hintText: string;
}

const _camRight = new THREE.Vector3();
const _camUp = new THREE.Vector3();
const _flameScreen = new THREE.Vector3();
const _flowVec = new THREE.Vector3();
const _earthCol = new THREE.Color(0xe1b983);
const _microCol = new THREE.Color(0x22d3ee);

export function HomeFlameScene({ hintText }: HomeFlameSceneProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

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
      setFallback(true);
      return;
    }

    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.setPixelRatio(isSoftwareGl ? 1 : Math.min(window.devicePixelRatio || 1, 2));
    renderer.setClearColor(0x000000, 0);

    const w = container.clientWidth || 360;
    const h = container.clientHeight || 360;
    renderer.setSize(w, h);
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    const envRT = pmremGenerator.fromScene(new RoomEnvironment(), 0.04);
    scene.environment = envRT.texture;
    pmremGenerator.dispose();

    const camera = new THREE.PerspectiveCamera(35, w / h, 0.1, 20);
    camera.position.set(0.55, 1.05, 2.55);
    camera.lookAt(0, 0.44, 0);

    scene.add(new THREE.HemisphereLight(0xb89ee8, 0x150a24, 0.55));
    const key = new THREE.DirectionalLight(0xffe9cc, 1.1);
    key.position.set(2.5, 3.5, 2.5);
    scene.add(key);

    const flameLight = new THREE.PointLight(0x38bdf8, 1.8, 5, 1.8);
    flameLight.position.set(0, 0.45, 0);
    scene.add(flameLight);

    // Minimal scientific burner plinth (3-part composite)
    const plinth = new THREE.Group();
    const baseMat = new THREE.MeshStandardMaterial({
      color: 0x221636,
      roughness: 0.55,
      metalness: 0.72,
    });
    const collarMat = new THREE.MeshStandardMaterial({
      color: 0xc89b4b,
      roughness: 0.28,
      metalness: 0.88,
    });
    const ceramicMat = new THREE.MeshStandardMaterial({
      color: 0xd9d2c7,
      roughness: 0.82,
      metalness: 0.05,
    });

    const baseDisk = new THREE.Mesh(new THREE.CylinderGeometry(0.46, 0.52, 0.08, 36), baseMat);
    baseDisk.position.y = -0.04;
    const nozzleRing = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.18, 0.09, 28), collarMat);
    nozzleRing.position.y = 0.045;
    const ceramicTip = new THREE.Mesh(new THREE.CylinderGeometry(0.095, 0.11, 0.035, 24), ceramicMat);
    ceramicTip.position.y = 0.105;
    plinth.add(baseDisk, nozzleRing, ceramicTip);
    scene.add(plinth);

    // Volumetric Flame
    const flameGroup = new THREE.Group();
    flameGroup.position.y = 0.115;
    scene.add(flameGroup);

    const flameGeo = new THREE.SphereGeometry(0.32, 40, 40);
    const outerUniforms = createFlameUniforms(false);
    outerUniforms.uOxygenNorm.value = 0.36;
    outerUniforms.uPressureNorm.value = 0.72;
    const outerMat = createFlameMaterial(outerUniforms);
    const outerMesh = new THREE.Mesh(flameGeo, outerMat);
    outerMesh.renderOrder = 3;
    flameGroup.add(outerMesh);

    const innerUniforms = createFlameUniforms(true);
    innerUniforms.uOxygenNorm.value = 0.36;
    innerUniforms.uPressureNorm.value = 0.72;
    const innerMat = createFlameMaterial(innerUniforms);
    const innerMesh = new THREE.Mesh(flameGeo, innerMat);
    innerMesh.renderOrder = 4;
    flameGroup.add(innerMesh);

    const haloGeo = new THREE.PlaneGeometry(1.9, 2.0);
    const haloMat = createHaloMaterial();
    haloMat.uniforms.uOxygenNorm.value = 0.38;
    const haloMesh = new THREE.Mesh(haloGeo, haloMat);
    haloMesh.position.y = 0.38;
    haloMesh.quaternion.copy(camera.quaternion);
    haloMesh.renderOrder = 2;
    flameGroup.add(haloMesh);

    // Subtle luminous sparks
    const spriteTex = createParticleSpriteTexture();
    const EMBER_COUNT = 34;
    const emberPos = new Float32Array(EMBER_COUNT * 3);
    const emberVel = new Float32Array(EMBER_COUNT * 3);
    const emberLife = new Float32Array(EMBER_COUNT);
    const emberMax = new Float32Array(EMBER_COUNT);

    const resetEmber = (i: number, randomAge = false) => {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * 0.09;
      emberPos[i * 3] = Math.cos(a) * r;
      emberPos[i * 3 + 1] = 0.06 + Math.random() * 0.14;
      emberPos[i * 3 + 2] = Math.sin(a) * r;
      emberVel[i * 3] = (Math.random() - 0.5) * 0.08;
      emberVel[i * 3 + 1] = 0.2 + Math.random() * 0.22;
      emberVel[i * 3 + 2] = (Math.random() - 0.5) * 0.08;
      emberMax[i] = 0.9 + Math.random() * 1.0;
      emberLife[i] = randomAge ? Math.random() * emberMax[i] : 0;
    };
    for (let i = 0; i < EMBER_COUNT; i++) resetEmber(i, true);

    const emberGeo = new THREE.BufferGeometry();
    emberGeo.setAttribute('position', new THREE.BufferAttribute(emberPos, 3));
    const emberMat = new THREE.PointsMaterial({
      map: spriteTex,
      color: 0x38bdf8,
      size: 0.065,
      transparent: true,
      opacity: 0.65,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const embers = new THREE.Points(emberGeo, emberMat);
    embers.renderOrder = 5;
    flameGroup.add(embers);

    if (!isSoftwareGl) {
      renderer.compile(scene, camera);
    }

    // Cursor spring disturbance
    const cursorPos = new THREE.Vector3();
    const cursorVel = new THREE.Vector3();
    const cursorImpulse = new THREE.Vector3();
    let lastX = 0;
    let lastY = 0;
    let hasLast = false;

    const onPointerMove = (e: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const ndcX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const ndcY = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      if (!hasLast) {
        lastX = ndcX;
        lastY = ndcY;
        hasLast = true;
        return;
      }

      const dx = ndcX - lastX;
      const dy = ndcY - lastY;
      lastX = ndcX;
      lastY = ndcY;

      _flameScreen.set(0, 0.44, 0).project(camera);
      const dist = Math.hypot(ndcX - _flameScreen.x, ndcY - _flameScreen.y);
      const prox = THREE.MathUtils.smoothstep(1.3 - dist, 0.0, 1.1);

      if (prox > 0.02) {
        camera.updateMatrixWorld();
        _camRight.setFromMatrixColumn(camera.matrixWorld, 0).normalize();
        _camUp.setFromMatrixColumn(camera.matrixWorld, 1).normalize();
        const strength = 19.0 * prox;
        cursorImpulse.x = THREE.MathUtils.clamp(
          cursorImpulse.x + (_camRight.x * dx + _camUp.x * dy) * strength,
          -1.6,
          1.6
        );
        cursorImpulse.y = THREE.MathUtils.clamp(
          cursorImpulse.y + (_camRight.y * dx + _camUp.y * dy) * strength * 0.4,
          -0.6,
          0.6
        );
        cursorImpulse.z = THREE.MathUtils.clamp(
          cursorImpulse.z + (_camRight.z * dx + _camUp.z * dy) * strength,
          -1.6,
          1.6
        );
      }
    };

    const onPointerLeave = () => {
      hasLast = false;
    };

    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);

    const resizeObserver = new ResizeObserver(() => {
      const cw = container.clientWidth || 1;
      const ch = container.clientHeight || 1;
      camera.aspect = cw / ch;
      camera.updateProjectionMatrix();
      renderer.setSize(cw, ch);
    });
    resizeObserver.observe(container);

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
        if (gl.getSyncParameter(sync, gl.SYNC_STATUS) === gl.UNSIGNALED) {
          frameId = window.setTimeout(poll, 5);
        } else {
          gl.deleteSync(sync);
          frameId = window.setTimeout(cb, 80);
        }
      };
      frameId = window.setTimeout(poll, 5);
    };

    const tick = () => {
      if (disposed || document.hidden) return;
      const now = performance.now();
      const rawDt = Math.min((now - lastNow) / 1000, 0.05);
      lastNow = now;
      const dt = Math.max(rawDt, 0.001);
      elapsed += prefersReduced ? dt * 0.2 : dt;

      // Subtle slow oscillation between microgravity-dominant blue/cyan and warm core hint
      const gMix = prefersReduced ? 0.85 : 0.72 + 0.25 * Math.sin(elapsed * 0.35);

      cursorImpulse.multiplyScalar(Math.exp(-5.4 * dt));
      const stiffness = 36.0;
      const damping = 7.2;
      cursorVel.x += ((cursorImpulse.x - cursorPos.x) * stiffness - cursorVel.x * damping) * dt;
      cursorVel.y += ((cursorImpulse.y - cursorPos.y) * stiffness - cursorVel.y * damping) * dt;
      cursorVel.z += ((cursorImpulse.z - cursorPos.z) * stiffness - cursorVel.z * damping) * dt;
      cursorPos.addScaledVector(cursorVel, dt);

      _flowVec.copy(cursorPos);

      outerUniforms.uTime.value = elapsed;
      outerUniforms.uGravityMix.value = gMix;
      outerUniforms.uFlowVec.value.copy(_flowVec);

      innerUniforms.uTime.value = elapsed;
      innerUniforms.uGravityMix.value = gMix;
      innerUniforms.uFlowVec.value.copy(_flowVec);

      haloMat.uniforms.uGravityMix.value = gMix;
      haloMat.uniforms.uFlowOffset.value.set(_flowVec.x, _flowVec.y);

      flameLight.color.copy(_earthCol).lerp(_microCol, gMix);
      emberMat.color.copy(_earthCol).lerp(_microCol, gMix);

      for (let i = 0; i < EMBER_COUNT; i++) {
        emberLife[i] += dt;
        if (emberLife[i] >= emberMax[i]) {
          resetEmber(i, false);
        } else {
          const i3 = i * 3;
          emberPos[i3] += (_flowVec.x * 1.1 + emberVel[i3]) * dt;
          emberPos[i3 + 1] += (0.28 + _flowVec.y * 0.5 + emberVel[i3 + 1]) * dt;
          emberPos[i3 + 2] += (_flowVec.z * 1.1 + emberVel[i3 + 2]) * dt;
        }
      }
      emberGeo.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);

      if (isSoftwareGl) afterDraw(tick);
      else frameId = window.requestAnimationFrame(tick);
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
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);

      baseDisk.geometry.dispose();
      nozzleRing.geometry.dispose();
      ceramicTip.geometry.dispose();
      baseMat.dispose();
      collarMat.dispose();
      ceramicMat.dispose();
      flameGeo.dispose();
      outerMat.dispose();
      innerMat.dispose();
      haloGeo.dispose();
      haloMat.dispose();
      emberGeo.dispose();
      emberMat.dispose();
      spriteTex.dispose();
      envRT.dispose();
      renderer.dispose();

      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  if (fallback) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <div className="h-32 w-32 rounded-full bg-gradient-to-t from-[#3B82F6]/60 via-[#22D3EE]/50 to-[#E1B983]/70 blur-xl" />
      </div>
    );
  }

  return (
    <div className="relative h-full w-full select-none">
      <div
        ref={mountRef}
        className="h-full w-full cursor-crosshair"
        aria-label="Interactive 3D microgravity flame"
      />
      <p className="pointer-events-none absolute inset-x-0 bottom-2 text-center text-xs text-[#C7B9DC]/80">
        {hintText}
      </p>
    </div>
  );
}
