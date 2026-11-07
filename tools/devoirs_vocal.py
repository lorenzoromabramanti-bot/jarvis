# -*- coding: utf-8 -*-
"""Outils JARVIS : « Jarvis, j'ai quoi comme devoirs ? » et « c'est quoi ma moyenne ? », à la voix comme à l'écrit.

Le HUD lisait déjà les devoirs Pronote (get_devoirs_notes) ; à la voix, la question partait au modèle,
qui n'a pas ces données et risquait d'inventer. On lit les mêmes données (agenda_scolaire, via Home
Assistant) et on répond court : les devoirs pas encore cochés des prochains jours, contrôles en premier.

Même capacité que le HUD : décochée, l'outil répond le refus du catalogue.
Priorité 8 : avant les commandes locales (10), dont les motifs « demain » auraient pu l'avaler.
"""
import datetime as dt
import re

from . import contient, outil, sans_accents

MOTIFS = ("mes devoirs", "quoi comme devoirs", "quels devoirs", "des devoirs", "les devoirs",
          "devoirs pour", "devoir pour demain", "devoirs a faire", "mes evaluations", "mes controles",
          "j'ai un controle", "j'ai une evaluation", "j'ai une eval", "prochain controle",
          "prochaine evaluation", "prochaine eval")
_EVAL = re.compile(r"(?i)contr[oô]le|[ée]valuation|\binterro|\bds\b")
_COLLEES = re.compile(r"([a-zà-ÿ]{3})([A-ZÀ-Ý][a-zà-ÿ])")
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _jour(date_iso, aujourdhui):
    d = dt.date.fromisoformat(date_iso)
    if d == aujourdhui:
        return "aujourd'hui"
    if d == aujourdhui + dt.timedelta(days=1):
        return "demain"
    return JOURS[d.weekday()]


def resume_devoirs(devoirs, aujourdhui, seulement_aujourdhui=False, jours=7, maxi=4, seulement_evals=False):
    """Phrase à dire : devoirs non cochés (fiches de agenda_scolaire.normaliser_devoir), contrôles d'abord.

    De demain à `jours` jours (aujourd'hui seulement si demandé), au plus `maxi` devoirs cités ;
    seulement les contrôles si la question porte sur eux.
    """
    debut = aujourdhui if seulement_aujourdhui else aujourdhui + dt.timedelta(days=1)
    fin = aujourdhui if seulement_aujourdhui else aujourdhui + dt.timedelta(days=jours)
    a_faire = []
    for d in devoirs:
        date = str(d.get("date", ""))[:10]
        try:
            jour = dt.date.fromisoformat(date)
        except ValueError:
            continue
        if d.get("fait") or not debut <= jour <= fin:
            continue
        texte = " ".join((d.get("titre") or d.get("description") or "").split())
        texte = _COLLEES.sub(r"\1. \2", texte)  # Pronote colle ses lignes : « rédactionSavoir refaire »
        a_faire.append((not _EVAL.search(texte), date, d.get("matiere", "").strip().capitalize(), texte))
    if seulement_evals:
        a_faire = [x for x in a_faire if not x[0]]
        if not a_faire:
            return f"Aucun contrôle annoncé dans Pronote d'ici {JOURS[fin.weekday()]} prochain."
    if not a_faire:
        return ("Rien à rendre aujourd'hui, tout est coché." if seulement_aujourdhui
                else f"Rien à rendre d'ici {JOURS[fin.weekday()]} prochain, tout est coché.")
    a_faire = sorted(set(a_faire), key=lambda x: (x[1], x[0]))  # sans doublon ; par date, le contrôle en tête
    # Les contrôles d'abord dans les `maxi` cités (un contrôle ne doit jamais finir en « et 1 autre »),
    # puis remis dans l'ordre des jours pour être dits.
    cites = sorted(([x for x in a_faire if not x[0]] + [x for x in a_faire if x[0]])[:maxi], key=lambda x: (x[1], x[0]))
    morceaux = []
    for pas_eval, date, matiere, texte in cites:
        de = "d'" if matiere[:1].lower() in "aeiouyhéè" else "de "
        quoi = (f"contrôle {de}" if not pas_eval else "") + matiere
        detail = texte.rstrip(".")
        if len(detail) > 90:
            detail = detail[:90].rsplit(" ", 1)[0]  # coupé entre deux mots
        morceaux.append(f"{_jour(date, aujourdhui)}, {quoi}{' : ' + detail if detail else ''}")
    phrase = "Tu as " + " ; ".join(morceaux) + "."
    if len(a_faire) > maxi:
        phrase += f" Et {len(a_faire) - maxi} autre{'s' if len(a_faire) - maxi > 1 else ''} après."
    return phrase[0].upper() + phrase[1:]


