import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

/**
 * JARVIS GLOBE 3D — Realistic Earth Implementation
 * Replaces the old 2D canvas logic with a high-fidelity Three.js globe.
 */

let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let renderer: THREE.WebGLRenderer;
let controls: OrbitControls;
let earth: THREE.Mesh;
let clouds: THREE.Mesh;
let atmosphere: THREE.Mesh;
let markersGroup: THREE.Group;
let routesGroup: THREE.Group;

let isInitialized = false;
let animationId: number | null = null;
const overlay = document.getElementById("globe-overlay") as HTMLDivElement;
const canvas = document.getElementById("globe-canvas") as HTMLCanvasElement;
const tLabel = document.getElementById("globe-target-label");
const cLabel = document.getElementById("globe-coords");
const orbCanvas = document.getElementById("orb-canvas") as HTMLCanvasElement;
let scanLine: THREE.Mesh;
let flightTarget: { lat: number, lon: number, distance: number } | null = null;

// Configuration
const EARTH_RADIUS = 100;
const TEXTURES = {
  day: "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg",
  night: "https://unpkg.com/three-globe/example/img/earth-night.jpg",
  bump: "https://unpkg.com/three-globe/example/img/earth-topology.png",
  clouds: "https://unpkg.com/three-globe/example/img/earth-clouds.png",
};

export function initJarvisGlobe() {
  if (isInitialized) return;

  // ── Scene Setup ─────────────────────────────────────────────────────────────
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  camera = new THREE.PerspectiveCamera(
    45,
    window.innerWidth / window.innerHeight,
    0.1,
    2000
  );
  camera.position.z = 400;

  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
  });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);

  // ── Lights ──────────────────────────────────────────────────────────────────
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambientLight);

  const sunLight = new THREE.DirectionalLight(0xffffff, 1.2);
  sunLight.position.set(5, 3, 5);
  scene.add(sunLight);

  // ── Stars ──────────────────────────────────────────────────────────────────
  const starGeo = new THREE.BufferGeometry();
  const starPos = new Float32Array(5000 * 3);
  for (let i = 0; i < 5000; i++) {
    starPos[i * 3] = (Math.random() - 0.5) * 2000;
    starPos[i * 3 + 1] = (Math.random() - 0.5) * 2000;
    starPos[i * 3 + 2] = (Math.random() - 0.5) * 2000;
  }
  starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
  const starMat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.7, transparent: true, opacity: 0.8 });
  const stars = new THREE.Points(starGeo, starMat);
  scene.add(stars);

  // ── Earth ───────────────────────────────────────────────────────────────────
  const loader = new THREE.TextureLoader();

  const earthGeo = new THREE.SphereGeometry(EARTH_RADIUS, 64, 64);
  const earthMat = new THREE.MeshStandardMaterial({
    map: loader.load(TEXTURES.day),
    bumpMap: loader.load(TEXTURES.bump),
    bumpScale: 2,
    metalness: 0.1,
    roughness: 0.8,
  });
  earth = new THREE.Mesh(earthGeo, earthMat);
  scene.add(earth);

  // Night lights (optional addition if we want cool blending, but let's keep it simple for now)
  // For a Jarvis look, night lights are actually cooler.
  // earthMat.emissiveMap = loader.load(TEXTURES.night);
  // earthMat.emissive = new THREE.Color(0xffff88);
  // earthMat.emissiveIntensity = 0.5;

  // ── Clouds ──────────────────────────────────────────────────────────────────
  const cloudGeo = new THREE.SphereGeometry(EARTH_RADIUS + 2, 64, 64);
  const cloudMat = new THREE.MeshStandardMaterial({
    map: loader.load(TEXTURES.clouds),
    transparent: true,
    opacity: 0.4,
    depthWrite: false,
  });
  clouds = new THREE.Mesh(cloudGeo, cloudMat);
  scene.add(clouds);

  // ── Atmosphere Glow ────────────────────────────────────────────────────────
  const atmosphereGeo = new THREE.SphereGeometry(EARTH_RADIUS * 1.15, 64, 64);
  const atmosphereMat = new THREE.ShaderMaterial({
    vertexShader: `
      varying vec3 vNormal;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vNormal;
      void main() {
        float intensity = pow(0.7 - dot(vNormal, vec3(0, 0, 1.0)), 3.0);
        gl_FragColor = vec4(0.0, 0.9, 1.0, 1.0) * intensity;
      }
    `,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true,
  });
  atmosphere = new THREE.Mesh(atmosphereGeo, atmosphereMat);
  scene.add(atmosphere);

  // ── Holographic Scan Line ──────────────────────────────────────────────────
  const scanGeo = new THREE.RingGeometry(EARTH_RADIUS * 1.02, EARTH_RADIUS * 1.03, 64);
  const scanMat = new THREE.MeshBasicMaterial({
    color: 0x00e5ff,
    transparent: true,
    opacity: 0.3,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending
  });
  scanLine = new THREE.Mesh(scanGeo, scanMat);
  scanLine.rotation.x = Math.PI / 2;
  scene.add(scanLine);

  // ── Interaction ─────────────────────────────────────────────────────────────
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.rotateSpeed = 0.5;
  controls.zoomSpeed = 0.5; // Slower zoom for more control
  controls.minDistance = 160; // Keep camera further away
  controls.maxDistance = 600;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.5;

  markersGroup = new THREE.Group();
  scene.add(markersGroup);

  routesGroup = new THREE.Group();
  scene.add(routesGroup);

  createStarfield();

  window.addEventListener("resize", onResize);

  isInitialized = true;
  animate();
}

