# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Orbe flottante
============================
Une petite orbe de verre (1.5 : la même que le HUD « Orbe de verre », claire
le jour, sombre la nuit), toujours au-dessus des autres fenêtres, en bas à
droite de l'écran. Elle respire au repos, prend un anneau quand JARVIS
réfléchit, vibre quand il parle (état lu sur /api/events, le flux du HUD).
Clic : la barre rapide. Glisser : la déplacer. Double-clic : cachée jusqu'au
prochain démarrage.

UNE FENÊTRE WINDOWS, PAS UNE PAGE WEB
Une fenêtre pywebview « transparente » ne l'est pas : WinForms peint dessous
une photo figée de ce qu'il y avait derrière à sa création (mesuré le 15/10
devant une fenêtre rouge : aucun rouge aux coins). Dès que l'arrière-plan
change, on voit un rectangle. Ici, une fenêtre « layered » reçoit une image
avec sa transparence pixel par pixel (UpdateLayeredWindow, BGRA prémultiplié) :
rien d'autre que l'orbe n'est dessiné. ctypes, Pillow et numpy, déjà là.

JAMAIS PAR-DESSUS UN JEU
Un fil regarde toutes les deux secondes si un jeu ou une vidéo occupe l'écran
(plein_ecran_actif) et cache l'orbe tant que c'est le cas.

Désactivable : JARVIS_ORBE=0 dans l'environnement.
"""

import ctypes
import functools
import json
import math
import os
import threading
import time
import urllib.request
from ctypes import wintypes

TAILLE = 132            # pixels logiques
MARGE = 18
IMAGES_PAR_SECONDE = 20
PERIODE_PLEIN_ECRAN = 2.0
TEINTE = 186            # teinte des particules d'avant la 1.5 (JARVIS_ORBE_TEINTE) : plus utilisée par le verre

_url_evenements = None
_etat = {"nom": "idle", "depuis": 0.0}
_hwnd = None
_cachee_par_lui = False   # double-clic : on ne la remontre plus d'ici le prochain démarrage
_cachee_plein_ecran = False

# Chargées au démarrage, pas à l'import : JARVIS doit rester importable hors Windows (_test_portabilite).
user32 = gdi32 = None


def _charger_win32():
    global user32, gdi32
    if user32 is None and os.name == "nt":
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    return user32 is not None


def active():
    return os.environ.get("JARVIS_ORBE", "1") != "0"


# ── Dessin : l'orbe de verre (1.5) : la même que celle du HUD « Orbe de verre », claire le jour, sombre la nuit ──
PALETTES = {
    "clair": ((0.0, (255, 255, 255)), (0.30, (228, 239, 251)), (0.66, (188, 213, 240)), (1.0, (143, 180, 224))),
    "sombre": ((0.0, (201, 224, 250)), (0.28, (94, 141, 196)), (0.66, (35, 62, 102)), (1.0, (16, 27, 46))),
}
ACCENTS = {"clair": (31, 111, 196), "sombre": (127, 184, 245)}


def theme_du_moment(heure=None):
    """« clair » de 7 h à 20 h, « sombre » sinon, comme le HUD ; JARVIS_ORBE_THEME=clair|sombre l'impose."""
    choix = os.environ.get("JARVIS_ORBE_THEME", "auto")
    if choix in PALETTES:
        return choix
    h = time.localtime().tm_hour if heure is None else heure
    return "clair" if 7 <= h < 20 else "sombre"


def rayon(taille, t, intensite):
    """Rayon de la sphère à l'instant t : elle respire, et vibre quand JARVIS parle."""
    return taille * (.30 + math.sin(t * 1.6) * .025 + intensite * .035 * math.sin(t * 9))


@functools.lru_cache(maxsize=64)
def _sphere(diametre, theme):
    """La sphère de verre (numpy) : dégradé éclairé d'en haut à gauche, reflet, ombre interne vers le bas.
    Opaque dedans ; seul le bord (un pixel) est adouci. Rien autour : pas de halo, donc pas de voile."""
    import numpy as np
    from PIL import Image

    n = diametre
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) + 0.5
    r = n / 2
    dx, dy = (x - r) / r, (y - r) / r
    dist = np.sqrt(dx * dx + dy * dy)
    lum = np.sqrt((dx + 0.32) ** 2 + (dy + 0.44) ** 2) / 1.45
    positions = [p for p, _ in PALETTES[theme]]
    rgb = np.stack([np.interp(lum, positions, [c[i] for _, c in PALETTES[theme]]) for i in range(3)], axis=-1)
    hx, hy = (dx + 0.30) / 0.30, (dy + 0.58) / 0.13
    reflet = np.clip(1 - (hx * hx + hy * hy), 0, 1) ** 0.6 * (0.9 if theme == "clair" else 0.55)
    rgb = rgb * (1 - reflet[..., None]) + 255 * reflet[..., None]
    ombre = np.clip((dist - 0.55) / 0.45, 0, 1) * np.clip(dy, 0, 1) * (0.18 if theme == "clair" else 0.35)
    rgb = rgb * (1 - ombre[..., None])
    alpha = np.clip((1 - dist) * r, 0, 1)
    return Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8), "RGBA")


