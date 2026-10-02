# -*- coding: utf-8 -*-
r"""
J.A.R.V.I.S — Emploi du temps Pronote dans Google Agenda
=========================================================
Pronote sait ce qui se passe ; l'agenda du telephone, non. Ce module recopie
l'emploi du temps dans un agenda Google DEDIE, et le corrige quand un cours
saute : le cours passe en « ANNULE », il devient transparent (l'heure
redevient libre pour tout ce qui lit ton agenda) et sa raison est ecrite
dedans.

POURQUOI PAS L'ABONNEMENT iCal DE PRONOTE
Pronote publie une URL iCal, et Google sait s'y abonner sans une ligne de
code. Deux raisons de ne pas s'en contenter : un agenda abonne est en
LECTURE SEULE — impossible d'y marquer une annulation — et Google ne le
rafraichit que toutes les quelques heures, parfois une fois par jour. Pour
« mon prof est absent ce matin », c'est exactement le delai qui rend
l'information inutile.

UN AGENDA A PART, JAMAIS L'AGENDA PRINCIPAL
Tout est ecrit dans un agenda cree pour ca. Une resynchronisation peut donc
supprimer ce qu'elle a mis sans jamais risquer un rendez-vous personnel. Et
la suppression ne vise QUE les evenements portant la marque de ce module
(`jarvis_source = pronote`) : un evenement ajoute a la main dans cet agenda
survit.

CE MODULE NE PARLE NI A HA NI A GOOGLE DIRECTEMENT
Il transforme et compare. Le lecteur d'etat HA et le service Google lui sont
passes, ce qui rend la partie qui peut se tromper — la normalisation d'un
cours et le calcul creer/modifier/supprimer — verifiable sans reseau.

    venv\Scripts\python.exe agenda_scolaire.py
"""

import hashlib
import os
import sys
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:      # Python < 3.9 : la fenetre partira en UTC, pas faux, juste large
    ZoneInfo = None

NOM_AGENDA = "Emploi du temps — Pronote (JARVIS)"
MARQUE = "pronote"
FUSEAU = "Europe/Paris"
COULEUR_NORMALE = "9"      # Myrtille
COULEUR_ANNULE = "8"       # Graphite

# Les cles varient selon les versions de l'integration : on accepte les
# alternatives plutot que de dependre d'un seul nom. Un cours dont on ne sait
# pas lire l'heure est ECARTE et signale, jamais pose n'importe ou.
_CLES_DEBUT = ("start_at", "start_time", "start", "debut")
_CLES_FIN = ("end_at", "end_time", "end", "fin")
_CLES_MATIERE = ("lesson", "subject", "matiere", "name")
_CLES_SALLE = ("classroom", "room", "salle")
_CLES_PROF = ("teacher_name", "teacher", "prof")
_CLES_STATUT = ("status", "statut")


def _val(cours, cles, defaut=""):
    """Première clé présente et non vide. Tolère un dict comme un objet."""
    for cle in cles:
        valeur = cours.get(cle) if hasattr(cours, "get") else getattr(cours, cle, None)
        if valeur not in (None, "", []):
            return valeur
    return defaut


def est_annule(cours):
    """
    Un cours est-il annulé ?

    Deux signaux, parce qu'ils ne sont pas toujours tous les deux là :
    le drapeau `canceled`, et un statut contenant « annul » (Pronote écrit
    « Cours annulé », « Prof. absent »). Un accès direct à `cours['canceled']`
    sur un cours où la clé manque lève — c'est ce qui a cassé la première
    version de l'automatisation Home Assistant.
    """
    if bool(_val(cours, ("canceled", "cancelled", "annule"), False)):
        return True
    statut = str(_val(cours, _CLES_STATUT, "")).lower()
    return "annul" in statut or "absent" in statut


def cle_stable(debut, matiere):
    """
    L'identité d'un cours pour l'agenda : début + matière, hachés.

    Pas l'identifiant interne de Pronote : il n'est pas garanti stable d'un
    rafraîchissement à l'autre, et deux resynchronisations créeraient alors
    des doublons au lieu de mettre à jour.
    """
    graine = "%s|%s" % (str(debut).strip(), str(matiere).strip().lower())
    return hashlib.sha1(graine.encode("utf-8")).hexdigest()[:20]


def normaliser(cours):
    """
    (fiche, raison). Un cours Pronote brut -> ce dont l'agenda a besoin.

    `raison` non vide = ce cours est inexploitable et pourquoi. On ne pose
    pas un cours dont on n'a pas su lire l'heure : un événement à la mauvaise
    heure est pire qu'un événement absent.
    """
    debut = str(_val(cours, _CLES_DEBUT, ""))
    fin = str(_val(cours, _CLES_FIN, ""))
    matiere = str(_val(cours, _CLES_MATIERE, ""))
    if not debut or ("T" not in debut and " " not in debut):
        return None, "heure de début illisible (%r)" % (debut,)
    if not fin or ("T" not in fin and " " not in fin):
        return None, "heure de fin illisible (%r)" % (fin,)
    if not matiere:
        return None, "matière absente"
    return {
        "cle": cle_stable(debut, matiere),
        "debut": debut.replace(" ", "T"),
        "fin": fin.replace(" ", "T"),
        "matiere": matiere,
        "salle": str(_val(cours, _CLES_SALLE, "")),
        "prof": str(_val(cours, _CLES_PROF, "")),
        "statut": str(_val(cours, _CLES_STATUT, "")),
        "annule": est_annule(cours),
    }, ""