let stars: THREE.Points;
let starRotationSpeed = 0.0001;

function createStarfield() {
  const vertices = [];
  for (let i = 0; i < 5000; i++) {
    const x = THREE.MathUtils.randFloatSpread(2000);
    const y = THREE.MathUtils.randFloatSpread(2000);
    const z = THREE.MathUtils.randFloatSpread(2000);
    vertices.push(x, y, z);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.7, transparent: true, opacity: 0.8 });
  stars = new THREE.Points(geo, mat);
  scene.add(stars);
}

let isTransitioning = false;

function checkZoomLevel() {
  if (isTransitioning) return;

  const distance = camera.position.distanceTo(controls.target);
  if (distance < 175 && overlay.style.display !== "none" && overlay.style.opacity === "1") {
    // Zoomed in enough to switch to map
    switchToDetailedMap();
  }
}

function switchToDetailedMap() {
  isTransitioning = true;
  // Get current Lat/Lon from center
  const vector = new THREE.Vector3(0, 0, -1);
  vector.applyQuaternion(camera.quaternion);

  // Calculate approximate lat/lon from view vector (simplified)
  // For better accuracy, we'd raycast to earth mesh
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(new THREE.Vector2(0, 0), camera);
  const intersects = raycaster.intersectObject(earth);

  if (intersects.length > 0) {
    const point = intersects[0].point;
    const lat = Math.asin(point.y / EARTH_RADIUS) * (180 / Math.PI);
    const lon = Math.atan2(point.z, -point.x) * (180 / Math.PI);

    // Dispatch event or call a function to show map
    (window as any).showDetailedMap(lat, lon);
  }
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

(window as any).resetGlobeTransition = () => {
  isTransitioning = false;
  // Push camera back further to see the whole earth
  if (camera) camera.position.setLength(350);
  if (controls) controls.update();
};

function animate() {
  animationId = requestAnimationFrame(animate);
  controls.update();

  // Rotate clouds slightly faster than earth
  if (clouds) clouds.rotation.y += 0.0002;

  // Rotate stars
  if (stars) stars.rotation.y += starRotationSpeed;

  // Update scan line position
  if (scanLine) {
    const time = Date.now() * 0.001;
    scanLine.position.y = Math.sin(time * 0.5) * (EARTH_RADIUS * 0.8);
    (scanLine.material as THREE.MeshBasicMaterial).opacity = 0.2 + Math.abs(Math.sin(time)) * 0.2;
  }

  // Smooth flight animation
  if (flightTarget) {
    const targetPos = latLonToVector3(flightTarget.lat, flightTarget.lon, flightTarget.distance);
    const lookAtPos = latLonToVector3(flightTarget.lat, flightTarget.lon, EARTH_RADIUS);

    camera.position.lerp(targetPos, 0.05);
    controls.target.lerp(lookAtPos, 0.05);

    // Stop flight when close enough
    if (camera.position.distanceTo(targetPos) < 1) {
      flightTarget = null;
    }
  }

  checkZoomLevel();

  renderer.render(scene, camera);
}

// ── API for J.A.R.V.I.S ──────────────────────────────────────────────────────

function latLonToVector3(lat: number, lon: number, radius: number) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const z = radius * Math.sin(phi) * Math.sin(theta);
  const y = radius * Math.cos(phi);
  return new THREE.Vector3(x, y, z);
}

function clearGroups() {
  while (markersGroup.children.length > 0) markersGroup.remove(markersGroup.children[0]);
  while (routesGroup.children.length > 0) routesGroup.remove(routesGroup.children[0]);
}

function addMarker(lat: number, lon: number, color: string = "#00e5ff") {
  const pos = latLonToVector3(lat, lon, EARTH_RADIUS);

  // Outer glow
  const ringGeo = new THREE.RingGeometry(2, 3, 32);
  const ringMat = new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: 0.6 });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.position.copy(pos);
  ring.lookAt(new THREE.Vector3(0, 0, 0));
  markersGroup.add(ring);

  // Inner dot
  const dotGeo = new THREE.SphereGeometry(1, 16, 16);
  const dotMat = new THREE.MeshBasicMaterial({ color });
  const dot = new THREE.Mesh(dotGeo, dotMat);
  dot.position.copy(pos);
  markersGroup.add(dot);
}

