/* ============================================================
   hologramme.js — Mode Hologramme JARVIS
   Adapté depuis mode holograme/script.js
   Exports: activerHolo() / desactiverHolo()
   ============================================================ */

import * as THREE from 'three';
import { EffectComposer }  from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass }      from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass }      from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass }      from 'three/addons/postprocessing/OutputPass.js';
import { mergeVertices }   from 'three/addons/utils/BufferGeometryUtils.js';

const COLOR = {
  CYAN:      0x00e5ff,
  CYAN_SOFT: 0x6ff8ff,
  BLUE:      0x2b7bff,
  ORANGE:    0xff8a1a,
  ORANGE2:   0xffb454,
  RED:       0xff2e4d,
  WHITE:     0xeafcff,
};

const lerp  = (a, b, t) => a + (b - a) * t;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const HAND_CONNECTIONS = [
  [0,1],[1,2],[2,3],[3,4],
  [0,5],[5,6],[6,7],[7,8],
  [5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],
  [13,17],[0,17],[17,18],[18,19],[19,20],
];

let _glowTex = null;
function glowTexture() {
  if (_glowTex) return _glowTex;
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const ctx = c.getContext('2d');
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0.00, 'rgba(255,255,255,1)');
  g.addColorStop(0.18, 'rgba(180,240,255,0.85)');
  g.addColorStop(0.45, 'rgba(0,160,255,0.30)');
  g.addColorStop(1.00, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  _glowTex = new THREE.CanvasTexture(c);
  return _glowTex;
}

/* ── HandTracker ─────────────────────────────────────────── */
class HandTracker {
  constructor(video, app) {
    this.video = video;
    this.app = app;
    this.results = null;
    this.onResults = null;
    this.ready = false;
    if (typeof Hands === 'undefined') throw new Error('MediaPipe Hands not loaded');
    this.hands = new Hands({
      locateFile: (file) =>
        `https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4.1675469240/${file}`,
    });
    this.hands.setOptions({ maxNumHands: 2, modelComplexity: 0, minDetectionConfidence: 0.55, minTrackingConfidence: 0.5 });
    this.hands.onResults((r) => { this.results = r; this.ready = true; if (this.onResults) this.onResults(r); });
  }

  async start() {
    if (typeof Hands === 'undefined') throw new Error('MediaPipe Hands non chargé.');
    try {
      const constraints = {
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      };
      if (window.JARVIS_CAMERA_DEVICE_ID) {
        constraints.video.deviceId = { exact: window.JARVIS_CAMERA_DEVICE_ID };
      } else {
        constraints.video.facingMode = 'user';
      }
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.video.srcObject = stream;
      await new Promise((resolve) => { this.video.onloadedmetadata = () => { this.video.play(); resolve(); }; });
      let frameCounter = 0;
      const processFrame = async () => {
        if (!this.app._running || this.video.paused || this.video.ended) return;
        frameCounter++;
        if (frameCounter % 3 !== 0) { requestAnimationFrame(processFrame); return; }
        try { await this.hands.send({ image: this.video }); } catch (e) {}
        requestAnimationFrame(processFrame);
      };
      processFrame();
    } catch (err) {
      let msg = 'Erreur caméra: ';
      if (err.name === 'NotAllowedError') msg = 'Accès caméra REFUSÉ.';
      else if (err.name === 'NotFoundError') msg = 'Aucune caméra détectée.';
      else if (err.name === 'NotReadableError') msg = 'Caméra occupée par une autre appli.';
      else msg += err.message;
      throw new Error(msg);
    }
  }
}

/* ── GestureSystem ───────────────────────────────────────── */
class GestureSystem {
  constructor() { this.history = [[], []]; this.openFlag = [false, false]; this.fistFlag = [false, false]; }
  static dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }
  static pinchValue(hand) { return GestureSystem.dist(hand[4], hand[8]); }
  static isPinched(hand)  { return GestureSystem.pinchValue(hand) < 0.08; }
  static pinchCenter(hand) { return { x: (hand[4].x + hand[8].x) * 0.5, y: (hand[4].y + hand[8].y) * 0.5, z: ((hand[4].z || 0) + (hand[8].z || 0)) * 0.5 }; }
  static isOpenHand(hand) {
    const palm = hand[0], tips = [4,8,12,16,20];
    let avg = 0; for (const t of tips) avg += GestureSystem.dist(hand[t], palm); avg /= tips.length;
    const extended = hand[8].y < hand[5].y && hand[12].y < hand[9].y && hand[16].y < hand[13].y && hand[20].y < hand[17].y;
    return avg > 0.21 && extended;
  }
  static isFist(hand) {
    const palm = hand[0], tips = [8,12,16,20];
    let avg = 0; for (const t of tips) avg += GestureSystem.dist(hand[t], palm); avg /= tips.length;
    const curled = hand[8].y > hand[6].y && hand[12].y > hand[10].y && hand[16].y > hand[14].y && hand[20].y > hand[18].y;
    return avg < 0.12 && curled;
  }
  pushHistory(handIdx, hand) {
    if (!hand) { this.history[handIdx].length = 0; return; }
    const wrist = hand[0];
    this.history[handIdx].push({ x: wrist.x, y: wrist.y, t: performance.now() });
    while (this.history[handIdx].length > 18) this.history[handIdx].shift();
  }
  detectSwipe(handIdx) {
    const hist = this.history[handIdx];
    if (!hist || hist.length < 8) return null;
    const now = performance.now(), old = hist[0];
    if (now - old.t > 550) return null;
    const dx = hist[hist.length - 1].x - old.x, dy = hist[hist.length - 1].y - old.y;
    if (Math.abs(dx) > 0.28 && Math.abs(dx) > Math.abs(dy) * 1.5) { hist.length = 0; return dx > 0 ? 'left' : 'right'; }
    return null;
  }
}

