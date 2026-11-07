# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Mode Professeur
=============================
Par-dessus le mode révision (revisions.py garde le déroulé, la correction et le score) :

    « interroge-moi sur la Révolution française »  -> quiz de 10 questions, sur n'importe quel sujet
    « fais-moi un cours sur les fractions »         -> petit cours dit à voix haute, puis 4 questions
    « révise mes erreurs »                          -> les questions ratées reviennent (cartes mémoire)
    « reprends la révision »                        -> le quiz interrompu repart à sa question
    « mode professeur »                             -> ce qui est possible, erreurs à revoir comprises

Pendant le quiz : « répète », « indice », « redis le cours », « stop révision ».

Le quiz et le cours sont écrits en un seul appel par le cerveau isolé de JARVIS
(demander_ia_isolee : Gemini, Ollama en secours), passé par main2.py : quelques secondes,
au lieu des minutes du modèle local qui prépare les quiz Pronote la veille.
« Fais-moi réviser [en maths] » reste le quiz Pronote de revisions.py.

Idée reprise du Mode Professeur de J.A.R.V.I.S. 10.6 (TechEnClair) ; code écrit à part.
"""
import io
import json
import os
import re
from datetime import date, timedelta

import revisions
from agenda_scolaire import _sans_accents

INTERVALLES = (0, 2, 5)  # jours avant de revoir une carte de la boîte 1, 2, 3 ; juste en boîte 3 : apprise
MAX_CARTES = 300
NB_CARTES_QUIZ = 10

_SUJET = r"(?:sur|a propos de|au sujet de|autour de)\s+(?P<s>.+)"
_QUIZ = re.compile(r"\b(?:interroge[- ]moi|questionne[- ]moi|teste[- ]moi|pose[- ]moi des questions|"
                   r"fais[- ]moi (?:reviser|un quiz|une interro|un qcm|un test|des exercices)|un quiz|quiz)\b"
                   r"(?:\s+\S+){0,3}?\s+" + _SUJET)
_REVISER = re.compile(r"\bfais[- ]moi reviser\s+(?P<s>.+)")
_COURS = re.compile(r"\b(?:fais|fait|donne)[- ]moi (?:un |une |le )?(?:petit |petite )?(?:cours|lecon)\b"
                    r"(?:\s+(?:(?:sur|des|du|de|a propos de|au sujet de)\s+|d')(?P<s>.+))?")
_APPRENDS = re.compile(r"\bapprends[- ]moi\s+(?P<s>.+)")
_MENU = re.compile(r"\bmode prof(?:esseur)?\b|\bsois mon prof(?:esseur)?\b")
_MENU_SUJET = re.compile(r"\bmode prof(?:esseur)?\b.*?\b" + _SUJET)
_ERREURS = re.compile(r"\b(?:revise|reviser|revoir|refais|refaire|repasse|repasser|interroge[- ]moi sur)\b.*"
                      r"\bmes (?:erreurs|fautes|cartes)\b|\bcartes memoire\b")
_REPRISE = re.compile(r"\b(?:reprends|reprend|reprenons|continue|continuons)\b(?:\s+\S+){0,2}?\s+"
                      r"(?:la |le |ma |mon )?(?:revision|quiz|interro|cours)\b")
# « Fais-moi réviser » + une matière, une date ou un contrôle : c'est le quiz Pronote de revisions.py.
_MATIERE_SEULE = re.compile(r"^(?:(?:la|le|les|l'|mes|ma|mon|en|pour|de|du|d')\s*)*(?:maths?|mathematiques|francais|"
                            r"histoire|geo|geographie|histoire[- ]geo\w*|hg|svt|sciences?|physique\w*|chimie|"
                            r"anglais|espagnol|allemand|italien|latin|techno\w*|musique|arts? plastiques|eps)\W*$")
_QUAND = re.compile(r"\b(?:demain|apres[- ]demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
                    r"semaine|prochaine?s?|bientot|aujourd'hui|ce soir)\b")

_FORMAT = ('"qcm": [{"q": "...", "choix": ["...", "...", "...", "..."], "reponse": "...", "explication": "..."}], '
           '"ouvertes": [{"q": "...", "reponse": "...", "explication": "..."}]}')
_REGLES = ("« reponse » recopie exactement le bon choix. Chaque question a une « explication » d'une ou deux "
           "phrases. Jamais de question qui renvoie à un document, un texte ou une image que l'élève n'a pas "
           "sous les yeux. Réponds uniquement avec ce JSON, sans texte autour : ")
CONSIGNE_QUIZ = ("Tu es professeur. Écris un quiz de révision en français pour un élève de %s, sur : « %s ». "
                 "Reste à son niveau et au programme officiel. « qcm » : 6 QCM à 4 choix dont UN SEUL est juste ; "
                 "« ouvertes » : 4 questions ouvertes courtes (réponse en quelques mots). " + _REGLES + "{" + _FORMAT)
CONSIGNE_COURS = ("Tu es professeur et tu fais un cours oral très court, en français, à un élève de %s, sur : « %s ». "
                  "« cours » : 5 à 7 phrases simples, faites pour être dites à voix haute : l'idée principale, "
                  "un exemple concret, le piège à éviter. Pas de liste, pas de Markdown, pas de formule illisible à "
                  "l'oral. Puis 4 questions sur ce que dit le cours : « qcm » : 2 QCM à 4 choix dont UN SEUL est "
                  "juste ; « ouvertes » : 2 questions courtes. " + _REGLES + '{"cours": "...", ' + _FORMAT)


# ── Reconnaître la demande ───────────────────────────────────────────────

def _sujet(texte, m, groupe="s"):
    """Le sujet tel que l'élève l'a dit (accents, majuscules), sans politesse ni ponctuation autour."""
    if not m or not m.group(groupe):
        return None
    s = re.sub(r"(?i)\b(s.il (te|vous) pla[iî]t|stp|jarvis|merci)\b", " ", texte[m.start(groupe):m.end(groupe)])
    s = " ".join(s.split()).strip(" ,.;:!?\"«»")
    return s[:80] or None


def _pour_pronote(sujet_normalise):
    return bool(revisions._MOTS_EVAL.search(sujet_normalise) or _QUAND.search(sujet_normalise)
                or _MATIERE_SEULE.match(sujet_normalise.strip()))


def reconnait(texte):
    """(genre, sujet) d'une demande du Mode Professeur, sinon None.

    genre : « quiz », « cours », « erreurs », « reprise » ou « menu ». « Explique-moi… » n'en est pas une :
    c'est une question pour le cerveau, pas un cours avec des questions derrière.
    """
    texte = str(texte or "").replace("’", "'")
    # Un caractère normalisé par caractère du texte : les positions trouvées valent dans le texte d'origine.
    t = "".join((_sans_accents(c) + " ")[0] for c in texte)
    if _REPRISE.search(t):
        return ("reprise", None)
    if _ERREURS.search(t):
        return ("erreurs", None)
    m = _COURS.search(t) or _APPRENDS.search(t) or _MENU_SUJET.search(t)
    if m:
        return ("cours", _sujet(texte, m))
    m = _QUIZ.search(t) or _REVISER.search(t)
    if m and not _pour_pronote(m.group("s")):
        return ("quiz", _sujet(texte, m))
    if _MENU.search(t):
        return ("menu", None)
    return None


# ── Écrire le quiz ou le cours ───────────────────────────────────────────

def _json(brut):
    """Le premier objet JSON du texte : Gemini l'entoure souvent de ```json … ```."""
    texte = str(brut or "")
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        raise ValueError("pas de JSON dans la réponse")
    return json.loads(texte[debut:fin + 1])