def rendu(taille, t, intensite, teinte=TEINTE, theme=None):
    """
    L'image RGBA d'un instant : la sphère de verre (opaque, bord adouci d'un pixel), un disque à alpha 1/255,
    invisible, pour que la souris attrape l'orbe autour, et un arc quand JARVIS réfléchit ou parle.
    `teinte` (JARVIS_ORBE_TEINTE) servait aux particules d'avant la 1.5 : gardée pour ne casser aucun appel.
    """
    from PIL import Image, ImageDraw

    theme = theme or theme_du_moment()
    img = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    cx = cy = taille / 2
    r = rayon(taille, t, intensite)
    ImageDraw.Draw(img).ellipse((cx - r * 1.35, cy - r * 1.35, cx + r * 1.35, cy + r * 1.35), fill=(0, 0, 0, 1))
    diametre = max(8, int(round(r * 2)))
    img.alpha_composite(_sphere(diametre, theme), (int(round(cx - diametre / 2)), int(round(cy - diametre / 2))))
    if intensite > .05:
        a0 = math.degrees(t * 2.2)
        r1 = r * 1.22
        ImageDraw.Draw(img).arc((cx - r1, cy - r1, cx + r1, cy + r1), a0, a0 + 109,
                                fill=ACCENTS[theme] + (255,), width=max(2, round(taille / 75)))
    return img


def _octets_bgra(img):
    """BGRA prémultiplié, ce qu'attend UpdateLayeredWindow. Non prémultiplié, un bord adouci devenait un
    liseré clair : c'est le « voile » du 15/10, et la raison pour laquelle l'orbe n'avait que des pixels opaques."""
    import numpy as np
    a = np.asarray(img.convert("RGBA"), dtype=np.uint16)
    rgb = a[..., :3] * a[..., 3:4] // 255
    return np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], a[..., 3]]).astype(np.uint8).tobytes()


# ── État de JARVIS (même flux que le HUD et la barre rapide) ──────────────

def _changer_etat(nom):
    _etat["nom"], _etat["depuis"] = nom, time.time()


def lire_evenement(ligne):
    """Une ligne « data: {...} » du flux SSE → nouvel état, ou None si elle ne change rien."""
    if not ligne.startswith("data:"):
        return None
    try:
        d = json.loads(ligne[5:])
    except ValueError:
        return None
    t = d.get("type")
    if isinstance(t, str) and t.startswith("agent-state:"):
        return t[len("agent-state:"):]
    if t is None and d.get("role") == "assistant" and d.get("text"):
        return "idle" if d.get("done") else "responding"
    return None


def _suivre_etat():
    while True:
        try:
            with urllib.request.urlopen(_url_evenements, timeout=120) as flux:
                for brut in flux:
                    nom = lire_evenement(brut.decode("utf-8", "replace").strip())
                    if nom:
                        _changer_etat(nom)
        except Exception:
            pass
        time.sleep(5)   # HUD redémarré, coupure : on se reconnecte