/* ── HologramShape ───────────────────────────────────────── */
class HologramShape {
  constructor(type, position) {
    this.type = type;
    this.group = new THREE.Group();
    this.group.position.copy(position);
    const { geom, baseScale } = HologramShape._buildGeometry(type);
    this.baseScale = baseScale;
    this.geometry = mergeVertices(geom, 0.001);
    this.geometry.computeVertexNormals();
    this.basePositions = new Float32Array(this.geometry.attributes.position.array);
    this.vertexCount = this.basePositions.length / 3;
    this.material = new THREE.MeshBasicMaterial({ color: COLOR.CYAN, wireframe: true, transparent: true, opacity: 0.15, depthWrite: false, blending: THREE.AdditiveBlending });
    this.mesh = new THREE.Mesh(this.geometry, this.material);
    this.mesh.scale.setScalar(baseScale);
    this.group.add(this.mesh);
    this.innerMat = new THREE.MeshBasicMaterial({ color: COLOR.ORANGE, transparent: true, opacity: 0.08, side: THREE.BackSide, depthWrite: false, blending: THREE.AdditiveBlending });
    this.inner = new THREE.Mesh(this.geometry, this.innerMat);
    this.inner.scale.setScalar(baseScale * 0.95);
    this.group.add(this.inner);
    const coreGeom = new THREE.IcosahedronGeometry(0.18, 1);
    const coreMat = new THREE.MeshBasicMaterial({ color: COLOR.WHITE, wireframe: true, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending });
    this.core = new THREE.Mesh(coreGeom, coreMat);
    this.group.add(this.core);
    this.coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture(), color: COLOR.CYAN, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
    this.coreGlow.scale.set(1.6, 1.6, 1.6);
    this.group.add(this.coreGlow);
    this.rings = [];
    const ringColors = [COLOR.CYAN, COLOR.ORANGE, COLOR.RED];
    for (let i = 0; i < 3; i++) {
      const r = baseScale * (1.06 + i * 0.18);
      const rg = new THREE.TorusGeometry(r, 0.012 + i * 0.003, 8, 80);
      const rm = new THREE.MeshBasicMaterial({ color: ringColors[i], transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false });
      const ring = new THREE.Mesh(rg, rm);
      ring.userData.spin = new THREE.Vector3(0.004 + i * 0.003, 0.007 + i * 0.002, 0.003);
      ring.rotation.set(i * 0.7, i * 1.1, i * 0.4);
      this.rings.push(ring);
      this.group.add(ring);
    }
    this.cpGeom = new THREE.SphereGeometry(0.035, 8, 8);
    this.cpDefaultColor = new THREE.Color(COLOR.WHITE);
    this.cpGrabbedColor = new THREE.Color(COLOR.ORANGE);
    this.controlPoints = [];
    for (let i = 0; i < this.vertexCount; i++) {
      const cpMat = new THREE.MeshBasicMaterial({ color: COLOR.WHITE, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false });
      const cp = new THREE.Mesh(this.cpGeom, cpMat);
      cp.userData.grabbed = false;
      this.controlPoints.push(cp);
      this.group.add(cp);
    }
    this._buildAura(baseScale);
    this.grabbed = new Map();
    this.userScale = 1.0; this.targetUserScale = 1.0;
    this.compression = 1.0; this.targetCompression = 1.0;
    this.pulsePhase = Math.random() * Math.PI * 2;
    this.time = 0; this.selected = false;
    this.rotateAuto = true;
    this.autoSpin = new THREE.Vector3(0.004, 0.006, 0.002);
    this._updateControlPoints();
  }
  static _buildGeometry(type) {
    let geom, baseScale = 1.0;
    switch (type) {
      case 'sphere':   geom = new THREE.IcosahedronGeometry(1.0, 2); break;
      case 'cube':     geom = new THREE.BoxGeometry(1.4, 1.4, 1.4, 3, 3, 3); break;
      case 'triangle': geom = new THREE.CylinderGeometry(1.0, 1.0, 0.6, 3, 2); break;
      case 'pyramid':  geom = new THREE.ConeGeometry(1.0, 1.4, 4, 2); break;
      case 'tetra':    geom = new THREE.TetrahedronGeometry(1.15, 1); break;
      case 'octa':     geom = new THREE.OctahedronGeometry(1.15, 2); break;
      case 'torus':    geom = new THREE.TorusGeometry(1.0, 0.32, 14, 36); break;
      case 'dna':      geom = new THREE.TorusKnotGeometry(0.8, 0.18, 96, 10, 2, 3); break;
      case 'ring':     geom = new THREE.TorusGeometry(1.15, 0.05, 10, 96); break;
      case 'free':     geom = new THREE.DodecahedronGeometry(1.05, 1); break;
      default:         geom = new THREE.IcosahedronGeometry(1.0, 2);
    }
    return { geom, baseScale };
  }
  _buildAura(scale) {
    const N = 30;
    const positions = new Float32Array(N * 3), speeds = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const r = scale * (1.25 + Math.random() * 0.85), t = Math.random() * Math.PI * 2, p = Math.acos(2 * Math.random() - 1);
      positions[i*3+0] = r * Math.sin(p) * Math.cos(t);
      positions[i*3+1] = r * Math.sin(p) * Math.sin(t);
      positions[i*3+2] = r * Math.cos(p);
      speeds[i*3+0] = (Math.random() - 0.5) * 0.005;
      speeds[i*3+1] = (Math.random() - 0.5) * 0.005;
      speeds[i*3+2] = (Math.random() - 0.5) * 0.005;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    g.userData.speeds = speeds; g.userData.maxR = scale * 2.3;
    const m = new THREE.PointsMaterial({ color: COLOR.CYAN_SOFT, size: 0.05, map: glowTexture(), transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending, depthWrite: false });
    this.aura = new THREE.Points(g, m);
    this.group.add(this.aura);
  }
  _updateControlPoints() {
    const pos = this.geometry.attributes.position.array;
    for (let i = 0; i < this.vertexCount; i++) {
      const cp = this.controlPoints[i];
      cp.position.set(pos[i*3+0] * this.baseScale, pos[i*3+1] * this.baseScale, pos[i*3+2] * this.baseScale);
    }
  }
  grabVertex(idx, handIdx) {
    this.grabbed.set(idx, handIdx);
    const cp = this.controlPoints[idx];
    cp.material.color.copy(this.cpGrabbedColor); cp.material.opacity = 1; cp.scale.setScalar(2.0); cp.userData.grabbed = true;
  }
  releaseVertex(idx) {
    if (!this.grabbed.has(idx)) return;
    this.grabbed.delete(idx);
    const cp = this.controlPoints[idx];
    cp.material.color.copy(this.cpDefaultColor); cp.material.opacity = 0.85; cp.scale.setScalar(1.0); cp.userData.grabbed = false;
  }
  releaseAllByHand(handIdx) { for (const [vIdx, h] of this.grabbed) { if (h === handIdx) this.releaseVertex(vIdx); } }
  setVertexLocal(idx, localInGroup) {
    const pos = this.geometry.attributes.position.array;
    pos[idx*3+0] = localInGroup.x / this.baseScale;
    pos[idx*3+1] = localInGroup.y / this.baseScale;
    pos[idx*3+2] = localInGroup.z / this.baseScale;
    this.geometry.attributes.position.needsUpdate = true;
  }
  getWorldVertex(idx, target = new THREE.Vector3()) {
    const pos = this.geometry.attributes.position.array;
    target.set(pos[idx*3+0] * this.baseScale, pos[idx*3+1] * this.baseScale, pos[idx*3+2] * this.baseScale);
    this.group.updateMatrixWorld();
    return target.applyMatrix4(this.group.matrixWorld);
  }
  compress(factor) { this.targetCompression = clamp(factor, 0.25, 1.6); }
  explode() {
    const pos = this.geometry.attributes.position.array, maxR = 2.4;
    for (let i = 0; i < this.vertexCount; i++) {
      if (this.grabbed.has(i)) continue;
      const dx = pos[i*3+0], dy = pos[i*3+1], dz = pos[i*3+2], len = Math.hypot(dx, dy, dz) || 0.0001;
      if (len > maxR) continue;
      const k = 0.22 / len;
      pos[i*3+0] += dx * k; pos[i*3+1] += dy * k; pos[i*3+2] += dz * k;
    }
    this.geometry.attributes.position.needsUpdate = true;
  }
  resetDeformation() {
    const pos = this.geometry.attributes.position.array;
    for (let i = 0; i < pos.length; i++) pos[i] = this.basePositions[i];
    this.geometry.attributes.position.needsUpdate = true;
  }
  update(dt) {
    this.time += dt;
    if (this.rotateAuto && this.grabbed.size === 0) { this.group.rotation.x += this.autoSpin.x; this.group.rotation.y += this.autoSpin.y; this.group.rotation.z += this.autoSpin.z; }
    const pulse = 1 + Math.sin(this.time * 2 + this.pulsePhase) * 0.06;
    this.core.scale.setScalar(pulse);
    this.coreGlow.scale.setScalar(1.4 + pulse * 0.45);
    this.coreGlow.material.opacity = 0.6 + Math.sin(this.time * 3) * 0.25;
    this.userScale = lerp(this.userScale, this.targetUserScale, 0.15);
    this.compression = lerp(this.compression, this.targetCompression, 0.10);
    this.group.scale.setScalar(this.userScale * this.compression);
    for (const ring of this.rings) { ring.rotation.x += ring.userData.spin.x; ring.rotation.y += ring.userData.spin.y; ring.rotation.z += ring.userData.spin.z; }
    const ap = this.aura.geometry.attributes.position.array, sp = this.aura.geometry.userData.speeds, maxR = this.aura.geometry.userData.maxR;
    for (let i = 0; i < ap.length; i += 3) {
      ap[i+0] += sp[i+0]; ap[i+1] += sp[i+1]; ap[i+2] += sp[i+2];
      const r = Math.hypot(ap[i], ap[i+1], ap[i+2]);
      if (r > maxR) { sp[i+0] = -sp[i+0]*0.7; sp[i+1] = -sp[i+1]*0.7; sp[i+2] = -sp[i+2]*0.7; const sc = (maxR*0.95)/r; ap[i+0]*=sc; ap[i+1]*=sc; ap[i+2]*=sc; }
    }
    this.aura.geometry.attributes.position.needsUpdate = true;
    this.aura.rotation.y += 0.002;
    this._updateControlPoints();
    const base = this.selected ? 0.95 : 0.78;
    this.material.opacity = base + Math.sin(this.time * 4) * 0.06;
    this.material.color.setHex(this.selected ? COLOR.ORANGE2 : COLOR.CYAN);
  }
  dispose() {
    this.group.parent?.remove(this.group);
    this.geometry.dispose(); this.material.dispose(); this.innerMat.dispose();
    this.core.geometry.dispose(); this.core.material.dispose();
    for (const r of this.rings) { r.geometry.dispose(); r.material.dispose(); }
    for (const cp of this.controlPoints) cp.material.dispose();
    this.cpGeom.dispose(); this.aura.geometry.dispose(); this.aura.material.dispose(); this.coreGlow.material.dispose();
  }
}

