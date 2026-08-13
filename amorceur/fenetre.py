# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Fenêtre de l'amorceur
===================================
L'interface du programme qu'on télécharge. tkinter, parce qu'il est dans la
bibliothèque standard : cette fenêtre doit s'ouvrir avant que quoi que ce
soit soit installé.

POURQUOI ÇA NE RESSEMBLE PAS À DU TKINTER
Aucun widget par défaut n'est utilisé tel quel. Les reliefs 3D, les gris et
les bordures en creux sont ce qui date un installeur de vingt ans. Tout est
à plat, sombre, avec la teinte du HUD — l'amorceur est la première image que
quelqu'un a de JARVIS.

La barre de progression est dessinée sur un Canvas : ttk.Progressbar suit le
thème du système et jurerait avec le reste.
"""

import os
import queue
import sys
import threading
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import amorceur

FOND       = "#080b10"
FOND_CARTE = "#0e131b"
FOND_HAUT  = "#0b1017"
ACCENT     = "#35e7e0"
TEXTE      = "#d6e6e8"
SOURDINE   = "#6b858a"
ALERTE     = "#ffb454"
REFUS      = "#ff6b6b"

POLICE     = ("Segoe UI", 10)
POLICE_GRAS= ("Segoe UI", 10, "bold")
TITRE      = ("Segoe UI", 17, "bold")
MONO       = ("Consolas", 8)


class Bouton(tk.Canvas):
    """
    Bouton dessiné.

    tk.Button impose un relief et une couleur de fond que Windows redéfinit.
    Le dessiner évite d'avoir un rectangle gris au milieu d'une fenêtre noire.
    """

    def __init__(self, parent, texte, action, principal=True, largeur=150):
        super().__init__(parent, width=largeur, height=38, bg=FOND_HAUT,
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
            fond, bord, encre = FOND_HAUT, "#1a2129", "#3a4a50"
        elif self.principal:
            fond = "#5cf0ea" if survol else ACCENT
            bord, encre = fond, "#05161b"
        else:
            fond, bord = FOND_HAUT, ("#3a4a50" if survol else "#1f2831")
            encre = TEXTE if survol else SOURDINE
        self.create_rectangle(1, 1, l - 2, h - 2, fill=fond, outline=bord, width=1)
        self.create_text(l // 2, h // 2, text=self.texte, fill=encre,
                         font=POLICE_GRAS)

    def _clic(self, _):
        if self.actif:
            self.action()

    def activer(self, oui=True):
        self.actif = oui
        self.configure(cursor="hand2" if oui else "arrow")
        self._dessiner()


class Barre(tk.Canvas):
    """Progression dessinée : ttk.Progressbar suivrait le thème du système."""

    def __init__(self, parent, largeur=620):
        super().__init__(parent, width=largeur, height=5, bg="#131a22",
                         highlightthickness=0)
        self.largeur = largeur
        self.fraction = 0.0

    def poser(self, fraction):
        self.fraction = max(0.0, min(1.0, fraction))
        self.delete("all")
        if self.fraction > 0:
            self.create_rectangle(0, 0, self.largeur * self.fraction, 5,
                                  fill=ACCENT, outline="")


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
        haut = tk.Frame(self.racine, bg=FOND_HAUT, height=86)
        haut.pack(fill="x")
        haut.pack_propagate(False)
        tk.Label(haut, text="J · A · R · V · I · S", bg=FOND_HAUT, fg=ACCENT,
                 font=("Consolas", 12)).pack(anchor="w", padx=34, pady=(24, 0))
        self.sous_titre = tk.Label(
            haut, text="Assistant vocal de bureau", bg=FOND_HAUT, fg=SOURDINE,
            font=("Segoe UI", 9))
        self.sous_titre.pack(anchor="w", padx=34)

        self.corps = tk.Frame(self.racine, bg=FOND)
        self.corps.pack(fill="both", expand=True, padx=34, pady=26)

        bas = tk.Frame(self.racine, bg=FOND_HAUT, height=68)
        bas.pack(fill="x", side="bottom")
        bas.pack_propagate(False)
        self.bouton = Bouton(bas, "Installer", self._demarrer)
        self.bouton.pack(side="right", padx=(0, 34), pady=15)
        self.quitter = Bouton(bas, "Annuler", self._fermer, principal=False,
                              largeur=110)
        self.quitter.pack(side="right", padx=(0, 10), pady=15)

        self._ecran_accueil()

    def _vider(self):
        for w in self.corps.winfo_children():
            w.destroy()

    def _ecran_accueil(self):
        self._vider()
        tk.Label(self.corps, text="Installer JARVIS", bg=FOND, fg=TEXTE,
                 font=TITRE).pack(anchor="w")
        tk.Label(self.corps, bg=FOND, fg=SOURDINE, font=POLICE, justify="left",
                 wraplength=630,
                 text="Ce programme télécharge la dernière version publiée, "
                      "prépare son environnement, puis ouvre l'assistant de "
                      "configuration.").pack(anchor="w", pady=(6, 22))

        python, version, avertissement = amorceur.meilleur_python()
        if python:
            texte = "Python %d.%d détecté" % version
            couleur = ACCENT if not avertissement else ALERTE
        else:
            texte = "Aucun Python 3.10 ou plus récent"
            couleur = REFUS
        carte = tk.Frame(self.corps, bg=FOND_CARTE)
        carte.pack(fill="x", pady=(0, 16))
        tk.Label(carte, text=texte, bg=FOND_CARTE, fg=couleur,
                 font=POLICE_GRAS).pack(anchor="w", padx=16, pady=(13, 0))
        detail = (avertissement if avertissement else
                  (python or "Installez Python depuis python.org, puis relancez."))
        tk.Label(carte, text=detail, bg=FOND_CARTE, fg=SOURDINE, font=("Segoe UI", 9),
                 wraplength=600, justify="left").pack(anchor="w", padx=16, pady=(2, 13))
        if not python:
            self.bouton.activer(False)

        tk.Label(self.corps, text="Dossier d'installation", bg=FOND, fg=TEXTE,
                 font=POLICE_GRAS).pack(anchor="w")
        champ = tk.Entry(self.corps, textvariable=self.dossier, bg="#060a0e",
                         fg=TEXTE, insertbackground=ACCENT, relief="flat",
                         font=("Consolas", 9), highlightthickness=1,
                         highlightbackground="#1f2831", highlightcolor=ACCENT)
        champ.pack(fill="x", ipady=7, pady=(5, 4))
        tk.Label(self.corps, bg=FOND, fg=SOURDINE, font=("Segoe UI", 9),
                 text="Pas dans « Program Files » : Windows y refuse l'écriture "
                      "sans élévation.").pack(anchor="w", pady=(0, 18))

        case = tk.Checkbutton(
            self.corps, variable=self.avec_voix, bg=FOND, fg=TEXTE,
            activebackground=FOND, activeforeground=TEXTE, selectcolor=FOND_CARTE,
            font=POLICE, highlightthickness=0, bd=0, anchor="w",
            text="Installer aussi la reconnaissance vocale")
        case.pack(anchor="w")
        tk.Label(self.corps, bg=FOND, fg=SOURDINE, font=("Segoe UI", 9),
                 wraplength=630, justify="left",
                 text="Plusieurs gigaoctets à télécharger. Sans elle, JARVIS "
                      "fonctionne au clavier et par le raccourci Ctrl+Alt+J ; "
                      "seule la dictée manque.").pack(anchor="w", padx=(24, 0))

    def _ecran_travail(self):
        self._vider()
        tk.Label(self.corps, text="Installation en cours", bg=FOND, fg=TEXTE,
                 font=TITRE).pack(anchor="w")
        self.etat = tk.Label(self.corps, text="Préparation…", bg=FOND, fg=SOURDINE,
                             font=POLICE, anchor="w")
        self.etat.pack(anchor="w", pady=(6, 16))
        self.barre = Barre(self.corps)
        self.barre.pack(anchor="w", pady=(0, 18))

        cadre = tk.Frame(self.corps, bg="#060a0e")
        cadre.pack(fill="both", expand=True)
        self.journal = tk.Text(cadre, bg="#060a0e", fg=SOURDINE, font=MONO,
                               relief="flat", wrap="none", height=12,
                               highlightthickness=0, padx=12, pady=10)
        self.journal.pack(fill="both", expand=True)
        self.journal.configure(state="disabled")

    def _ecran_fin(self, ok, message):
        self._vider()
        tk.Label(self.corps, text="C'est installé" if ok else "L'installation a échoué",
                 bg=FOND, fg=TEXTE if ok else REFUS, font=TITRE).pack(anchor="w")
        tk.Label(self.corps, bg=FOND, fg=SOURDINE, font=POLICE, wraplength=630,
                 justify="left",
                 text=("JARVIS est installé dans %s.\n\nL'assistant de "
                       "configuration va s'ouvrir : il vous demandera ce que "
                       "vous voulez activer." % message) if ok
                      else str(message)).pack(anchor="w", pady=(8, 0))
        self.bouton.texte = "Configurer" if ok else "Fermer"
        self.bouton.action = self._terminer if ok else self._fermer
        self.bouton.activer(True)
        self.quitter.texte = "Fermer"
        self.quitter.action = self._fermer
        self.quitter._dessiner()

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
