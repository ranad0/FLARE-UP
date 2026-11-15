import * as THREE from 'three';

const NOISE_GLSL = /* glsl */ `
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

  float snoise(vec3 v) {
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i  = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
              i.z + vec4(0.0, i1.z, i2.z, 1.0))
            + i.y + vec4(0.0, i1.y, i2.y, 1.0))
            + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x;
    p1 *= norm.y;
    p2 *= norm.z;
    p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
  }
`;

export interface FlameUniforms {
  [uniform: string]: THREE.IUniform<unknown>;
  uTime: THREE.IUniform<number>;
  uGravityMix: THREE.IUniform<number>; // 0 = Earth 1g, 1 = Microgravity
  uOxygenNorm: THREE.IUniform<number>; // 0..1 (15%..40%)
  uPressureNorm: THREE.IUniform<number>; // 0..1 (4.3..14.7 psi)
  uAirflowMag: THREE.IUniform<number>; // 0..1
  uFlowVec: THREE.IUniform<THREE.Vector3>; // combined airflow + cursor disturbance in world space
  uSampleMode: THREE.IUniform<number>; // 0=gas, 1=liquid, 2=fabric, 3=polymer
  uIsCore: THREE.IUniform<number>; // 0 = outer envelope, 1 = bright inner core
}

export function createFlameUniforms(isCore = false): FlameUniforms {
  return {
    uTime: { value: 0 },
    uGravityMix: { value: 1 },
    uOxygenNorm: { value: 0.24 },
    uPressureNorm: { value: 1.0 },
    uAirflowMag: { value: 0.12 },
    uFlowVec: { value: new THREE.Vector3(0, 0, 0) },
    uSampleMode: { value: 0 },
    uIsCore: { value: isCore ? 1.0 : 0.0 },
  };
}

