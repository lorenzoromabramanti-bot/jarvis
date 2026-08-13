/**
 * Voice Assistant — Multi-mode particle visualization.
 *
 * States:
 *  idle      – slow drift, minimal connections
 *  listening – tighter cloud, moderate connections
 *  thinking  – dense connections, travelling electrons
 *  speaking  – VORTEX + SHOCKWAVE + BREATHING + color pulse + fast electrons
 *
 * Special:
 *  triggerDemo() – 10-second spectacular light show (Big Bang → Hypervortex →
 *                  Pulse Rings → Rainbow Collapse → settle)
 *
 * Ported & heavily enhanced from https://github.com/ethanplusai/jarvis
 */

import * as THREE from "three";

export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "searching";

export interface Orb {
  setState(s: OrbState): void;
  setVolume(v: number): void;
  setAnalyser(a: AnalyserNode | null): void;
  triggerDemo(): void;
  setQuality(q: "low" | "high"): void;
  destroy(): void;
  setNemotronActive(active: boolean): void;
  showWord(word: string, durationMs: number): void;
  setTheme(theme: string): void;
  setDeformation?(scaleX: number, scaleY: number, rotationZ: number): void;
}

export function createOrb(canvas: HTMLCanvasElement): Orb {
  let destroyed = false;
  const N = 2000;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(
    45,
    window.innerWidth / window.innerHeight,
    1,
    1000
  );
  camera.position.z = 115;



  // ── Particles ──────────────────────────────────────────────────────────────
  const geo = new THREE.BufferGeometry();
  const pos = new Float32Array(N * 3);
  const vel = new Float32Array(N * 3);
  const phase = new Float32Array(N);

  for (let i = 0; i < N; i++) {
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    const r = Math.pow(Math.random(), 0.5) * 25;
    pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
    pos[i * 3 + 2] = r * Math.cos(phi);
    phase[i] = Math.random() * 1000;
  }

  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));

  const mat = new THREE.PointsMaterial({
    color: 0x4ca8e8,
    size: 0.4,
    transparent: true,
    opacity: 0.6,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const points = new THREE.Points(geo, mat);
  scene.add(points);

  // ── Connection lines ────────────────────────────────────────────────────────
  const MAX_LINES = 8000;
  const linePos = new Float32Array(MAX_LINES * 6);
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute("position", new THREE.BufferAttribute(linePos, 3));
  lineGeo.setDrawRange(0, 0);

  const lineMat = new THREE.LineBasicMaterial({
    color: 0x4ca8e8,
    transparent: true,
    opacity: 0.0,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const lines = new THREE.LineSegments(lineGeo, lineMat);
  scene.add(lines);

  // ── Electrons ──────────────────────────────────────────────────────────────
  const MAX_ELECTRONS = 200;
  const electronGeo = new THREE.BufferGeometry();
  const electronPos = new Float32Array(MAX_ELECTRONS * 3);
  electronGeo.setAttribute(
    "position",
    new THREE.BufferAttribute(electronPos, 3)
  );
  electronGeo.setDrawRange(0, 0);

  const electronMat = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 0.8,
    transparent: true,
    opacity: 1.0,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  const electronPoints = new THREE.Points(electronGeo, electronMat);
  scene.add(electronPoints);

  // ── Rings Shader (ORB Anneaux) ──────────────────────────────────────────────
  const ringsGeo = new THREE.PlaneGeometry(2, 2);
  const ringsUniforms = {
    iTime: { value: 0 },
    iResolution: { value: new THREE.Vector3(window.innerWidth, window.innerHeight, window.innerWidth / window.innerHeight) },
    hue: { value: 0 },
    hover: { value: 0 },
    rot: { value: 0 },
    hoverIntensity: { value: 0.2 },
    backgroundColor: { value: new THREE.Vector3(0, 0, 0) },
    audioIntensity: { value: 0 }
  };

  const ringsVert = `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = vec4(position.xyz, 1.0);
    }
  `;

  const ringsFrag = `
    precision highp float;

    uniform float iTime;
    uniform vec3 iResolution;
    uniform float hue;
    uniform float hover;
    uniform float rot;
    uniform float hoverIntensity;
    uniform vec3 backgroundColor;
    uniform float audioIntensity;
    varying vec2 vUv;

    vec3 rgb2yiq(vec3 c) {
      float y = dot(c, vec3(0.299, 0.587, 0.114));
      float i = dot(c, vec3(0.596, -0.274, -0.322));
      float q = dot(c, vec3(0.211, -0.523, 0.312));
      return vec3(y, i, q);
    }
    
    vec3 yiq2rgb(vec3 c) {
      float r = c.x + 0.956 * c.y + 0.621 * c.z;
      float g = c.x - 0.272 * c.y - 0.647 * c.z;
      float b = c.x - 1.106 * c.y + 1.703 * c.z;
      return vec3(r, g, b);
    }
    
    vec3 adjustHue(vec3 color, float hueDeg) {
      float hueRad = hueDeg * 3.14159265 / 180.0;
      vec3 yiq = rgb2yiq(color);
      float cosA = cos(hueRad);
      float sinA = sin(hueRad);
      float i = yiq.y * cosA - yiq.z * sinA;
      float q = yiq.y * sinA + yiq.z * cosA;
      yiq.y = i;
      yiq.z = q;
      return yiq2rgb(yiq);
    }

    vec3 hash33(vec3 p3) {
      p3 = fract(p3 * vec3(0.1031, 0.11369, 0.13787));
      p3 += dot(p3, p3.yxz + 19.19);
      return -1.0 + 2.0 * fract(vec3(
        p3.x + p3.y,
        p3.x + p3.z,
        p3.y + p3.z
      ) * p3.zyx);
    }

    float snoise3(vec3 p) {
      const float K1 = 0.333333333;
      const float K2 = 0.166666667;
      vec3 i = floor(p + (p.x + p.y + p.z) * K1);
      vec3 d0 = p - (i - (i.x + i.y + i.z) * K2);
      vec3 e = step(vec3(0.0), d0 - d0.yzx);
      vec3 i1 = e * (1.0 - e.zxy);
      vec3 i2 = 1.0 - e.zxy * (1.0 - e);
      vec3 d1 = d0 - (i1 - K2);
      vec3 d2 = d0 - (i2 - K1);
      vec3 d3 = d0 - 0.5;
      vec4 h = max(0.6 - vec4(
        dot(d0, d0),
        dot(d1, d1),
        dot(d2, d2),
        dot(d3, d3)
      ), 0.0);
      vec4 n = h * h * h * h * vec4(
        dot(d0, hash33(i)),
        dot(d1, hash33(i + i1)),
        dot(d2, hash33(i + i2)),
        dot(d3, hash33(i + 1.0))
      );
      return dot(vec4(31.316), n);
    }

    vec4 extractAlpha(vec3 colorIn) {
      float a = max(max(colorIn.r, colorIn.g), colorIn.b);
      return vec4(colorIn.rgb / (a + 1e-5), a);
    }

    const vec3 baseColor1 = vec3(0.611765, 0.262745, 0.996078);
    const vec3 baseColor2 = vec3(0.298039, 0.760784, 0.913725);
    const vec3 baseColor3 = vec3(0.062745, 0.078431, 0.600000);
    const float noiseScale = 0.65;

    float light1(float intensity, float attenuation, float dist) {
      return intensity / (1.0 + dist * attenuation);
    }
    float light2(float intensity, float attenuation, float dist) {
      return intensity / (1.0 + dist * dist * attenuation);
    }

    vec4 draw(vec2 uv) {
      vec3 color1 = adjustHue(baseColor1, hue);
      vec3 color2 = adjustHue(baseColor2, hue);
      vec3 color3 = adjustHue(baseColor3, hue);
      
      float ang = atan(uv.y, uv.x);
      float len = length(uv);
      float invLen = len > 0.0 ? 1.0 / len : 0.0;

      float bgLuminance = dot(backgroundColor, vec3(0.299, 0.587, 0.114));
      
      // Speed up the noise time in the shader for faster plasma morphing
      float n0 = snoise3(vec3(uv * noiseScale, iTime * 1.3)) * 0.5 + 0.5;
      
      // Dynamic inner radius reacting very slightly to audio/voice
      float innerRadius = 0.55 + audioIntensity * 0.02;
      
      // Dynamic wave wobble amplitude: silent = subtle waves, speaking = larger responsive ripples
      float wobbleAmp = 0.08 + audioIntensity * 0.35;
      float minRadius = innerRadius + (1.0 - innerRadius) * (0.5 - wobbleAmp * 0.5);
      float maxRadius = innerRadius + (1.0 - innerRadius) * (0.5 + wobbleAmp * 0.5);
      float r0 = mix(minRadius, maxRadius, n0);
      float d0 = distance(uv, (r0 * invLen) * uv);
      float v0 = light1(1.0, 10.0, d0);

      v0 *= smoothstep(r0 * 1.05, r0, len);
      float innerFade = smoothstep(r0 * 0.8, r0 * 0.95, len);
      v0 *= mix(innerFade, 1.0, bgLuminance * 0.7);
      float cl = cos(ang + iTime * 2.0) * 0.5 + 0.5;
      
      float a = iTime * -1.0;
      vec2 pos = vec2(cos(a), sin(a)) * r0;
      float d = distance(uv, pos);
      float v1 = light2(1.5, 5.0, d);
      v1 *= light1(1.0, 50.0, d0);
      
      float v2 = smoothstep(1.0, mix(innerRadius, 1.0, n0 * 0.5), len);
      float v3 = smoothstep(innerRadius, mix(innerRadius, 1.0, 0.5), len);
      
      vec3 colBase = mix(color1, color2, cl);
      float fadeAmount = mix(1.0, 0.1, bgLuminance);
      
      vec3 darkCol = mix(color3, colBase, v0);
      darkCol = (darkCol + v1) * v2 * v3;
      darkCol = clamp(darkCol, 0.0, 1.0);
      
      vec3 lightCol = (colBase + v1) * mix(1.0, v2 * v3, fadeAmount);
      lightCol = mix(backgroundColor, lightCol, v0);
      lightCol = clamp(lightCol, 0.0, 1.0);
      
      vec3 finalCol = mix(darkCol, lightCol, bgLuminance);
      
      return extractAlpha(finalCol);
    }

    vec4 mainImage(vec2 fragCoord) {
      vec2 center = iResolution.xy * 0.5;
      float size = min(iResolution.x, iResolution.y);
      vec2 uv = (fragCoord - center) / size * 3.6;
      
      float angle = rot;
      float s = sin(angle);
      float c = cos(angle);
      uv = vec2(c * uv.x - s * uv.y, s * uv.x + c * uv.y);
      
      uv.x += hover * hoverIntensity * 0.1 * sin(uv.y * 10.0 + iTime);
      uv.y += hover * hoverIntensity * 0.1 * sin(uv.x * 10.0 + iTime);
      
      return draw(uv);
    }

    void main() {
      vec2 fragCoord = vUv * iResolution.xy;
      vec4 col = mainImage(fragCoord);
      gl_FragColor = vec4(col.rgb * col.a, col.a);
    }
  `;

  const ringsMat = new THREE.ShaderMaterial({
    vertexShader: ringsVert,
    fragmentShader: ringsFrag,
    uniforms: ringsUniforms,
    transparent: true,
    depthWrite: false,
    depthTest: false
  });

  const ringsMesh = new THREE.Mesh(ringsGeo, ringsMat);
  ringsMesh.frustumCulled = false;
  ringsMesh.visible = false;
  scene.add(ringsMesh);



  let targetHover = 0;
  let currentRot = 0;
  let ringsTime = 0;
  let currentRingsSpeed = 0.8;

  function handleMouseMove(e: MouseEvent) {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const width = rect.width;
    const height = rect.height;
    const size = Math.min(width, height);
    const centerX = width / 2;
    const centerY = height / 2;
    const uvX = ((x - centerX) / size) * 2.0;
    const uvY = ((y - centerY) / size) * 2.0;

    if (Math.sqrt(uvX * uvX + uvY * uvY) < 0.8) {
      targetHover = 1;
    } else {
      targetHover = 0;
    }
  }

  function handleMouseLeave() {
    targetHover = 0;
  }

  canvas.addEventListener("mousemove", handleMouseMove);
  canvas.addEventListener("mouseleave", handleMouseLeave);

  interface Electron {
    sx: number; sy: number; sz: number;
    ex: number; ey: number; ez: number;
    t: number;
    speed: number;
  }
  const activeElectrons: Electron[] = [];
  let electronSpawnRate = 0;
  let targetElectronRate = 0;
  let lastElectronSpawn = 0;

  let activeConnections: {
    x1: number; y1: number; z1: number;
    x2: number; y2: number; z2: number;
  }[] = [];

  // ── Base state vars ────────────────────────────────────────────────────────
  let state: OrbState = "idle";
  let nemotronActive = false;
  let targetRadius = 25, currentRadius = 25;
  let targetSpeed = 0.3, currentSpeed = 0.3;
  let targetBright = 0.6, currentBright = 0.6;
  let targetSize = 0.4, currentSize = 0.4;
  let lineAmount = 0, targetLineAmount = 0;
  const lineDistance = 8;

  let wordModeActive = false;
  let wordEndTime = 0;
  let textTargets = new Float32Array(N * 3);

  let spinX = 0, spinY = 0, spinZ = 0;
  let transitionEnergy = 0;
  let lastState: OrbState = "idle";
  let cloudZ = 0, cloudZVel = 0;

  // ── Speaking-specific vars ─────────────────────────────────────────────────
  let vortexStrength = 0, targetVortex = 0;
  let breathAmp = 0, targetBreathAmp = 0;
  let shockwave = 0;
  let prevBass = 0;
  let burstCooldown = 1.5;

  // Delta time tracking
  let prevT = 0;

  // ── Audio ──────────────────────────────────────────────────────────────────
  let analyser: AnalyserNode | null = null;
  let externalVolume = 0; // External volume from WebSocket
  let freqData = new Uint8Array(64);
  let bass = 0, mid = 0, treble = 0;

  const clock = new THREE.Clock();

  // ── Colour helpers ─────────────────────────────────────────────────────────
  const COL_FLASH = new THREE.Color(0xffffff);
  const _tmpColor = new THREE.Color();
  const _rainbowCol = new THREE.Color();

  const COL_NVIDIA_BASE = new THREE.Color(0x76b900);
  const COL_NVIDIA_THINK = new THREE.Color(0x99e52a);
  const COL_NVIDIA_SPEAK = new THREE.Color(0x8ae51c);
  const COL_NVIDIA_BRIGHT = new THREE.Color(0xccff88);

  let activeTheme = "default";

  const THEMES: Record<string, {
    base: THREE.Color;
    think: THREE.Color;
    speak: THREE.Color;
    bright: THREE.Color;
    search: THREE.Color;
  }> = {
    default: {
      base: new THREE.Color(0x4ca8e8),
      think: new THREE.Color(0x6ec4ff),
      speak: new THREE.Color(0x5ab8f0),
      bright: new THREE.Color(0xb8eeff),
      search: new THREE.Color(0x00e5ff),
    },
    // Suit le thème visuel : néon (vert) et aurum (or)
    neon: {
      base: new THREE.Color(0x35ff8b),
      think: new THREE.Color(0x7dffb4),
      speak: new THREE.Color(0x5bff9c),
      bright: new THREE.Color(0xc9ffe0),
      search: new THREE.Color(0x35ff8b),
    },
    aurum: {
      base: new THREE.Color(0xffbf5e),
      think: new THREE.Color(0xffd68a),
      speak: new THREE.Color(0xffcf7a),
      bright: new THREE.Color(0xffe9c6),
      search: new THREE.Color(0xffd68a),
    },
    pastel_blue: {
      base: new THREE.Color(0xCADCFC),
      think: new THREE.Color(0xA0B9D1),
      speak: new THREE.Color(0xB5CBE8),
      bright: new THREE.Color(0xE3EDFC),
      search: new THREE.Color(0xA0B9D1),
    },
    sand: {
      base: new THREE.Color(0xF6E7D8),
      think: new THREE.Color(0xE0CFC2),
      speak: new THREE.Color(0xEADCD0),
      bright: new THREE.Color(0xFAF4EE),
      search: new THREE.Color(0xE0CFC2),
    },
    grey: {
      base: new THREE.Color(0xE5E7EB),
      think: new THREE.Color(0x9CA3AF),
      speak: new THREE.Color(0xD1D5DB),
      bright: new THREE.Color(0xF3F4F6),
      search: new THREE.Color(0x9CA3AF),
    },
    iron_man: {
      base: new THREE.Color(0xff3344),
      think: new THREE.Color(0xff6688),
      speak: new THREE.Color(0xff1122),
      bright: new THREE.Color(0xff99aa),
      search: new THREE.Color(0xff3344),
    },
    nvidia: {
      base: new THREE.Color(0x76b900),
      think: new THREE.Color(0x99e52a),
      speak: new THREE.Color(0x8ae51c),
      bright: new THREE.Color(0xccff88),
      search: new THREE.Color(0x00ff88),
    },
    anneaux: {
      base: new THREE.Color(0x9b42fc),
      think: new THREE.Color(0x4cc2e9),
      speak: new THREE.Color(0x9b42fc),
      bright: new THREE.Color(0xe3edfc),
      search: new THREE.Color(0x00e5ff),
    }
  };

  let demoActive = false;
  let demoStartTime = 0;
  let demoBurstNextAt = 0;  // clock time of next forced burst
  const DEMO_DURATION = 10.0; // seconds

  let textCanvas: HTMLCanvasElement | null = null;
  let textCtx: CanvasRenderingContext2D | null = null;

  function generateTextTargets(text: string): Float32Array | null {
    if (!textCanvas) {
      textCanvas = document.createElement("canvas");
      textCtx = textCanvas.getContext("2d");
    }
    const ctx = textCtx;
    if (!ctx) return null;

    const fontSize = 48;
    ctx.font = `bold ${fontSize}px "Outfit", "Inter", "Segoe UI", sans-serif`;
    const metrics = ctx.measureText(text);
    const textWidth = Math.ceil(metrics.width) + 40;
    const textHeight = fontSize + 30;

    textCanvas.width = textWidth;
    textCanvas.height = textHeight;

    ctx.font = `bold ${fontSize}px "Outfit", "Inter", "Segoe UI", sans-serif`;
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, textWidth / 2, textHeight / 2);

    const imgData = ctx.getImageData(0, 0, textWidth, textHeight);
    const data = imgData.data;

    const pointsList: { x: number; y: number }[] = [];
    let filledCount = 0;
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] > 128) filledCount++;
    }

    let step = 1;
    if (filledCount > 3000) step = 3;
    else if (filledCount > 1500) step = 2;

    for (let y = 0; y < textHeight; y += step) {
      for (let x = 0; x < textWidth; x += step) {
        const idx = (y * textWidth + x) * 4;
        if (data[idx + 3] > 128) {
          pointsList.push({ x, y });
        }
      }
    }

    if (pointsList.length === 0) return null;

    const maxThreeJSWidth = 55;
    const scale = Math.min(0.2, maxThreeJSWidth / textWidth);

    const centerX = textWidth / 2;
    const centerY = textHeight / 2;

    const targets = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const pt = pointsList[i % pointsList.length];
      const i3 = i * 3;
      const jitter = 0.15;
      targets[i3] = (pt.x - centerX) * scale + (Math.random() - 0.5) * jitter;
      targets[i3 + 1] = -(pt.y - centerY) * scale + (Math.random() - 0.5) * jitter;
      targets[i3 + 2] = (Math.random() - 0.5) * 3.5;
    }

    return targets;
  }

  // ── Animate ────────────────────────────────────────────────────────────────
  function animate() {
    if (destroyed) return;
    requestAnimationFrame(animate);

    const t = clock.getElapsedTime();
    const currentThemeColors = THEMES[activeTheme] || THEMES.default;
    const baseColor = nemotronActive ? COL_NVIDIA_BASE : currentThemeColors.base;
    const thinkColor = nemotronActive ? COL_NVIDIA_THINK : currentThemeColors.think;
    const speakColor = nemotronActive ? COL_NVIDIA_SPEAK : currentThemeColors.speak;
    const brightColor = nemotronActive ? COL_NVIDIA_BRIGHT : currentThemeColors.bright;
    const searchColor = nemotronActive ? new THREE.Color(0x00ff88) : currentThemeColors.search;
    const dt = Math.min(t - prevT, 0.05);
    prevT = t;

    if (wordModeActive && t > wordEndTime) {
      wordModeActive = false;
    }

    // ── Demo expiry ──────────────────────────────────────────────────────────
    if (demoActive && t - demoStartTime >= DEMO_DURATION) {
      demoActive = false;
    }

    const demoElapsed = demoActive ? (t - demoStartTime) : -1;
    // Phases: 0-2s=BigBang, 2-5s=Hypervortex, 5-7.5s=PulseRings, 7.5-10s=Collapse
    const demoBigBang = demoActive && demoElapsed < 2.0;
    const demoVortex = demoActive && demoElapsed >= 2.0 && demoElapsed < 5.0;
    const demoPulse = demoActive && demoElapsed >= 5.0 && demoElapsed < 7.5;
    const demoCollapse = demoActive && demoElapsed >= 7.5;

    // ── Per-state targets ───────────────────────────────────────────────────
    if (demoActive) {
      if (demoBigBang) {
        targetRadius = 40; targetSpeed = 1.0; targetBright = 1.0; targetSize = 0.75;
        targetLineAmount = 1.0; targetElectronRate = 0.04;
        targetVortex = 0.5; targetBreathAmp = 2.5;
      } else if (demoVortex) {
        targetRadius = 32; targetSpeed = 0.9; targetBright = 1.0; targetSize = 0.65;
        targetLineAmount = 1.0; targetElectronRate = 0.04;
        targetVortex = 4.5; targetBreathAmp = 2.0;
      } else if (demoPulse) {
        targetRadius = 28; targetSpeed = 0.7; targetBright = 0.95; targetSize = 0.55;
        targetLineAmount = 0.9; targetElectronRate = 0.03;
        targetVortex = 2.0; targetBreathAmp = 3.0;
      } else {
        // Collapse
        targetRadius = 10; targetSpeed = 0.5; targetBright = 0.85; targetSize = 0.5;
        targetLineAmount = 0.7; targetElectronRate = 0.015;
        targetVortex = 1.0; targetBreathAmp = 0.5;
      }
    } else {
      switch (state) {
        case "idle":
          targetRadius = 15; targetSpeed = 0.2; targetBright = 0.55; targetSize = 0.35;
          targetLineAmount = 0.15; targetElectronRate = 0;
          targetVortex = 0; targetBreathAmp = 0;
          break;

        case "listening":
          targetRadius = 13; targetSpeed = 0.3; targetBright = 0.7; targetSize = 0.42;
          targetLineAmount = 0.4; targetElectronRate = 0;
          targetVortex = 0; targetBreathAmp = 0;
          break;

        case "thinking":
          targetRadius = 9; targetSpeed = 0.5; targetBright = 0.8; targetSize = 0.32;
          targetLineAmount = 1.0; targetElectronRate = 0.015;
          targetVortex = 0; targetBreathAmp = 0;
          break;

        case "speaking":
          targetRadius = 12.5; targetSpeed = 0.45; targetBright = 0.85; targetSize = 0.46;
          targetLineAmount = 0.8; targetElectronRate = 0.02;
          targetVortex = 0.3; targetBreathAmp = 0.9;
          break;

        case "searching":
          targetRadius = 18; targetSpeed = 0.8; targetBright = 0.8; targetSize = 0.45;
          targetLineAmount = 0.1; targetElectronRate = 0.01;
          targetVortex = 2.0; targetBreathAmp = 0.3;
          break;
      }
    }

    // ── Lerp base params ────────────────────────────────────────────────────
    const L = demoActive ? 0.06 : 0.035;
    currentRadius += (targetRadius - currentRadius) * L;
    currentSpeed += (targetSpeed - currentSpeed) * L;
    currentBright += (targetBright - currentBright) * L;
    currentSize += (targetSize - currentSize) * L;
    lineAmount += (targetLineAmount - lineAmount) * L;
    electronSpawnRate += (targetElectronRate - electronSpawnRate) * L;
    vortexStrength += (targetVortex - vortexStrength) * (demoActive ? 0.08 : 0.025);
    breathAmp += (targetBreathAmp - breathAmp) * (demoActive ? 0.08 : 0.025);

    // ── Transition tumble ───────────────────────────────────────────────────
    if (wordModeActive) {
      // Smoothly align the orb to face the camera directly when spelling
      spinX += (0 - spinX) * 0.1;
      spinY += (0 - spinY) * 0.1;
      spinZ += (0 - spinZ) * 0.1;
    } else {
      if (state !== lastState) { transitionEnergy = 1.0; lastState = state; }
      transitionEnergy *= 0.985;
      if (transitionEnergy > 0.05) {
        spinX += transitionEnergy * 0.012 * Math.sin(t * 1.7);
        spinY += transitionEnergy * 0.015;
        spinZ += transitionEnergy * 0.008 * Math.cos(t * 1.3);
      }
      if (demoActive) {
        spinY += 0.008 * (demoVortex ? 3.0 : 1.0);
        spinX += Math.sin(t * 0.7) * 0.003;
      }
    }

    // ── Audio ────────────────────────────────────────────────────────────────
    bass = 0; mid = 0; treble = 0;
    const isAudioActive = state === "speaking" || state === "listening" || state === "searching" || demoActive;
    if (isAudioActive) {
      if (analyser) {
        analyser.getByteFrequencyData(freqData);
        let bS = 0, mS = 0, tS = 0;
        for (let i = 0; i < 8;  i++) bS += freqData[i];
        for (let i = 8; i < 24; i++) mS += freqData[i];
        for (let i = 24;i < 48; i++) tS += freqData[i];
        bass   = bS / (8  * 255);
        mid    = mS / (16 * 255);
        treble = tS / (24 * 255);
      } else {
        // Use external volume if no analyser (Jarvis on PC)
        bass = externalVolume * 0.8;
        mid = externalVolume * 0.4;
        treble = externalVolume * 0.2;
      }
    } else {
      externalVolume = 0;
    }

    // ── Shockwave — bass spike detection ────────────────────────────────────
    const bassJump = Math.max(0, bass - prevBass - 0.04) * 5.0;
    shockwave = Math.max(shockwave * 0.82, bassJump);
    prevBass = bass;

    // ── Demo forced bursts ────────────────────────────────────────────────────
    if (demoActive) {
      if (t >= demoBurstNextAt) {
        const intensity = demoBigBang ? 0.9 : demoVortex ? 0.6 : demoPulse ? 0.75 : 0.4;
        shockwave = Math.max(shockwave, intensity);
        // During Big Bang: shoot ALL electrons out immediately
        if (demoBigBang && demoElapsed < 0.05) {
          shockwave = 1.0;
        }
        const interval = demoBigBang ? 0.5 : demoVortex ? 0.7 : demoPulse ? 0.9 : 1.5;
        demoBurstNextAt = t + interval + Math.random() * 0.3;
      }
    } else {
      // ── Periodic burst every ~1.5 s during speaking ──────────────────────
      if (state === "speaking") {
        burstCooldown -= dt;
        if (burstCooldown <= 0) {
          shockwave = Math.max(shockwave, 0.28);
          burstCooldown = 1.3 + Math.random() * 0.5;
        }
      } else {
        burstCooldown = 1.5;
      }
    }

    // ── Cloud drift ──────────────────────────────────────────────────────────
    let zTarget = Math.sin(t * 0.12) * 8;
    if (state === "thinking") zTarget = Math.sin(t * 0.3) * 15 + Math.sin(t * 0.9) * 6;
    else if (state === "speaking") zTarget = Math.sin(t * 0.18) * 7 - bass * 8;
    else if (demoActive) zTarget = Math.sin(t * 0.4) * 12;
    cloudZVel += (zTarget - cloudZ) * 0.008;
    cloudZVel *= 0.94;
    cloudZ += cloudZVel;

    points.rotation.x = spinX; points.rotation.y = spinY; points.rotation.z = spinZ;
    points.position.z = cloudZ;
    lines.rotation.x = spinX; lines.rotation.y = spinY; lines.rotation.z = spinZ;
    lines.position.z = cloudZ;

    // ── Update particles ─────────────────────────────────────────────────────
    const p = geo.getAttribute("position") as THREE.BufferAttribute;
    const a = p.array as Float32Array;
    const speaking = state === "speaking" && !demoActive;

    for (let i = 0; i < N; i++) {
      const i3 = i * 3;
      let x = a[i3], y = a[i3 + 1], z = a[i3 + 2];
      const px = phase[i];

      // Safety check: if a particle flies too far or is NaN, reset it
      const safetyDist = Math.sqrt(x * x + y * y + z * z) || 0.01;
      if (safetyDist > 120 || isNaN(x) || isNaN(y) || isNaN(z)) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = Math.pow(Math.random(), 0.5) * currentRadius;
        x = a[i3] = r * Math.sin(phi) * Math.cos(theta);
        y = a[i3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        z = a[i3 + 2] = r * Math.cos(phi);
        vel[i3] = 0;
        vel[i3 + 1] = 0;
        vel[i3 + 2] = 0;
      }

      if (wordModeActive) {
        const tx = textTargets[i3];
        const ty = textTargets[i3 + 1];
        const tz = textTargets[i3 + 2];

        const pullX = tx - x;
        const pullY = ty - y;
        const pullZ = tz - z;

        vel[i3] += pullX * 0.08;
        vel[i3 + 1] += pullY * 0.08;
        vel[i3 + 2] += pullZ * 0.08;

        // Apply voice reactiveness to text if speaking
        if (speaking && bass > 0.05) {
          const jitter = bass * 0.15;
          vel[i3] += (Math.random() - 0.5) * jitter;
          vel[i3 + 1] += (Math.random() - 0.5) * jitter;
          vel[i3 + 2] += (Math.random() - 0.5) * jitter;
        }

        // Damping specific to text mode for stability
        vel[i3] *= 0.82;
        vel[i3 + 1] *= 0.82;
        vel[i3 + 2] *= 0.82;
      } else {
        // ── Noise forces ──
        vel[i3] += Math.sin(t * 0.05 + px) * 0.001 * currentSpeed;
        vel[i3 + 1] += Math.cos(t * 0.06 + px * 1.3) * 0.001 * currentSpeed;
        vel[i3 + 2] += Math.sin(t * 0.055 + px * 0.7) * 0.001 * currentSpeed;
        vel[i3] += Math.sin(t * 0.02 + px * 2.1 + y * 0.1) * 0.0008 * currentSpeed;
        vel[i3 + 1] += Math.cos(t * 0.025 + px * 1.7 + z * 0.1) * 0.0008 * currentSpeed;
        vel[i3 + 2] += Math.sin(t * 0.022 + px * 0.9 + x * 0.1) * 0.0008 * currentSpeed;

        // ── Radial containment ──
        const dist = Math.sqrt(x * x + y * y + z * z) || 0.01;

        const radiusTarget = (speaking || demoActive)
          ? currentRadius * (1.0 + Math.sin(t * 3.5 + px * 0.2) * 0.15 * breathAmp)
          : currentRadius;

        // During demo collapse or searching: strong inward pull
        const pullBase = (demoCollapse || state === "searching")
          ? Math.max(0, dist - radiusTarget) * 0.15 + 0.04
          : Math.max(0, dist - radiusTarget) * 0.024 + 0.0003;
        vel[i3] -= (x / dist) * pullBase;
        vel[i3 + 1] -= (y / dist) * pullBase;
        vel[i3 + 2] -= (z / dist) * pullBase;

        // ── Bass push ──
        if (bass > 0.05) {
          const bf = (speaking || demoActive) ? bass * 0.012 : bass * 0.015;
          vel[i3] += (x / dist) * bf;
          vel[i3 + 1] += (y / dist) * bf;
          vel[i3 + 2] += (z / dist) * bf;
        }

        // ── Mid pulse ──
        if (mid > 0.1) {
          const pulse = Math.sin(t * 8 + px);
          const mf = (speaking || demoActive) ? mid * 0.015 : mid * 0.01;
          vel[i3] += (x / dist) * mf * pulse;
          vel[i3 + 1] += (y / dist) * mf * pulse;
        }

        // ══ SPEAKING EXCLUSIVE EFFECTS ══════════════════════════════════════════
        if (speaking) {
          // 1. RIPPLE PULSE (Integrated look)
          if (vortexStrength > 0.01) {
            const wave = Math.sin(dist * 0.8 - t * 12.0) * vortexStrength * 0.0035;
            vel[i3] += (x / dist) * wave;
            vel[i3 + 1] += (y / dist) * wave;
            vel[i3 + 2] += (z / dist) * wave;
          }

          // 2. SHOCKWAVE (Balanced push)
          if (shockwave > 0.005) {
            vel[i3] += (x / dist) * shockwave * 0.035;
            vel[i3 + 1] += (y / dist) * shockwave * 0.018;
            vel[i3 + 2] += (z / dist) * shockwave * 0.035;
          }

          // 3. BREATHING (Natural organic breathing)
          if (breathAmp > 0.005) {
            const bp = Math.sin(t * 7.5 + px * 0.4) * breathAmp * 0.0012;
            vel[i3] += (x / dist) * bp;
            vel[i3 + 1] += (y / dist) * bp;
            vel[i3 + 2] += (z / dist) * bp;
          }

          // 4. TREBLE flutter
          if (treble > 0.08) {
            const jitter = (Math.random() - 0.5) * treble * 0.025;
            vel[i3] += jitter;
            vel[i3 + 1] += jitter * 0.5;
            vel[i3 + 2] += jitter;
          }
        }

        // ══ SEARCHING EXCLUSIVE EFFECTS (RADAR DISK) ───────────────────────────
        if (state === "searching") {
          // 1. Aplatir légèrement sur l'axe Y pour un effet ellipsoïde 3D élégant au lieu d'un disque plat
          vel[i3 + 1] -= y * 0.02;

          // 2. Swirl rotation fluide autour de l'axe Y
          const xzLen = Math.sqrt(x * x + z * z) || 0.01;
          vel[i3] += (-z / xzLen) * 0.025 * currentSpeed;
          vel[i3 + 2] += (x / xzLen) * 0.025 * currentSpeed;

          // 3. Vagues d'ondes de choc radiales (radar pulses)
          const dist2D = Math.sqrt(x * x + z * z) || 0.01;
          const wave = Math.sin(dist2D * 0.5 - t * 10.0) * 0.005;
          vel[i3] += (x / dist2D) * wave;
          vel[i3 + 2] += (z / dist2D) * wave;
        }

        // ══ DEMO EXCLUSIVE EFFECTS ═══════════════════════════════════════════════
        if (demoActive) {
          // 1. HYPERVORTEX — massive swirl around Y axis
          if (vortexStrength > 0.01) {
            const xzLen = Math.sqrt(x * x + z * z) || 0.01;
            vel[i3] += (-z / xzLen) * vortexStrength * 0.004;
            vel[i3 + 2] += (x / xzLen) * vortexStrength * 0.004;
            // Also spiral around Z axis during vortex phase
            if (demoVortex) {
              const xyLen = Math.sqrt(x * x + y * y) || 0.01;
              vel[i3] += (-y / xyLen) * vortexStrength * 0.0015;
              vel[i3 + 1] += (x / xyLen) * vortexStrength * 0.0015;
            }
            vel[i3 + 1] += Math.sin(px * 2.3 + t) * vortexStrength * 0.001;
          }

          // 2. SHOCKWAVE blast (stronger than speaking)
          if (shockwave > 0.005) {
            vel[i3] += (x / dist) * shockwave * 0.18;
            vel[i3 + 1] += (y / dist) * shockwave * 0.18;
            vel[i3 + 2] += (z / dist) * shockwave * 0.18;
          }

          // 3. BREATHING — big sinusoidal surge
          if (breathAmp > 0.005) {
            const bp = Math.sin(t * 9.0 + px * 0.5) * breathAmp * 0.0035;
            vel[i3] += (x / dist) * bp;
            vel[i3 + 1] += (y / dist) * bp;
            vel[i3 + 2] += (z / dist) * bp;
          }

          // 4. PULSE RINGS — during pulse phase, extra radial waves
          if (demoPulse) {
            const ringFreq = 5.0;
            const ring = Math.sin(dist * ringFreq - t * 12.0 + px) * 0.003;
            vel[i3] += (x / dist) * ring;
            vel[i3 + 1] += (y / dist) * ring;
            vel[i3 + 2] += (z / dist) * ring;
          }

          // 5. SCATTER CHAOS — random turbulence during Big Bang
          if (demoBigBang) {
            const chaos = (Math.random() - 0.5) * 0.04;
            vel[i3] += chaos;
            vel[i3 + 1] += chaos * 0.7;
            vel[i3 + 2] += chaos;
          }
        }

        // Apply standard damping (stronger damping when speaking to keep it concentrated)
        const damp = demoActive ? 0.988 : (speaking ? 0.975 : 0.992);
        vel[i3] *= damp;
        vel[i3 + 1] *= damp;
        vel[i3 + 2] *= damp;
      }

      // Integrate is common to both modes
      a[i3] += vel[i3];
      a[i3 + 1] += vel[i3 + 1];
      a[i3 + 2] += vel[i3 + 2];
    }
    p.needsUpdate = true;

    // ── Connection lines ──────────────────────────────────────────────────────
    if (lineAmount > 0.01) {
      const lp = lineGeo.getAttribute("position") as THREE.BufferAttribute;
      const la = lp.array as Float32Array;
      let lineCount = 0;
      const maxDist = wordModeActive
        ? 2.5
        : (lineDistance - 1) * (1 + bass * ((speaking || demoActive) ? 0.6 : 0.4));
      const maxDistSq = maxDist * maxDist;
      const step = Math.max(1, Math.floor(N / 600));

      for (let i = 0; i < N && lineCount < MAX_LINES; i += step) {
        const i3 = i * 3;
        const x1 = a[i3], y1 = a[i3 + 1], z1 = a[i3 + 2];
        for (let j = i + step; j < N && lineCount < MAX_LINES; j += step) {
          const j3 = j * 3;
          const dx = a[j3] - x1, dy = a[j3 + 1] - y1, dz = a[j3 + 2] - z1;
          if (dx * dx + dy * dy + dz * dz < maxDistSq) {
            const idx = lineCount * 6;
            la[idx] = x1; la[idx + 1] = y1; la[idx + 2] = z1;
            la[idx + 3] = a[j3]; la[idx + 4] = a[j3 + 1]; la[idx + 5] = a[j3 + 2];
            lineCount++;
          }
        }
      }
      lineGeo.setDrawRange(0, lineCount * 2);
      lp.needsUpdate = true;
      lineMat.opacity = lineAmount * 0.12 + shockwave * 0.15;

      activeConnections = [];
      for (let c = 0; c < Math.min(lineCount, 500); c++) {
        const ci = c * 6;
        activeConnections.push({
          x1: la[ci], y1: la[ci + 1], z1: la[ci + 2],
          x2: la[ci + 3], y2: la[ci + 4], z2: la[ci + 5],
        });
      }
    } else {
      lineGeo.setDrawRange(0, 0);
      activeConnections = [];
    }

    // ── Electrons ─────────────────────────────────────────────────────────────
    const maxElec = demoActive ? 25 : speaking ? 10 : 3;
    const spawnGap = demoActive ? 0.06 : speaking ? 0.18 : 1.0;
    const eSpeed = demoActive
      ? 0.014 + Math.random() * 0.012
      : speaking
        ? 0.009 + Math.random() * 0.009
        : 0.003 + Math.random() * 0.003;

    if (activeConnections.length > 0 && electronSpawnRate > 0.005) {
      if (activeElectrons.length < maxElec && (t - lastElectronSpawn) > spawnGap) {
        const conn = activeConnections[Math.floor(Math.random() * activeConnections.length)];
        activeElectrons.push({
          sx: conn.x1, sy: conn.y1, sz: conn.z1,
          ex: conn.x2, ey: conn.y2, ez: conn.z2,
          t: 0,
          speed: eSpeed,
        });
        lastElectronSpawn = t;
      }
    }

    const ep = electronGeo.getAttribute("position") as THREE.BufferAttribute;
    const ea = ep.array as Float32Array;
    let aliveCount = 0;

    for (let e = activeElectrons.length - 1; e >= 0; e--) {
      const el = activeElectrons[e];
      el.t += el.speed;
      if (el.t >= 1) { activeElectrons.splice(e, 1); continue; }
      const ei = aliveCount * 3;
      ea[ei] = el.sx + (el.ex - el.sx) * el.t;
      ea[ei + 1] = el.sy + (el.ey - el.sy) * el.t;
      ea[ei + 2] = el.sz + (el.ez - el.sz) * el.t;
      aliveCount++;
    }

    electronGeo.setDrawRange(0, aliveCount);
    ep.needsUpdate = true;

    electronPoints.rotation.x = spinX; electronPoints.rotation.y = spinY; electronPoints.rotation.z = spinZ;
    electronPoints.position.z = cloudZ;
    electronMat.size = demoActive ? 1.4 + shockwave * 1.2 : speaking ? 1.0 + shockwave * 0.8 : 0.8;
    electronMat.opacity = demoActive ? 1.0 : speaking ? 1.0 + shockwave * 0.5 : 1.0;

    // ── Material update ───────────────────────────────────────────────────────
    if (demoActive) {
      // RAINBOW colour — hue cycles rapidly through the spectrum
      const hue = ((t - demoStartTime) * 0.2) % 1.0;  // full cycle every ~5s
      _rainbowCol.setHSL(hue, 1.0, 0.6);

      // On big shockwaves: flash white
      if (shockwave > 0.4) {
        _rainbowCol.lerp(COL_FLASH, Math.min(1, (shockwave - 0.4) * 2.0));
      }

      mat.opacity = Math.min(1.4, currentBright + shockwave * 0.3);
      mat.size = currentSize + shockwave * 0.5;
      mat.color.lerp(_rainbowCol, 0.12);
      lineMat.color.lerp(_rainbowCol, 0.12);
      lineMat.opacity = lineAmount * 0.18 + shockwave * 0.25;
      // Electrons also match rainbow
      electronMat.color.lerp(_rainbowCol, 0.15);

    } else if (speaking) {
      mat.opacity = Math.min(1.2, currentBright + bass * 0.18 + shockwave * 0.25);
      mat.size = currentSize + bass * 0.12 + shockwave * 0.20;

      const pulseIntensity = (bass * 0.7 + mid * 0.2 + shockwave * 0.5);
      const wave = 0.5 + 0.5 * Math.sin(t * 12.0 + bass * 8.0);
      _tmpColor.lerpColors(speakColor, brightColor, Math.min(1, pulseIntensity * wave));

      // Removed white flash effect to keep the chosen theme colors pure and clean
      mat.color.lerp(_tmpColor, 0.14);
      lineMat.color.lerp(_tmpColor, 0.14);
      electronMat.color.set(0xffffff);

    } else {
      mat.opacity = currentBright + bass * 0.08;
      mat.size = currentSize + bass * 0.05;

      if (state === "searching") {
        mat.color.lerp(searchColor, 0.15);
        lineMat.color.lerp(searchColor, 0.15);
        lineMat.opacity = lineAmount * 0.28;
      } else if (state === "thinking") {
        mat.color.lerp(thinkColor, 0.015);
        lineMat.color.lerp(thinkColor, 0.015);
      } else {
        mat.color.lerp(baseColor, 0.015);
        lineMat.color.lerp(baseColor, 0.015);
      }
      electronMat.color.set(0xffffff);
    }

    if (wordModeActive) {
      lineMat.opacity = 0.04;
      mat.opacity = 0.55;
    }

    // ── Camera drift ──────────────────────────────────────────────────────────
    if (demoActive) {
      // Camera swoops around during demo
      const demoT = demoElapsed;
      camera.position.x = Math.sin(demoT * 0.5) * 12;
      camera.position.y = Math.cos(demoT * 0.35) * 8;
      camera.position.z = 80 + Math.sin(demoT * 0.6) * 15;
    } else {
      camera.position.x = Math.sin(t * 0.02) * 5;
      camera.position.y = Math.cos(t * 0.03) * 3;
      camera.position.z = 80;
    }


    camera.lookAt(0, 0, cloudZ * 0.2);

    // ── Rings visibility toggle and uniforms updates ──
    const isAnneaux = activeTheme === "anneaux";
    const showParticles = !isAnneaux || wordModeActive;
    const showRings = isAnneaux && !wordModeActive;
    
    points.visible = showParticles;
    lines.visible = showParticles;
    electronPoints.visible = showParticles;
    ringsMesh.visible = showRings;

    if (isAnneaux) {
      // Speed reacts smoothly to bass when speaking, with lower idle speed (0.45) and higher speaking speed
      const targetRingsSpeed = 0.45 + bass * 7.5;
      currentRingsSpeed += (targetRingsSpeed - currentRingsSpeed) * 0.22;
      ringsTime += dt * currentRingsSpeed;

      ringsUniforms.iTime.value = ringsTime;
      ringsUniforms.iResolution.value.set(
        window.innerWidth * window.devicePixelRatio,
        window.innerHeight * window.devicePixelRatio,
        window.innerWidth / window.innerHeight
      );
      ringsUniforms.audioIntensity.value = bass; // dynamic voice reactivity!
      
      const effectiveHover = targetHover;
      ringsUniforms.hover.value += (effectiveHover - ringsUniforms.hover.value) * 0.1;
      
      if (ringsUniforms.hover.value > 0.5) {
        currentRot += dt * 0.3;
      } else if (state === "searching") {
        currentRot += dt * 1.5; // Rotate faster when searching!
      } else {
        // Smoothly return rotation to its base classic position (0) when not active
        currentRot += (0 - currentRot) * 0.08;
      }
      ringsUniforms.rot.value = currentRot;
    }

    renderer.render(scene, camera);
  }

  function onResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  }

  window.addEventListener("resize", onResize);
  animate();

  return {
    setState(s: OrbState) {
      state = s;
    },
    setVolume(v: number) {
      externalVolume = v;
      // Kick shockwave on sharp volume increases
      if (v > 0.4) shockwave = Math.max(shockwave, v * 0.5);
    },
    setAnalyser(a: AnalyserNode | null) {
      analyser = a;
      if (a) freqData = new Uint8Array(a.frequencyBinCount);
    },
    triggerDemo() {
      demoActive = true;
      demoStartTime = clock.getElapsedTime();
      demoBurstNextAt = demoStartTime; // fire immediately
      // Kick things off with a huge shockwave
      shockwave = 1.0;
      transitionEnergy = 1.0;
    },
    setQuality(q: "low" | "high") {
      if (q === "high") {
        renderer.setPixelRatio(window.devicePixelRatio);
        mat.opacity = 0.6;
        lineMat.opacity = 0.15;
      } else {
        renderer.setPixelRatio(1);
        mat.opacity = 0.3;
        lineMat.opacity = 0.05;
      }
    },
    destroy() {
      destroyed = true;
      window.removeEventListener("resize", onResize);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mouseleave", handleMouseLeave);
      renderer.dispose();
    },
    setNemotronActive(active: boolean) {
      nemotronActive = active;
    },
    showWord(word: string, durationMs: number) {
      const targets = generateTextTargets(word);
      if (targets) {
        textTargets = targets as any;
        wordModeActive = true;
        wordEndTime = clock.getElapsedTime() + durationMs / 1000;
        // Kick a light shockwave to burst into text formation
        shockwave = Math.max(shockwave, 0.4);
      }
    },
    setTheme(theme: string) {
      if (THEMES[theme]) {
        activeTheme = theme;
      }
    },
    setDeformation(scaleX: number, scaleY: number, rotationZ: number) {
      if (ringsMesh) {
        ringsMesh.scale.set(scaleX, scaleY, 1);
        ringsMesh.rotation.z = rotationZ;
      }
    },
  };
}