/* ── ShapeManager ────────────────────────────────────────── */
class ShapeManager {
  constructor(scene) { this.scene = scene; this.shapes = []; this.selectedIndex = -1; }
  add(type, position = null) {
    const pos = position || this._spawnPosition();
    const shape = new HologramShape(type, pos);
    this.scene.add(shape.group); this.shapes.push(shape); this.select(this.shapes.length - 1); return shape;
  }
  remove(idx) { const s = this.shapes[idx]; if (!s) return; s.dispose(); this.shapes.splice(idx, 1); if (this.selectedIndex >= this.shapes.length) this.selectedIndex = this.shapes.length - 1; this._updateSelection(); }
  clear() { while (this.shapes.length) this.remove(0); }
  select(idx) { this.selectedIndex = idx; this._updateSelection(); }
  current() { return this.shapes[this.selectedIndex] || null; }
  cycle(dir) { if (!this.shapes.length) return; this.selectedIndex = (this.selectedIndex + dir + this.shapes.length) % this.shapes.length; this._updateSelection(); }
  _updateSelection() { for (let i = 0; i < this.shapes.length; i++) this.shapes[i].selected = (i === this.selectedIndex); }
  _spawnPosition() { const n = this.shapes.length, angle = n * 0.85, radius = 0.4 + (n % 3) * 0.4; return new THREE.Vector3(Math.cos(angle) * radius, ((n % 5) - 2) * 0.35, Math.sin(angle) * radius - 0.2); }
  update(dt) { for (const s of this.shapes) s.update(dt); }
  closestVertex(worldPoint, threshold = 0.4) {
    let best = null; const tmp = new THREE.Vector3();
    for (let i = 0; i < this.shapes.length; i++) { const s = this.shapes[i]; for (let v = 0; v < s.vertexCount; v++) { if (s.grabbed.has(v)) continue; s.getWorldVertex(v, tmp); const d = tmp.distanceTo(worldPoint); if (d < threshold && (!best || d < best.d)) best = { shape: s, shapeIdx: i, vertexIdx: v, d, worldPos: tmp.clone() }; } }
    return best;
  }
  closestShape(worldPoint) {
    let best = null;
    for (let i = 0; i < this.shapes.length; i++) { const s = this.shapes[i]; const d = s.group.position.distanceTo(worldPoint); if (!best || d < best.d) best = { shape: s, shapeIdx: i, d }; }
    return best;
  }
}

/* ── ParticleEngine ──────────────────────────────────────── */
class ParticleEngine {
  constructor(scene) { this.scene = scene; this.bursts = []; this.rings = []; this._initDust(); this._initComets(); }
  _initDust() {
    const N = 120, positions = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) { positions[i*3+0] = (Math.random()-0.5)*18; positions[i*3+1] = (Math.random()-0.5)*11; positions[i*3+2] = -Math.random()*13-1; }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const m = new THREE.PointsMaterial({ color: COLOR.CYAN_SOFT, size: 0.04, map: glowTexture(), transparent: true, opacity: 0.50, blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true });
    this.dust = new THREE.Points(g, m); this.scene.add(this.dust);
  }
  _initComets() {
    this.comets = [];
    for (let i = 0; i < 2; i++) {
      const TRAIL = 18, trail = new Float32Array(TRAIL * 3), cg = new THREE.BufferGeometry();
      cg.setAttribute('position', new THREE.BufferAttribute(trail, 3));
      const cm = new THREE.LineBasicMaterial({ color: i % 2 ? COLOR.ORANGE : COLOR.CYAN, transparent: true, opacity: 0.70, blending: THREE.AdditiveBlending });
      const line = new THREE.Line(cg, cm);
      this.scene.add(line);
      this.comets.push({ line, TRAIL, history: [], pos: new THREE.Vector3((Math.random()-0.5)*10, (Math.random()-0.5)*6, -Math.random()*8-2), vel: new THREE.Vector3((Math.random()-0.5)*0.06, (Math.random()-0.5)*0.03, 0), life: 100+Math.random()*200 });
    }
  }
  explode(worldPos, color = COLOR.CYAN, count = 80) {
    const positions = new Float32Array(count*3), velocities = new Float32Array(count*3);
    for (let i = 0; i < count; i++) {
      positions[i*3+0] = worldPos.x; positions[i*3+1] = worldPos.y; positions[i*3+2] = worldPos.z;
      const theta = Math.random()*Math.PI*2, phi = Math.acos(2*Math.random()-1), s = 0.04+Math.random()*0.12;
      velocities[i*3+0] = Math.sin(phi)*Math.cos(theta)*s; velocities[i*3+1] = Math.sin(phi)*Math.sin(theta)*s; velocities[i*3+2] = Math.cos(phi)*s*0.7;
    }
    const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const m = new THREE.PointsMaterial({ color, size: 0.07, map: glowTexture(), transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false });
    const points = new THREE.Points(g, m); this.scene.add(points); this.bursts.push({ points, velocities, life: 1.4, age: 0 });
  }
  spawnRing(worldPos, color = COLOR.ORANGE, lookAtCam = null) {
    const g = new THREE.TorusGeometry(0.18, 0.014, 10, 64), m = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1, blending: THREE.AdditiveBlending, depthWrite: false });
    const ring = new THREE.Mesh(g, m); ring.position.copy(worldPos); if (lookAtCam) ring.lookAt(lookAtCam);
    this.scene.add(ring); this.rings.push({ ring, age: 0, life: 1.4, growth: 4.5 });
  }
  update(dt) {
    for (let i = this.bursts.length-1; i >= 0; i--) {
      const b = this.bursts[i]; b.age += dt;
      const p = b.points.geometry.attributes.position.array;
      for (let j = 0; j < p.length; j++) { p[j] += b.velocities[j]; b.velocities[j] *= 0.96; }
      b.points.geometry.attributes.position.needsUpdate = true;
      b.points.material.opacity = clamp(1 - b.age/b.life, 0, 1);
      if (b.age >= b.life) { this.scene.remove(b.points); b.points.geometry.dispose(); b.points.material.dispose(); this.bursts.splice(i, 1); }
    }
    for (let i = this.rings.length-1; i >= 0; i--) {
      const r = this.rings[i]; r.age += dt; const t = r.age/r.life;
      r.ring.scale.setScalar(1 + r.growth * t); r.ring.material.opacity = clamp(1-t, 0, 1);
      if (t >= 1) { this.scene.remove(r.ring); r.ring.geometry.dispose(); r.ring.material.dispose(); this.rings.splice(i, 1); }
    }
    for (const c of this.comets) {
      c.life -= dt*60; c.pos.add(c.vel); c.history.unshift(c.pos.clone()); if (c.history.length > c.TRAIL) c.history.length = c.TRAIL;
      const arr = c.line.geometry.attributes.position.array;
      for (let i = 0; i < c.TRAIL; i++) { const h = c.history[i] || c.pos; arr[i*3+0]=h.x; arr[i*3+1]=h.y; arr[i*3+2]=h.z; }
      c.line.geometry.attributes.position.needsUpdate = true;
      if (c.life <= 0 || Math.abs(c.pos.x) > 12 || Math.abs(c.pos.y) > 8) { c.pos.set((Math.random()-0.5)*10, (Math.random()-0.5)*6, -Math.random()*8-2); c.vel.set((Math.random()-0.5)*0.06, (Math.random()-0.5)*0.03, 0); c.life = 100+Math.random()*200; c.history.length = 0; }
    }
    this.dust.rotation.y += 0.0004;
  }
}

