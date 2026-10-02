# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Révisions Pronote
===============================
La veille d'une évaluation annoncée sur Pronote, prépare un quiz de 10
questions avec le modèle LOCAL (Ollama) et le range dans
revisions/. En conversation, « fais-moi réviser » fait passer JARVIS en mode
quiz : question, correction et score sont produits ici (demarrer/repondre),
appelés par main2.py : traiter_reponse_ia, sans passer par le modèle de chat.

OÙ SONT LES ÉVALUATIONS (constaté dans Home Assistant avec hass-pronote)
Le capteur *_evaluations de hass-pronote ne liste PAS les contrôles à venir :
ce sont les évaluations par compétences DÉJÀ notées (avec « acquisitions »).
Les contrôles annoncés arrivent dans les DEVOIRS (« Evaluation prevue en classe »,
« Évaluation sur le chapitre exemple »). On prend donc les deux : un devoir dont le
texte parle d'évaluation/contrôle, et une évaluation datée du jour visé si
jamais Pronote en publie une. Les évaluations déjà notées servent de
« chapitres » au modèle.

FORMAT DES FICHIERS (relu par Carnet)
revisions/AAAA-MM-JJ_matiere.json, UTF-8 :
    {"date": "2030-01-15", "matiere": "MATHEMATIQUES",
     "evaluation": "Evaluation prevue en classe",
     "questions": [{"q": "...",
                    "choix": ["...", "...", "...", "..."],   # QCM seulement
                    "reponse": "...",     # pour un QCM : exactement un des choix
                    "explication": "..."}]}

    venv\\Scripts\\python.exe revisions.py          (prépare les quiz de demain)
