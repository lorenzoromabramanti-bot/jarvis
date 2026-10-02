# -*- coding: utf-8 -*-
r"""
J.A.R.V.I.S — Presse-papiers intelligent
=========================================
On copie un paragraphe, et on veut en faire quelque chose tout de suite :
le traduire, le résumer, se le faire expliquer, ou en corriger la langue.
Aujourd'hui il faut ouvrir le HUD, coller, écrire la consigne. Ici :
« Jarvis, traduis le presse-papiers » — ou Ctrl+Alt+J puis le même mot.

CE MODULE NE PARLE PAS AU MODÈLE
Il lit le presse-papiers et fabrique la consigne. C'est tout. L'appel au
modèle reste dans main2.py, qui sait déjà lequel est actif, quel canal
répond, et quelle autorisation s'applique. Un module qui appellerait le
modèle lui-même en dupliquerait le choix, et les deux divergeraient.

    prompt_pour(mode, texte)  ->  la consigne, sans appel réseau
    lire()                    ->  (texte, raison) — jamais une chaîne vide muette

PAS DE NOUVELLE DÉPENDANCE
`pyperclip` ferait le travail, mais l'API Windows le fait déjà et elle est
dans ctypes. Même raisonnement que barre_rapide.py pour le raccourci global.

CE QUI EST REFUSÉ, ET POURQUOI
Un presse-papiers vide, une image, un texte de 200 000 caractères : chacun
renvoie une raison lisible. Envoyer 200 000 caractères au modèle coûterait
cher et échouerait plus loin, sans que personne sache pourquoi.

    venv\Scripts\python.exe presse_papiers.py
"""

import ctypes
import sys

# Au-delà, on tronque plutôt que d'envoyer : un roman entier ne se résume
# pas mieux qu'un chapitre, et la troncature est DITE à l'utilisateur.
LIMITE = 12000

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

MODES = {
    "traduire": "Traduis en français, sans commentaire ni préambule. "
                "Si le texte est déjà en français, traduis-le en anglais.",
    "resumer": "Résume en cinq phrases maximum, en français. "
               "Garde les chiffres et les noms propres, ils portent le sens.",
    "expliquer": "Explique ce texte simplement, en français, à quelqu'un qui "
                 "découvre le sujet. Dis d'abord de quoi il s'agit en une phrase.",
    "corriger": "Corrige l'orthographe, la grammaire et la ponctuation. "
                "Renvoie UNIQUEMENT le texte corrigé, sans commentaire, sans "
                "guillemets, et sans rien reformuler d'autre.",
}


def disponible():
    """(ok, raison). Le presse-papiers Windows, ou la raison de l'absence."""
    if sys.platform != "win32":
        return False, "le presse-papiers n'est lisible que sous Windows ici"
    return True, ""


def _user32_kernel32():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    # Sans restype explicite, ctypes ramène un int 32 bits : sur un Windows
    # 64 bits le handle est tronqué et GlobalLock reçoit une adresse fausse.
    user32.GetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [ctypes.c_uint]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    return user32, kernel32


def lire():
    """
    (texte, raison). Le texte du presse-papiers, ou pourquoi il n'y en a pas.

    Une image copiée n'est pas une erreur : c'est un cas normal, et il se
    dit. Le presse-papiers appartient à tout le système — on l'ouvre le
    temps de lire, jamais plus, sinon les autres applications se figent.
    """
    ok, raison = disponible()
    if not ok:
        return "", raison
    user32, kernel32 = _user32_kernel32()
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return "", "le presse-papiers ne contient pas de texte"
    if not user32.OpenClipboard(None):
        return "", "le presse-papiers est occupé par une autre application"
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return "", "le presse-papiers est vide"
        adresse = kernel32.GlobalLock(handle)
        if not adresse:
            return "", "lecture du presse-papiers impossible"
        try:
            texte = ctypes.wstring_at(adresse)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()
    if not texte.strip():
        return "", "le presse-papiers ne contient que des espaces"
    return texte, ""