async def _generer(consigne, appel_ia, mini, maxi):
    """(données, questions validées). Deux essais : le modèle ne rate pas deux fois pareil."""
    erreur = None
    for _ in range(2):
        try:
            donnees = _json(await appel_ia(consigne))
            return donnees, revisions.valider(donnees, mini=mini, maxi=maxi)
        except ValueError as e:
            erreur = e
    raise ValueError(str(erreur))


def _oral(texte):
    """Un cours lisible à voix haute : sans Markdown, sans espaces en trop, pas interminable."""
    t = " ".join(re.sub(r"[*_`#>]+", "", str(texte or "")).split())
    return t if len(t) <= 1200 else t[:1200].rsplit(". ", 1)[0] + "."


def _combien(n, mot):
    return "%d %s%s" % (n, mot, "s" if n > 1 else "")


# ── Cartes mémoire : les questions ratées reviennent ─────────────────────

def _chemin_cartes():
    return os.path.join(revisions.DOSSIER, "cartes.json")


def _lire_cartes():
    try:
        with io.open(_chemin_cartes(), encoding="utf-8") as f:
            cartes = json.load(f)
        return [c for c in cartes if isinstance(c, dict)] if isinstance(cartes, list) else []
    except (OSError, ValueError):
        return []


def _ecrire_cartes(cartes):
    os.makedirs(revisions.DOSSIER, exist_ok=True)
    with io.open(_chemin_cartes() + ".tmp", "w", encoding="utf-8") as f:
        json.dump(cartes[-MAX_CARTES:], f, ensure_ascii=False, indent=1)
    os.replace(_chemin_cartes() + ".tmp", _chemin_cartes())