/* ── BallGame ────────────────────────────────────────────── */
class BallGame {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.active = false;
    this.ball = { x: 0, y: 0, vx: 0, vy: 0, r: 22, trail: [] };
    this.paddle = { x: -999, y: -999, r: 65, prevX: -999, prevY: -999 };
    // Points & combo
    this.points = 0;
    this.combo = 0;
    this.comboTimer = 0;
    this.rebounds = 0;
    this.bestPoints  = parseInt(localStorage.getItem('holo_best_pts')  || '0', 10);
    this.bestRebounds = parseInt(localStorage.getItem('holo_best_reb') || '0', 10);
    this.newRecord = false;
    this.newRecordTimer = 0;
    this.floatTexts = [];
    this.gravity = 900;
    this.bounceFlash = 0;
    this._resizeH = () => this._resize();
    window.addEventListener('resize', this._resizeH);
    this._resize();
  }

  _resize() { this.w = this.canvas.width = window.innerWidth; this.h = this.canvas.height = window.innerHeight; }

  _multiplier() {
    if (this.combo >= 20) return 5;
    if (this.combo >= 10) return 4;
    if (this.combo >= 6)  return 3;
    if (this.combo >= 3)  return 2;
    return 1;
  }

  start() {
    this.active = true;
    this.points = 0; this.combo = 0; this.comboTimer = 0; this.rebounds = 0;
    this.newRecord = false; this.floatTexts = [];
    this._resetBall();
  }

  stop() { this.active = false; this.ctx.clearRect(0, 0, this.w, this.h); }

  _resetBall() {
    this.ball.x = this.w / 2 + (Math.random() - 0.5) * 100;
    this.ball.y = this.h * 0.25;
    this.ball.vx = (Math.random() - 0.5) * 250;
    this.ball.vy = 50;
    this.ball.trail = [];
  }

  _onBallLost() {
    // Sauvegarde rebounds si battu
    if (this.rebounds > this.bestRebounds) {
      this.bestRebounds = this.rebounds;
      localStorage.setItem('holo_best_reb', this.bestRebounds);
    }
    // Annonce JARVIS une seule fois si nouveau record de points ce tour
    if (this.newRecord) {
      window.dispatchEvent(new CustomEvent('holo-record', { detail: { points: this.bestPoints, rebounds: this.bestRebounds } }));
    }
    // Reset session
    this.points = 0; this.combo = 0; this.comboTimer = 0; this.rebounds = 0;
    this.newRecord = false; this.floatTexts = [];
    this._resetBall();
  }

  update(dt, handPixelPos) {
    if (!this.active) return;

    this.paddle.prevX = this.paddle.x; this.paddle.prevY = this.paddle.y;
    if (handPixelPos) { this.paddle.x = handPixelPos.x; this.paddle.y = handPixelPos.y; }
    else { this.paddle.x = -999; this.paddle.y = -999; }

    // Combo timeout — si pas de frappe depuis 2s, le combo tombe
    if (this.combo > 0) {
      this.comboTimer -= dt;
      if (this.comboTimer <= 0) { this.combo = 0; }
    }

    this.ball.vy += this.gravity * dt;
    this.ball.x += this.ball.vx * dt;
    this.ball.y += this.ball.vy * dt;
    if (this.bounceFlash > 0) this.bounceFlash -= dt * 3;
    if (this.newRecordTimer > 0) this.newRecordTimer -= dt;

    this.ball.trail.push({ x: this.ball.x, y: this.ball.y });
    if (this.ball.trail.length > 12) this.ball.trail.shift();

    if (this.ball.x - this.ball.r < 0) { this.ball.x = this.ball.r; this.ball.vx = Math.abs(this.ball.vx) * 0.85; }
    if (this.ball.x + this.ball.r > this.w) { this.ball.x = this.w - this.ball.r; this.ball.vx = -Math.abs(this.ball.vx) * 0.85; }

    if (handPixelPos && this.paddle.x > 0) {
      const dx = this.ball.x - this.paddle.x, dy = this.ball.y - this.paddle.y;
      const dist = Math.hypot(dx, dy), combined = this.ball.r + this.paddle.r;
      if (dist < combined && this.ball.vy > -100) {
        const handVy = this.paddle.prevY > 0 ? (this.paddle.y - this.paddle.prevY) / Math.max(dt, 0.001) : 0;
        const handVx = this.paddle.prevX > 0 ? (this.paddle.x - this.paddle.prevX) / Math.max(dt, 0.001) : 0;
        this.ball.vy = Math.min(-350, this.ball.vy * -0.75 + clamp(handVy * -0.6, -500, -100));
        this.ball.vx = this.ball.vx * 0.8 + clamp(handVx * 0.35, -300, 300);
        if (dist > 0) { const push = (combined - dist) + 2; this.ball.x += (dx / dist) * push; this.ball.y += (dy / dist) * push; }

        // --- Calcul des points ---
        this.combo++;
        this.comboTimer = 2.2;
        this.rebounds++;
        const handSpeed = Math.hypot(handVx, handVy);
        const speedBonus = Math.round(clamp(handSpeed / 55, 0, 20));
        const mult = this._multiplier();
        const earned = (10 + speedBonus) * mult;
        this.points += earned;
        this.bounceFlash = 1.0;

        // Texte flottant "+30 x3"
        const label = speedBonus > 0 ? `+${earned}${mult > 1 ? ' ×'+mult : ''}` : `+${earned}${mult > 1 ? ' ×'+mult : ''}`;
        this.floatTexts.push({ text: label, x: this.ball.x, y: this.ball.y - 30, age: 0, life: 1.1, color: mult >= 3 ? '#ff8a1a' : mult === 2 ? '#ffb454' : '#00e5ff' });

        // Nouveau record en cours — juste visuellement, l'annonce JARVIS se fait à la fin
        if (this.points > this.bestPoints) {
          this.bestPoints = this.points;
          localStorage.setItem('holo_best_pts', this.bestPoints);
          this.newRecord = true; this.newRecordTimer = 2.5;
        }
      }
    }

    // Mise à jour textes flottants
    for (let i = this.floatTexts.length - 1; i >= 0; i--) {
      this.floatTexts[i].age += dt;
      this.floatTexts[i].y -= 55 * dt;
      if (this.floatTexts[i].age >= this.floatTexts[i].life) this.floatTexts.splice(i, 1);
    }

    if (this.ball.y > this.h + 80) this._onBallLost();

    this._draw(handPixelPos);
  }

  _draw(handPixelPos) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);
    if (!this.active) return;

    // Paddle
    if (handPixelPos && this.paddle.x > 0) {
      const flash = Math.max(0, this.bounceFlash);
      const mult = this._multiplier();
      const padColor = mult >= 3 ? '#ff8a1a' : mult === 2 ? '#ffb454' : '#00e5ff';
      ctx.beginPath();
      ctx.arc(this.paddle.x, this.paddle.y, this.paddle.r, 0, Math.PI * 2);
      ctx.strokeStyle = flash > 0.1 ? `rgba(255,138,26,${0.55 + flash * 0.4})` : padColor + '60';
      ctx.lineWidth = flash > 0.1 ? 3 : 1.5;
      ctx.setLineDash([6, 4]);
      ctx.shadowColor = flash > 0.1 ? '#ff8a1a' : padColor;
      ctx.shadowBlur = 10 + flash * 20;
      ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = flash > 0.1 ? 'rgba(255,138,26,0.07)' : 'rgba(0,229,255,0.04)';
      ctx.fill(); ctx.shadowBlur = 0;
    }

    // Traînée balle
    for (let i = 0; i < this.ball.trail.length; i++) {
      const t = this.ball.trail[i], a = (i / this.ball.trail.length) * 0.35, r = this.ball.r * (i / this.ball.trail.length) * 0.7;
      ctx.beginPath(); ctx.arc(t.x, t.y, r, 0, Math.PI * 2); ctx.fillStyle = `rgba(0,229,255,${a})`; ctx.fill();
    }

    // Balle
    const ballColor = this.bounceFlash > 0.1 ? '#ff8a1a' : '#00e5ff';
    ctx.shadowColor = ballColor; ctx.shadowBlur = 18 + this.bounceFlash * 20;
    ctx.beginPath(); ctx.arc(this.ball.x, this.ball.y, this.ball.r, 0, Math.PI * 2);
    ctx.fillStyle = ballColor; ctx.fill(); ctx.shadowBlur = 0;
    ctx.beginPath(); ctx.arc(this.ball.x - this.ball.r * 0.3, this.ball.y - this.ball.r * 0.3, this.ball.r * 0.35, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255,255,255,0.45)'; ctx.fill();

    // Textes flottants "+30 ×3"
    for (const ft of this.floatTexts) {
      const a = 1 - ft.age / ft.life;
      ctx.globalAlpha = a;
      ctx.font = 'bold 18px Courier New';
      ctx.fillStyle = ft.color;
      ctx.textAlign = 'center';
      ctx.shadowColor = ft.color; ctx.shadowBlur = 10;
      ctx.fillText(ft.text, ft.x, ft.y);
      ctx.shadowBlur = 0;
    }
    ctx.globalAlpha = 1;

    // HUD score principal
    ctx.textAlign = 'center';
    ctx.shadowColor = '#00e5ff'; ctx.shadowBlur = 20;
    ctx.fillStyle = '#00e5ff'; ctx.font = 'bold 62px Courier New';
    ctx.fillText(this.points, this.w / 2, 72);
    ctx.shadowBlur = 0;

    ctx.font = '10px Courier New'; ctx.fillStyle = 'rgba(0,229,255,0.5)';
    ctx.fillText('POINTS', this.w / 2, 92);

    // Record à battre
    if (this.bestPoints > 0 && !this.newRecord) {
      ctx.fillStyle = 'rgba(0,229,255,0.3)';
      ctx.fillText(`RECORD À BATTRE · ${this.bestPoints} PTS`, this.w / 2, 110);
    }

    // Badge combo
    const mult = this._multiplier();
    if (mult > 1) {
      const comboColor = mult >= 4 ? '#ff2e4d' : mult === 3 ? '#ff8a1a' : '#ffb454';
      ctx.font = 'bold 20px Courier New';
      ctx.fillStyle = comboColor;
      ctx.shadowColor = comboColor; ctx.shadowBlur = 14;
      ctx.fillText(`⚡ ×${mult} COMBO`, this.w / 2, this.h - 110);
      ctx.font = '10px Courier New';
      ctx.fillStyle = comboColor + '99';
      ctx.fillText(`${this.combo} FRAPPES CONSÉCUTIVES`, this.w / 2, this.h - 92);
      ctx.shadowBlur = 0;
    }

    // NOUVEAU RECORD flash
    if (this.newRecordTimer > 0) {
      const a = Math.min(1, this.newRecordTimer / 0.5);
      ctx.globalAlpha = a;
      ctx.font = 'bold 32px Courier New';
      ctx.fillStyle = '#ffb454';
      ctx.shadowColor = '#ff8a1a'; ctx.shadowBlur = 30;
      ctx.fillText('★ NOUVEAU RECORD ★', this.w / 2, this.h / 2);
      ctx.font = '13px Courier New';
      ctx.fillStyle = '#ff8a1a';
      ctx.fillText(`${this.bestPoints} POINTS`, this.w / 2, this.h / 2 + 30);
      ctx.shadowBlur = 0; ctx.globalAlpha = 1;
    }

    ctx.textAlign = 'left';
  }

  dispose() { window.removeEventListener('resize', this._resizeH); this.stop(); }
}