"""

import glob
import io
import json
import os
import re
import sys
import time
from datetime import date, timedelta

import agenda_scolaire
from agenda_scolaire import _sans_accents
from agent_model_manager import DEFAULT_MODELS, OLLAMA_URL

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "revisions")
# Réglages (.env, assistant d'installation) : modèle Ollama et niveau de
# l'élève. Vides = modèle Ollama par défaut et niveau non précisé au modèle.
MODELE = os.getenv("JARVIS_REVISIONS_MODELE", "").strip() or DEFAULT_MODELS["Ollama"]
NIVEAU = os.getenv("JARVIS_NIVEAU_SCOLAIRE", "").strip()   # ex. « collège »
NB_QUESTIONS = 10
MIN_QUESTIONS = 6           # en dessous, le modèle a raté : quiz refusé
HEURE_PREPARATION = "17:30"
JOURS_A_PREPARER = (1,)     # (1, 2) pour préparer aussi l'après-demain
HORIZON_JOURS = 7           # « fais-moi réviser » cherche jusqu'à J+7
DUREE_MODE_S = 90 * 60      # sans réponse pendant 1 h 30, le mode quiz s'éteint

_MOTS_EVAL = re.compile(r"\b(evaluation|eval|controle|interros?|ds|devoir surveille|"
                        r"test|qcm|examen|brevet blanc)\b")
_DEMANDE = re.compile(r"fais[ -]moi (reviser|un quiz|une interro)|interroge[ -]moi|"
                      r"quiz de revision|mode revision")
_ARRET = re.compile(r"^(stop|arrete|fin)\W*$|\b(stop|arrete\w*|fin|termine\w*|quitte\w*)"
                    r"( la| le| de la| du)? (revision|quiz)\b")
_MOTS_VIDES = {"vie", "moi", "les", "des", "une", "sur"}

# Deux listes de taille imposée : avec une seule liste et « choix » facultatif,
# un modèle local a rendu tantôt 10 questions ouvertes, tantôt 10 QCM.
_TEXTE = {"type": "string"}
_SCHEMA = {"type": "object", "required": ["qcm", "ouvertes"], "properties": {
    "qcm": {"type": "array", "minItems": 6, "maxItems": 6, "items": {
        "type": "object", "required": ["q", "choix", "reponse", "explication"],
        "properties": {"q": _TEXTE, "reponse": _TEXTE, "explication": _TEXTE, "choix": {
            "type": "array", "minItems": 4, "maxItems": 4, "items": _TEXTE}}}},
    "ouvertes": {"type": "array", "minItems": 4, "maxItems": 4, "items": {
        "type": "object", "required": ["q", "reponse", "explication"],
        "properties": {"q": _TEXTE, "reponse": _TEXTE, "explication": _TEXTE}}}}}

CONSIGNE = (
    "Écris un quiz de révision de 10 questions, en français, du niveau de l'élève, sur ce que "
    "l'évaluation va probablement demander : appuie-toi sur les chapitres et les devoirs cités, "
    "sinon sur le programme officiel de la matière à ce niveau. "
    "« qcm » : 6 QCM à 4 choix dont UN SEUL est juste (« reponse » recopie exactement ce choix). "
    "« ouvertes » : 4 questions ouvertes courtes (réponse en quelques mots). Chaque question a "
    "une « explication » d'une ou deux phrases. Jamais de question qui renvoie à un document, "
    "un texte ou une image que l'élève n'a pas sous les yeux.\n"
    'Format : {"qcm": [{"q": "...", "choix": ["...", "...", "...", "..."], "reponse": "...", '
    '"explication": "..."}], "ouvertes": [{"q": "...", "reponse": "...", "explication": "..."}]}')


# ── Quelles évaluations, quel contexte ───────────────────────────────────

def _slug(matiere):
    return re.sub(r"[^a-z0-9]+", "-", _sans_accents(matiere)).strip("-") or "matiere"


def chemin_quiz(date_iso, matiere):
    return os.path.join(DOSSIER, "%s_%s.json" % (date_iso, _slug(matiere)))


def evaluations_du(donnees, date_iso):
    """Les évaluations prévues ce jour-là (donnees = devoirs_evaluations_notes), une par matière."""
    trouvees = {}
    for e in donnees.get("evaluations", []):
        if e["date"][:10] == date_iso and e["matiere"]:
            trouvees.setdefault(e["matiere"], {"date": date_iso, "matiere": e["matiere"],
                                               "nom": e["nom"] or "Évaluation",
                                               "description": e["description"]})
    for d in donnees.get("devoirs", []):
        if (d["date"][:10] == date_iso and d["matiere"]
                and _MOTS_EVAL.search(_sans_accents(d["titre"] + " " + d["description"]))):
            trouvees.setdefault(d["matiere"], {"date": date_iso, "matiere": d["matiere"],
                                               "nom": d["titre"][:120] or "Évaluation",
                                               "description": d["description"]})
    return list(trouvees.values())


def contexte(ev, donnees):
    """Ce que le modèle sait de l'évaluation : intitulé, chapitres notés, devoirs de la matière."""
    m = ev["matiere"]
    lignes = ["Matière : %s" % m, "Évaluation : %s" % ev["nom"]]
    if ev["description"] and ev["description"] != ev["nom"]:
        lignes.append("Détail : %s" % ev["description"][:500])
    chapitres = [e["nom"] for e in donnees.get("evaluations", []) if e["matiere"] == m and e["nom"]]
    if chapitres:
        lignes.append("Chapitres évalués récemment : " + " ; ".join(chapitres[:8]))
    devoirs = [d for d in donnees.get("devoirs", []) if d["matiere"] == m][:8]
    if devoirs:
        lignes.append("Devoirs récents :\n" + "\n".join(
            "- %s : %s" % (d["date"], (d["description"] or d["titre"])[:300]) for d in devoirs))
    return "\n".join(lignes)


# ── Génération ───────────────────────────────────────────────────────────

def _ollama(messages):
    import requests
    r = requests.post(OLLAMA_URL + "/api/chat", timeout=600, json={
        "model": MODELE, "messages": messages, "stream": False, "think": False,
        "format": _SCHEMA, "options": {"temperature": 0.4}})
    r.raise_for_status()
    return r.json()["message"]["content"]


