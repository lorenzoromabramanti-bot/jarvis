# -*- coding: utf-8 -*-
"""
Barre rapide : l'ouverture ne montre jamais un panneau vide.

Le 16/11/2026 la barre s'est ouverte VIDE (bonne taille, rien de peint). Cause exacte inconnue : afficher() sonde donc la
page, la recharge (cachee) si elle ne repond pas ou si la barre est restee fermee longtemps, et montre une phrase si rien
ne revient. Une fausse fenetre remplace pywebview : aucune fenetre n'est ouverte.

    python _test_barre_rapide.py
"""
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import barre_rapide as b  # noqa: E402

b.JOURNAL = os.path.join(tempfile.mkdtemp(prefix="barre-test-"), "barre_rapide.log")
b.PAS_ATTENTE = 0.01
b.ATTENTE_PAGE = 0.3
b._url_page = "http://localhost:8001/barre.html"
b._geometrie = lambda: (10, 20)


class FausseFenetre:
    """prete : la page repond. apres_rechargement : ce que devient `prete` quand load_url est appele (None = rien)."""

    def __init__(self, prete=True, apres_rechargement=True, js_bloque=False, js_leve=False):
        self.prete, self.apres, self.js_bloque, self.js_leve = prete, apres_rechargement, js_bloque, js_leve
        self.appels = []

    def resize(self, largeur, hauteur):
        self.appels.append(("resize", hauteur))

    def move(self, x, y):
        self.appels.append(("move", x, y))

    def show(self):
        self.appels.append("show")

    def hide(self):
        self.appels.append("hide")

    def load_url(self, url):
        self.appels.append(("load_url", url))
        if self.apres is not None:
            self.prete = self.apres

    def load_html(self, html):
        self.appels.append("load_html")
        self.prete = False

    def evaluate_js(self, code):
        if self.js_leve:
            raise RuntimeError("fenetre detruite")
        if self.js_bloque:
            time.sleep(5)
        if code.startswith("typeof"):
            return "function" if self.prete else "undefined"
        self.appels.append("reinitialiser")


def ouvrir(fen, ferme_depuis=5, visible=False):
    b._fenetre, b._visible = fen, visible
    b._fermee_a = time.monotonic() - ferme_depuis
    debut = time.monotonic()
    b.afficher()
    return time.monotonic() - debut


def noms(fen):
    return [a if isinstance(a, str) else a[0] for a in fen.appels]


# 1. Page vivante, fermee depuis peu : ouverture directe, aucun rechargement.
f = FausseFenetre()
ouvrir(f, ferme_depuis=5)
assert "load_url" not in noms(f), f.appels
assert noms(f) == ["resize", "resize", "move", "show", "reinitialiser"], noms(f)
assert [a[1] for a in f.appels if a[0] == "resize"] == [b.HAUTEUR_COMPACTE + 1, b.HAUTEUR_COMPACTE], \
    "le +1 px force WebView2 a recalculer ses limites"
assert b._visible is True

# 2. Page vivante mais barre fermee depuis longtemps : rechargement CACHE (avant show), puis ouverture.
f = FausseFenetre()
ouvrir(f, ferme_depuis=b.RECHARGE_APRES + 60)
assert noms(f).count("load_url") == 1 and noms(f).index("load_url") < noms(f).index("show"), noms(f)
premiere = f.appels[noms(f).index("load_url")][1]
assert premiere.startswith("http://localhost:8001/barre.html?r="), premiere
assert noms(f)[-1] == "reinitialiser"
# Deux rechargements de suite : jamais deux fois la meme adresse (load_url vers l'adresse deja affichee ne redevient
# jamais « pret » pour pywebview : mesure du 16/11).
ouvrir(f, ferme_depuis=b.RECHARGE_APRES + 60)
adresses = [a[1] for a in f.appels if a[0] == "load_url"]
assert len(adresses) == 2 and adresses[0] != adresses[1], adresses

# 3. Deja visible (appel direct de main2) : pas de rechargement meme si la derniere fermeture est ancienne.
f = FausseFenetre()
ouvrir(f, ferme_depuis=b.RECHARGE_APRES + 60, visible=True)
assert "load_url" not in noms(f), noms(f)

# 4. Page absente (serveur demarre apres JARVIS) puis revenue : rechargee, montree, jamais de phrase d'erreur.
f = FausseFenetre(prete=False, apres_rechargement=True)
ouvrir(f, ferme_depuis=5)
assert noms(f).count("load_url") == 1 and "load_html" not in noms(f) and noms(f)[-1] == "reinitialiser", noms(f)

# 5. Page qui ne revient pas : une phrase a la place du panneau vide, ouverture rapide, prochaine ouverture reessaie.
f = FausseFenetre(prete=False, apres_rechargement=False)
duree = ouvrir(f, ferme_depuis=5)
assert "show" in noms(f) and noms(f)[-1] == "load_html" and "reinitialiser" not in noms(f), noms(f)
assert duree < 3, "afficher() ne doit pas bloquer le raccourci (%.1f s)" % duree
assert "ne répond pas" in b.PAGE_ABSENTE and "<body" in b.PAGE_ABSENTE
f.apres = True                                    # le serveur est revenu : la page « absente » compte comme non prete
ouvrir(f, ferme_depuis=5)
assert noms(f).count("load_url") == 2 and noms(f)[-1] == "reinitialiser", noms(f)

# 6. JavaScript mort (evaluate_js ne rend jamais la main) : la sonde rend la main dans son delai.
f = FausseFenetre(js_bloque=True)
b._fenetre = f
debut = time.monotonic()
assert b._page_prete(0.2) is False
assert time.monotonic() - debut < 1.0, "la sonde doit respecter son delai"

# 7. Fenetre detruite (evaluate_js leve) : pas d'exception, trace dans le journal.
f = FausseFenetre(js_leve=True, apres_rechargement=None)
ouvrir(f, ferme_depuis=5)
assert os.path.exists(b.JOURNAL)

# 8. masquer() note l'heure de fermeture, rend la barre invisible.
f = FausseFenetre()
b._fenetre, b._visible, b._fermee_a = f, True, 0.0
b.masquer()
assert b._visible is False and time.monotonic() - b._fermee_a < 1 and noms(f) == ["hide"]

# 9. Le journal est tenu et ne grossit pas sans fin.
for i in range(3):
    b._noter("ligne %d" % i)
assert open(b.JOURNAL, encoding="utf-8").read().count("ligne") == 3
with open(b.JOURNAL, "a", encoding="utf-8") as fichier:
    fichier.write("x" * 210000)
b._noter("apres rotation")
assert os.path.exists(b.JOURNAL + ".1") and os.path.getsize(b.JOURNAL) < 1000

# 10. Aucun fil de sonde ne reste bloque apres les essais normaux (le bloque du cas 6 est un fil daemon).
time.sleep(0.1)
assert all(t.daemon for t in threading.enumerate() if t.name == "sonde-barre")

print("  Barre rapide : conforme.")
