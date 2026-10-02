# -*- coding: utf-8 -*-
"""Vérifie taches_nocturnes.py — la file, pas l'exécution (B2)."""

import io
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
import taches_nocturnes as tn

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


# Isoler le fichier réel : on redirige vers un fichier de test, on le
# restaure à la fin, pour ne jamais toucher la vraie file de l'utilisateur.
_chemin_reel = tn._chemin()
_sauvegarde = None
if os.path.exists(_chemin_reel):
    _sauvegarde = io.open(_chemin_reel, encoding="utf-8").read()

try:
    tn._ecrire_tout({"taches": []})

    id1 = tn.mettre_en_file("résume les actus tech de la semaine", source="voix")
    verifier("mise en file renvoie un id", bool(id1))
    verifier("nouvelle tâche en_attente", tn.lister("en_attente")[0]["id"] == id1)
    verifier("statut initial correct", tn.lister("en_attente")[0]["statut"] == "en_attente")

    id2 = tn.mettre_en_file("vérifie les mises à jour disponibles")
    verifier("2 tâches en attente", len(tn.lister("en_attente")) == 2)
    verifier("la plus ancienne en premier", tn.prochaine_en_attente()["id"] == id1)

    tn.marquer_en_cours(id1)
    verifier("passage en_cours", tn.lister("en_cours")[0]["id"] == id1)
    verifier("plus dans en_attente une fois en_cours", len(tn.lister("en_attente")) == 1)

    tn.marquer_terminee(id1, "5 articles trouvés, résumé prêt")
    t1 = [t for t in tn.lister() if t["id"] == id1][0]
    verifier("terminee : statut", t1["statut"] == "terminee")
    verifier("terminee : résultat conservé", t1["resultat"] == "5 articles trouvés, résumé prêt")
    verifier("terminee : horodatage de fin posé", t1["termine_le"] is not None)

    tn.marquer_en_cours(id2)
    tn.marquer_echouee(id2, "winget indisponible sur cette machine")
    t2 = [t for t in tn.lister() if t["id"] == id2][0]
    verifier("echouee : statut", t2["statut"] == "echouee")
    verifier("echouee : raison conservée", "winget" in t2["erreur"])

    erreur_raison_vide = False
    try:
        tn.marquer_echouee(id2, "")
    except ValueError:
        erreur_raison_vide = True
    verifier("marquer_echouee refuse une raison vide", erreur_raison_vide)

    a_voir = tn.a_signaler()
    verifier("2 tâches à signaler au réveil (1 réussie, 1 échouée)", len(a_voir) == 2)
    verifier("rien de modifié tant que non vu", all(not t["vue_au_reveil"] for t in a_voir))

    tn.marquer_vue(id1)
    a_voir_apres = tn.a_signaler()
    verifier("une seule tâche restante à signaler après avoir vu la première",
              len(a_voir_apres) == 1 and a_voir_apres[0]["id"] == id2)

    statut_invalide = False
    try:
        tn.lister("nimportequoi")
    except ValueError:
        statut_invalide = True
    verifier("statut inconnu refusé, pas silencieusement ignoré", statut_invalide)

    # ── Heure programmée (extension type cron, inspirée de Hermes) ─────────
    # Temps injecté, déterministe — pas de calcul relatif à l'heure réelle :
    # ça a cassé une fois pile au passage de minuit (23h20 + 1h = 00h20,
    # "demain" en vrai mais comparé comme "aujourd'hui" par erreur). Le bug
    # était réel, pas le test — corrigé dans prochaine_en_attente(). Le
    # test fixe maintenant "cree_le" directement dans le stockage plutôt
    # que de dépendre de l'heure réelle d'exécution.
    tn._ecrire_tout({"taches": []})

    def _a2(h, m):
        n = time.localtime()
        return time.localtime(time.mktime((n.tm_year, n.tm_mon, n.tm_mday, h, m, 0, 0, 0, -1)))

    _midi = time.mktime(_a2(12, 0))
    id_future = tn.mettre_en_file("tâche pour plus tard", heure="13:00")
    id_arrivee = tn.mettre_en_file("tâche dont l'heure est arrivée", heure="11:30")
    id_sans_heure = tn.mettre_en_file("tâche sans heure, comme avant")

    # Créées "à 11h" simulé : "11:30" est une cible propre dans le futur
    # PAR RAPPORT À LA CRÉATION (pas d'ambiguïté de roulement au lendemain),
    # et déjà arrivée au moment de la vérification à midi.
    # NOTE : une cible ANTÉRIEURE à sa propre création (ex. heure="11:00"
    # créée à midi) n'a pas de réponse évidente pour ce champ — "heure"
    # sert à différer VERS un futur (comme "echeance" dans raffinement.py),
    # donc _heure_arrivee() la roule au lendemain plutôt que de la traiter
    # comme "déjà satisfaite". Testé et confirmé volontaire, pas un bug.
    _onze_heures = time.mktime(_a2(11, 0))
    _donnees = tn._lire_tout()
    for _t in _donnees["taches"]:
        _t["cree_le"] = _onze_heures
    tn._ecrire_tout(_donnees)

    prete = tn.prochaine_en_attente(maintenant=_a2(12, 0))
    verifier("une tâche programmée dans le futur n'est PAS choisie",
              prete is not None and prete["id"] != id_future)
    verifier("une tâche dont l'heure est arrivée passe avant une tâche sans heure",
              prete is not None and prete["id"] == id_arrivee)

    heure_invalide = False
    try:
        tn.mettre_en_file("mauvaise heure", heure="25:99")
    except ValueError:
        heure_invalide = True
    verifier("heure invalide refusée à la création, pas silencieusement acceptée", heure_invalide)

    heure_invalide2 = False
    try:
        tn.mettre_en_file("mauvais format", heure="demain")
    except ValueError:
        heure_invalide2 = True
    verifier("format d'heure non HH:MM refusé", heure_invalide2)

    tn.marquer_en_cours(id_arrivee)
    tn.marquer_terminee(id_arrivee, "faite")
    prete2 = tn.prochaine_en_attente(maintenant=_a2(12, 0))
    verifier("la tâche sans heure est choisie une fois celle qui était due traitée",
              prete2 is not None and prete2["id"] == id_sans_heure)

    # Verrou anti-chevauchement : isole aussi le fichier .lock reel.
    _chemin_verrou = tn._chemin_verrou()
    if _chemin_verrou.exists():
        _chemin_verrou.unlink()
    try:
        with tn.verrou_executeur():
            verifier("verrou pose pendant le bloc `with`", _chemin_verrou.exists())
            leve = False
            try:
                with tn.verrou_executeur():
                    pass
            except tn.DejaEnCours:
                leve = True
            verifier("second verrou pendant que le premier tient -> DejaEnCours", leve)
        verifier("verrou relache a la sortie du `with`", not _chemin_verrou.exists())

        # Verrou perime (simulate un plantage precedent) : repris sans lever.
        io.open(str(_chemin_verrou), "w", encoding="utf-8").write("1234")
        vieux = time.time() - 999999
        os.utime(str(_chemin_verrou), (vieux, vieux))
        repris = False
        with tn.verrou_executeur(ttl_secondes=3600):
            repris = True
        verifier("verrou perime (age > TTL) est repris sans lever", repris)
    finally:
        if _chemin_verrou.exists():
            _chemin_verrou.unlink()

finally:
    if _sauvegarde is not None:
        io.open(_chemin_reel, "w", encoding="utf-8").write(_sauvegarde)
    elif os.path.exists(_chemin_reel):
        os.remove(_chemin_reel)

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Taches nocturnes (file B1) : conforme.")