def valider(brut):
    """Le JSON du modèle -> questions propres. ValueError si inexploitable."""
    donnees = json.loads(brut) if isinstance(brut, str) else brut
    questions = donnees
    if isinstance(donnees, dict):
        questions = donnees.get("questions")
        if questions is None:       # format demandé au modèle : {"qcm": [...], "ouvertes": [...]}
            questions = [q for cle in ("qcm", "ouvertes")
                         if isinstance(donnees.get(cle), list) for q in donnees[cle]]
    if not isinstance(questions, list):
        raise ValueError("pas de liste de questions")
    propres = []
    for q in questions:
        if not isinstance(q, dict):
            continue
        fiche = {k: str(q.get(k) or "").strip() for k in ("q", "reponse", "explication")}
        if not all(fiche.values()):
            continue
        choix = q.get("choix") if isinstance(q.get("choix"), list) else []
        choix = [str(c).strip() for c in choix if str(c).strip()]
        if len(choix) >= 2:
            if fiche["reponse"] not in choix:
                # Le modèle répond parfois « B » ou « B) texte » au lieu du texte.
                m = re.match(r"^([A-Da-d])(\W|$)", fiche["reponse"])
                i = "abcd".index(m.group(1).lower()) if m else -1
                if not 0 <= i < len(choix):
                    continue            # QCM dont la réponse n'est pas un choix : inutilisable
                fiche["reponse"] = choix[i]
            fiche = {"q": fiche["q"], "choix": choix, "reponse": fiche["reponse"],
                     "explication": fiche["explication"]}
        propres.append(fiche)
    if len(propres) < MIN_QUESTIONS:
        raise ValueError("%d question(s) exploitable(s) sur %d" % (len(propres), len(questions)))
    return propres[:NB_QUESTIONS]


def generer(ev, donnees, appel_modele=None):
    """Un quiz au format du fichier. Deux essais : le modèle ne rate pas deux fois pareil."""
    appel = appel_modele or _ollama
    messages = [{"role": "system", "content": "Tu es un professeur qui prépare un élève%s "
                                              "à une évaluation. Tu réponds uniquement en JSON."
                                              % (" de " + NIVEAU if NIVEAU else "")},
                {"role": "user", "content": contexte(ev, donnees) + "\n\n" + CONSIGNE}]
    try:
        questions = valider(appel(messages))
    except ValueError:
        questions = valider(appel(messages))
    return {"date": ev["date"], "matiere": ev["matiere"], "evaluation": ev["nom"],
            "questions": questions}


def enregistrer(quiz):
    os.makedirs(DOSSIER, exist_ok=True)
    chemin = chemin_quiz(quiz["date"], quiz["matiere"])
    with io.open(chemin + ".tmp", "w", encoding="utf-8") as f:
        json.dump(quiz, f, ensure_ascii=False, indent=2)
    os.replace(chemin + ".tmp", chemin)
    return chemin


def lire(chemin):
    with io.open(chemin, encoding="utf-8") as f:
        return json.load(f)


def _charger_ou_generer(ev, donnees, appel_modele=None):
    chemin = chemin_quiz(ev["date"], ev["matiere"])
    if os.path.exists(chemin):
        return lire(chemin)
    quiz = generer(ev, donnees, appel_modele)
    enregistrer(quiz)
    return quiz


def quiz_prepares():
    """Résumé des quiz sur disque (pour le HUD / Carnet), du plus ancien au plus récent."""
    sortie = []
    for chemin in sorted(glob.glob(os.path.join(DOSSIER, "????-??-??_*.json"))):
        try:
            q = lire(chemin)
            sortie.append({"date": q["date"], "matiere": q["matiere"], "evaluation": q["evaluation"],
                           "questions": len(q["questions"]), "fichier": os.path.basename(chemin)})
        except Exception:
            continue
    return sortie


def preparer(jours=JOURS_A_PREPARER, lecteur=None, appel_modele=None, aujourdhui=None):
    """Génère les quiz manquants. Renvoie une phrase de notification par quiz CRÉÉ."""
    aujourdhui = aujourdhui or date.today()
    donnees, _raisons = agenda_scolaire.devoirs_evaluations_notes(lecteur)
    phrases = []
    for n in jours:
        jour = (aujourdhui + timedelta(days=n)).isoformat()
        for ev in evaluations_du(donnees, jour):
            if os.path.exists(chemin_quiz(jour, ev["matiere"])):
                continue
            try:
                enregistrer(generer(ev, donnees, appel_modele))
            except Exception as e:
                print("[REVISIONS] quiz %s %s impossible : %r" % (jour, ev["matiere"], e))
                continue
            quand = {1: "demain", 2: "après-demain"}.get(n, "le " + jour)
            phrases.append("Évaluation de %s %s : quiz prêt, dis « fais-moi réviser »."
                           % (ev["matiere"].capitalize(), quand))
    return phrases