def normaliser_tout(cours_bruts):
    """(fiches, ecartes). Les cours exploitables, et ceux qui ne le sont pas."""
    fiches, ecartes = [], []
    for brut in cours_bruts or []:
        fiche, raison = normaliser(brut)
        if fiche:
            fiches.append(fiche)
        else:
            ecartes.append(raison)
    return fiches, ecartes


def evenement(fiche):
    """Le corps d'événement Google pour un cours."""
    titre = ("ANNULE — " + fiche["matiere"]) if fiche["annule"] else fiche["matiere"]
    details = []
    if fiche["prof"]:
        details.append("Professeur : " + fiche["prof"])
    if fiche["salle"]:
        details.append("Salle : " + fiche["salle"])
    if fiche["annule"]:
        details.append("Cours annulé" + (" — " + fiche["statut"] if fiche["statut"] else ""))
    details.append("Posé par JARVIS depuis Pronote.")
    return {
        "summary": titre,
        "location": fiche["salle"],
        "description": "\n".join(details),
        "start": {"dateTime": fiche["debut"], "timeZone": FUSEAU},
        "end": {"dateTime": fiche["fin"], "timeZone": FUSEAU},
        "colorId": COULEUR_ANNULE if fiche["annule"] else COULEUR_NORMALE,
        # transparent : l'heure d'un cours annulé redevient libre pour tout ce
        # qui lit l'agenda (partage familial, suggestions de créneaux).
        "transparency": "transparent" if fiche["annule"] else "opaque",
        # Aucun rappel : l'alerte utile part déjà sur le téléphone via Home
        # Assistant. Une notification par cours rendrait l'agenda inutilisable.
        "reminders": {"useDefault": False, "overrides": []},
        "extendedProperties": {"private": {"jarvis_cle": fiche["cle"],
                                           "jarvis_source": MARQUE}},
    }


def _marque(ev):
    return (ev.get("extendedProperties", {}) or {}).get("private", {}) or {}


def _identique(existant, voulu):
    """Comparaison sur ce que CE module écrit, rien d'autre."""
    for champ in ("summary", "location", "description", "colorId", "transparency"):
        if (existant.get(champ) or "") != (voulu.get(champ) or ""):
            return False
    for borne in ("start", "end"):
        if (existant.get(borne, {}) or {}).get("dateTime", "")[:19] != \
           (voulu.get(borne, {}) or {}).get("dateTime", "")[:19]:
            return False
    return True


def diff(fiches, evenements_existants):
    """
    (a_creer, a_modifier, a_supprimer).

    `a_supprimer` ne contient QUE des événements portant la marque de ce
    module : un rendez-vous ajouté à la main dans cet agenda n'est jamais
    touché, même s'il ne correspond à aucun cours.
    """
    voulus = {f["cle"]: evenement(f) for f in fiches}
    connus = {}
    for ev in evenements_existants or []:
        marque = _marque(ev)
        if marque.get("jarvis_source") != MARQUE:
            continue          # pas à nous : on n'y touche pas
        cle = marque.get("jarvis_cle")
        if cle:
            connus[cle] = ev

    a_creer = [voulus[c] for c in voulus if c not in connus]
    a_modifier = [(connus[c]["id"], voulus[c]) for c in voulus
                  if c in connus and not _identique(connus[c], voulus[c])]
    a_supprimer = [connus[c]["id"] for c in connus if c not in voulus]
    return a_creer, a_modifier, a_supprimer


def fenetre(fiches):
    """
    (timeMin, timeMax) RFC 3339 couvrant les cours, du premier jour a minuit
    au lendemain du dernier.

    Pronote donne des heures SANS fuseau. Y coller « +02:00 » en dur serait
    juste six mois par an ; on attache le vrai fuseau, qui connait l'heure
    d'ete. La fenetre est elargie a la journee entiere pour qu'un evenement
    pose plus tot dans la journee soit vu et compare, pas duplique.
    """
    jour_debut = min(f["debut"] for f in fiches)[:10]
    jour_fin = max(f["fin"] for f in fiches)[:10]
    tz = ZoneInfo(FUSEAU) if ZoneInfo else None
    d = datetime.fromisoformat(jour_debut).replace(tzinfo=tz)
    f = datetime.fromisoformat(jour_fin).replace(tzinfo=tz) + timedelta(days=1)
    if tz is None:
        return d.isoformat() + "Z", f.isoformat() + "Z"
    return d.isoformat(), f.isoformat()


# ── Côté Google ──────────────────────────────────────────────────────────