/* ── HologramRenderer ────────────────────────────────────── */
class HologramRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);
    this.camera.position.set(0, 0, 5);
    this.renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, powerPreference: 'high-performance', failIfMajorPerformanceCaveat: false });
    this.renderer.setPixelRatio(1.0);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setClearColor(0x000000, 0);
    this.composer = new EffectComposer(this.renderer);
    this.composer.setSize(window.innerWidth, window.innerHeight);
    this.renderPass = new RenderPass(this.scene, this.camera);
    this.renderPass.clear = true; this.renderPass.clearAlpha = 0;
    this.composer.addPass(this.renderPass);
    const bW = Math.round(window.innerWidth / 2), bH = Math.round(window.innerHeight / 2);
    this.bloomPass = new UnrealBloomPass(new THREE.Vector2(bW, bH), 0.22, 0.4, 0.30);
    this.composer.addPass(this.bloomPass);
    const chromaShader = {
      uniforms: { tDiffuse: { value: null }, offset: { value: 0.0025 }, time: { value: 0 } },
      vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      fragmentShader: `uniform sampler2D tDiffuse; uniform float offset; uniform float time; varying vec2 vUv; void main() { vec2 dir = vUv - 0.5; float ofs = offset * (0.6 + length(dir) * 1.4); float r = texture2D(tDiffuse, vUv + dir * ofs).r; float g = texture2D(tDiffuse, vUv).g; float b = texture2D(tDiffuse, vUv - dir * ofs).b; float a = texture2D(tDiffuse, vUv).a; float scan = 0.95 + 0.05 * sin((vUv.y * 1000.0) + time * 10.0); gl_FragColor = vec4(r,g,b,a) * scan; }`,
    };
    this.chromaPass = new ShaderPass(chromaShader);
    this.composer.addPass(this.chromaPass);
    this.composer.addPass(new OutputPass());
    const gl = this.renderer.getContext();
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    this.gpuName = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : 'Unknown GPU';
    this._addLights(); this._addPointers();
    this._resizeHandler = () => this._onResize();
    window.addEventListener('resize', this._resizeHandler);
  }
  _addPointers() {
    this.pointers = [];
    for (let i = 0; i < 2; i++) {
      const g = new THREE.SphereGeometry(0.06, 8, 8), m = new THREE.MeshBasicMaterial({ color: i===0 ? 0x00ffff : 0xffaa00, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending });
      const mesh = new THREE.Mesh(g, m); mesh.visible = false; this.scene.add(mesh); this.pointers.push(mesh);
    }
  }
  _addLights() {
    this.scene.add(new THREE.AmbientLight(0x223344, 0.2));
    const l1 = new THREE.PointLight(COLOR.CYAN, 0.4, 25); l1.position.set(2, 3, 4); this.scene.add(l1);
    const l2 = new THREE.PointLight(COLOR.ORANGE, 0.3, 25); l2.position.set(-3, -2, 3); this.scene.add(l2);
    const l3 = new THREE.PointLight(COLOR.RED, 0.2, 20); l3.position.set(0, 4, -2); this.scene.add(l3);
  }
  _onResize() {
    const W = window.innerWidth, H = window.innerHeight;
    this.camera.aspect = W/H; this.camera.updateProjectionMatrix();
    this.renderer.setSize(W, H); this.composer.setSize(W, H);
    this.bloomPass.resolution.set(Math.round(W/2), Math.round(H/2));
  }
  ndcToWorld(ndcX, ndcY, planeZ = 0) {
    const v = new THREE.Vector3(ndcX, ndcY, 0.5); v.unproject(this.camera);
    const dir = v.sub(this.camera.position).normalize(), t = (planeZ - this.camera.position.z) / dir.z;
    return this.camera.position.clone().add(dir.multiplyScalar(t));
  }
  render(dt) { this.chromaPass.uniforms.time.value += dt; this.composer.render(); }
  dispose() { window.removeEventListener('resize', this._resizeHandler); this.renderer.dispose(); }
}