# ── Conversation ─────────────────────────────────────────────────────────

def reconnait_demande(texte):
    return bool(_DEMANDE.search(_sans_accents(texte)))


def reconnait_arret(texte):
    return bool(_ARRET.search(_sans_accents(texte).strip()))


def matiere_demandee(texte, matieres):
    """« maths » -> MATHEMATIQUES, « svt » -> SCIENCES VIE & TERRE, sinon None."""
    mots = [m for m in re.findall(r"[a-z]{2,}", _sans_accents(texte)) if m not in _MOTS_VIDES]
    for matiere in matieres:
        jetons = [j for j in re.findall(r"[a-z]+", _sans_accents(matiere)) if len(j) > 1]
        sigle = "".join(j[0] for j in jetons)
        for mot in mots:
            if mot == sigle or (len(mot) >= 3 and any(j.startswith(mot[:4]) for j in jetons)):
                return matiere
    return None


def quiz_pour(texte, lecteur=None, appel_modele=None, aujourdhui=None):
    """
    (quiz, raison) pour « fais-moi réviser [en X] » : la prochaine évaluation
    (J+1..J+7, de la matière nommée s'il y en a une), quiz relu sur disque ou
    généré à la volée. Matière nommée sans évaluation = révision libre.
    """
    aujourdhui = aujourdhui or date.today()
    jours = [(aujourdhui + timedelta(days=n)).isoformat() for n in range(1, HORIZON_JOURS + 1)]
    try:
        donnees, raisons = agenda_scolaire.devoirs_evaluations_notes(lecteur)
        prepares = [q for q in quiz_prepares() if q["date"] in jours]
        matieres = {x["matiere"] for x in donnees["devoirs"] + donnees["evaluations"] + prepares
                    if x["matiere"]}
        matiere = matiere_demandee(texte, sorted(matieres))
        for jour in jours:
            for ev in evaluations_du(donnees, jour):
                if matiere in (None, ev["matiere"]):
                    return _charger_ou_generer(ev, donnees, appel_modele), ""
        # Home Assistant muet : les quiz déjà préparés restent utilisables.
        for q in prepares:
            if matiere in (None, q["matiere"]):
                return lire(os.path.join(DOSSIER, q["fichier"])), ""
        if matiere:
            ev = {"date": aujourdhui.isoformat(), "matiere": matiere,
                  "nom": "Révision libre (aucune évaluation annoncée)", "description": ""}
            return _charger_ou_generer(ev, donnees, appel_modele), ""
    except Exception as e:
        return None, "je n'ai pas pu préparer le quiz (%s)" % e
    if not donnees["devoirs"] and raisons:
        return None, "je n'arrive pas à lire Pronote : %s" % raisons[0]
    return None, ("aucune évaluation annoncée sur Pronote dans les %d prochains jours. "
                  "Dis par exemple « interroge-moi en maths »" % HORIZON_JOURS)


# ── Mode quiz (état en mémoire, un seul élève) ───────────────────────────
# Le déroulé est tenu par le CODE, pas par le modèle de conversation : testé
# via le WebSocket, le modèle de conversation comptait faux une
# bonne réponse, sautait la question 2 et déclarait la révision finie après
# deux réponses. Le modèle local ne sert plus qu'à juger une réponse ouverte.

MODELE_JUGE = os.getenv("JARVIS_REVISIONS_JUGE", "").strip() or MODELE
_JE_NE_SAIS_PAS = re.compile(r"\b(je (ne )?sais pas|j ?sais pas|aucune idee|joker)\b")
_ETAT = {"quiz": None, "repondues": 0, "score": 0, "vu": 0.0}


