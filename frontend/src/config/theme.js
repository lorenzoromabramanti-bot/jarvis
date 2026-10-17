/**
 * Theme Manager - 全域配色系統
 * 負責管理 CSS 變數和通知模組顏色變更
 */

/**
 * HSL 轉 RGB
 * @param {number} h - Hue (0-360)
 * @param {number} s - Saturation (0-100)
 * @param {number} l - Lightness (0-100)
 * @returns {Object} {r, g, b} (0-255)
 */
function hslToRgb(h, s, l) {
  s /= 100;
  l /= 100;
  const k = n => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return {
    r: Math.round(255 * f(0)),
    g: Math.round(255 * f(8)),
    b: Math.round(255 * f(4))
  };
}

/**
 * 設定主題色相
 * @param {number} hue - 色相值 (0-360)
 */
/**
 * 設定主題色相
 * @param {number} hue - 色相值 (0-360)
 * @param {number} sat - multiplicateur de saturation (0-1). 1 = couleurs
 *   pleines, valeur basse = gris. Necessaire pour le style « grey » : le gris
 *   n'est pas une teinte, c'est une absence de saturation.
 */
export function setThemeHue(hue, sat = 1) {
  const root = document.documentElement;

  // 設定 --hue 變數
  root.style.setProperty('--hue', hue);
  root.style.setProperty('--sat', sat);

  // 計算 RGB 值供 rgba() 使用
  // --accent-primary: hsl(hue, 100% * sat, 63%)
  const primary = hslToRgb(hue, 100 * sat, 63);
  root.style.setProperty('--accent-r', primary.r);
  root.style.setProperty('--accent-g', primary.g);
  root.style.setProperty('--accent-b', primary.b);
  root.style.setProperty('--accent-rgb', `${primary.r}, ${primary.g}, ${primary.b}`);

  // --accent-secondary: hsl(hue, 62% * sat, 47%)
  const secondary = hslToRgb(hue, 62 * sat, 47);
  root.style.setProperty('--accent-secondary-rgb', `${secondary.r}, ${secondary.g}, ${secondary.b}`);

  // --accent-tertiary: hsl(hue, 100% * sat, 84%)
  const tertiary = hslToRgb(hue, 100 * sat, 84);
  root.style.setProperty('--accent-tertiary-rgb', `${tertiary.r}, ${tertiary.g}, ${tertiary.b}`);

  // 儲存到 localStorage
  localStorage.setItem('jarvis-theme-hue', hue);
  localStorage.setItem('jarvis-theme-sat', sat);

  // 通知所有模組更新
  window.dispatchEvent(new CustomEvent('theme-change', {
    detail: {
      hue, sat,
      primary: { r: primary.r, g: primary.g, b: primary.b },
      secondary: { r: secondary.r, g: secondary.g, b: secondary.b },
      tertiary: { r: tertiary.r, g: tertiary.g, b: tertiary.b }
    }
  }));
}

/**
 * Styles d'orbe du selecteur SETTINGS -> PROFIL.
 *
 * Ils passent par setThemeHue, donc par le MEME mecanisme que les pastilles
 * de l'onglet CONTROLS. Avant, « STYLE ORBE » n'etait relu par personne — ni
 * dans le HUD ni dans main2.py — et le choix n'avait aucun effet visible.
 * Les teintes reprennent celles de l'ancien frontend : classic = le cyan
 * #00e5ff code en dur dans son index.html, neon = vert, aurum = or.
 */
export const STYLES_ORBE = {
  grey:    { hue: 200, sat: 0.06 },
  classic: { hue: 186, sat: 1 },
  neon:    { hue: 140, sat: 1 },
  aurum:   { hue: 45,  sat: 1 },
};

/** @returns {boolean} false si le nom de style est inconnu. */
export function appliquerStyleOrbe(nom) {
  const style = STYLES_ORBE[nom];
  if (!style) return false;
  setThemeHue(style.hue, style.sat);
  return true;
}

/**
 * 取得當前主題色相
 * @returns {number} 色相值
 */
// Teinte par defaut du HUD JARVIS : teal/turquoise.
// 169 = teinte exacte de #4dd9c0, la couleur des references Manina Labs.
// (le rouge 5 etait la valeur du projet clone d'origine)
export const HUE_DEFAUT_JARVIS = 169;

// Version du theme : incrementer invalide la teinte memorisee chez les
// utilisateurs existants. Sans ca, un localStorage ecrit avant ce changement
// garderait le rouge indefiniment.
const VERSION_THEME = '2-jarvis-teal';

export function getThemeHue() {
  if (localStorage.getItem('jarvis-theme-version') !== VERSION_THEME) {
    localStorage.removeItem('jarvis-theme-hue');
    localStorage.setItem('jarvis-theme-version', VERSION_THEME);
    return HUE_DEFAUT_JARVIS;
  }
  const stored = localStorage.getItem('jarvis-theme-hue');
  return stored ? parseInt(stored, 10) : HUE_DEFAUT_JARVIS;
}

export function getThemeSat() {
  const stored = parseFloat(localStorage.getItem('jarvis-theme-sat'));
  return Number.isFinite(stored) ? stored : 1;
}

/**
 * 取得 accent 顏色（HSL 字串）
 * @returns {string} CSS HSL 值
 */
export function getAccentColor() {
  const style = getComputedStyle(document.documentElement);
  return style.getPropertyValue('--accent-primary').trim();
}

/**
 * 取得 accent 顏色（RGB 字串）
 * @returns {string} "r, g, b" 格式
 */
export function getAccentRGB() {
  const style = getComputedStyle(document.documentElement);
  return style.getPropertyValue('--accent-rgb').trim();
}

/**
 * 取得 accent 顏色（RGB Object）
 * @returns {Object} {r, g, b}
 */
export function getAccentRGBObject() {
  const rgb = getAccentRGB();
  const [r, g, b] = rgb.split(',').map(v => parseInt(v.trim(), 10));
  return { r, g, b };
}

/**
 * 取得 accent 顏色（Hex）
 * @returns {string} #RRGGBB
 */
export function getAccentHex() {
  const { r, g, b } = getAccentRGBObject();
  return `#${[r, g, b].map(v => v.toString(16).padStart(2, '0')).join('')}`;
}

/**
 * 初始化主題系統
 */
export function initTheme() {
  setThemeHue(getThemeHue(), getThemeSat());
}

// 預設色板
export const THEME_PRESETS = [
  { name: 'Rouge', emoji: '🔴', hue: 5 },
  { name: 'Orange', emoji: '🟠', hue: 30 },
  { name: 'Vert', emoji: '🟢', hue: 140 },
  { name: 'JARVIS teal', emoji: '🩵', hue: HUE_DEFAUT_JARVIS },
  { name: 'Bleu', emoji: '🔵', hue: 220 },
  { name: 'Violet', emoji: '🟣', hue: 270 }
];