def noter(q, juste, quiz, aujourdhui=None):
    """Appelé par revisions.repondre après chaque correction (boîtes de Leitner).

    Ratée : carte en boîte 1, à revoir tout de suite. Juste sur une carte : boîte suivante, revue dans
    2 puis 5 jours ; juste en boîte 3 : apprise, retirée.
    """
    aujourdhui = aujourdhui or date.today()
    cartes = _lire_cartes()
    cle = revisions._norm(q["q"])
    carte = next((c for c in cartes if revisions._norm(c.get("q", "")) == cle), None)
    if not juste:
        if carte is None:
            carte = {k: q[k] for k in ("q", "choix", "reponse", "explication") if k in q}
            carte["sujet"] = quiz.get("matiere", "")
            cartes.append(carte)
        carte.update(boite=1, revoir=aujourdhui.isoformat())
    elif carte is None:
        return
    elif carte.get("boite", 1) >= len(INTERVALLES):
        cartes.remove(carte)
    else:
        carte["boite"] = carte.get("boite", 1) + 1
        carte["revoir"] = (aujourdhui + timedelta(days=INTERVALLES[carte["boite"] - 1])).isoformat()
    _ecrire_cartes(cartes)


def cartes_dues(aujourdhui=None):
    """Les cartes à revoir ce jour-là, les plus fragiles d'abord."""
    jour = (aujourdhui or date.today()).isoformat()
    dues = [c for c in _lire_cartes() if c.get("q") and c.get("reponse") and str(c.get("revoir", "")) <= jour]
    return sorted(dues, key=lambda c: (c.get("boite", 1), str(c.get("revoir", ""))))


# ── Lancer ───────────────────────────────────────────────────────────────

def menu(aujourdhui=None):
    texte = ("Mode professeur. Dis « interroge-moi sur… » pour un quiz, « fais-moi un cours sur… » pour une "
             "leçon, ou « fais-moi réviser » pour ta prochaine évaluation.")
    n = len(cartes_dues(aujourdhui))
    if n:
        texte += " Tu as %s à revoir : dis « révise mes erreurs »." % _combien(n, "erreur")
    if revisions.en_pause():
        texte += " Un quiz est en pause : dis « reprends la révision »."
    return texte


async def lancer(demande, appel_ia, aujourdhui=None):
    """(texte à dire, raison si impossible). appel_ia : coroutine texte -> texte (demander_ia_isolee)."""
    genre, sujet = demande
    aujourdhui = aujourdhui or date.today()
    if genre == "menu":
        return menu(aujourdhui), ""
    if genre == "reprise":
        texte = revisions.reprendre()
        return (texte, "") if texte else (None, "aucun quiz en pause à reprendre")
    if genre == "erreurs":
        cartes = cartes_dues(aujourdhui)[:NB_CARTES_QUIZ]
        if not cartes:
            return None, "aucune erreur à revoir aujourd'hui, tes cartes sont à jour"
        quiz = {"date": aujourdhui.isoformat(), "matiere": "tes erreurs", "evaluation": "cartes mémoire",
                "questions": [{k: c[k] for k in ("q", "choix", "reponse", "explication") if k in c} for c in cartes]}
        return revisions.demarrer(quiz, intro="On revoit %s. Dis « indice » ou « répète » si besoin."
                                  % _combien(len(cartes), "erreur")), ""
    if not sujet:
        return ("Sur quel sujet ? Dis par exemple « fais-moi un cours sur les fractions », "
                "ou « interroge-moi sur la Révolution française »."), ""
    cours = ""
    try:
        if genre == "cours":
            donnees, questions = await _generer(CONSIGNE_COURS % (revisions.NIVEAU, sujet), appel_ia, mini=3, maxi=4)
            cours = _oral(donnees.get("cours") if isinstance(donnees, dict) else "")
            if not cours:
                raise ValueError("cours vide")
        else:
            donnees, questions = await _generer(CONSIGNE_QUIZ % (revisions.NIVEAU, sujet), appel_ia,
                                                mini=revisions.MIN_QUESTIONS, maxi=revisions.NB_QUESTIONS)
    except ValueError as e:
        print("[PROFESSEUR] %s inutilisable : %s" % (genre, e))
        return None, "le modèle m'a rendu un %s inutilisable, réessaie" % ("cours" if genre == "cours" else "quiz")
    except Exception as e:  # cerveau injoignable (Gemini et Ollama), délai dépassé…
        print("[PROFESSEUR] cerveau injoignable : %r" % (e,))
        return None, "le cerveau ne répond pas pour l'instant"
    quiz = {"date": aujourdhui.isoformat(), "matiere": sujet, "evaluation": "Mode professeur", "questions": questions}
    if cours:
        quiz["cours"] = cours
        intro = (cours + "\nMaintenant, %s pour vérifier. Dis « redis le cours » si besoin."
                 % _combien(len(questions), "question"))
    else:
        intro = ("Mode professeur : %s sur %s. Dis « indice », « répète » ou « stop révision »."
                 % (_combien(len(questions), "question"), sujet))
    return revisions.demarrer(quiz, intro=intro), ""