export function createFlameMaterial(uniforms: FlameUniforms): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      uniform float uTime;
      uniform float uGravityMix;
      uniform float uOxygenNorm;
      uniform float uPressureNorm;
      uniform float uAirflowMag;
      uniform vec3 uFlowVec;
      uniform float uSampleMode;
      uniform float uIsCore;

      varying float vHeight;
      varying float vNoise;
      varying vec3 vNormalView;
      varying vec3 vViewPos;
      varying vec2 vUv;

      ${NOISE_GLSL}

      void main() {
        vUv = uv;
        // Input geometry is a unit sphere centered at origin: y in [-1, 1]
        float h = clamp((position.y / 0.32 + 1.0) * 0.5, 0.0, 1.0);
        vHeight = h;

        vec3 p = position / 0.32;

        // Sample-specific base shape modulation
        float liquidSpread = step(0.5, uSampleMode) * (1.0 - step(1.5, uSampleMode));
        float fabricSpread = step(1.5, uSampleMode) * (1.0 - step(2.5, uSampleMode));
        float polymerSpread = step(2.5, uSampleMode);

        // Earth 1g vs Microgravity base silhouette
        // Earth: elongated teardrop tapering upward; Microgravity: compact rounded sphere
        float earthTaper = mix(0.95, 0.14, pow(h, 0.88)) * (1.0 + 0.16 * sin(h * 3.14159));
        float microRadius = mix(0.84, 0.72, pow(h, 1.4)) * (1.0 + 0.14 * sin(h * 3.14159));
        float radialScale = mix(earthTaper, microRadius, uGravityMix);

        // Subtle pressure tightness (higher pressure slightly crisper/tighter core)
        radialScale *= mix(1.06, 0.94, uPressureNorm);
        // Oxygen luminosity / subtle volume expansion
        radialScale *= mix(0.88, 1.14, uOxygenNorm);

        // Sample geometry flavor
        radialScale *= 1.0 + liquidSpread * 0.14 * (1.0 - h * 0.5);
        p.x *= 1.0 + fabricSpread * 0.34 * (1.0 - h * 0.35);
        p.z *= 1.0 - fabricSpread * 0.18;
        radialScale *= 1.0 + polymerSpread * 0.08;

        // Vertical elongation
        float earthHeight = mix(1.42, 1.76, uOxygenNorm);
        float microHeight = mix(1.45, 1.65, uOxygenNorm);
        float yScale = mix(earthHeight, microHeight, uGravityMix);

        // Core shell is nested inside outer envelope
        float coreScale = mix(1.0, 0.56, uIsCore);

        vec3 shaped = vec3(p.x * radialScale, (p.y + 1.0) * 0.5 * yScale, p.z * radialScale) * coreScale * 0.65;

        // Multi-scale turbulent advection
        float turbRate = mix(2.3, 1.1, uGravityMix) * (1.0 + uOxygenNorm * 0.55 + uAirflowMag * 0.9);
        vec3 flowDir = length(uFlowVec) > 0.001 ? normalize(uFlowVec) : vec3(0.0, 1.0, 0.0);
        float flowStrength = length(uFlowVec);

        vec3 noiseCoord = vec3(
          shaped.x * 2.6 - uFlowVec.x * 0.9,
          shaped.y * 2.1 - uTime * turbRate * (1.0 - uGravityMix),
          shaped.z * 2.6 - uFlowVec.z * 0.9
        );
        float n1 = snoise(noiseCoord);
        float n2 = snoise(noiseCoord * 2.1 + vec3(3.1 + sin(uTime * .4) * uGravityMix, -uTime * turbRate * 0.6 * (1.0 - uGravityMix), 1.7 + cos(uTime * .4) * uGravityMix));
        float turb = n1 * 0.65 + n2 * 0.35;
        vNoise = turb;

        // Turbulence amplitude stronger in Earth buoyancy & high airflow, gentler in microgravity
        float turbAmp = mix(0.055, 0.018, uGravityMix) * (0.65 + uOxygenNorm * 0.6 + flowStrength * 0.4);
        turbAmp *= smoothstep(0.05, 0.65, h) * mix(1.0, 0.55, uIsCore);

        shaped.x += turb * turbAmp + n2 * fabricSpread * 0.07 * h;
        shaped.z += n2 * turbAmp;
        shaped.y += turb * turbAmp * mix(0.45, 0.25, uGravityMix);

        // Illustrative downstream bending from combined steady airflow + cursor disturbance
        float bendFactor = pow(h, mix(1.25, 1.05, uGravityMix));
        // Anchor base at y=0 so root stays seated on the fuel sample
        float rootLock = smoothstep(0.02, 0.28, h);
        shaped += vec3(uFlowVec.x, uFlowVec.y * 0.35, uFlowVec.z) * bendFactor * rootLock * mix(0.95, 1.12, uGravityMix);

        // Slight leeward wake stretch along flow
        float stretch = min(flowStrength, 1.8) * 0.22 * bendFactor * rootLock;
        shaped += flowDir * stretch * 0.35;

        vec4 mvPosition = modelViewMatrix * vec4(shaped, 1.0);
        vViewPos = -mvPosition.xyz;
        vNormalView = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uTime;
      uniform float uGravityMix;
      uniform float uOxygenNorm;
      uniform float uPressureNorm;
      uniform float uAirflowMag;
      uniform vec3 uFlowVec;
      uniform float uSampleMode;
      uniform float uIsCore;

      varying float vHeight;
      varying float vNoise;
      varying vec3 vNormalView;
      varying vec3 vViewPos;
      varying vec2 vUv;

      void main() {
        vec3 viewDir = normalize(vViewPos);
        float ndotv = abs(dot(normalize(vNormalView), viewDir));

        // Soft volumetric edge falloff
        float edgeSharpness = mix(1.45, 2.05, uPressureNorm);
        float rimFade = mix(pow(clamp(ndotv, 0.0, 1.0), edgeSharpness), 0.12 + pow(1.0-ndotv, 1.8)*0.8, uGravityMix);

        // Earth 1g palette: blue base -> Warm Sand (#E1B983) -> Gold (#C88B00) -> rich amber tip
        vec3 earthBaseBlue = vec3(0.22, 0.52, 0.96);
        vec3 earthSand = vec3(0.92, 0.76, 0.52);
        vec3 earthGold = vec3(0.90, 0.56, 0.08);
        vec3 earthTip = vec3(0.75, 0.30, 0.08);

        vec3 earthCol = mix(earthBaseBlue, earthSand, smoothstep(0.05, 0.34, vHeight));
        earthCol = mix(earthCol, earthGold, smoothstep(0.32, 0.68, vHeight));
        earthCol = mix(earthCol, earthTip, smoothstep(0.68, 0.98, vHeight));

        // Microgravity palette: Electric Blue (#3B82F6) + Cyan (#22D3EE) outer, warm-white inner core
        vec3 microDeepBlue = vec3(0.18, 0.44, 0.96);
        vec3 microCyan = vec3(0.14, 0.84, 0.96);
        vec3 microWarmCore = mix(vec3(0.76, 0.93, 1.0), vec3(0.96, 0.84, 0.62), uOxygenNorm);

        vec3 microOuter = mix(microDeepBlue, microCyan, smoothstep(0.15, 0.82, vHeight + vNoise * 0.25));
        vec3 microCol = mix(microOuter, microWarmCore, uIsCore * 0.82 + pow(ndotv, 2.4) * 0.35);

        vec3 col = mix(earthCol, microCol, uGravityMix);

        // Polymer slightly warmer amber soot highlights in upper flame
        float polymerMask = step(2.5, uSampleMode);
        col = mix(col, vec3(0.88, 0.46, 0.14), polymerMask * smoothstep(0.5, 0.95, vHeight) * (1.0 - uGravityMix * 0.65) * 0.45);

        // Brighten core with oxygen
        float oxLum = mix(0.68, 1.48, uOxygenNorm);
        float coreBoost = mix(1.0, 0.9, uIsCore);

        // Vertical & root fade so flame blends cleanly into burner/sample
        float bottomFade = smoothstep(0.0, 0.12, vHeight);
        float topFade = 1.0 - smoothstep(mix(0.72, 0.82, uGravityMix), 1.0, vHeight);

        // Subtle noise shimmer
        float shimmer = 0.88 + 0.18 * vNoise;

        float alpha = rimFade * bottomFade * topFade * shimmer * oxLum * mix(0.58, 0.35, uIsCore);
        alpha = clamp(alpha, 0.0, 0.95);

        gl_FragColor = vec4(col * oxLum * coreBoost, alpha);
      }
    `,
  });
}

export function createHaloMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    uniforms: {
      uGravityMix: { value: 1 },
      uOxygenNorm: { value: 0.24 },
      uFlowOffset: { value: new THREE.Vector2(0, 0) },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uGravityMix;
      uniform float uOxygenNorm;
      uniform vec2 uFlowOffset;
      varying vec2 vUv;

      void main() {
        vec2 center = vec2(0.5, 0.44) + uFlowOffset * 0.08;
        float dist = length((vUv - center) * vec2(1.15, mix(0.85, 1.15, uGravityMix)));
        float glow = exp(-dist * dist * 11.0) * mix(0.24, 0.46, uOxygenNorm);

        vec3 earthGlow = vec3(0.88, 0.62, 0.22);
        vec3 microGlow = vec3(0.18, 0.68, 0.96);
        vec3 col = mix(earthGlow, microGlow, uGravityMix);

        gl_FragColor = vec4(col, clamp(glow, 0.0, 0.6));
      }
    `,
  });
}

export function createParticleSpriteTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
  grad.addColorStop(0.32, 'rgba(255, 255, 255, 0.65)');
  grad.addColorStop(0.7, 'rgba(255, 255, 255, 0.14)');
  grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}