def trouver_ou_creer_agenda(service, nom=NOM_AGENDA):
    """L'id de l'agenda dédié, créé s'il n'existe pas. (id, raison)."""
    try:
        page = None
        while True:
            liste = service.calendarList().list(pageToken=page).execute()
            for entree in liste.get("items", []):
                if entree.get("summary") == nom:
                    return entree["id"], ""
            page = liste.get("nextPageToken")
            if not page:
                break
        cree = service.calendars().insert(
            body={"summary": nom, "timeZone": FUSEAU}).execute()
        return cree["id"], ""
    except Exception as e:
        return None, "agenda inaccessible : %s" % e


def evenements_existants(service, agenda_id, debut_iso, fin_iso):
    """Les événements de la fenêtre, toutes marques confondues."""
    sortie, page = [], None
    while True:
        reponse = service.events().list(
            calendarId=agenda_id, timeMin=debut_iso, timeMax=fin_iso,
            singleEvents=True, maxResults=2500, pageToken=page).execute()
        sortie.extend(reponse.get("items", []))
        page = reponse.get("nextPageToken")
        if not page:
            return sortie


def appliquer(service, agenda_id, a_creer, a_modifier, a_supprimer):
    """Exécute le diff. Renvoie le compte de ce qui a réellement été fait."""
    faits = {"crees": 0, "modifies": 0, "supprimes": 0, "echecs": []}
    for corps in a_creer:
        try:
            service.events().insert(calendarId=agenda_id, body=corps).execute()
            faits["crees"] += 1
        except Exception as e:
            faits["echecs"].append("création %s : %s" % (corps.get("summary"), e))
    for id_ev, corps in a_modifier:
        try:
            service.events().update(calendarId=agenda_id, eventId=id_ev, body=corps).execute()
            faits["modifies"] += 1
        except Exception as e:
            faits["echecs"].append("mise à jour %s : %s" % (corps.get("summary"), e))
    for id_ev in a_supprimer:
        try:
            service.events().delete(calendarId=agenda_id, eventId=id_ev).execute()
            faits["supprimes"] += 1
        except Exception as e:
            faits["echecs"].append("suppression %s : %s" % (id_ev, e))
    return faits


# ── Côté Pronote / Home Assistant ────────────────────────────────────────

# Les capteurs hass-pronote s'appellent sensor.pronote_<nom>_<prenom>_<quoi>.
# Le debut (« pronote_<nom>_<prenom> ») se regle dans .env / l'assistant
# d'installation (PRONOTE_SENSOR_PREFIX). Vide = fonction non configuree :
# rien n'est lu dans Home Assistant.
PREFIXE = os.getenv("PRONOTE_SENSOR_PREFIX", "").strip().removeprefix("sensor.").rstrip("_")
NON_CONFIGURE = ("Pronote n'est pas configure : renseigne PRONOTE_SENSOR_PREFIX "
                 "(ex. pronote_dupont_alex) dans l'assistant d'installation")


def _capteur(quoi):
    return "sensor.%s_%s" % (PREFIXE or "pronote_eleve", quoi)


def _lecteur_ha():
    """Lecteur d'etat HA reel, ou None tant que le prefixe n'est pas regle."""
    if not PREFIXE:
        return None
    import ha_config
    return ha_config.ha_get_etat


CAPTEURS = tuple(_capteur(q) for q in ("period_s_timetable", "today_s_timetable",
                                       "tomorrow_s_timetable", "next_day_s_timetable"))

CAPTEUR_DEVOIRS = _capteur("homework")
CAPTEUR_EVALUATIONS = _capteur("evaluations")
CAPTEUR_NOTES = _capteur("grades")
CAPTEUR_MOYENNE = _capteur("overall_average")
CAPTEUR_MOYENNES = _capteur("averages")
CAPTEUR_ABSENCES = _capteur("absences")
CAPTEUR_RETARDS = _capteur("delays")
CAPTEUR_PUNITIONS = _capteur("punishments")


def _liste_attribut(lecteur, capteur, attribut):
    """
    La liste portee par un attribut de capteur HA, ou (liste_vide, raison).

    Meme garde que cours_depuis_ha : `ha_get_etat` renvoie la CHAINE
    "inconnu" quand l'attribut manque, jamais None — verifie une fois de
    trop cette session pour ne plus jamais l'oublier. Sans ce controle de
    type, une boucle sur "inconnu" la parcourrait lettre par lettre.
    """
    try:
        valeur = lecteur(capteur, attribut)
    except Exception as e:
        return [], "%s injoignable : %s" % (capteur, e)
    if not isinstance(valeur, list):
        return [], "%s ne publie rien (hors periode scolaire ?)" % capteur
    return valeur, ""


def normaliser_devoir(brut):
    """
    Un devoir Pronote brut -> fiche d'affichage.

    Cles verifiees dans le code source de l'integration (delphiki/hass-pronote,
    pronote_formatter.format_homework) — PAS devinees, contrairement au
    premier jet de l'emploi du temps qui avait tolere plusieurs noms
    possibles faute de source fiable a l'epoque.
    """
    return {
        "date": str(brut.get("date", "")),
        "matiere": str(brut.get("subject", "")),
        "titre": str(brut.get("short_description", "")),
        "description": str(brut.get("description", "")),
        "fait": bool(brut.get("done", False)),
    }