# ── Fenêtre Windows « layered » ───────────────────────────────────────────

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x8, 0x80, 0x8000000
CS_DBLCLKS = 0x8
WM_DESTROY, WM_TIMER, WM_MOUSEMOVE = 0x2, 0x113, 0x200
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_LBUTTONDBLCLK = 0x201, 0x202, 0x203
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
SWP_NOSIZE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x4, 0x10
ULW_ALPHA, AC_SRC_ALPHA = 0x2, 0x1
SPI_GETWORKAREA = 0x30

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def _declarer_types():
    """Sous Python 64 bits, ctypes rend un int 32 bits par défaut : un handle de fenêtre ou de DC y serait tronqué."""
    H = ctypes.c_void_p
    for f, res, args in (
            (user32.CreateWindowExW, wintypes.HWND, (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                     wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)),
            (user32.DefWindowProcW, LRESULT, (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
            (user32.GetDC, H, (wintypes.HWND,)),
            (user32.ReleaseDC, ctypes.c_int, (wintypes.HWND, H)),
            (user32.LoadCursorW, H, (wintypes.HINSTANCE, H)),
            (user32.UpdateLayeredWindow, wintypes.BOOL, (wintypes.HWND, H, ctypes.c_void_p, ctypes.c_void_p, H,
                                                         ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)),
            (gdi32.CreateCompatibleDC, H, (H,)),
            (gdi32.CreateDIBSection, H, (H, ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, H, wintypes.DWORD)),
            (gdi32.SelectObject, H, (H, H)),
            (gdi32.DeleteObject, wintypes.BOOL, (H,)),
            (gdi32.DeleteDC, wintypes.BOOL, (H,)),
            (ctypes.windll.kernel32.GetModuleHandleW, wintypes.HMODULE, (wintypes.LPCWSTR,)),
    ):
        f.restype, f.argtypes = res, args


def _taille_physique():
    """132 pixels logiques à l'échelle de l'écran principal (225 % ici : 297 pixels)."""
    try:
        echelle = user32.GetDpiForSystem() / 96
    except Exception:
        echelle = 1
    return max(64, round(TAILLE * echelle)), echelle


def _position(taille, echelle):
    """En bas à droite de la zone de travail (barre des tâches exclue), en pixels physiques."""
    zone = wintypes.RECT()
    user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(zone), 0)
    m = round(MARGE * echelle)
    return zone.right - taille - m, zone.bottom - taille - m


def _boucle_fenetre():
    """Crée la fenêtre et tourne sa boucle de messages ; tout ce qui la touche se passe dans ce fil."""
    global _hwnd
    _declarer_types()
    try:
        user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))   # par moniteur v2 : pixels réels
    except AttributeError:
        pass   # Windows trop ancien : l'échelle système suffit
    taille, echelle = _taille_physique()
    x0, y0 = _position(taille, echelle)
    souris = {"bas": None, "fenetre": None, "bouge": False, "clic": None}

    def wndproc(hwnd, msg, wp, lp):
        if msg == WM_TIMER:
            _dessiner(hwnd, taille)
            return 0
        if msg == WM_LBUTTONDOWN:
            pt = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(pt))
            r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
            souris.update(bas=(pt.x, pt.y), fenetre=(r.left, r.top), bouge=False)
            user32.SetCapture(hwnd)
            return 0
        if msg == WM_MOUSEMOVE and souris["bas"]:
            pt = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(pt))
            dx, dy = pt.x - souris["bas"][0], pt.y - souris["bas"][1]
            if souris["bouge"] or abs(dx) + abs(dy) > 4:
                souris["bouge"] = True
                user32.SetWindowPos(hwnd, None, souris["fenetre"][0] + dx, souris["fenetre"][1] + dy, 0, 0,
                                    SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            return 0
        if msg == WM_LBUTTONUP:
            user32.ReleaseCapture()
            clic = souris["bas"] and not souris["bouge"]
            souris.update(bas=None)
            if clic:
                # Attendre un instant : un double-clic ne doit pas d'abord ouvrir la barre.
                jeton = object()
                souris["clic"] = jeton
                threading.Timer(.28, lambda: souris["clic"] is jeton and _ouvrir_barre()).start()
            return 0
        if msg == WM_LBUTTONDBLCLK:
            souris["clic"] = None
            cacher()
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wp, lp)

    proc = WNDPROC(wndproc)      # gardée en vie tant que la boucle tourne
    hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
    classe = WNDCLASSW(style=CS_DBLCLKS, lpfnWndProc=proc, hInstance=hinst,
                       hCursor=user32.LoadCursorW(None, ctypes.c_void_p(32649)),   # main : on peut cliquer
                       lpszClassName="JarvisOrbe")
    user32.RegisterClassW(ctypes.byref(classe))
    _hwnd = user32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                                   "JarvisOrbe", "JARVIS orbe", WS_POPUP, x0, y0, taille, taille,
                                   None, None, hinst, None)
    _dessiner(_hwnd, taille)
    if not _cachee_plein_ecran:
        user32.ShowWindow(_hwnd, SW_SHOWNOACTIVATE)
    user32.SetTimer(_hwnd, 1, int(1000 / IMAGES_PAR_SECONDE), None)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


_intensite = [0.0]


def _dessiner(hwnd, taille):
    if _cachee_par_lui or _cachee_plein_ecran:
        return   # cachée : on ne dessine pas pour rien
    nom = _etat["nom"]
    if nom != "idle" and time.time() - _etat["depuis"] > 60:
        _changer_etat("idle")   # un état jamais clos (flux coupé) ne doit pas l'agiter pour toujours
    cible = {"responding": 1.0, "thinking": .65}.get(_etat["nom"], 0.0)
    _intensite[0] += (cible - _intensite[0]) * .12
    try:
        teinte = float(os.environ.get("JARVIS_ORBE_TEINTE", TEINTE))
    except ValueError:
        teinte = TEINTE
    img = rendu(taille, time.time(), _intensite[0], teinte)
    _poser_image(hwnd, img)


