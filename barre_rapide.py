# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Barre rapide et raccourci global
==============================================
Ctrl+Alt+J depuis n'importe quelle application fait apparaitre une barre au
centre de l'ecran. On tape, on lit la reponse, Echap referme.

POURQUOI UN RACCOURCI ET PAS UNE FENETRE DE PLUS
Le HUD est une fenetre qu'on va chercher. Une barre invoquee au clavier
arrive sous les doigts, la ou on travaille deja. C'est la difference entre
« ouvrir l'assistant » et « demander quelque chose ».

PAS DE NOUVELLE DEPENDANCE
Le paquet `keyboard` installe un hook clavier global — il voit TOUTES les
frappes, y compris les mots de passe, et reclame souvent l'elevation.
RegisterHotKey de l'API Windows fait exactement ce qu'il faut et rien de
plus : le systeme ne previent QUE pour la combinaison enregistree. Il est
dans ctypes, donc rien a installer.

    MOD_NOREPEAT evite que maintenir la touche declenche en rafale.

LA FENETRE EST CREEE CACHEE AU DEMARRAGE
La creer a la premiere pression couterait une seconde de chargement a chaque
fois — precisement ce qu'une barre rapide ne doit pas coder. Elle existe des
le lancement, masquee ; l'afficher est instantane.

CE MODULE NE FAIT RIEN SANS FENETRE
Sur un systeme sans pywebview ou hors Windows, `demarrer()` renvoie une
raison lisible au lieu d'echouer en vol. Le reste de JARVIS continue.
"""

import ctypes
import sys
import threading

# Combinaison : Ctrl + Alt + J. J comme JARVIS, et libre sous Windows —
# Alt+Espace ouvre le menu systeme, Ctrl+Espace est pris par les IME.
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
VK_J = 0x4A
ID_RACCOURCI = 0xB19E

HAUTEUR_COMPACTE = 66          # la ligne de saisie fait 62 px + la bordure
HAUTEUR_MAX = 520
LARGEUR = 720

# pywebview impose min_size=(200, 100) par defaut. Sans ce reglage, la barre
# refermee gardait 100 px de haut pour 62 px de contenu : une bande noire
# sous le champ, a chaque ouverture. Le minimum doit etre SOUS la hauteur
# compacte, sinon c'est lui qui decide.
TAILLE_MINIMALE = (300, 50)

_fenetre = None
_visible = False
_fil = None


class Api:
    """Expose a la page le strict minimum : se cacher, se redimensionner."""

    def cacher(self):
        masquer()
        return True

    def redimensionner(self, hauteur):
        try:
            h = max(HAUTEUR_COMPACTE, min(int(hauteur), HAUTEUR_MAX))
            _fenetre.resize(LARGEUR, h)
        except Exception:
            pass
        return True


def _geometrie():
    """Centree horizontalement, au tiers superieur — la hauteur des yeux."""
    try:
        from screeninfo import get_monitors
        m = get_monitors()[0]
        larg, haut = m.width, m.height
    except Exception:
        larg, haut = 1920, 1080
    return (larg - LARGEUR) // 2, int(haut * 0.26)


def creer(url_base):
    """Cree la fenetre, masquee. A appeler une seule fois, avant webview.start()."""
    global _fenetre
    if _fenetre is not None:
        return _fenetre
    import webview
    x, y = _geometrie()
    _fenetre = webview.create_window(
        title="JARVIS",
        url="%s/barre.html" % url_base.rstrip("/"),
        width=LARGEUR, height=HAUTEUR_COMPACTE, x=x, y=y,
        frameless=True, easy_drag=False, on_top=True,
        resizable=False, hidden=True, min_size=TAILLE_MINIMALE,
        background_color="#080b10",
        js_api=Api(),
    )
    return _fenetre


def afficher():
    global _visible
    if _fenetre is None:
        return
    try:
        _fenetre.resize(LARGEUR, HAUTEUR_COMPACTE)
        x, y = _geometrie()
        _fenetre.move(x, y)
        _fenetre.show()
        # Vider le champ et y remettre le curseur : rouvrir la barre sur la
        # question precedente obligerait a l'effacer avant chaque usage.
        _fenetre.evaluate_js("window.reinitialiser && window.reinitialiser()")
        _visible = True
    except Exception as e:
        print("[BARRE] affichage impossible : %r" % (e,))


def masquer():
    global _visible
    if _fenetre is None:
        return
    try:
        _fenetre.hide()
        _visible = False
    except Exception:
        pass


def basculer():
    (masquer if _visible else afficher)()


def _boucle_raccourci():
    """
    Fil dedie : RegisterHotKey lie le raccourci au FIL qui l'enregistre, et
    les messages arrivent dans la file de CE fil. L'enregistrer depuis le fil
    principal bloquerait la boucle de pywebview.
    """
    u32 = ctypes.windll.user32
    if not u32.RegisterHotKey(None, ID_RACCOURCI,
                              MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_J):
        # Deja pris par une autre application : le dire, ne pas faire semblant.
        print("[BARRE] Ctrl+Alt+J refuse par Windows (deja utilise ailleurs).")
        return
    print("[BARRE] Ctrl+Alt+J actif.")

    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                    ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p),
                    ("time", ctypes.c_uint),
                    ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long)]

    msg = MSG()
    WM_HOTKEY = 0x0312
    try:
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == ID_RACCOURCI:
                basculer()
    finally:
        u32.UnregisterHotKey(None, ID_RACCOURCI)


def demarrer():
    """Lance l'ecoute du raccourci. Renvoie (actif, raison)."""
    global _fil
    if sys.platform != "win32":
        return False, "raccourci global non implemente hors Windows"
    if _fenetre is None:
        return False, "barre non creee"
    if _fil is not None:
        return True, "deja actif"
    _fil = threading.Thread(target=_boucle_raccourci, daemon=True,
                            name="raccourci-barre")
    _fil.start()
    return True, "Ctrl+Alt+J"


if __name__ == "__main__":
    # Essai isole : la barre seule, sans le reste de JARVIS.
    import webview
    creer("http://localhost:8001")
    ok, raison = None, None

    def _apres_demarrage():
        global ok, raison
        ok, raison = demarrer()
        print("  raccourci : %s (%s)" % (ok, raison))
        afficher()

    webview.start(_apres_demarrage, private_mode=False)