def normaliser_evaluation(brut):
    """Une evaluation annoncee. Cles verifiees (format_evaluation)."""
    return {
        "date": str(brut.get("date", "")),
        "matiere": str(brut.get("subject", "")),
        "nom": str(brut.get("name", "")),
        "coefficient": str(brut.get("coefficient", "")),
        "description": str(brut.get("description", "")),
    }


def normaliser_note(brut):
    """
    Une note. `note` reste une CHAINE deliberement : Pronote y met parfois
    « Absent », « Dispensé », « Non noté » — la convertir en nombre casserait
    sur ces cas, et ce module n'a besoin d'afficher, jamais de calculer
    (la moyenne existe deja cote Pronote, voir moyenne_generale_depuis_ha).
    """
    return {
        "date": str(brut.get("date", "")),
        "matiere": str(brut.get("subject", "")),
        "note": str(brut.get("grade", "")),
        "bareme": str(brut.get("out_of", "")),
        "coefficient": str(brut.get("coefficient", "")),
        "commentaire": str(brut.get("comment", "")),
    }


def normaliser_moyenne(brut):
    """Une moyenne par matiere. La note reste une CHAINE (Pronote peut renvoyer autre chose qu-un nombre)."""
    return {
        "matiere": str(brut.get("subject", "") or ""),
        "eleve": str(brut.get("average", "") or ""),
        "classe": str(brut.get("class", "") or ""),
        "mini": str(brut.get("min", "") or ""),
        "maxi": str(brut.get("max", "") or ""),
        "bareme": str(brut.get("out_of", "") or ""),
    }


def normaliser_absence(brut):
    """Une absence. `justifiee` peut manquer -> False, jamais une exception."""
    return {
        "debut": str(brut.get("from", "") or ""),
        "fin": str(brut.get("to", "") or ""),
        "heures": str(brut.get("hours", "") or ""),
        "justifiee": bool(brut.get("justified", False)),
        "motif": str(brut.get("reason", "") or ""),
    }


def normaliser_retard(brut):
    """Un retard."""
    return {
        "date": str(brut.get("date", "") or ""),
        "minutes": str(brut.get("minutes", "") or ""),
        "justifie": bool(brut.get("justified", False)),
        "motif": str(brut.get("justification", "") or ""),
    }


def normaliser_punition(brut):
    """Une punition."""
    return {
        "date": str(brut.get("date", "") or ""),
        "matiere": str(brut.get("subject", "") or ""),
        "nature": str(brut.get("nature", "") or ""),
        "motif": str(brut.get("reasons", "") or ""),
        "donnee_par": str(brut.get("giver", "") or ""),
    }


def devoirs_evaluations_notes(lecteur=None):
    """
    (donnees, raisons). Devoirs, evaluations, notes et moyenne generale, en
    un seul appel — le panneau du HUD les affiche ensemble.

    Chaque source est INDEPENDANTE : si les evaluations sont muettes mais
    les devoirs repondent, on renvoie les devoirs quand meme. `raisons` liste
    ce qui a echoue, source par source, jamais une liste vide silencieuse
    a la place d'un « Pronote ne publie rien ».
    """
    if lecteur is None:
        lecteur = _lecteur_ha()
    if lecteur is None:
        vide = {"devoirs": [], "evaluations": [], "notes": [], "moyenne": None,
                "moyennes": [], "absences": [], "retards": [], "punitions": []}
        return vide, [NON_CONFIGURE]

    devoirs_bruts, raison_dev = _liste_attribut(lecteur, CAPTEUR_DEVOIRS, "homework")
    evals_bruts, raison_eval = _liste_attribut(lecteur, CAPTEUR_EVALUATIONS, "evaluations")
    notes_bruts, raison_notes = _liste_attribut(lecteur, CAPTEUR_NOTES, "grades")
    moyennes_bruts, raison_moys = _liste_attribut(lecteur, CAPTEUR_MOYENNES, "averages")
    absences_bruts, raison_abs = _liste_attribut(lecteur, CAPTEUR_ABSENCES, "absences")
    retards_bruts, raison_ret = _liste_attribut(lecteur, CAPTEUR_RETARDS, "delays")
    punitions_bruts, raison_pun = _liste_attribut(lecteur, CAPTEUR_PUNITIONS, "punishments")

    try:
        moyenne = lecteur(CAPTEUR_MOYENNE)
    except Exception as e:
        moyenne = None
        raison_moy = "moyenne injoignable : %s" % e
    else:
        raison_moy = "" if moyenne not in (None, "inconnu", "unknown", "unavailable") else \
            "moyenne indisponible"
        if raison_moy:
            moyenne = None

    donnees = {
        "devoirs": [normaliser_devoir(d) for d in devoirs_bruts if isinstance(d, dict)],
        "evaluations": [normaliser_evaluation(e) for e in evals_bruts if isinstance(e, dict)],
        "notes": [normaliser_note(n) for n in notes_bruts if isinstance(n, dict)],
        "moyenne": moyenne,
        "moyennes": [normaliser_moyenne(m) for m in moyennes_bruts if isinstance(m, dict)],
        "absences": [normaliser_absence(a) for a in absences_bruts if isinstance(a, dict)],
        "retards": [normaliser_retard(r) for r in retards_bruts if isinstance(r, dict)],
        "punitions": [normaliser_punition(p) for p in punitions_bruts if isinstance(p, dict)],
    }
    raisons = [r for r in (raison_dev, raison_eval, raison_notes, raison_moy,
                           raison_moys, raison_abs, raison_ret, raison_pun) if r]
    return donnees, raisons


