// JARVIS Mail — logique client (PWA)
const $ = (id) => document.getElementById(id);
const statusEl = $('status');
const listEl = $('list');
const accountsBar = $('accounts-bar');
const searchInput = $('search-input');
const unreadToggle = $('unread-toggle');

// ── État des filtres (côté client uniquement) ──
let allMessages = [];
let lastAccounts = [];
let activeAccount = null; // null = tous les comptes
let unreadOnly = false;

// ── Lu / non-lu : purement cosmétique, jamais envoyé au serveur IMAP/Graph ──
const READ_KEY = 'jmail_read_ids';
function loadReadSet() {
  try { return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); } catch (e) { return new Set(); }
}
function saveReadSet(set) {
  try { localStorage.setItem(READ_KEY, JSON.stringify([...set])); } catch (e) {}
}
let readIds = loadReadSet();
function mailKey(compte, id) { return `${compte}:${id}`; }
function isRead(m) { return readIds.has(mailKey(m.compte, m.id)); }
function markRead(compte, id) {
  readIds.add(mailKey(compte, id));
  saveReadSet(readIds);
}

function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2600);
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}

async function loadInbox() {
  statusEl.textContent = 'Relève des boîtes en cours…';
  try {
    const r = await fetch('api/inbox', { cache: 'no-store' });
    const data = await r.json();
    renderAccounts(data.accounts || []);
    if (!data.configured) {
      statusEl.textContent = 'Aucune boîte connectée. Touchez « + » pour ajouter Gmail, iCloud ou Outlook.';
      allMessages = [];
      listEl.innerHTML = '';
      return;
    }
    allMessages = data.messages || [];
    renderList();
  } catch (e) {
    statusEl.textContent = 'Impossible de joindre JARVIS. Vérifiez que JARVIS tourne sur le même réseau.';
  }
}

function filteredMessages() {
  const q = searchInput.value.trim().toLowerCase();
  return allMessages.filter((m) => {
    if (activeAccount && m.compte !== activeAccount) return false;
    if (unreadOnly && isRead(m)) return false;
    if (q) {
      const hay = `${m.sujet || ''} ${m.de || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderList() {
  const msgs = filteredMessages();
  const filtering = activeAccount || unreadOnly || searchInput.value.trim();
  if (!allMessages.length) {
    statusEl.textContent = 'Aucun message. Tout est calme.';
  } else if (!msgs.length) {
    statusEl.textContent = 'Aucun message ne correspond aux filtres.';
  } else {
    statusEl.textContent = filtering
      ? `${msgs.length} / ${allMessages.length} message(s).`
      : `${allMessages.length} message(s) sur ${new Set(allMessages.map(m => m.compte)).size} boîte(s).`;
  }
  listEl.innerHTML = msgs.map((m) => `
    <div class="mail ${isRead(m) ? 'is-read' : 'is-unread'}" data-account="${escapeHtml(m.compte)}" data-id="${escapeHtml(String(m.id || ''))}">
      <div class="top">
        <span class="unread-dot" aria-hidden="true"></span>
        <span class="from">${escapeHtml(m.de.split('<')[0].trim() || m.de)}</span>
        <span class="meta">${fmtDate(m.date)}</span>
      </div>
      <div class="subject">${escapeHtml(m.sujet)}</div>
      <span class="acct">${escapeHtml(m.compte)}</span>
    </div>`).join('');
}

function renderAccounts(accts) {
  lastAccounts = accts;
  accountsBar.innerHTML = accts.map((a) =>
    `<span class="chip ${a.ok ? '' : 'ko'} ${activeAccount === a.name ? 'active' : ''}" data-account="${escapeHtml(a.name)}">${escapeHtml(a.name)} · ${a.ok ? a.count : '⚠'}</span>`
  ).join('') || '<span class="chip">Aucune boîte</span>';
}

// Clic sur un compte → filtre la liste sur ce compte (reclic = enlève le filtre)
accountsBar.addEventListener('click', (e) => {
  const chip = e.target.closest('.chip[data-account]');
  if (!chip) return;
  const acct = chip.dataset.account;
  activeAccount = (activeAccount === acct) ? null : acct;
  renderAccounts(lastAccounts);
  renderList();
});

searchInput.addEventListener('input', renderList);
unreadToggle.addEventListener('click', () => {
  unreadOnly = !unreadOnly;
  unreadToggle.classList.toggle('active', unreadOnly);
  unreadToggle.setAttribute('aria-pressed', String(unreadOnly));
  renderList();
});

// ── Ajout de compte ──
$('add-fab').addEventListener('click', () => $('modal').classList.add('open'));
$('m-cancel').addEventListener('click', () => $('modal').classList.remove('open'));
$('m-save').addEventListener('click', async () => {
  const compte = {
    name: $('f-name').value.trim() || $('f-user').value.trim(),
    provider: $('f-provider').value,
    user: $('f-user').value.trim(),
    password: $('f-pass').value,
  };
  if (!compte.user || !compte.password) { toast('E-mail et mot de passe requis.'); return; }
  try {
    const r = await fetch('api/accounts', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(compte),
    });
    const res = await r.json();
    if (res.ok) {
      toast('Boîte ajoutée.');
      $('modal').classList.remove('open');
      $('f-name').value = $('f-user').value = $('f-pass').value = '';
      loadInbox();
    } else {
      toast(res.error || 'Échec de l’enregistrement.');
    }
  } catch (e) {
    toast('JARVIS injoignable.');
  }
});

$('refresh-btn').addEventListener('click', loadInbox);

// ── Ouverture d'un mail (corps) ──
async function openMail(account, id) {
  const modal = $('mail-modal');
  $('mail-subject').textContent = 'Chargement…';
  $('mail-from').textContent = '';
  $('mail-date').textContent = '';
  $('mail-body').textContent = '';
  modal.classList.add('open');
  try {
    const r = await fetch(`api/message?account=${encodeURIComponent(account)}&id=${encodeURIComponent(id)}`, { cache: 'no-store' });
    const m = await r.json();
    if (m.error) {
      $('mail-subject').textContent = 'Erreur';
      $('mail-body').textContent = m.error;
      return;
    }
    $('mail-subject').textContent = m.sujet || '(sans objet)';
    $('mail-from').textContent = m.de || '';
    $('mail-date').textContent = fmtDate(m.date);
    $('mail-body').textContent = m.corps || '(vide)';
  } catch (e) {
    $('mail-subject').textContent = 'Erreur';
    $('mail-body').textContent = 'Chargement impossible (JARVIS injoignable).';
  }
}

// Clic sur un mail de la liste → ouvre son corps + le marque comme lu (local uniquement)
listEl.addEventListener('click', (e) => {
  const el = e.target.closest('.mail');
  if (!el || !el.dataset.id) return;
  markRead(el.dataset.account, el.dataset.id);
  el.classList.remove('is-unread');
  el.classList.add('is-read');
  openMail(el.dataset.account, el.dataset.id);
});
$('mail-close').addEventListener('click', () => $('mail-modal').classList.remove('open'));
$('mail-overlay').addEventListener('click', () => $('mail-modal').classList.remove('open'));

// ── Service worker (installabilité + offline) ──
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}

loadInbox();
setInterval(loadInbox, 120000); // rafraîchit toutes les 2 min