def ecrire(texte):
    """
    Remplace le contenu du presse-papiers. Renvoie (ok, raison).

    Sert au mode « corriger » : le texte corrigé revient là où on l'avait
    pris, prêt à être recollé — sinon il faudrait le retaper depuis la
    réponse vocale, ce qui annule tout l'intérêt.
    """
    ok, raison = disponible()
    if not ok:
        return False, raison
    if not str(texte or "").strip():
        return False, "rien à écrire"
    user32, kernel32 = _user32_kernel32()
    if not user32.OpenClipboard(None):
        return False, "le presse-papiers est occupé par une autre application"
    try:
        user32.EmptyClipboard()
        donnees = ctypes.create_unicode_buffer(str(texte))
        taille = ctypes.sizeof(donnees)
        bloc = kernel32.GlobalAlloc(GMEM_MOVEABLE, taille)
        if not bloc:
            return False, "allocation mémoire refusée par le système"
        adresse = kernel32.GlobalLock(bloc)
        try:
            ctypes.memmove(adresse, ctypes.byref(donnees), taille)
        finally:
            kernel32.GlobalUnlock(bloc)
        if not user32.SetClipboardData(CF_UNICODETEXT, bloc):
            return False, "le système a refusé l'écriture"
        return True, "ok"
    finally:
        user32.CloseClipboard()


def reconnaitre_mode(texte):
    """
    Le mode demandé dans une phrase, ou None si elle ne parle pas du
    presse-papiers. Utilisé par l'outil vocal — les deux mots comptent :
    « traduis ça » sans « presse-papiers » viserait autre chose.
    """
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                if unicodedata.category(c) != "Mn")
    if not any(m in t for m in ("presse-papier", "presse papier", "pressepapier",
                                "le copier", "ce que j'ai copie", "ce que j ai copie")):
        return None
    for mot, mode in (("tradui", "traduire"), ("resum", "resumer"),
                      ("expliqu", "expliquer"), ("corrig", "corriger"),
                      ("orthograph", "corriger"), ("fautes", "corriger")):
        if mot in t:
            return mode
    return None


def prompt_pour(mode, texte):
    """
    La consigne à envoyer au modèle. Lève ValueError sur un mode inconnu —
    un mode mal orthographié doit se voir, pas produire un prompt vide.
    """
    if mode not in MODES:
        raise ValueError("mode inconnu : %r (attendus : %s)"
                         % (mode, ", ".join(sorted(MODES))))
    contenu = str(texte or "")
    tronque = len(contenu) > LIMITE
    if tronque:
        contenu = contenu[:LIMITE]
    consigne = MODES[mode]
    if tronque:
        consigne += (" (Le texte a été tronqué à %d caractères : dis-le en "
                     "une phrase à la fin.)" % LIMITE)
    return "%s\n\n---\n%s\n---" % (consigne, contenu)


def preparer(mode):
    """
    (prompt, texte_source, raison). Lit le presse-papiers et fabrique la
    consigne en une fois — ce que main2.py appelle. `raison` non vide
    signifie qu'il n'y a rien à envoyer, et dit pourquoi.
    """
    if mode not in MODES:
        return "", "", ("mode inconnu : %s (attendus : %s)"
                        % (mode, ", ".join(sorted(MODES))))
    texte, raison = lire()
    if raison:
        return "", "", raison
    return prompt_pour(mode, texte), texte, ""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    texte, raison = lire()
    print()
    print("=" * 70)
    print("PRESSE-PAPIERS")
    print("=" * 70)
    if raison:
        print("  %s" % raison)
    else:
        apercu = texte.strip().replace("\n", " ")[:120]
        print("  %d caractères : %s%s" % (len(texte), apercu,
                                          "…" if len(texte) > 120 else ""))
        print()
        for mode in sorted(MODES):
            print("  %-10s -> consigne de %d caractères"
                  % (mode, len(prompt_pour(mode, texte))))
    print("=" * 70)