/* ── Starfield ───────────────────────────────────────────── */
class Starfield {
  constructor(canvas) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.stars = []; this.resize();
    for (let i = 0; i < 100; i++) this.stars.push({ x: Math.random()*this.w, y: Math.random()*this.h, s: Math.random()*1.4+0.2, a: Math.random()*0.6+0.35, phase: Math.random()*Math.PI*2, speed: Math.random()*0.6+0.2, vx: -(Math.random()*0.04+0.005) });
    this._resizeH = () => this.resize();
    window.addEventListener('resize', this._resizeH);
  }
  resize() { this.w = this.canvas.width = window.innerWidth; this.h = this.canvas.height = window.innerHeight; }
  update(t) {
    const ctx = this.ctx; ctx.clearRect(0, 0, this.w, this.h);
    for (const s of this.stars) {
      const a = s.a * (0.55 + 0.45 * Math.sin(t * s.speed + s.phase));
      ctx.fillStyle = `rgba(180,240,255,${a.toFixed(3)})`; ctx.beginPath(); ctx.arc(s.x, s.y, s.s, 0, Math.PI*2); ctx.fill();
      s.x += s.vx; if (s.x < -2) s.x = this.w + 2;
    }
  }
  dispose() { window.removeEventListener('resize', this._resizeH); }
}

/* ── HandOverlay ─────────────────────────────────────────── */
class HandOverlay {
  constructor(canvas) {
    this.canvas = canvas; this.ctx = canvas.getContext('2d'); this.resize();
    this._resizeH = () => this.resize();
    window.addEventListener('resize', this._resizeH);
  }
  resize() { this.w = this.canvas.width = window.innerWidth; this.h = this.canvas.height = window.innerHeight; }
  draw(results, mirror = true) {
    const ctx = this.ctx; ctx.clearRect(0, 0, this.w, this.h);
    if (!results || !results.multiHandLandmarks) return;
    const xp = (lm) => mirror ? (1 - lm.x) * this.w : lm.x * this.w;
    for (let hi = 0; hi < results.multiHandLandmarks.length; hi++) {
      const hand = results.multiHandLandmarks[hi];
      const pinched = GestureSystem.isPinched(hand), openHand = GestureSystem.isOpenHand(hand), fist = GestureSystem.isFist(hand);
      let color = '#00e5ff'; if (pinched) color = '#ff8a1a'; if (openHand) color = '#6ff8ff'; if (fist) color = '#ff2e4d';
      ctx.lineWidth = 1.6; ctx.strokeStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 14;
      for (const [a, b] of HAND_CONNECTIONS) {
        const pa = hand[a], pb = hand[b];
        ctx.beginPath(); ctx.moveTo(xp(pa), pa.y*this.h); ctx.lineTo(xp(pb), pb.y*this.h); ctx.stroke();
      }
      ctx.fillStyle = color; ctx.shadowBlur = 10;
      for (let i = 0; i < hand.length; i++) {
        const p = hand[i]; let r = 3.5;
        if (i === 4 || i === 8) r = pinched ? 7 : 5; if (i === 0) r = 5;
        ctx.beginPath(); ctx.arc(xp(p), p.y*this.h, r, 0, Math.PI*2); ctx.fill();
      }
      const t = hand[4], idx = hand[8];
      ctx.strokeStyle = pinched ? '#ffb454' : '#00e5ff'; ctx.shadowColor = ctx.strokeStyle; ctx.lineWidth = pinched ? 3 : 1.2; ctx.setLineDash(pinched ? [] : [4,4]);
      ctx.beginPath(); ctx.moveTo(xp(t), t.y*this.h); ctx.lineTo(xp(idx), idx.y*this.h); ctx.stroke(); ctx.setLineDash([]);
      if (pinched) {
        const cx = (xp(t) + xp(idx)) * 0.5, cy = (t.y + idx.y) * 0.5 * this.h;
        ctx.strokeStyle = '#ffb454'; ctx.shadowBlur = 24; ctx.lineWidth = 1.3;
        ctx.beginPath(); ctx.arc(cx, cy, 22+Math.sin(performance.now()*0.012)*4, 0, Math.PI*2); ctx.stroke();
        ctx.beginPath(); ctx.arc(cx, cy, 34+Math.sin(performance.now()*0.012+1)*4, 0, Math.PI*2); ctx.stroke();
      }
    }
    ctx.shadowBlur = 0;
  }
  dispose() { window.removeEventListener('resize', this._resizeH); }
}

/* ── UIManager (scopé au container) ─────────────────────── */
class UIManager {
  constructor(app, container) {
    this.app = app;
    this.container = container;
    this.toast = container.querySelector('#holo-gesture-toast');
    this._lastToast = null;
    this._toastTimer = 0;
    this._bindDock();
    const d = new Date();
    const dateEl = container.querySelector('#holo-hud-date');
    if (dateEl) dateEl.textContent = d.toISOString().slice(0, 16).replace('T', ' ');
  }

