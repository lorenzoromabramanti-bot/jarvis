// ── 頻譜分析器（收合 + 波形顯示） ──

import { getAccentRGB, getThemeHue } from '../config/theme.js';

// 取得當前主題色（用於 canvas 繪圖）
function getThemeRgbaValue(alpha) {
  return `rgba(${getAccentRGB()}, ${alpha})`;
}

// 收合功能
const circularCanvas = document.getElementById('circular-canvas');
const circularCtx = circularCanvas ? circularCanvas.getContext('2d') : null;

function resizeCircularCanvas() {
  if (!circularCanvas) return;
  circularCanvas.width = circularCanvas.offsetWidth;
  circularCanvas.height = circularCanvas.offsetHeight;
}

export function drawCircularVisualizer(frequencyData, audioSensitivity, audioReactivity) {
  if (!circularCtx || !circularCanvas) return;
  const width = circularCanvas.width;
  const height = circularCanvas.height;
  const centerX = width / 2;
  const centerY = height / 2;
  circularCtx.clearRect(0, 0, width, height);

  const numPoints = 180;
  const baseRadius = Math.min(width, height) * 0.4;

  circularCtx.beginPath();
  circularCtx.arc(centerX, centerY, baseRadius * 1.2, 0, Math.PI * 2);
  circularCtx.fillStyle = getThemeRgbaValue(0.05);
  circularCtx.fill();

  const numRings = 3;
  const analyserBinCount = frequencyData.length;

  for (let ring = 0; ring < numRings; ring++) {
    const ringRadius = baseRadius * (0.7 + ring * 0.15);
    const opacity = 0.8 - ring * 0.2;

    circularCtx.beginPath();
    for (let i = 0; i < numPoints; i++) {
      const freqRangeStart = Math.floor((ring * analyserBinCount) / (numRings * 1.5));
      const freqRangeEnd = Math.floor(((ring + 1) * analyserBinCount) / (numRings * 1.5));
      const freqRange = freqRangeEnd - freqRangeStart;
      let sum = 0;
      const segmentSize = Math.floor(freqRange / numPoints);
      for (let j = 0; j < segmentSize; j++) {
        const freqIndex = freqRangeStart + ((i * segmentSize + j) % freqRange);
        sum += frequencyData[freqIndex];
      }
      const value = sum / (segmentSize * 255);
      const adjustedValue = value * (audioSensitivity / 5) * audioReactivity;
      const dynamicRadius = ringRadius * (1 + adjustedValue * 0.5);
      const angle = (i / numPoints) * Math.PI * 2;
      const x = centerX + Math.cos(angle) * dynamicRadius;
      const y = centerY + Math.sin(angle) * dynamicRadius;
      if (i === 0) circularCtx.moveTo(x, y);
      else circularCtx.lineTo(x, y);
    }
    circularCtx.closePath();

    // 使用主題顏色計算 gradient (從 CSS 變數取得 HSL)
    const accentRGB = getAccentRGB();
    let gradient;
    gradient = circularCtx.createRadialGradient(
      centerX, centerY, ringRadius * 0.8,
      centerX, centerY, ringRadius * 1.2
    );
    gradient.addColorStop(0, `rgba(${accentRGB}, ${opacity})`);
    gradient.addColorStop(1, `rgba(${accentRGB}, ${opacity * 0.7})`);

    circularCtx.strokeStyle = gradient;
    circularCtx.lineWidth = 2 + (numRings - ring);
    circularCtx.stroke();
    circularCtx.shadowBlur = 15;
    circularCtx.shadowColor = getThemeRgbaValue(0.7);
  }
  circularCtx.shadowBlur = 0;
}

// 波形圖 (data-center metrics)
export function initVisualizers() {
  resizeCircularCanvas();
  window.addEventListener('resize', resizeCircularCanvas);
}

export function resizeAllCanvases() {
  resizeCircularCanvas();
}
