# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — File d'attente de tâches différées (mission B1)
===============================================================
« Fais ça cette nuit » -> mise en file, pas d'exécution immédiate.
Ce module gère UNIQUEMENT la file : écrire, lire, changer de statut.
L'exécution (B2) et le rattachement au briefing sont ailleurs — main2.py
connaît le modèle et le briefing, ce module n'a pas à les connaître.

POURQUOI UN FICHIER JSON, PAS UNE BASE
Quelques tâches à la fois, jamais concurrent avec lui-même (un seul
exécuteur en arrière-plan, voir B2) — un fichier suffit et reste lisible
à la main, comme `capacites.json`.

STATUTS
en_attente -> en_cours -> terminee | echouee

Une tâche échouée le RESTE échouée — elle n'est jamais retirée de la file
tant qu'elle n'a pas été vue au réveil (voir `a_signaler`). Silence absent
= silence, jamais la norme de ce dépôt.

VERROU D'EXÉCUTEUR (mission comparaison roadmap, 2026-09-18)
Rien n'empêchait aujourd'hui deux passages de l'exécuteur (B2) de se
chevaucher — un redémarrage rapide ou un appel manuel pendant qu'une tâche
tourne déjà. `verrou_executeur` pose un fichier `.lock` à côté de la file :
un fichier, pas un verrou en mémoire, parce qu'un verrou en mémoire disparaît
au premier plantage et ne protège plus rien après. Le TTL existe pour la
même raison en sens inverse : un exécuteur qui plante SANS relâcher son
verrou ne doit pas bloquer tous les passages suivants indéfiniment.
"""

import io
import json
import os
import time
import uuid

import config

FICHIER = "taches_nocturnes.json"

STATUTS = ("en_attente", "en_cours", "terminee", "echouee")


class DejaEnCours(Exception):
    """Un exécuteur de tâches nocturnes tourne déjà (verrou non expiré)."""


def _chemin_verrou():
    return config.chemin_donnees(FICHIER + ".lock", creer_dossier=True)


class verrou_executeur:
    """
    Contexte : garantit qu'un seul passage de l'exécuteur de tâches
    nocturnes tourne à la fois. Prévu pour main2.py (boucle_rappels) :

        with taches_nocturnes.verrou_executeur():
            tache = prochaine_en_attente()
            ...

    Si un verrou est déjà posé et pas encore périmé, lève `DejaEnCours` —
    l'appelant doit sauter ce passage plutôt qu'empiler les exécutions,
    jamais attendre en bloquant (voir Tier 5 du cahier des charges : « ne
    pas empiler les exécutions qui se chevauchent »). Pas encore appelé
    depuis main2.py à ce jour — voir la note d'intégration dans
    cout_suivi.py pour pourquoi ce dépôt n'y touche pas aujourd'hui.
    """

    def __init__(self, ttl_secondes=3600):
        self._ttl = ttl_secondes
        self._chemin = _chemin_verrou()

    def __enter__(self):
        chemin = self._chemin
        if chemin.exists():
            age = time.time() - chemin.stat().st_mtime
            if age < self._ttl:
                raise DejaEnCours("verrou posé il y a %ds (TTL %ds)" % (int(age), self._ttl))
            # Verrou périmé (plantage du passage précédent) : on le reprend.
        io.open(str(chemin), "w", encoding="utf-8").write(str(os.getpid()))
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._chemin.unlink()
        except FileNotFoundError:
            pass
        return False


def _chemin():
    return config.chemin_donnees(FICHIER, creer_dossier=True)


def _lire_tout():
    chemin = _chemin()
    try:
        with io.open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"taches": []}


def _ecrire_tout(donnees):
    chemin = _chemin()
    tmp = str(chemin) + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(donnees, ensure_ascii=False, indent=2))
    os.replace(tmp, chemin)


def _heure_valide(heure):
    if heure is None:
        return True
    try:
        h, m = heure.split(":")
        return len(heure) == 5 and 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except Exception:
        return False


def mettre_en_file(description, source="texte", heure=None, echeance=None):
    """
    Ajoute une tâche en attente. Renvoie son identifiant.

    `heure` (optionnel, "HH:MM") : ne pas traiter avant cette heure locale.
    Même mécanique que `boucle_rappels()` (comparaison de chaîne "HH:MM"
    contre l'heure courante) — pas un second moteur de cron, la même
    vérification appliquée à une file différente. Sans `heure`, la tâche
    est traitée dès que l'exécuteur en arrière-plan l'atteint (comportement
    B1/B2 d'origine, inchangé).

    `echeance` (optionnel, "HH:MM", mission E) : au lieu d'une seule
    réponse, l'exécuteur se critique et s'améliore (raffinement.py) tant
    qu'il reste du temps avant cette heure. Sans `echeance`, une seule
    passe (comportement B2 d'origine).
    """
    if not _heure_valide(heure):
        raise ValueError("heure invalide : %r (attendu HH:MM, 00-23:00-59, ou None)" % (heure,))
    if not _heure_valide(echeance):
        raise ValueError("echeance invalide : %r (attendu HH:MM, 00-23:00-59, ou None)" % (echeance,))
    donnees = _lire_tout()
    tache = {
        "id": uuid.uuid4().hex[:12],
        "description": description,
        "source": source,
        "heure": heure,
        "echeance": echeance,
        "statut": "en_attente",
        "cree_le": time.time(),
        "termine_le": None,
        "resultat": None,
        "erreur": None,
        "vue_au_reveil": False,
    }
    donnees.setdefault("taches", []).append(tache)
    _ecrire_tout(donnees)
    return tache["id"]


def lister(statut=None):
    """Toutes les tâches, ou seulement celles d'un statut donné."""
    taches = _lire_tout().get("taches", [])
    if statut is None:
        return taches
    if statut not in STATUTS:
        raise ValueError("statut inconnu : %r (attendus : %s)" % (statut, ", ".join(STATUTS)))
    return [t for t in taches if t["statut"] == statut]


def _heure_arrivee(heure_cible, cree_le, maintenant=None):
    """
    Le prochain passage de `heure_cible` (HH:MM) après la création de la
    tâche est-il déjà là ?

    PAS une comparaison de chaînes "HH:MM" <= "HH:MM" — testée en pratique,
    elle casse au passage de minuit : à 23h20, une tâche pour "00:20" (donc
    demain) comparait "00:20" <= "23:20" comme VRAI (ordre lexicographique),
    la traitant comme déjà due alors qu'elle ne l'est pas encore. La cible
    est donc ancrée en timestamp réel au moment de la création — si l'heure
    demandée est déjà passée CE jour-là, elle vise le lendemain. Cette
    ancre ne bouge plus ensuite, contrairement à une comparaison refaite
    à chaque vérification qui redonnerait un résultat différent selon
    quand on regarde.
    """
    if not heure_cible:
        return True
    h, m = (int(x) for x in heure_cible.split(":"))
    cree = time.localtime(cree_le)
    cible_ts = time.mktime((cree.tm_year, cree.tm_mon, cree.tm_mday, h, m, 0, 0, 0, -1))
    if cible_ts < cree_le:
        cible_ts += 86400
    maintenant_ts = time.mktime(maintenant) if maintenant else time.time()
    return maintenant_ts >= cible_ts


def prochaine_en_attente(maintenant=None):
    """
    La plus ancienne tâche en_attente PRÊTE à être traitée, ou None.

    Une tâche sans `heure` est toujours prête (comportement d'origine).
    `maintenant` (struct_time) est injectable pour les tests, comme
    temps_restant_secondes() dans raffinement.py.
    """
    pretes = [t for t in lister("en_attente")
              if _heure_arrivee(t.get("heure"), t["cree_le"], maintenant)]
    return min(pretes, key=lambda t: t["cree_le"]) if pretes else None


def _maj(id_tache, **champs):
    donnees = _lire_tout()
    for t in donnees.get("taches", []):
        if t["id"] == id_tache:
            t.update(champs)
            _ecrire_tout(donnees)
            return True
    return False


def marquer_en_cours(id_tache):
    return _maj(id_tache, statut="en_cours")


def marquer_terminee(id_tache, resultat):
    return _maj(id_tache, statut="terminee", resultat=resultat, termine_le=time.time())


def marquer_echouee(id_tache, raison):
    """
    Une raison est OBLIGATOIRE — pas de champ vide. `traiter_reponse_ia`
    dit pourquoi une capacité manque ; l'exécuteur de nuit doit dire
    pourquoi il a échoué, avec la même discipline.
    """
    if not raison or not str(raison).strip():
        raise ValueError("marquer_echouee exige une raison non vide")
    return _maj(id_tache, statut="echouee", erreur=str(raison), termine_le=time.time())


def a_signaler():
    """
    Tâches terminées ou échouées, jamais encore vues au réveil.

    Ne modifie rien : c'est à l'appelant (le briefing) d'appeler
    `marquer_vue` une fois qu'il les a réellement montrées/dites —
    sinon une tâche pourrait disparaître du briefing sans que
    l'utilisateur l'ait vue passer.
    """
    return [t for t in lister() if t["statut"] in ("terminee", "echouee") and not t["vue_au_reveil"]]


def marquer_vue(id_tache):
    return _maj(id_tache, vue_au_reveil=True)