  _bindDock() {
    this.container.querySelectorAll('.holo-dock-btn[data-shape]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.shape;
        this.app.spawnShape(type);
        this.container.querySelectorAll('.holo-dock-btn[data-shape]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        setTimeout(() => btn.classList.remove('active'), 600);
      });
    });
    this.container.querySelector('#holo-btn-game')?.addEventListener('click', () => {
      this.app.toggleGame();
      const btn = this.container.querySelector('#holo-btn-game');
      if (btn) btn.classList.toggle('active', this.app.ballGame.active);
    });
    this.container.querySelector('#holo-btn-clear')?.addEventListener('click', () => this.app.clearShapes());
    this.container.querySelector('#holo-btn-mirror')?.addEventListener('click', () => {
      this.app.toggleMirror();
      const btn = this.container.querySelector('#holo-btn-mirror');
      if (btn) btn.classList.toggle('active', this.app._mirror);
    });
    this.container.querySelector('#holo-btn-fullscreen')?.addEventListener('click', () => {
      if (document.fullscreenElement) document.exitFullscreen();
      else document.documentElement.requestFullscreen?.();
    });
  }

  showGesture(name) {
    if (!name || name === this._lastToast) return;
    this._lastToast = name;
    if (this.toast) { this.toast.textContent = name; this.toast.classList.add('visible'); }
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { this.toast?.classList.remove('visible'); this._lastToast = null; }, 850);
  }

  updateHUD(state) {
    const q = (id) => this.container.querySelector('#' + id);
    const setTxt = (id, val) => { const el = q(id); if (el) el.textContent = val; };
    setTxt('holo-hud-fps', state.fps.toFixed(0));
    setTxt('holo-hud-hands', state.hands);
    setTxt('holo-hud-shapes', state.shapes);
    setTxt('holo-hud-gesture', state.gesture);
    const gpuEl = q('holo-hud-gpu') || this._createGpuLine();
    if (gpuEl && state.gpu) {
      const gpuName = state.gpu.replace('ANGLE (', '').replace(', Direct3D11 vs_5_0 ps_5_0)', '').split('/')[0];
      gpuEl.textContent = gpuName;
      gpuEl.style.color = gpuName.toLowerCase().includes('intel') ? '#ff2e4d' : '#ff8a1a';
    }
    const setW = (id, val) => { const el = q(id); if (el) el.style.width = val + '%'; };
    setW('holo-bar-energy', state.energy);
    setW('holo-bar-flux', state.flux);
    setW('holo-bar-link', state.link);
  }

  _createGpuLine() {
    const parent = this.container.querySelector('.holo-hud-tl .holo-hud-block');
    if (!parent) return null;
    const div = document.createElement('div');
    div.className = 'holo-hud-line holo-muted';
    div.style.fontSize = '8px';
    div.innerHTML = '<span class="holo-key">GPU</span><span id="holo-hud-gpu">...</span>';
    parent.appendChild(div);
    return this.container.querySelector('#holo-hud-gpu');
  }
}

/* ── App (orchestration scopée) ─────────────────────────── */
class App {
  constructor(container) {
    this.container = container;
    const q = (id) => container.querySelector('#' + id);

    this.video       = q('holo-webcam');
    this.threeCanvas = q('holo-three-canvas');
    this.handCanvas  = q('holo-hand-canvas');
    this.starCanvas  = q('holo-starfield');
    this.gameCanvas  = q('holo-game-canvas');

    this._running = true;
    this._raf = null;
    this._mirror = true;

    this.starfield   = new Starfield(this.starCanvas);
    this.handOverlay = new HandOverlay(this.handCanvas);
    this.renderer    = new HologramRenderer(this.threeCanvas);
    this.shapes      = new ShapeManager(this.renderer.scene);
    this.particles   = new ParticleEngine(this.renderer.scene);
    this.ballGame    = new BallGame(this.gameCanvas);
    this.ui          = new UIManager(this, container);
    this.gestures    = new GestureSystem();

    this.tracker = null;
    this._lastT = performance.now(); this._fps = 60; this._fpsAcc = 0; this._fpsCount = 0; this._handCount = 0;
    this.handPos3D = [null, null]; this.handGrab = [null, null];
    this.openFlag = [false, false]; this.fistFlag = [false, false];
    this.lastTwoDist = null; this.lastTwoAngle = null; this.lastTwoShape = null;
    this.gestureLabel = 'BOOT'; this.lastResults = null;

    setTimeout(() => { if (this._running && !this.shapes.shapes.length) this.shapes.add('sphere', new THREE.Vector3(0, 0, 0)); }, 250);

    this._loop = this._loop.bind(this);
    this._raf = requestAnimationFrame(this._loop);
  }

  destroy() {
    this._running = false;
    if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
    if (this.video && this.video.srcObject) {
      this.video.srcObject.getTracks().forEach(t => t.stop());
      this.video.srcObject = null;
    }
    this.shapes.clear();
    this.ballGame.dispose();
    this.starfield.dispose();
    this.handOverlay.dispose();
    this.renderer.dispose();
  }

  async start() {
    this.ui.updateHUD({ fps: 0, hands: 0, shapes: this.shapes.shapes.length, gesture: 'BOOT', energy: 70, flux: 50, link: 20, gpu: this.renderer.gpuName });
    try {
      if (typeof Hands === 'undefined') throw new Error('MediaPipe non chargé');
      this.tracker = new HandTracker(this.video, this);
      this.tracker.onResults = (r) => { this.lastResults = r; };
      this.tracker.start().catch(err => this._showCameraError(err.message));
      this.gestureLabel = 'INITIALIZING';
    } catch (err) {
      this._showCameraError(err.message);
    }
  }

  _showCameraError(msg) {
    this.gestureLabel = 'NO CAM';
    setTimeout(() => {
      if (!this.toast) return;
      const toast = this.container.querySelector('#holo-gesture-toast');
      if (!toast) return;
      toast.textContent = '⚠ CAM: ' + (msg ? msg.slice(0, 40) : 'accès refusé');
      toast.classList.add('visible');
      toast.style.color = '#ff2e4d'; toast.style.borderColor = '#ff2e4d';
      setTimeout(() => { toast.classList.remove('visible'); toast.style.color = ''; toast.style.borderColor = ''; }, 4000);
    }, 500);
  }

  spawnShape(type)  { this.shapes.add(type); this.ui.showGesture('+ ' + type.toUpperCase()); }
  clearShapes()     { this.shapes.clear(); this.ui.showGesture('CLEAR'); }
  toggleMirror()    { this._mirror = !this._mirror; this.ui.showGesture(this._mirror ? '⇄ MIRROR ON' : '⇄ MIRROR OFF'); }
  toggleGame() {
    if (this.ballGame.active) {
      this.ballGame.stop();
      this.threeCanvas.style.display = 'block';
      this.ui.showGesture('GAME OFF');
    } else {
      this.ballGame.start();
      this.threeCanvas.style.display = 'none';
      this.ui.showGesture('GAME ON !');
    }
  }

  _getHandPixelPos() {
    const results = this.lastResults;
    if (!results || !results.multiHandLandmarks || !results.multiHandLandmarks.length) return null;
    const lm = results.multiHandLandmarks[0][9]; // centre de la paume
    return {
      x: this._mirror ? (1 - lm.x) * window.innerWidth : lm.x * window.innerWidth,
      y: lm.y * window.innerHeight,
    };
  }

