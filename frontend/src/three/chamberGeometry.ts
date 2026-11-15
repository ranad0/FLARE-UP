import * as THREE from 'three';
import type { SampleType } from '../types/flare';

export interface ChamberAssembly {
  root: THREE.Group;
  airflowIndicatorRing: THREE.Group;
  sampleGroups: Record<SampleType, THREE.Group>;
  setSampleType: (type: SampleType) => void;
  setAirflowDirection: (degrees: number, magnitude: number) => void;
  dispose: () => void;
}

function createWovenFabricTexture(maxAnisotropy: number): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#d8d0c4';
  ctx.fillRect(0, 0, size, size);

  for (let y = 0; y < size; y += 8) {
    ctx.fillStyle = y % 16 === 0 ? 'rgba(90, 75, 65, 0.24)' : 'rgba(255, 250, 240, 0.25)';
    ctx.fillRect(0, y, size, 4);
  }
  for (let x = 0; x < size; x += 8) {
    ctx.fillStyle = x % 16 === 0 ? 'rgba(85, 70, 60, 0.22)' : 'rgba(255, 250, 240, 0.22)';
    ctx.fillRect(x, 0, 4, size);
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(2, 2);
  tex.anisotropy = maxAnisotropy;
  tex.needsUpdate = true;
  return tex;
}

function createCompassDialTexture(maxAnisotropy: number): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const cx = size / 2;
  const cy = size / 2;

  ctx.clearRect(0, 0, size, size);

  ctx.strokeStyle = 'rgba(225, 185, 131, 0.28)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(cx, cy, 224, 0, Math.PI * 2);
  ctx.stroke();

  ctx.strokeStyle = 'rgba(122, 84, 152, 0.35)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(cx, cy, 196, 0, Math.PI * 2);
  ctx.stroke();

  for (let deg = 0; deg < 360; deg += 15) {
    const rad = (deg * Math.PI) / 180;
    const isMajor = deg % 90 === 0;
    const isMid = deg % 45 === 0;
    const rOuter = 222;
    const rInner = isMajor ? 202 : isMid ? 209 : 215;

    ctx.strokeStyle = isMajor ? 'rgba(225, 185, 131, 0.72)' : 'rgba(180, 155, 210, 0.36)';
    ctx.lineWidth = isMajor ? 2.5 : 1.2;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(rad) * rInner, cy + Math.sin(rad) * rInner);
    ctx.lineTo(cx + Math.cos(rad) * rOuter, cy + Math.sin(rad) * rOuter);
    ctx.stroke();
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = maxAnisotropy;
  tex.needsUpdate = true;
  return tex;
}

function createContactShadowTexture(): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createRadialGradient(size / 2, size / 2, 12, size / 2, size / 2, size / 2);
  grad.addColorStop(0, 'rgba(5, 2, 10, 0.85)');
  grad.addColorStop(0.55, 'rgba(9, 5, 18, 0.48)');
  grad.addColorStop(1, 'rgba(9, 5, 18, 0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.needsUpdate = true;
  return tex;
}