def demarrer(quiz):
    _ETAT.update(quiz=quiz, repondues=0, score=0, vu=time.time())
    return ("Mode révision : %s, %s du %s, %d questions. Dis « stop révision » pour arrêter.\n%s"
            % (quiz["matiere"].capitalize(), quiz["evaluation"],
               "/".join(reversed(quiz["date"].split("-"))), len(quiz["questions"]), _question(0)))


def arreter():
    _ETAT.update(quiz=None, repondues=0, score=0)


def quiz_actif():
    if _ETAT["quiz"] and time.time() - _ETAT["vu"] > DUREE_MODE_S:
        arreter()
    return _ETAT["quiz"] is not None


def _question(i):
    qs = _ETAT["quiz"]["questions"]
    q = qs[i]
    texte = "Question %d sur %d : %s" % (i + 1, len(qs), q["q"])
    if q.get("choix"):
        texte += "\n" + "\n".join("%s) %s" % (chr(65 + j), c) for j, c in enumerate(q["choix"]))
    return texte


def _norm(s):
    return re.sub(r"[^a-z0-9,+-]+", " ", _sans_accents(str(s)).lower()).strip()


def _juger_ouverte(q, reponse):
    import requests
    r = requests.post(OLLAMA_URL + "/api/chat", timeout=90, json={
        "model": MODELE_JUGE, "stream": False, "think": False,
        "format": {"type": "object", "required": ["juste"], "properties": {"juste": {"type": "boolean"}}},
        "options": {"temperature": 0},
        "messages": [{"role": "user", "content":
                      "Question : %s\nRéponse attendue : %s\nRéponse de l'élève : %s\n"
                      "Tu corriges un élève avec indulgence : juste si l'idée principale est là, "
                      "même mal formulée, incomplète ou avec des fautes. L'élève a-t-il juste ?"
                      % (q["q"], q["reponse"], reponse)}]})
    r.raise_for_status()
    return bool(json.loads(r.json()["message"]["content"]).get("juste"))


def est_juste(q, reponse, juge=None):
    """QCM : la lettre ou le texte du bon choix. Ouverte : texte exact, sinon le modèle."""
    rep, attendu = _norm(reponse).replace("moins ", "-"), _norm(q["reponse"])  # voix : « moins 8 »
    if not rep or _JE_NE_SAIS_PAS.search(rep):
        return False
    if q.get("choix"):
        bonne = chr(97 + [_norm(c) for c in q["choix"]].index(attendu)) if attendu in [
            _norm(c) for c in q["choix"]] else None
        lettre = re.match(r"^(?:(?:c est |la |reponse )+)?([a-d])\b", rep)
        if lettre:
            return lettre.group(1) == bonne
        return re.search(r"(^|\s)%s($|\s)" % re.escape(attendu), rep) is not None
    if attendu in rep:
        return True
    try:
        return (juge or _juger_ouverte)(q, reponse)
    except Exception:
        return False    # modèle injoignable : l'explication s'affiche quand même


def repondre(reponse, juge=None):
    """La réponse de l'élève -> correction, score, puis question suivante ou bilan."""
    quiz, i = _ETAT["quiz"], _ETAT["repondues"]
    q, total = quiz["questions"][i], len(quiz["questions"])
    juste = est_juste(q, reponse, juge)
    _ETAT.update(repondues=i + 1, score=_ETAT["score"] + juste, vu=time.time())
    texte = ("Juste ! " if juste else "Faux. La réponse était : %s. " % q["reponse"]) + q["explication"]
    texte += " Score : %d sur %d." % (_ETAT["score"], i + 1)
    if i + 1 < total:
        return texte + "\n" + _question(i + 1)
    note = _ETAT["score"]
    arreter()
    return texte + ("\nRévision terminée : %d sur %d. %s" % (note, total,
                    "Tu es prêt." if note >= total * 0.8 else "Relis la leçon sur les questions ratées."))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for p in preparer():
        print(p)
    for q in quiz_prepares():
        print("  %(date)s  %(matiere)-25s %(questions)2d questions  %(evaluation)s" % q)
