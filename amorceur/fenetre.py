# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Fenêtre de l'amorceur
===================================
L'interface du programme qu'on télécharge. tkinter, parce qu'il est dans la
bibliothèque standard : cette fenêtre doit s'ouvrir avant que quoi que ce
soit soit installé.

POURQUOI ÇA NE RESSEMBLE PAS À DU TKINTER
Aucun widget par défaut n'est utilisé tel quel. Les reliefs 3D, les gris et
les bordures en creux sont ce qui date un installeur de vingt ans.

LE STYLE DE L'ORBE DE VERRE (1.6)
Mêmes couleurs que le HUD et l'assistant de configuration (src/verre/verre.css
du HUD), même règle de thème : clair le jour, sombre le soir. L'amorceur est
la première image que quelqu'un a de JARVIS. tkinter n'a ni transparence ni
dégradé : l'orbe et les halos sont des disques empilés dont la couleur glisse
d'une teinte à l'autre, les boutons des pilules dessinées.

La barre de progression est dessinée sur un Canvas : ttk.Progressbar suit le
thème du système et jurerait avec le reste.
"""

import datetime
import os
import queue
import sys
import threading
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amorceur


def melange(a, b, t):
    """Couleur entre a et b (« #rrggbb ») : t = 0 donne a, t = 1 donne b.
    C'est le rgba() du CSS posé sur un fond connu, puisque tkinter n'a pas d'alpha."""
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# Les deux thèmes de l'Orbe de verre. Les couples (couleur, alpha) sont les
# rgba() de verre.css, mélangés au fond plus bas.
THEMES = {
    "sombre": dict(fond="#0b0d12", texte="#e8edf5", doux="#9aa7ba", accent="#7fb8f5",
                   sur_accent="#0b0d12", ok="#4ade80", alerte="#ffb454", refus="#ff6b6b",
                   carte=("#ffffff", 0.07), bord=("#ffffff", 0.14), champ=("#000000", 0.25),
                   halo=("#2dd4bf", 0.36), halo2=("#8b5cf6", 0.28),
                   orbe=("#c9e0fa", "#5e8dc4", "#233e66", "#101b2e"), reflet=0.55),
    "clair": dict(fond="#eef2f7", texte="#0e1726", doux="#4a5a70", accent="#1f6fc4",
                  sur_accent="#ffffff", ok="#15803d", alerte="#b45309", refus="#dc2626",
                  carte=("#ffffff", 0.8), bord=("#0e1726", 0.12), champ=("#ffffff", 1.0),
                  halo=("#2dd4bf", 0.24), halo2=("#8b5cf6", 0.14),
                  orbe=("#ffffff", "#e4effb", "#bcd5f0", "#8fb4e0"), reflet=0.9),
}
# Même règle que le HUD en mode « auto » : clair de 7 h à 20 h.
_T = THEMES["clair" if 7 <= datetime.datetime.now().hour < 20 else "sombre"]

FOND, TEXTE, SOURDINE, ACCENT = _T["fond"], _T["texte"], _T["doux"], _T["accent"]
SUR_ACCENT, OK, ALERTE, REFUS = _T["sur_accent"], _T["ok"], _T["alerte"], _T["refus"]
FOND_CARTE, BORD, CHAMP = (melange(FOND, *_T[k]) for k in ("carte", "bord", "champ"))
HALO, HALO2 = melange(FOND, *_T["halo"]), melange(FOND, *_T["halo2"])

POLICE      = ("Segoe UI", 10)
POLICE_GRAS = ("Segoe UI", 10, "bold")
PETITE      = ("Segoe UI", 9)
TITRE       = ("Segoe UI", 18, "bold")
MONO        = ("Consolas", 8)


# ── Dessins ─────────────────────────────────────────────────────────────

def pilule(c, x0, y0, x1, y1, fond, bord=None):
    """Rectangle aux bouts ronds (boutons, barre). `bord` : 1 px autour."""
    for (a0, b0, a1, b1), couleur in (((x0, y0, x1, y1), bord or fond),
                                      ((x0 + 1, y0 + 1, x1 - 1, y1 - 1), fond)):
        r = (b1 - b0) / 2
        c.create_oval(a0, b0, a0 + 2 * r, b1, fill=couleur, outline="")
        c.create_oval(a1 - 2 * r, b0, a1, b1, fill=couleur, outline="")
        c.create_rectangle(a0 + r, b0, a1 - r, b1, fill=couleur, outline="")


def orbe(c, cx, cy, r, pas=36):
    """Le logo : le dégradé radial de l'orbe, décentré en haut à gauche
    (34 %, 28 % comme dans verre.css), fait de disques empilés du bord
    sombre au point lumineux. Chaque disque reste dans l'orbe : le point
    lumineux est à 0,54 r du centre."""
    hx, hy = cx - 0.32 * r, cy - 0.44 * r
    arrets, teintes = (0.0, 0.28, 0.66, 1.0), _T["orbe"]
    for i in range(pas, 0, -1):
        t = i / pas
        k = next(j for j in (1, 2, 3) if t <= arrets[j])
        couleur = melange(teintes[k - 1], teintes[k], (t - arrets[k - 1]) / (arrets[k] - arrets[k - 1]))
        x, y, rr = hx + (cx - hx) * t, hy + (cy - hy) * t, r * t
        c.create_oval(x - rr, y - rr, x + rr, y + rr, fill=couleur, outline="")
    c.create_oval(cx - 0.58 * r, cy - 0.72 * r, cx + 0.02 * r, cy - 0.44 * r,
                  fill=melange(teintes[0], "#ffffff", _T["reflet"]), outline="")
    # Le liseré de verre (--orbe-bord) : sans lui, l'orbe claire se perd sur le fond clair.
    c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=melange(FOND, ACCENT, 0.55), width=1)