function show() {
  overlay.style.display = "flex";
  if (orbCanvas) orbCanvas.classList.add("minimized");

  // Masquer les brackets HUD pour l'intégration
  const brackets = document.querySelectorAll('.globe-bracket');
  brackets.forEach(b => (b as HTMLElement).style.opacity = '0');

  setTimeout(() => {
    overlay.style.transition = "opacity 0.8s ease";
    overlay.style.opacity = "1";
  }, 10);
  controls.autoRotate = true;
}

function hide() {
  overlay.style.transition = "opacity 0.5s ease";
  overlay.style.opacity = "0";
  if (orbCanvas) orbCanvas.classList.remove("minimized");

  // Réafficher les brackets HUD
  const brackets = document.querySelectorAll('.globe-bracket');
  brackets.forEach(b => (b as HTMLElement).style.opacity = '0.6');

  setTimeout(() => {
    overlay.style.display = "none";
  }, 520);
  clearGroups();
}

function flyTo(lat: number, lon: number, distance: number = 300) {
  controls.autoRotate = false;
  flightTarget = { lat, lon, distance };
}

// Expose to window for the backend
(window as any).jarvisGlobe = function (data: any) {
  initJarvisGlobe();

  const action = data.globe_action || "";
  switch (action) {
    case "show_earth":
      show();
      if (tLabel) tLabel.textContent = "GLOBE TERRESTRE";
      if (cLabel) cLabel.textContent = "";
      break;

    case "fly_to":
      show();
      const lt = data.lat || 0;
      const ln = data.lon || 0;
      clearGroups();
      addMarker(lt, ln);
      flyTo(lt, ln);

      // If we are already in map mode, update the map too!
      if (overlay.style.display !== "none" && overlay.style.opacity === "1") {
        if (typeof (window as any).showDetailedMap === "function") {
          (window as any).showDetailedMap(lt, ln);
        }
      }

      if (tLabel) tLabel.textContent = "⊕ " + (data.target || "").toUpperCase();
      if (cLabel) cLabel.textContent = `LAT ${lt.toFixed(4)}°  LON ${ln.toFixed(4)}°`;
      break;

    case "route":
      show();
      clearGroups();
      if (data.from_lat !== undefined) addMarker(data.from_lat, data.from_lon, "#00e5ff");
      if (data.to_lat !== undefined) addMarker(data.to_lat, data.to_lon, "#ff6b35");

      // Draw route curve
      if (data.from_lat !== undefined && data.to_lat !== undefined) {
        const start = latLonToVector3(data.from_lat, data.from_lon, EARTH_RADIUS);
        const end = latLonToVector3(data.to_lat, data.to_lon, EARTH_RADIUS);

        // Midpoint pushed out for curve
        const mid = start.clone().lerp(end, 0.5).normalize().multiplyScalar(EARTH_RADIUS * 1.5);
        const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
        const points = curve.getPoints(50);
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({ color: 0x00e5ff, transparent: true, opacity: 0.6 });
        const line = new THREE.Line(geometry, material);
        routesGroup.add(line);

        flyTo((data.from_lat + data.to_lat) / 2, (data.from_lon + data.to_lon) / 2);
      }

      if (tLabel) tLabel.textContent = `ROUTE : ${(data.from_name || "?").toUpperCase()} → ${(data.to_name || "?").toUpperCase()}`;
      break;

    case "my_location":
      show();
      if (data.lat) {
        clearGroups();
        addMarker(data.lat, data.lon, "#00ff88");
        flyTo(data.lat, data.lon);
        if (tLabel) tLabel.textContent = "📍 VOTRE POSITION";
        if (cLabel) cLabel.textContent = `LAT ${data.lat.toFixed(4)}°  LON ${data.lon.toFixed(4)}°`;
      } else if (navigator.geolocation) {
        if (tLabel) tLabel.textContent = "📍 LOCALISATION...";
        navigator.geolocation.getCurrentPosition((pos) => {
          const mLat = pos.coords.latitude;
          const mLon = pos.coords.longitude;
          clearGroups();
          addMarker(mLat, mLon, "#00ff88");
          flyTo(mLat, mLon);
          if (tLabel) tLabel.textContent = "📍 VOTRE POSITION";
          if (cLabel) cLabel.textContent = `LAT ${mLat.toFixed(4)}°  LON ${mLon.toFixed(4)}°`;
        }, () => {
          if (tLabel) tLabel.textContent = "⚠ LOCALISATION REFUSÉE";
        });
      }
      break;

    case "hide":
      hide();
      break;
  }
};
