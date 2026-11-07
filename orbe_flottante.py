# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Orbe flottante
============================
Une petite orbe, toujours au-dessus des autres fenêtres, en bas à droite de
l'écran. Elle respire au repos, tourne plus vite avec un anneau quand JARVIS
réfléchit, ondule quand il parle (état lu sur /api/events, le flux du HUD).
Clic : la barre rapide. Glisser : la déplacer. Double-clic : cachée jusqu'au
prochain démarrage.

UNE FENÊTRE WINDOWS, PAS UNE PAGE WEB
Une fenêtre pywebview « transparente » ne l'est pas : WinForms peint dessous
une photo figée de ce qu'il y avait derrière à sa création (mesuré le 15/10
devant une fenêtre rouge : aucun rouge aux coins). Dès que l'arrière-plan
change, on voit un rectangle. Ici, une fenêtre « layered » reçoit une image
avec sa transparence pixel par pixel (UpdateLayeredWindow) : rien d'autre que
les particules n'est dessiné. ctypes et Pillow, déjà là : rien à installer.

JAMAIS PAR-DESSUS UN JEU
Un fil regarde toutes les deux secondes si un jeu ou une vidéo occupe l'écran
(plein_ecran_actif) et cache l'orbe tant que c'est le cas.

Désactivable : JARVIS_ORBE=0 dans l'environnement.
"""

import ctypes
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
TEINTE = 186            # cyan du thème « classic » ; JARVIS_ORBE_TEINTE pour une autre (140 neon, 45 aurum)
N_POINTS = 520

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


# ── Dessin ────────────────────────────────────────────────────────────────

def _points():
    """Points répartis sur la sphère (Fibonacci) : projetés, ils se serrent sur le bord, comme la sphère creuse du HUD."""
    pts = []
    for i in range(N_POINTS):
        y = 1 - (i + .5) / N_POINTS * 2
        r = math.sqrt(1 - y * y)
        a = i * 2.39996
        pts.append((math.cos(a) * r, y, math.sin(a) * r, (i * 7.31) % 6.28))
    return pts


_POINTS = _points()


def _hsl(h, s, l):
    """(r, g, b) 0-255 depuis une teinte en degrés, saturation et luminosité 0-1."""
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


def rendu(taille, t, intensite, teinte=TEINTE):
    """
    L'image RGBA d'un instant. Fond transparent, particules opaques (rien de semi-transparent : pas de voile),
    et un disque à alpha 1/255, invisible, pour que la souris attrape l'orbe entre les particules.
    """
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = taille / 2
    souffle = math.sin(t * 1.6) * .025
    rayon = taille * (.30 + souffle + intensite * .03)
    d.ellipse((cx - rayon * 1.35, cy - rayon * 1.35, cx + rayon * 1.35, cy + rayon * 1.35), fill=(0, 0, 0, 1))
    vitesse = .25 + intensite * 1.2
    ca, sa = math.cos(t * vitesse), math.sin(t * vitesse)
    cb, sb = math.cos(.42), math.sin(.42)
    epais = max(1, round(taille / 150))
    for px, py, pz, ph in _POINTS:
        onde = 1 + intensite * .07 * math.sin(t * 9 + ph * 3)
        x, z = px * ca + pz * sa, -px * sa + pz * ca
        y = py * cb - z * sb
        z = py * sb + z * cb
        bord = 1 - abs(z)
        avant = (z + 1) / 2
        r, g, b = _hsl(teinte, 1, .30 + avant * .30 + bord * .30)
        sx, sy = round(cx + x * rayon * onde), round(cy + y * rayon * onde)
        e = epais * (2 if bord > .6 else 1)
        d.rectangle((sx, sy, sx + e - 1, sy + e - 1), fill=(r, g, b, 255))
    if intensite > .05:
        a0 = math.degrees(t * 2.2)
        r1 = rayon * 1.28
        d.arc((cx - r1, cy - r1, cx + r1, cy + r1), a0, a0 + 109,
              fill=_hsl(teinte, 1, .25 + intensite * .40) + (255,), width=2 * epais)
    return img


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
    """Donne l'image à la fenêtre avec sa transparence (BGRA prémultiplié : nos pixels sont opaques ou d'alpha ~0)."""
    w, h = img.size
    ecran = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(ecran)
    bmi = BITMAPINFOHEADER(biSize=ctypes.sizeof(BITMAPINFOHEADER), biWidth=w, biHeight=-h, biPlanes=1, biBitCount=32)
    bits = ctypes.c_void_p()
    dib = gdi32.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    ancien = gdi32.SelectObject(mem, dib)
    donnees = img.tobytes("raw", "BGRA")
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
