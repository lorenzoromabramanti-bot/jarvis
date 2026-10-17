// ── 時間戳更新 ──

export function initTimestamp() {
  const topClockEl = document.getElementById('top-clock');
  function updateTimestamp() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const t = `${hours}:${minutes}:${seconds}`;
    const el = document.getElementById('timestamp');
    if (el) el.textContent = t;
    // Horloge du bandeau superieur : meme source, pas un 2e timer.
    if (topClockEl) topClockEl.textContent = t;
  }
  setInterval(updateTimestamp, 1000);
  updateTimestamp();
}
