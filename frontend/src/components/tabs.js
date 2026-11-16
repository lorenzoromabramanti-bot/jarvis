// ── Tab 切換系統（DATA CENTER 統一面板） ──

function initDataCenterTabs() {
  document.querySelectorAll('.tab-btn-r').forEach((btn) => {
    btn.addEventListener('click', () => {
      const tabId = btn.dataset.rtab;
      document.querySelectorAll('.tab-btn-r').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.rtab-content').forEach((c) => c.classList.remove('active'));
      const target = document.getElementById(`rtab-${tabId}`);
      if (target) target.classList.add('active');
    });
  });
}

export function initTabs() {
  initDataCenterTabs();
  // « ouvre tes réglages » (JARVIS) ouvre index.html?onglet=settings : on tombe directement sur cet onglet.
  const onglet = new URLSearchParams(location.search).get('onglet');
  if (onglet) document.querySelector(`.tab-btn-r[data-rtab="${CSS.escape(onglet)}"]`)?.click();
}