# ── Plan de revision ──────────────────────────────────────────────────────
#
# Meme algorithme que la maquette du panneau scolaire, porte ici sur des
# donnees REELLES. Une
# difference assumee : Pronote ne dit jamais combien de temps prend un
# devoir. DUREE_DEVOIR_PAR_DEFAUT_MIN est une ESTIMATION, presentee comme
# telle au HUD — jamais donnee pour une valeur venue de Pronote.

DUREE_DEVOIR_PAR_DEFAUT_MIN = 30
DUREE_REVISION_MIN = 30
FENETRE_JOURS = 7
NOMS_JOURS = ("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche")


def _prochains_jours(nombre=FENETRE_JOURS, aujourdhui=None):
    """
    [{index, date, nom, capacite, minutes, blocs, utilise}] pour les N
    prochains jours, aujourd'hui inclus en index 0.

    `capacite` est un multiplicateur de `minutes_par_soir` : plus large le
    week-end, uniforme en semaine — on ne connait pas l'emploi du temps
    reel de chaque jour tant que les capteurs sont muets (voir
    cours_depuis_ha), donc pas de traitement special pour un mercredi
    apres-midi qui pourrait tres bien avoir cours.
    """
    import datetime
    base = aujourdhui or datetime.date.today()
    jours = []
    for i in range(nombre):
        d = base + datetime.timedelta(days=i)
        capacite = 1.5 if d.weekday() >= 5 else 1.0
        jours.append({"index": i, "date": d.isoformat(), "nom": NOMS_JOURS[d.weekday()],
                      "capacite": capacite, "minutes": 0, "blocs": [], "utilise": 0})
    return jours


def _index_jour(date_iso, jours):
    """
    L'index du jour correspondant a une date ISO, ou None.

    None couvre deux cas distincts, DELIBEREMENT confondus ici : une date
    illisible (pas de sens a planifier) et une echeance au-dela de la
    fenetre (pas encore le moment d'y penser). L'appelant compte les deux
    comme "pas planifie", jamais comme une erreur qui interrompt le plan.
    Une echeance DEJA PASSEE est ramenee au premier jour : en retard,
    jamais escamotee.
    """
    date_iso = str(date_iso or "")
    if len(date_iso) < 10:
        return None
    date_iso = date_iso[:10]
    if not jours:
        return None
    if date_iso < jours[0]["date"]:
        return 0
    for j in jours:
        if j["date"] == date_iso:
            return j["index"]
    return None