  _processGestures(dt) {
    const results = this.lastResults, hands = (results && results.multiHandLandmarks) || [];
    this._handCount = hands.length;
    for (let i = 0; i < 2; i++) {
      const h = hands[i]; this.gestures.pushHistory(i, h);
      if (!h) { if (this.handGrab[i]) { if (this.handGrab[i].vertexIdx >= 0) this.handGrab[i].shape.releaseVertex(this.handGrab[i].vertexIdx); this.handGrab[i] = null; } this.handPos3D[i] = null; this.openFlag[i] = false; this.fistFlag[i] = false; continue; }
      const c = GestureSystem.pinchCenter(h), ndcX = this._mirror ? -(c.x*2-1) : (c.x*2-1), ndcY = -(c.y*2-1), planeZ = clamp(-c.z*1.5, -1.5, 1.5);
      this.handPos3D[i] = this.renderer.ndcToWorld(ndcX, ndcY, planeZ);
      const pinched = GestureSystem.isPinched(h);
      if (this.renderer.pointers[i]) { this.renderer.pointers[i].visible = true; this.renderer.pointers[i].position.copy(this.handPos3D[i]); this.renderer.pointers[i].scale.setScalar(pinched ? 0.6 : 1.0); }
      if (pinched) {
        if (!this.handGrab[i]) {
          const v = this.shapes.closestVertex(this.handPos3D[i], 0.6);
          if (v) { v.shape.grabVertex(v.vertexIdx, i); this.handGrab[i] = { shape: v.shape, vertexIdx: v.vertexIdx }; this.particles.explode(v.worldPos, COLOR.ORANGE, 18); }
          else { const sh = this.shapes.closestShape(this.handPos3D[i]); if (sh && sh.d < 2.5) { this.handGrab[i] = { shape: sh.shape, vertexIdx: -1 }; this.shapes.select(sh.shapeIdx); } }
        } else {
          const g = this.handGrab[i];
          if (g.vertexIdx >= 0) { const local = g.shape.group.worldToLocal(this.handPos3D[i].clone()); g.shape.setVertexLocal(g.vertexIdx, local); }
          else if (hands.length === 1) { g.shape.group.position.lerp(this.handPos3D[i], 0.3); }
        }
      } else { if (this.handGrab[i]) { if (this.handGrab[i].vertexIdx >= 0) this.handGrab[i].shape.releaseVertex(this.handGrab[i].vertexIdx); this.handGrab[i] = null; } }
    }
    if (hands.length >= 2 && this.handPos3D[0] && this.handPos3D[1]) {
      const pA = GestureSystem.pinchCenter(hands[0]), pB = GestureSystem.pinchCenter(hands[1]);
      const dx = pB.x-pA.x, dy = pB.y-pA.y, dist = Math.hypot(dx, dy), angle = Math.atan2(dy, dx);
      const bothPinched = GestureSystem.isPinched(hands[0]) && GestureSystem.isPinched(hands[1]);
      const canTransform = bothPinched && (!this.handGrab[0]||this.handGrab[0].vertexIdx<0) && (!this.handGrab[1]||this.handGrab[1].vertexIdx<0);
      if (canTransform) {
        const center = this.handPos3D[0].clone().add(this.handPos3D[1]).multiplyScalar(0.5);
        const sh = this.shapes.closestShape(center);
        if (sh) {
          const target = sh.shape; this.lastTwoShape = target; this.shapes.select(sh.shapeIdx); target.group.position.lerp(center, 0.18);
          if (this.lastTwoDist != null) { const ratio = dist/Math.max(this.lastTwoDist, 0.001); target.targetUserScale = clamp(target.targetUserScale*ratio, 0.2, 4.5); }
          if (this.lastTwoAngle != null) { target.group.rotation.z -= (angle - this.lastTwoAngle); }
        }
        this.lastTwoDist = dist; this.lastTwoAngle = angle; this.gestureLabel = '2-HANDS XFORM';
      } else { this.lastTwoDist = null; this.lastTwoAngle = null; }
    } else { this.lastTwoDist = null; this.lastTwoAngle = null; }

    let gestureMsg = null, anyFist = false;
    for (let i = 0; i < hands.length; i++) {
      const h = hands[i], wp = this.handPos3D[i], isOpen = GestureSystem.isOpenHand(h), isFist = GestureSystem.isFist(h), swipe = this.gestures.detectSwipe(i);
      if (isOpen && !this.openFlag[i]) { this.openFlag[i] = true; if (wp) { this.particles.explode(wp, COLOR.CYAN, 90); this.particles.spawnRing(wp, COLOR.ORANGE, this.renderer.camera.position); const sh = this.shapes.closestShape(wp); if (sh && sh.d < 2) sh.shape.explode(); } gestureMsg = 'EXPLODE'; }
      else if (!isOpen) { this.openFlag[i] = false; }
      if (isFist) { if (!this.fistFlag[i]) { this.fistFlag[i] = true; gestureMsg = 'COMPRESS'; if (wp) { const sh = this.shapes.closestShape(wp); if (sh && sh.d < 2) sh.shape.compress(0.55); } } anyFist = true; }
      else { if (this.fistFlag[i]) { if (wp) { const sh = this.shapes.closestShape(wp); if (sh && sh.d < 2) sh.shape.resetDeformation(); } } this.fistFlag[i] = false; }
      if (swipe) { this.shapes.cycle(swipe === 'right' ? 1 : -1); gestureMsg = swipe === 'right' ? 'SWIPE ▶' : '◀ SWIPE'; }
    }
    if (!anyFist) { for (const s of this.shapes.shapes) s.targetCompression = 1.0; }
    if (gestureMsg) { this.gestureLabel = gestureMsg; this.ui.showGesture(gestureMsg); }
    else if (this.lastTwoDist != null) { this.gestureLabel = '2-HANDS'; }
    else if (this.handGrab[0] || this.handGrab[1]) { this.gestureLabel = 'GRAB'; }
    else if (hands.length === 0) { this.gestureLabel = 'IDLE'; }
    else { this.gestureLabel = 'TRACKING'; }
  }

  _loop(now) {
    if (!this._running) return;
    const dt = Math.min((now - this._lastT) / 1000, 0.05);
    this._lastT = now;
    this._fpsAcc += dt; this._fpsCount++;
    if (this._fpsAcc >= 0.5) { this._fps = this._fpsCount / this._fpsAcc; this._fpsAcc = 0; this._fpsCount = 0; }
    this._processGestures(dt);
    this.shapes.update(dt);
    this.particles.update(dt, this.renderer.camera.position);
    this.starfield.update(now / 1000);
    this.handOverlay.draw(this.lastResults, this._mirror);
    if (this.ballGame.active) this.ballGame.update(dt, this._getHandPixelPos());
    if (!this.ballGame.active) this.renderer.render(dt);
    const energyVal = clamp(72 + Math.sin(now/600)*18, 0, 100), fluxVal = clamp(52 + Math.sin(now/320+1.7)*28, 0, 100), linkVal = this._handCount > 0 ? 95 : 28;
    this.ui.updateHUD({ fps: this._fps, hands: this._handCount, shapes: this.shapes.shapes.length, gesture: this.gestureLabel, energy: energyVal, flux: fluxVal, link: linkVal, gpu: this.renderer.gpuName });
    this._raf = requestAnimationFrame(this._loop);
  }
}

/* ── Exports ─────────────────────────────────────────────── */
let _holoApp = null;
let _keyHandler = null;

const SHAPE_KEYS = { '1':'sphere','2':'cube','3':'triangle','4':'pyramid','5':'tetra','6':'octa','7':'torus','8':'dna','9':'ring','0':'free' };

export function activerHolo() {
  if (_holoApp) return;
  const container = document.getElementById('holo-overlay');
  if (!container) return;
  _holoApp = new App(container);
  _keyHandler = (e) => {
    if (!_holoApp) return;
    if (SHAPE_KEYS[e.key]) { _holoApp.spawnShape(SHAPE_KEYS[e.key]); return; }
    switch (e.key) {
      case 'Delete': case 'Backspace': _holoApp.clearShapes(); break;
      case 'ArrowRight': _holoApp.shapes.cycle(1);  _holoApp.ui.showGesture('NEXT ▶'); break;
      case 'ArrowLeft':  _holoApp.shapes.cycle(-1); _holoApp.ui.showGesture('◀ PREV'); break;
      case 'r': case 'R': { const s = _holoApp.shapes.current(); if (s) { s.resetDeformation(); _holoApp.ui.showGesture('RESET'); } break; }
    }
  };
  window.addEventListener('keydown', _keyHandler);
  _holoApp.start();
}

export function desactiverHolo() {
  if (!_holoApp) return;
  _holoApp.destroy();
  _holoApp = null;
  if (_keyHandler) { window.removeEventListener('keydown', _keyHandler); _keyHandler = null; }
}