def halo(c, cx, cy, rx, ry, couleur, pas=28):
    """Lueur douce : ellipses empilées, du fond (dehors) à la couleur (dedans).
    Le bord extérieur EST le fond : aucune ligne visible là où le Canvas s'arrête."""
    for i in range(pas):
        t = i / pas
        c.create_oval(cx - rx * (1 - t), cy - ry * (1 - t), cx + rx * (1 - t), cy + ry * (1 - t),
                      fill=melange(FOND, couleur, t), outline="")


class Bouton(tk.Canvas):
    """
    Bouton dessiné, en pilule comme ceux de l'Orbe.

    tk.Button impose un relief et une couleur de fond que Windows redéfinit.
    """

    def __init__(self, parent, texte, action, principal=True, largeur=150):
        super().__init__(parent, width=largeur, height=40, bg=FOND,
                         highlightthickness=0, cursor="hand2")
        self.action, self.principal, self.actif = action, principal, True
        self.texte = texte
        self._dessiner()
        self.bind("<Button-1>", self._clic)
        self.bind("<Enter>", lambda e: self._dessiner(survol=True))
        self.bind("<Leave>", lambda e: self._dessiner())

    def _dessiner(self, survol=False):
        self.delete("all")
        l, h = int(self["width"]), int(self["height"])
        if not self.actif:
            fond, bord, encre = FOND_CARTE, BORD, melange(SOURDINE, FOND, 0.45)
        elif self.principal:
            fond = melange(ACCENT, "#ffffff", 0.15) if survol else ACCENT
            bord, encre = fond, SUR_ACCENT
        else:
            fond, bord, encre = FOND_CARTE, (ACCENT if survol else BORD), TEXTE
        pilule(self, 0, 0, l - 1, h - 1, fond, bord)
        self.create_text(l // 2, h // 2, text=self.texte, fill=encre, font=POLICE_GRAS)

    def _clic(self, _):
        if self.actif:
            self.action()

    def activer(self, oui=True):
        self.actif = oui
        self.configure(cursor="hand2" if oui else "arrow")
        self._dessiner()


class Barre(tk.Canvas):
    """Progression dessinée : ttk.Progressbar suivrait le thème du système."""

    def __init__(self, parent, largeur=652):
        super().__init__(parent, width=largeur, height=8, bg=FOND, highlightthickness=0)
        self.largeur = largeur
        self.poser(0.0)

    def poser(self, fraction):
        self.fraction = max(0.0, min(1.0, fraction))
        self.delete("all")
        pilule(self, 0, 0, self.largeur - 1, 7, FOND_CARTE, BORD)
        if self.fraction > 0:
            pilule(self, 0, 0, max(8, self.largeur * self.fraction) - 1, 7, ACCENT)


class Fenetre:
    def __init__(self):
        self.racine = tk.Tk()
        self.racine.title("Installation de J.A.R.V.I.S")
        self.racine.configure(bg=FOND)
        self.racine.geometry("720x520")
        self.racine.resizable(False, False)
        self._centrer(720, 520)

        self.messages = queue.Queue()
        self.dossier = tk.StringVar(value=amorceur.dossier_defaut())
        self.avec_voix = tk.BooleanVar(value=False)
        self.en_cours = False
        self.reussi = False

        self._construire()
        self.racine.after(80, self._vider_file)

    def _centrer(self, l, h):
        e = self.racine.winfo_screenwidth()
        t = self.racine.winfo_screenheight()
        self.racine.geometry("%dx%d+%d+%d" % (l, h, (e - l) // 2, (t - h) // 3))

    # ── Construction ────────────────────────────────────────────────────
    def _construire(self):
        # En-tête : halo teal en haut à droite, comme l'Orbe ; l'orbe en logo.
        haut = tk.Canvas(self.racine, bg=FOND, height=86, highlightthickness=0)
        haut.pack(fill="x")
        halo(haut, 720, 0, 340, 86, HALO)
        # L'ombre bleue de l'orbe (box-shadow de verre.css) : sans elle, l'orbe
        # claire se perd sur le fond clair.
        halo(haut, 34 + 15, 47, 31, 31, melange(FOND, ACCENT, 0.45), pas=16)
        orbe(haut, 34 + 15, 44, 15)
        haut.create_text(34 + 42, 35, text="JARVIS", anchor="w", fill=TEXTE,
                         font=("Segoe UI", 13, "bold"))
        haut.create_text(34 + 42, 55, text="Assistant vocal de bureau", anchor="w",
                         fill=SOURDINE, font=PETITE)

        # Pied : halo violet en bas à gauche, les boutons à droite.
        bas = tk.Canvas(self.racine, bg=FOND, height=72, highlightthickness=0)
        bas.pack(fill="x", side="bottom")
        bas.pack_propagate(False)
        halo(bas, 0, 72, 300, 72, HALO2)
        self.bouton = Bouton(bas, "Installer", self._demarrer)
        self.bouton.pack(side="right", padx=(0, 34), pady=16)
        self.quitter = Bouton(bas, "Annuler", self._fermer, principal=False,
                              largeur=110)
        self.quitter.pack(side="right", padx=(0, 10), pady=16)

        self.corps = tk.Frame(self.racine, bg=FOND)
        self.corps.pack(fill="both", expand=True, padx=34, pady=8)

        self._ecran_accueil()

    def _vider(self):
        for w in self.corps.winfo_children():
            w.destroy()

    def _texte(self, texte, couleur=None, police=POLICE, **pack):
        """Un paragraphe sur le fond. Les Label de tkinter, à plat."""
        tk.Label(self.corps, text=texte, bg=FOND, fg=couleur or SOURDINE, font=police,
                 wraplength=640, justify="left").pack(anchor="w", **pack)

    def _ecran_accueil(self):
        self._vider()
        self._texte("Installer JARVIS", TEXTE, TITRE)
        self._texte("Ce programme télécharge la dernière version publiée, prépare son "
                    "environnement, puis ouvre l'assistant de configuration.",
                    pady=(4, 18))

        python, version, avertissement = amorceur.meilleur_python()
        if python:
            texte = "Python %d.%d détecté" % version
            couleur = OK if not avertissement else ALERTE
        else:
            texte = "Aucun Python 3.10 ou plus récent"
            couleur = REFUS
        carte = tk.Frame(self.corps, bg=FOND_CARTE, highlightthickness=1,
                         highlightbackground=BORD)
        carte.pack(fill="x", pady=(0, 16))
        tk.Label(carte, text=texte, bg=FOND_CARTE, fg=couleur,
                 font=POLICE_GRAS).pack(anchor="w", padx=16, pady=(12, 0))
        detail = (avertissement if avertissement else
                  (python or "Installez Python depuis python.org, puis relancez."))
        tk.Label(carte, text=detail, bg=FOND_CARTE, fg=SOURDINE, font=PETITE,
                 wraplength=600, justify="left").pack(anchor="w", padx=16, pady=(2, 12))
        if not python:
            self.bouton.activer(False)

        self._texte("Dossier d'installation", TEXTE, POLICE_GRAS)
        champ = tk.Entry(self.corps, textvariable=self.dossier, bg=CHAMP,
                         fg=TEXTE, insertbackground=ACCENT, relief="flat",
                         font=("Consolas", 9), highlightthickness=1,
                         highlightbackground=BORD, highlightcolor=ACCENT)
        champ.pack(fill="x", ipady=7, pady=(5, 4))
        self._texte("Pas dans « Program Files » : Windows y refuse l'écriture sans élévation.",
                    police=PETITE, pady=(0, 16))

        case = tk.Checkbutton(
            self.corps, variable=self.avec_voix, bg=FOND, fg=TEXTE,
            activebackground=FOND, activeforeground=TEXTE, selectcolor=FOND_CARTE,
            font=POLICE, highlightthickness=0, bd=0, anchor="w",
            text="Installer aussi la reconnaissance vocale")
        case.pack(anchor="w")
        self._texte("Plusieurs gigaoctets à télécharger. Sans elle, JARVIS fonctionne au "
                    "clavier et par le raccourci Ctrl+Alt+J ; seule la dictée manque.",
                    police=PETITE, padx=(24, 0))

    def _ecran_travail(self):
        self._vider()
        self._texte("Installation en cours", TEXTE, TITRE)
        self.etat = tk.Label(self.corps, text="Préparation…", bg=FOND, fg=SOURDINE,
                             font=POLICE, anchor="w")
        self.etat.pack(anchor="w", pady=(6, 14))
        self.barre = Barre(self.corps)
        self.barre.pack(anchor="w", pady=(0, 16))

        cadre = tk.Frame(self.corps, bg=CHAMP, highlightthickness=1, highlightbackground=BORD)
        cadre.pack(fill="both", expand=True)
        self.journal = tk.Text(cadre, bg=CHAMP, fg=SOURDINE, font=MONO,
                               relief="flat", wrap="none", height=12,
                               highlightthickness=0, padx=12, pady=10)
        self.journal.pack(fill="both", expand=True)
        self.journal.configure(state="disabled")

    def _ecran_fin(self, ok, message):
        self._vider()
        self._texte("C'est installé" if ok else "L'installation a échoué",
                    TEXTE if ok else REFUS, TITRE)
        self._texte(("JARVIS est installé dans %s.\n\nL'assistant de configuration va "
                     "s'ouvrir : il vous demandera ce que vous voulez activer." % message)
                    if ok else str(message), pady=(8, 0))
        self.bouton.texte = "Configurer" if ok else "Fermer"
        self.bouton.action = self._terminer if ok else self._fermer
        self.bouton.activer(True)
        if ok:
            self.quitter.texte = "Fermer"
            self.quitter.action = self._fermer
            self.quitter._dessiner()
        else:
            self.quitter.pack_forget()      # « Fermer » une seule fois : deux boutons identiques ne servent à rien

    # ── Déroulé ─────────────────────────────────────────────────────────
    def _demarrer(self):
        if self.en_cours:
            return
        self.en_cours = True
        self.bouton.activer(False)
        self._ecran_travail()
        threading.Thread(target=self._travailler, daemon=True).start()

    def _travailler(self):
        """
        Dans un fil : tkinter se fige si on télécharge depuis le sien.

        Rien ne touche à l'interface ici — tout passe par une file, que le fil
        graphique vide. Modifier un widget depuis un autre fil marche parfois,
        et plante le reste du temps.
        """
        try:
            ok, message = amorceur.installer(
                self.dossier.get().strip() or amorceur.dossier_defaut(),
                avec_voix=self.avec_voix.get(),
                journal=lambda l: self.messages.put(("journal", l)),
                avancement=lambda f, t: self.messages.put(("avance", (f, t))))
        except Exception as e:
            ok, message = False, "%s : %s" % (type(e).__name__, e)
        self.messages.put(("fin", (ok, message)))

    def _vider_file(self):
        try:
            while True:
                genre, charge = self.messages.get_nowait()
                if genre == "journal":
                    self.journal.configure(state="normal")
                    self.journal.insert("end", str(charge) + "\n")
                    self.journal.see("end")
                    self.journal.configure(state="disabled")
                elif genre == "avance":
                    fraction, texte = charge
                    self.barre.poser(fraction)
                    self.etat.configure(text=texte)
                elif genre == "fin":
                    ok, message = charge
                    self.reussi = ok
                    self.en_cours = False
                    self._ecran_fin(ok, message)
        except queue.Empty:
            pass
        self.racine.after(80, self._vider_file)

    def _terminer(self):
        amorceur.lancer_assistant(self.dossier.get().strip())
        self.racine.destroy()

    def _fermer(self):
        if self.en_cours:
            return          # ne pas laisser fermer au milieu d'une installation
        self.racine.destroy()

    def ouvrir(self):
        self.racine.protocol("WM_DELETE_WINDOW", self._fermer)
        self.racine.mainloop()
        return self.reussi


def ouvrir():
    return Fenetre().ouvrir()


if __name__ == "__main__":
    ouvrir()