def construire_plan(devoirs, evaluations, minutes_par_soir=75, aujourdhui=None):
    """
    Repartit les devoirs non faits et des seances de revision d'evaluations
    sur les prochains jours, sans jamais depasser la capacite de chacun.

    - un devoir NON FAIT devient une tache, echeance = sa date Pronote
    - une evaluation devient 2 seances de revision de 30 min (3 si son
      coefficient est >= 2), espacees automatiquement par le placement,
      echeance = sa date
    - tri par echeance la plus proche, puis poids (coefficient) decroissant,
      puis duree decroissante
    - placement glouton AU PLUS TOT, un jour strictement AVANT l'echeance
      (jamais le jour meme : au moment ou c'est du, il est trop tard pour
      reviser) ; ce qui ne rentre nulle part est place au dernier jour
      possible et marque `deborde` — jamais efface du plan, meme regle que
      partout ailleurs dans ce depot.

    Renvoie {jours, en_surcharge, hors_fenetre, minutes_par_soir}.
    `hors_fenetre` compte les devoirs/evaluations dont l'echeance depasse
    FENETRE_JOURS : ils existent, mais ce plan ne les couvre pas encore.
    """
    minutes_par_soir = max(15, int(minutes_par_soir or 75))
    jours = _prochains_jours(aujourdhui=aujourdhui)
    for j in jours:
        j["minutes"] = round(minutes_par_soir * j["capacite"])

    taches = []
    hors_fenetre = 0

    for d in devoirs:
        if d.get("fait"):
            continue
        idx = _index_jour(d.get("date"), jours)
        if idx is None:
            hors_fenetre += 1
            continue
        taches.append({
            "matiere": d.get("matiere", ""), "titre": d.get("titre") or "Devoir",
            "minutes": DUREE_DEVOIR_PAR_DEFAUT_MIN, "avant": idx, "poids": 0.0,
            "type": "devoir",
        })

    for e in evaluations:
        idx = _index_jour(e.get("date"), jours)
        if idx is None:
            hors_fenetre += 1
            continue
        try:
            coefficient = float(str(e.get("coefficient", "1") or "1").replace(",", "."))
        except ValueError:
            coefficient = 1.0
        seances = 3 if coefficient >= 2 else 2
        for i in range(seances):
            taches.append({
                "matiere": e.get("matiere", ""),
                "titre": "Révision — %s (%d/%d)" % (e.get("nom") or "évaluation", i + 1, seances),
                "minutes": DUREE_REVISION_MIN, "avant": idx, "poids": coefficient,
                "type": "revision",
            })

    taches.sort(key=lambda t: (t["avant"], -t["poids"], -t["minutes"]))

    en_surcharge = 0
    for tache in taches:
        pose = False
        for i in range(0, tache["avant"]):
            if jours[i]["utilise"] + tache["minutes"] <= jours[i]["minutes"]:
                jours[i]["blocs"].append(tache)
                jours[i]["utilise"] += tache["minutes"]
                pose = True
                break
        if not pose:
            cible = min(max(tache["avant"], 0), len(jours) - 1)
            jours[cible]["blocs"].append(dict(tache, deborde=True))
            jours[cible]["utilise"] += tache["minutes"]
            en_surcharge += 1

    return {
        "jours": jours, "en_surcharge": en_surcharge, "hors_fenetre": hors_fenetre,
        "minutes_par_soir": minutes_par_soir,
        "duree_devoir_estimee": DUREE_DEVOIR_PAR_DEFAUT_MIN,
    }


def plan_revision(lecteur=None, minutes_par_soir=75, aujourdhui=None):
    """
    (plan, raisons). Lit devoirs/evaluations depuis HA et construit le plan
    en un seul appel — ce que main2.py expose au HUD.

    Reutilise devoirs_evaluations_notes() : memes garanties (sources
    independantes, jamais d'exception qui remonte, raisons explicites).
    Les notes/moyenne ne servent pas au plan, mais les recalculer separement
    aurait duplique la lecture des capteurs HA pour rien.
    """
    donnees, raisons = devoirs_evaluations_notes(lecteur)
    plan = construire_plan(donnees["devoirs"], donnees["evaluations"], minutes_par_soir,
                           aujourdhui=aujourdhui)
    return plan, raisons


def cours_depuis_ha(lecteur=None, capteurs=CAPTEURS):
    """
    (cours, raison). Tous les cours connus, dédupliqués.

    `lecteur(entity_id, attribut)` est injecté pour les tests ; par défaut
    c'est ha_config.ha_get_etat. Aucun capteur lisible = raison explicite,
    jamais une liste vide silencieuse — un agenda qu'on viderait parce que
    Home Assistant n'a pas répondu serait pire que pas d'agenda du tout.
    """
    if lecteur is None:
        lecteur = _lecteur_ha()
    if lecteur is None:
        return [], NON_CONFIGURE

    tous, vus, lus = [], set(), 0
    for capteur in capteurs:
        try:
            lecons = lecteur(capteur, "lessons")
        except Exception:
            lecons = None
        # ha_config.ha_get_etat renvoie la CHAINE "inconnu" quand l'attribut
        # manque, pas None. Sans ce controle de type, la boucle ci-dessous
        # parcourrait « inconnu » lettre par lettre et compterait le capteur
        # comme lu : on annoncerait « aucun cours exploitable » au lieu de
        # « Pronote ne publie rien ».
        if not isinstance(lecons, list) or not lecons:
            continue
        lus += 1
        for cours in lecons:
            empreinte = "%s|%s" % (_val(cours, _CLES_DEBUT, ""), _val(cours, _CLES_MATIERE, ""))
            if empreinte in vus:
                continue
            vus.add(empreinte)
            tous.append(cours)
    if lus == 0:
        return [], ("aucun capteur d'emploi du temps ne répond — "
                    "Pronote ne publie rien en dehors des périodes scolaires")
    return tous, ""


def synchroniser(service=None, lecteur=None, nom_agenda=NOM_AGENDA):
    """
    Recopie l'emploi du temps dans l'agenda dédié. Renvoie un compte rendu.

    Ne supprime RIEN quand la source est muette : sans cours lisibles, on
    s'arrête avec la raison. La règle du dépôt vaut ici plus qu'ailleurs —
    une source vide effacerait tout l'agenda.
    """
    bruts, raison = cours_depuis_ha(lecteur)
    if raison:
        return {"ok": False, "raison": raison}

    fiches, ecartes = normaliser_tout(bruts)
    if not fiches:
        return {"ok": False, "raison": "aucun cours exploitable (%d écarté(s))" % len(ecartes),
                "ecartes": ecartes}

    if service is None:
        import google_services
        service = google_services.get_calendar_service()
    if service is None:
        return {"ok": False, "raison": "Google Agenda n'est pas autorisé sur cette machine"}

    agenda_id, raison_agenda = trouver_ou_creer_agenda(service, nom_agenda)
    if not agenda_id:
        return {"ok": False, "raison": raison_agenda}

    debut, fin = fenetre(fiches)
    try:
        existants = evenements_existants(service, agenda_id, debut, fin)
    except Exception as e:
        return {"ok": False, "raison": "lecture de l'agenda impossible : %s" % e}

    a_creer, a_modifier, a_supprimer = diff(fiches, existants)
    faits = appliquer(service, agenda_id, a_creer, a_modifier, a_supprimer)
    faits.update({"ok": True, "agenda": nom_agenda, "cours": len(fiches),
                  "annules": sum(1 for f in fiches if f["annule"]), "ecartes": ecartes})
    return faits