def _poser_image(hwnd, img):
    """Donne l'image à la fenêtre avec sa transparence (BGRA prémultiplié, _octets_bgra)."""
    w, h = img.size
    ecran = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(ecran)
    bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
    bits = ctypes.c_void_p()
    dib = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    ancien = gdi32.SelectObject(mem, dib)
    donnees = _octets_bgra(img)
    ctypes.memmove(bits, donnees, len(donnees))
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    pos, taille, src = wintypes.POINT(r.left, r.top), wintypes.SIZE(w, h), wintypes.POINT(0, 0)
    melange = BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
    user32.UpdateLayeredWindow(hwnd, ecran, ctypes.byref(pos), ctypes.byref(taille), mem, ctypes.byref(src), 0,
                               ctypes.byref(melange), ULW_ALPHA)
    gdi32.SelectObject(mem, ancien)
    gdi32.DeleteObject(dib)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(None, ecran)


def _ouvrir_barre():
    try:
        import barre_rapide
        barre_rapide.afficher()
    except Exception as e:
        print("[ORBE] barre rapide : %r" % (e,))


def cacher():
    global _cachee_par_lui
    _cachee_par_lui = True
    if _hwnd:
        user32.ShowWindowAsync(_hwnd, SW_HIDE)


# ── Plein écran ───────────────────────────────────────────────────────────

class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT), ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]


def plein_ecran_actif():
    """
    Un jeu ou une vidéo occupe-t-il l'écran ? Oui si Windows le dit lui-même (l'état qui coupe les notifications :
    occupé, Direct3D plein écran, présentation), ou si une fenêtre NON agrandie couvre tout son écran (plein écran
    fenêtré d'un jeu). Une fenêtre simplement agrandie ne compte pas : celles d'Electron, l'app Claude comprise,
    débordent de l'écran une fois agrandies et passaient pour du plein écran (orbe cachée en permanence).
    """
    if not _charger_win32():
        return False
    etat = ctypes.c_int(0)
    if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(etat)) == 0 and etat.value in (2, 3, 4):
        return True
    hwnd = user32.GetForegroundWindow()
    if not hwnd or hwnd in (user32.GetDesktopWindow(), user32.GetShellWindow(), _hwnd) or user32.IsZoomed(hwnd):
        return False
    classe = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, classe, 64)
    if classe.value in ("Progman", "WorkerW", "Shell_TrayWnd"):
        return False
    rect = _RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    info = _MONITORINFO(cbSize=ctypes.sizeof(_MONITORINFO))
    if not user32.GetMonitorInfoW(user32.MonitorFromWindow(hwnd, 2), ctypes.byref(info)):
        return False
    m = info.rcMonitor
    return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom


def _surveiller_plein_ecran():
    global _cachee_plein_ecran
    while True:
        time.sleep(PERIODE_PLEIN_ECRAN)
        if _cachee_par_lui or not _hwnd:
            continue
        try:
            plein = plein_ecran_actif()
        except Exception:
            continue
        if plein and not _cachee_plein_ecran:
            _cachee_plein_ecran = True
            user32.ShowWindowAsync(_hwnd, SW_HIDE)
        elif not plein and _cachee_plein_ecran:
            _cachee_plein_ecran = False
            user32.ShowWindowAsync(_hwnd, SW_SHOWNOACTIVATE)


# ── Démarrage (appelé par main2.py) ───────────────────────────────────────

def creer(url_base):
    """Prépare l'orbe (avant webview.start, comme la barre rapide) ; renvoie None si elle est désactivée."""
    global _url_evenements
    if not active() or not _charger_win32():
        return None
    _url_evenements = "%s/api/events" % url_base.rstrip("/")
    return _url_evenements


def demarrer():
    """Après le lancement de la boucle graphique. Renvoie (actif, raison)."""
    if _url_evenements is None:
        return False, "orbe désactivée (JARVIS_ORBE=0)"
    for cible, nom in ((_boucle_fenetre, "orbe-fenetre"), (_suivre_etat, "orbe-etat"),
                       (_surveiller_plein_ecran, "orbe-plein-ecran")):
        threading.Thread(target=cible, name=nom, daemon=True).start()
    return True, "orbe en bas à droite, cachée pendant les jeux en plein écran"