export function createCombustionChamber(
  renderer: THREE.WebGLRenderer,
  isSoftwareGl: boolean
): ChamberAssembly {
  const root = new THREE.Group();
  const maxAniso = renderer.capabilities.getMaxAnisotropy();

  const disposables: Array<{ dispose: () => void }> = [];
  const track = <T extends { dispose: () => void }>(item: T): T => {
    disposables.push(item);
    return item;
  };

  // Shared calibrated PBR materials (varying roughness >= 0.25 between adjacent parts)
  const anodizedDeckMat = track(
    new THREE.MeshStandardMaterial({
      color: 0x1e142e,
      roughness: 0.58,
      metalness: 0.72,
    })
  );

  const brushedTitaniumMat = track(
    new THREE.MeshPhysicalMaterial({
      color: 0x7b7192,
      roughness: 0.24,
      metalness: 0.92,
      anisotropy: 0.75,
    })
  );

  const brassCollarMat = track(
    new THREE.MeshStandardMaterial({
      color: 0xc89b4b,
      roughness: 0.28,
      metalness: 0.88,
    })
  );

  const ceramicMat = track(
    new THREE.MeshStandardMaterial({
      color: 0xd9d2c7,
      roughness: 0.82,
      metalness: 0.04,
    })
  );

  const glassMat = track(
    new THREE.MeshPhysicalMaterial({
      color: 0xdcd4f2,
      roughness: 0.08,
      metalness: 0.0,
      transmission: isSoftwareGl ? 0 : 0.86,
      transparent: true,
      opacity: isSoftwareGl ? 0.06 : 0.09,
      ior: 1.48,
      thickness: 0.15,
      clearcoat: 0.9,
      clearcoatRoughness: 0.08,
      depthWrite: false,
      side: THREE.DoubleSide,
    })
  );

  // 1. Soft radial contact shadow grounded beneath pedestal
  const shadowTex = track(createContactShadowTexture());
  const shadowPlane = new THREE.Mesh(
    track(new THREE.PlaneGeometry(5.8, 5.8)),
    track(
      new THREE.MeshBasicMaterial({
        map: shadowTex,
        transparent: true,
        depthWrite: false,
        opacity: 0.72,
      })
    )
  );
  shadowPlane.rotation.x = -Math.PI / 2;
  shadowPlane.position.y = -0.34;
  root.add(shadowPlane);

  // 2. Primary lower chamber pedestal (anodized violet-slate base)
  const basePlate = new THREE.Mesh(
    track(new THREE.CylinderGeometry(1.78, 1.94, 0.22, 48)),
    anodizedDeckMat
  );
  basePlate.position.y = -0.22;
  basePlate.receiveShadow = true;
  basePlate.castShadow = true;
  root.add(basePlate);

  // 3. Machined titanium deck collar
  const deckCollar = new THREE.Mesh(
    track(new THREE.CylinderGeometry(1.52, 1.62, 0.12, 48)),
    brushedTitaniumMat
  );
  deckCollar.position.y = -0.05;
  deckCollar.receiveShadow = true;
  root.add(deckCollar);

  // 4. Calibrated degree ring decal on deck
  const dialTex = track(createCompassDialTexture(maxAniso));
  const dialRing = new THREE.Mesh(
    track(new THREE.RingGeometry(0.68, 1.48, 64)),
    track(
      new THREE.MeshBasicMaterial({
        map: dialTex,
        transparent: true,
        depthWrite: false,
        opacity: 0.8,
        polygonOffset: true,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -1,
      })
    )
  );
  dialRing.rotation.x = -Math.PI / 2;
  dialRing.position.y = 0.015;
  root.add(dialRing);

  // 5. Recessed inner thermal stage
  const centerStage = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.56, 0.62, 0.08, 36)),
    anodizedDeckMat
  );
  centerStage.position.y = 0.02;
  centerStage.receiveShadow = true;
  root.add(centerStage);

  // 6. Upper chamber crown ring
  const topRing = new THREE.Mesh(
    track(new THREE.TorusGeometry(1.44, 0.055, 16, 64)),
    brushedTitaniumMat
  );
  topRing.rotation.x = Math.PI / 2;
  topRing.position.y = 2.15;
  root.add(topRing);

  const topCapTrim = new THREE.Mesh(
    track(new THREE.CylinderGeometry(1.48, 1.48, 0.05, 48, 1, true)),
    anodizedDeckMat
  );
  topCapTrim.position.y = 2.19;
  root.add(topCapTrim);

  // 7. Four structural chamber struts + fasteners (InstancedMesh for fasteners)
  const strutGeo = track(new THREE.CylinderGeometry(0.032, 0.032, 2.22, 16));
  const boltGeo = track(new THREE.CylinderGeometry(0.035, 0.035, 0.04, 12));
  const boltInstanced = new THREE.InstancedMesh(boltGeo, brassCollarMat, 8);
  const dummy = new THREE.Object3D();

  for (let i = 0; i < 4; i++) {
    const angle = (i * Math.PI) / 2;
    const x = Math.cos(angle) * 1.44;
    const z = Math.sin(angle) * 1.44;

    const strut = new THREE.Mesh(strutGeo, brushedTitaniumMat);
    strut.position.set(x, 1.05, z);
    strut.castShadow = true;
    root.add(strut);

    dummy.position.set(x, 0.02, z);
    dummy.updateMatrix();
    boltInstanced.setMatrixAt(i, dummy.matrix);

    dummy.position.set(x, 2.17, z);
    dummy.updateMatrix();
    boltInstanced.setMatrixAt(i + 4, dummy.matrix);
  }
  boltInstanced.instanceMatrix.needsUpdate = true;
  boltInstanced.computeBoundingSphere();
  root.add(boltInstanced);

  // 8. Borosilicate optical observation glass cylinder
  const glassCylinder = new THREE.Mesh(
    track(new THREE.CylinderGeometry(1.41, 1.41, 2.16, 48, 1, true)),
    glassMat
  );
  glassCylinder.position.y = 1.08;
  glassCylinder.renderOrder = 10;
  root.add(glassCylinder);

  // 9. Airflow direction indicator ring (rotates smoothly to match 0-360° airflow)
  const airflowIndicatorRing = new THREE.Group();
  airflowIndicatorRing.position.y = 0.04;

  const indicatorMat = track(
    new THREE.MeshBasicMaterial({
      color: 0x22d3ee,
      transparent: true,
      opacity: 0.78,
    })
  );

  // Nozzle arrow pointer positioned on perimeter pointing inward toward flame
  const chevronShape = new THREE.Shape();
  chevronShape.moveTo(0, 0.12);
  chevronShape.lineTo(-0.08, -0.06);
  chevronShape.lineTo(0, -0.01);
  chevronShape.lineTo(0.08, -0.06);
  chevronShape.closePath();

  const chevronGeo = track(new THREE.ShapeGeometry(chevronShape));
  const chevron = new THREE.Mesh(chevronGeo, indicatorMat);
  chevron.rotation.x = -Math.PI / 2;
  chevron.rotation.z = Math.PI; // point inward from +Z toward center
  chevron.position.set(0, 0.005, 1.18);
  airflowIndicatorRing.add(chevron);

  const nozzlePod = new THREE.Mesh(
    track(new THREE.BoxGeometry(0.16, 0.06, 0.12)),
    brushedTitaniumMat
  );
  nozzlePod.position.set(0, 0.02, 1.32);
  airflowIndicatorRing.add(nozzlePod);

  root.add(airflowIndicatorRing);

  // 10. Four interchangeable Sample Assemblies seated at y = 0.06 (flame origin around y = 0.24)
  const sampleContainer = new THREE.Group();
  sampleContainer.position.y = 0.06;
  root.add(sampleContainer);

  // 10a. Gaseous fuel: precision brass micro-burner + ceramic diffuser ring
  const gaseousGroup = new THREE.Group();
  const gasStem = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.09, 0.13, 0.14, 24)),
    brassCollarMat
  );
  gasStem.position.y = 0.07;
  const gasDiffuser = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.075, 0.085, 0.045, 24)),
    ceramicMat
  );
  gasDiffuser.position.y = 0.16;
  gaseousGroup.add(gasStem, gasDiffuser);

  // 10b. Liquid fuel: recessed crucible dish + shimmering liquid pool
  const liquidGroup = new THREE.Group();
  const crucibleOuter = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.24, 0.20, 0.12, 32)),
    brushedTitaniumMat
  );
  crucibleOuter.position.y = 0.06;
  const liquidSurfaceMat = track(
    new THREE.MeshPhysicalMaterial({
      color: 0x3b2a5a,
      roughness: 0.08,
      metalness: 0.1,
      clearcoat: 1.0,
      clearcoatRoughness: 0.05,
    })
  );
  const liquidPool = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.20, 0.20, 0.02, 32)),
    liquidSurfaceMat
  );
  liquidPool.position.y = 0.115;
  liquidGroup.add(crucibleOuter, liquidPool);

  // 10c. Fabric: twin-prong vertical specimen clamp + woven textile swatch
  const fabricGroup = new THREE.Group();
  const clampBase = new THREE.Mesh(
    track(new THREE.BoxGeometry(0.46, 0.05, 0.12)),
    brushedTitaniumMat
  );
  clampBase.position.y = 0.025;
  const prongGeo = track(new THREE.CylinderGeometry(0.016, 0.016, 0.24, 12));
  const leftProng = new THREE.Mesh(prongGeo, brassCollarMat);
  leftProng.position.set(-0.20, 0.14, 0);
  const rightProng = new THREE.Mesh(prongGeo, brassCollarMat);
  rightProng.position.set(0.20, 0.14, 0);

  const fabricTex = track(createWovenFabricTexture(maxAniso));
  const fabricMat = track(
    new THREE.MeshStandardMaterial({
      map: fabricTex,
      roughness: 0.9,
      metalness: 0.0,
      side: THREE.DoubleSide,
    })
  );
  const fabricSwatch = new THREE.Mesh(
    track(new THREE.BoxGeometry(0.36, 0.18, 0.014)),
    fabricMat
  );
  fabricSwatch.position.y = 0.13;
  fabricGroup.add(clampBase, leftProng, rightProng, fabricSwatch);

  // 10d. Polymer: collet chuck + cylindrical polymer rod
  const polymerGroup = new THREE.Group();
  const collet = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.11, 0.15, 0.10, 24)),
    brassCollarMat
  );
  collet.position.y = 0.05;
  const polymerRodMat = track(
    new THREE.MeshPhysicalMaterial({
      color: 0xebe6dc,
      roughness: 0.42,
      metalness: 0.0,
      clearcoat: 0.25,
    })
  );
  const polymerRod = new THREE.Mesh(
    track(new THREE.CylinderGeometry(0.058, 0.062, 0.16, 24)),
    polymerRodMat
  );
  polymerRod.position.y = 0.14;
  polymerGroup.add(collet, polymerRod);

  const sampleGroups: Record<SampleType, THREE.Group> = {
    gaseous: gaseousGroup,
    liquid: liquidGroup,
    fabric: fabricGroup,
    polymer: polymerGroup,
  };

  Object.values(sampleGroups).forEach((g) => sampleContainer.add(g));

  const setSampleType = (type: SampleType) => {
    (Object.keys(sampleGroups) as SampleType[]).forEach((key) => {
      sampleGroups[key].visible = key === type;
    });
  };
  setSampleType('gaseous');

  const setAirflowDirection = (degrees: number, magnitude: number) => {
    const rad = THREE.MathUtils.degToRad(degrees);
    // Air blows *from* nozzle or *toward* direction: rotate nozzle behind origin so it points along flow vector
    airflowIndicatorRing.rotation.y = -rad + Math.PI;
    indicatorMat.opacity = magnitude <= 0.02 ? 0.22 : 0.45 + magnitude * 0.5;
  };

  const dispose = () => {
    disposables.forEach((d) => d.dispose());
  };

  return {
    root,
    airflowIndicatorRing,
    sampleGroups,
    setSampleType,
    setAirflowDirection,
    dispose,
  };
}