_JOURS_SEMAINE = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _sans_accents(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                   if unicodedata.category(c) != "Mn")


def jour_demande(texte, aujourdhui=None):
    """
    (date ISO, libelle) du jour visé par la phrase, ou (None, "").

    Sans precision -> aujourd'hui. Un nom de jour vise la prochaine
    occurrence, aujourd'hui inclus : « les cours de jeudi » un jeudi parle
    de la journee en cours, pas de la semaine prochaine.
    """
    import datetime
    base = aujourdhui or datetime.date.today()
    t = _sans_accents(texte)

    if "apres-demain" in t or "apres demain" in t:
        d = base + datetime.timedelta(days=2)
        return d.isoformat(), "apres-demain"
    if "demain" in t:
        d = base + datetime.timedelta(days=1)
        return d.isoformat(), "demain"
    for i, nom in enumerate(_JOURS_SEMAINE):
        if nom in t:
            ecart = (i - base.weekday()) % 7
            d = base + datetime.timedelta(days=ecart)
            return d.isoformat(), nom
    return base.isoformat(), "aujourd'hui"


def reconnait_question_emploi_du_temps(texte, aujourdhui=None):
    """
    (date ISO, libelle) si la phrase POSE UNE QUESTION sur l'emploi du
    temps, sinon (None, "").

    Trois routages distincts se partagent le sujet « emploi du temps », et
    l'ordre compte :
      - un verbe de mise a jour  -> reconnait_demande (ecrit dans Google)
      - un verbe d'affichage     -> reconnait_ouverture_panneau (ouvre le HUD)
      - le reste, ici            -> on REPOND avec les vraies donnees

    Sans ce troisieme cas, une question libre tombait au modele, a qui le
    prompt affirme « tu AS acces a l'emploi du temps » sans jamais lui
    donner les donnees : il inventait des cours et des salles plausibles.
    """
    t = _sans_accents(texte)

    if any(m in t for m in ("synchronis", "mets a jour", "met a jour", "actualise",
                            "rafraichi", "remets", "mets dans")):
        return None, ""
    if any(m in t for m in ("montre", "ouvre", "affiche", "fais voir")):
        return None, ""

    # « au cours de la journee » n'est pas une question d'emploi du temps :
    # l'idiome contient le mot « cours » et passerait la detection large.
    sans_idiome = t.replace("au cours de", " ").replace("au cours d'", " ")

    explicite = any(m in t for m in ("emploi du temps", "planning scolaire"))
    quand = any(m in sans_idiome for m in _JOURS_SEMAINE) or any(
        m in sans_idiome for m in ("demain", "aujourd"))
    tourne = any(m in sans_idiome for m in ("mes cours", "ses cours", "les cours",
                                            "quels cours", "quel cours", "comme cours",
                                            "j'ai quoi", "jai quoi", "il a quoi"))
    # « cours » seul ne suffit jamais : il lui faut soit un jour vise, soit une
    # tournure de question. Sinon « cours d'eau » declencherait Pronote.
    sujet = explicite or ("cours" in sans_idiome and (quand or tourne)) or (tourne and quand)
    if not sujet:
        return None, ""
    return jour_demande(texte, aujourdhui)


def cours_du_jour(date_iso, lecteur=None):
    """
    (fiches triees, raison) — les cours reels d'une date donnee.

    Filtre sur la date plutot que de faire confiance a un capteur « du
    jour » : le capteur de periode couvre plusieurs semaines, c'est le seul
    qui permette de repondre sur demain ou sur jeudi prochain.
    """
    bruts, raison = cours_depuis_ha(lecteur)
    if raison:
        return [], raison
    fiches, _ecartes = normaliser_tout(bruts)
    dujour = [f for f in fiches if f["debut"][:10] == str(date_iso)]
    dujour.sort(key=lambda f: f["debut"])
    return dujour, ""