MOTIFS_NOTES = ("ma moyenne", "mes moyennes", "ma derniere note", "mes dernieres notes", "quelle note j'ai",
                "j'ai eu combien", "mes resultats scolaires")  # pas « mes notes » : c'est Obsidian dans JARVIS
_ALIAS = {"svt": "scie", "eps": "educ", "hg": "hist", "lv1": "angl", "lv2": "espa"}


def _matiere(nom):
    """« ANGLAIS LV1 > ORAL » -> « Anglais lv1 oral » ; « HG > HG » -> « Hg » (la voix lirait le « > »)."""
    parties = []
    for p in (x.strip() for x in str(nom).split(">")):
        if p and p.lower() not in (q.lower() for q in parties):
            parties.append(p)
    return " ".join(parties).capitalize()


def _note(n):
    bareme = n.get("bareme", "")
    return n.get("note", "") + ("/" + bareme if bareme and bareme != "20" else " sur 20" if bareme else "")


def resume_notes(texte, donnees, maxi=3):
    """Phrase à dire : moyenne d'une matière si elle est nommée, sinon moyenne générale + dernières notes."""
    mots = [_ALIAS.get(m, m)[:4] for m in re.findall(r"[a-z0-9]+", sans_accents(texte)) if len(m) >= 4 or m in _ALIAS]
    for moy in donnees.get("moyennes", []):
        prefixes = {w[:4] for w in re.findall(r"[a-z]+", sans_accents(moy.get("matiere", ""))) if len(w) >= 4}
        if moy.get("eleve") and prefixes & set(mots):
            classe = f" La classe est à {moy['classe']}." if moy.get("classe") else ""
            return f"En {_matiere(moy['matiere'])}, tu as {moy['eleve']} de moyenne.{classe}"
    morceaux = []
    if donnees.get("moyenne"):
        morceaux.append(f"Ta moyenne générale est de {donnees['moyenne']}.")
    notes = sorted((n for n in donnees.get("notes", []) if n.get("note")), key=lambda n: n.get("date", ""), reverse=True)
    if notes:
        morceaux.append("Tes dernières notes : " + ", ".join(
            f"{_note(n)} en {_matiere(n.get('matiere', ''))}" for n in notes[:maxi]) + ".")
    return " ".join(morceaux) or "Pronote n'a encore aucune note ce trimestre."


@outil(nom="notes_vocal", priorite=8, description="Moyenne et dernières notes Pronote, dites à la voix", mode="bloquant")
def notes_vocal(texte):
    texte = texte.replace("’", "'")
    if not contient(texte, MOTIFS_NOTES):
        return None
    import catalogue
    if not catalogue.action_autorisee("get_devoirs_notes"):
        return catalogue.refus("get_devoirs_notes")
    import agenda_scolaire
    donnees, raisons = agenda_scolaire.devoirs_evaluations_notes()
    if not donnees["notes"] and not donnees["moyenne"] and raisons:
        return "Je n'arrive pas à lire Pronote en ce moment : " + raisons[0] + "."
    return resume_notes(texte, donnees)


@outil(nom="devoirs_vocal", priorite=8, description="Devoirs Pronote à venir, dits à la voix", mode="bloquant")
def devoirs_vocal(texte):
    texte = texte.replace("’", "'")  # la dictée écrit souvent l'apostrophe typographique
    if not contient(texte, MOTIFS):
        return None
    import catalogue
    if not catalogue.action_autorisee("get_devoirs_notes"):
        return catalogue.refus("get_devoirs_notes")
    import agenda_scolaire
    donnees, raisons = agenda_scolaire.devoirs_evaluations_notes()
    if not donnees["devoirs"] and raisons:
        return "Je n'arrive pas à lire Pronote en ce moment : " + raisons[0] + "."
    return resume_devoirs(donnees["devoirs"], dt.date.today(),
                          seulement_aujourdhui=contient(texte, ("aujourd'hui", "aujourdhui", "ce matin")),
                          seulement_evals=contient(texte, ("controle", "evaluation", "eval ", "interro")))