def phrase_emploi_du_temps(libelle, fiches):
    """La reponse a dire/afficher. Jamais de cours invente : liste vide = liste vide."""
    if not fiches:
        return "Aucun cours %s." % libelle

    lignes = []
    for f in fiches:
        heure = "%s-%s" % (f["debut"][11:16].replace(":", "h"),
                           f["fin"][11:16].replace(":", "h"))
        bout = "%s : %s" % (heure, f["matiere"])
        if f["salle"]:
            bout += " (%s)" % f["salle"]
        if f["annule"]:
            bout += " — ANNULE"
        lignes.append(bout)

    entete = "Emploi du temps %s (%d cours" % (libelle, len(fiches))
    annules = sum(1 for f in fiches if f["annule"])
    entete += ", %d annule%s" % (annules, "" if annules == 1 else "s") if annules else ""
    entete += ") :"
    saut = chr(10)
    return entete + saut + saut.join("- " + l for l in lignes)


def reconnait_demande(texte):
    """
    La phrase demande-t-elle une synchronisation ? Deux mots exiges (agenda
    ou emploi du temps ET un verbe de mise a jour) : « ouvre mon agenda »
    ne doit pas declencher une ecriture.
    """
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                if unicodedata.category(c) != "Mn")
    sujet = any(m in t for m in ("emploi du temps", "agenda scolaire", "mon agenda",
                                 "agenda google", "google agenda"))
    verbe = any(m in t for m in ("synchronis", "mets a jour", "met a jour", "mets-le a jour",
                                 "actualise", "rafraichi", "remets", "mets dans"))
    return sujet and verbe


def reconnait_ouverture_panneau(texte):
    """
    La phrase demande-t-elle d'OUVRIR le panneau scolaire du HUD (par
    opposition a synchroniser l'agenda) ? Un verbe d'affichage ET le sujet
    scolaire : « ouvre mon agenda » (Google, sans « panneau ») reste du
    ressort de reconnait_demande plus haut, pas de celui-ci.
    """
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", str(texte or "").lower())
                if unicodedata.category(c) != "Mn")
    sujet = any(m in t for m in ("panneau scolaire", "panneau ecole", "emploi du temps",
                                 "agenda scolaire"))
    verbe = any(m in t for m in ("montre", "ouvre", "affiche", "fais voir"))
    return sujet and verbe


def resume_du_jour(lecteur=None, capteur=CAPTEURS[1]):
    """
    (phrase, raison) — ce que le briefing du matin dit de la journee.

    Les annulations d'abord : c'est la seule information qui change ce que
    tu fais en sortant de chez toi. Une journee sans cours renvoie une
    phrase vide, pas une phrase inutile — un briefing qui parle de l'ecole le
    dimanche est un briefing qu'on cesse d'ecouter.
    """
    cours, raison = cours_depuis_ha(lecteur, capteurs=(capteur,))
    if raison:
        return "", raison
    fiches, _ecartes = normaliser_tout(cours)
    if not fiches:
        return "", "aucun cours exploitable aujourd'hui"

    fiches.sort(key=lambda f: f["debut"])
    annules = [f for f in fiches if f["annule"]]
    tenus = [f for f in fiches if not f["annule"]]

    bouts = []
    if annules:
        details = ["%s de %s" % (f["matiere"], f["debut"][11:16].replace(":", "h"))
                   for f in annules]
        bouts.append("Attention, %s annule%s aujourd'hui : %s."
                     % ("un cours" if len(annules) == 1 else "%d cours" % len(annules),
                        "" if len(annules) == 1 else "s", ", ".join(details)))
    if tenus:
        bouts.append("Vous commencez a %s et finissez a %s."
                     % (tenus[0]["debut"][11:16].replace(":", "h"),
                        tenus[-1]["fin"][11:16].replace(":", "h")))
    else:
        bouts.append("Plus aucun cours ne tient aujourd'hui.")
    return " ".join(bouts), ""


def phrase(compte_rendu):
    """La phrase à dire après une synchronisation."""
    if not compte_rendu.get("ok"):
        return "Je n'ai pas pu mettre l'agenda à jour : %s." % compte_rendu.get("raison", "raison inconnue")
    bouts = []
    if compte_rendu["crees"]:
        bouts.append("%d cours ajouté(s)" % compte_rendu["crees"])
    if compte_rendu["modifies"]:
        bouts.append("%d modifié(s)" % compte_rendu["modifies"])
    if compte_rendu["supprimes"]:
        bouts.append("%d retiré(s)" % compte_rendu["supprimes"])
    if not bouts:
        return "Agenda déjà à jour, rien à changer."
    texte = "Agenda mis à jour : " + ", ".join(bouts) + "."
    if compte_rendu.get("annules"):
        texte += " %d cours annulé(s) marqué(s) dans l'agenda." % compte_rendu["annules"]
    return texte


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print()
    print("=" * 70)
    print("EMPLOI DU TEMPS -> GOOGLE AGENDA")
    print("=" * 70)
    bruts, raison = cours_depuis_ha()
    if raison:
        print("  %s" % raison)
    else:
        fiches, ecartes = normaliser_tout(bruts)
        print("  %d cours lus, %d exploitables, %d annulés"
              % (len(bruts), len(fiches), sum(1 for f in fiches if f["annule"])))
        for e in ecartes:
            print("  ecarte : %s" % e)
    print("=" * 70)
