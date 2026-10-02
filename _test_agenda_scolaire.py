# -*- coding: utf-8 -*-
r"""
Vérifie la recopie de l'emploi du temps dans Google Agenda, sans réseau :
le lecteur Home Assistant et le service Google sont injectés.

CE QU'IL GARDE VRAIMENT
1. Une source MUETTE ne vide pas l'agenda. Pronote ne publie rien pendant les
   vacances : une synchronisation qui prendrait « aucun cours » pour la
   vérité effacerait toute l'année.
2. Un événement ajouté à la main dans l'agenda n'est JAMAIS supprimé — seuls
   ceux que ce module a posés le sont.
3. Deux synchronisations d'affilée ne créent pas de doublons : la clé d'un
   cours est stable.
4. Un cours dont l'heure est illisible est écarté ET signalé, pas posé à une
   heure inventée.

    venv\Scripts\python.exe _test_agenda_scolaire.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import agenda_scolaire as ag

echecs = []


def verifier(libelle, condition):
    if condition:
        print("  OK  %s" % libelle)
    else:
        print("  X   %s" % libelle)
        echecs.append(libelle)


COURS = [
    {"start_at": "2026-09-01 08:00:00", "end_at": "2026-09-01 09:00:00",
     "lesson": "MATHS", "classroom": "B12", "teacher_name": "M. Dupont", "canceled": False},
    {"start_at": "2026-09-01 10:15:00", "end_at": "2026-09-01 11:10:00",
     "lesson": "PHYSIQUE-CHIMIE", "classroom": "C04", "canceled": True,
     "status": "Prof. absent"},
    # Pas de cle `canceled` du tout : c'est ce cas qui a casse la premiere
    # version du template Home Assistant.
    {"start_at": "2026-09-01 13:30:00", "end_at": "2026-09-01 15:20:00",
     "subject": "SVT", "room": "SVT2", "status": "Cours annulé"},
]

# ── Normalisation ────────────────────────────────────────────────────────
fiches, ecartes = ag.normaliser_tout(COURS)
verifier("les 3 cours sont exploitables", len(fiches) == 3 and not ecartes)
verifier("les cles alternatives sont lues (subject/room)",
         fiches[2]["matiere"] == "SVT" and fiches[2]["salle"] == "SVT2")
verifier("un drapeau canceled vaut annulation", fiches[1]["annule"])
verifier("un statut « Cours annulé » sans cle canceled vaut annulation aussi",
         fiches[2]["annule"])
verifier("un cours normal n'est pas marque annule", not fiches[0]["annule"])
verifier("l'espace du format Pronote devient un T ISO",
         fiches[0]["debut"] == "2026-09-01T08:00:00")

mauvais, raison = ag.normaliser({"lesson": "MATHS", "start_at": "", "end_at": ""})
verifier("heure illisible -> ecarte avec la raison", mauvais is None and "début" in raison)
mauvais2, raison2 = ag.normaliser({"start_at": "2026-09-01 08:00:00",
                                   "end_at": "2026-09-01 09:00:00"})
verifier("matiere absente -> ecarte avec la raison", mauvais2 is None and "matière" in raison2)

# ── Cle stable ───────────────────────────────────────────────────────────
verifier("la cle d'un cours ne bouge pas d'un appel a l'autre",
         ag.cle_stable("2026-09-01T08:00:00", "MATHS") == ag.cle_stable("2026-09-01T08:00:00", "MATHS"))
verifier("la casse de la matiere ne change pas la cle",
         ag.cle_stable("2026-09-01T08:00:00", "maths") == ag.cle_stable("2026-09-01T08:00:00", "MATHS"))
verifier("deux matieres a la meme heure ont des cles differentes",
         ag.cle_stable("2026-09-01T08:00:00", "MATHS") != ag.cle_stable("2026-09-01T08:00:00", "SVT"))

# ── Evenement ────────────────────────────────────────────────────────────
ev_normal = ag.evenement(fiches[0])
ev_annule = ag.evenement(fiches[1])
verifier("un cours annule est titre ANNULE", ev_annule["summary"].startswith("ANNULE"))
verifier("un cours annule libere le creneau (transparent)",
         ev_annule["transparency"] == "transparent" and ev_normal["transparency"] == "opaque")
verifier("la raison de l'annulation est ecrite dans l'evenement",
         "Prof. absent" in ev_annule["description"])
verifier("aucun rappel n'est pose", ev_normal["reminders"]["overrides"] == [])
verifier("l'evenement porte la marque du module",
         ev_normal["extendedProperties"]["private"]["jarvis_source"] == ag.MARQUE)

# ── Diff ─────────────────────────────────────────────────────────────────
verifier("agenda vide -> tout est a creer",
         ag.diff(fiches, []) == (ag.diff(fiches, [])[0], [], []) and len(ag.diff(fiches, [])[0]) == 3)


def pose(fiche, id_ev):
    """L'evenement tel que Google le renverrait apres creation."""
    corps = dict(ag.evenement(fiche))
    corps["id"] = id_ev
    return corps


deja = [pose(f, "ev%d" % i) for i, f in enumerate(fiches)]
a_creer, a_modifier, a_supprimer = ag.diff(fiches, deja)
verifier("resynchroniser a l'identique ne fait RIEN (pas de doublon)",
         (a_creer, a_modifier, a_supprimer) == ([], [], []))

# Le cours de maths passe a annule entre deux rafraichissements.
COURS_APRES = [dict(COURS[0], canceled=True, status="Prof. absent"), COURS[1], COURS[2]]
fiches_apres, _ = ag.normaliser_tout(COURS_APRES)
a_creer, a_modifier, a_supprimer = ag.diff(fiches_apres, deja)
verifier("un cours qui passe a annule est MODIFIE, pas recree",
         a_creer == [] and len(a_modifier) == 1 and a_supprimer == [])
verifier("c'est bien l'evenement du cours de maths qui est modifie",
         a_modifier[0][0] == "ev0" and a_modifier[0][1]["summary"].startswith("ANNULE"))

# Un cours retire de Pronote disparait de l'agenda.
a_creer, a_modifier, a_supprimer = ag.diff(fiches[:2], deja)
verifier("un cours qui disparait de Pronote est supprime", a_supprimer == ["ev2"])

# Un rendez-vous personnel dans le meme agenda : intouchable.
perso = {"id": "perso1", "summary": "Dentiste",
         "start": {"dateTime": "2026-09-01T16:00:00"}, "end": {"dateTime": "2026-09-01T16:30:00"}}
a_creer, a_modifier, a_supprimer = ag.diff([], deja + [perso])
verifier("un evenement ajoute a la main n'est JAMAIS supprime",
         "perso1" not in a_supprimer)
verifier("mais les cours poses par JARVIS le sont",
         sorted(a_supprimer) == ["ev0", "ev1", "ev2"])

# ── Fenetre ──────────────────────────────────────────────────────────────
debut, fin = ag.fenetre(fiches)
verifier("la fenetre commence a minuit le premier jour", debut.startswith("2026-09-01T00:00:00"))
verifier("la fenetre finit le lendemain du dernier jour", fin.startswith("2026-09-02T00:00:00"))
verifier("la fenetre porte un vrai fuseau, pas un decalage code en dur",
         "+02:00" in debut or debut.endswith("Z"))

# ── Lecture Home Assistant ───────────────────────────────────────────────
def lecteur_ok(entity_id, attribut=None):
    if entity_id.endswith("period_s_timetable"):
        return COURS
    if entity_id.endswith("today_s_timetable"):
        return [COURS[0]]        # doublon volontaire
    return None


lus, raison = ag.cours_depuis_ha(lecteur_ok)
verifier("les cours de plusieurs capteurs sont fusionnes sans doublon",
         len(lus) == 3 and not raison)


def lecteur_muet(entity_id, attribut=None):
    return None


lus, raison = ag.cours_depuis_ha(lecteur_muet)
verifier("aucun capteur ne repond -> raison explicite, pas une liste vide muette",
         lus == [] and "ne publie rien" in raison)


def lecteur_inconnu(entity_id, attribut=None):
    """Ce que ha_get_etat renvoie VRAIMENT quand l'attribut manque."""
    return "inconnu"


lus, raison = ag.cours_depuis_ha(lecteur_inconnu)
verifier("l'attribut manquant (\"inconnu\") est traite comme absent, pas parcouru lettre a lettre",
         lus == [] and "ne publie rien" in raison)


def lecteur_qui_leve(entity_id, attribut=None):
    raise OSError("Home Assistant injoignable")


lus, raison = ag.cours_depuis_ha(lecteur_qui_leve)
verifier("Home Assistant injoignable -> raison, jamais d'exception",
         lus == [] and bool(raison))

# ── Le point critique : source muette = on ne touche a RIEN ──────────────
class ServiceInterdit:
    def __getattr__(self, nom):
        raise AssertionError("Google ne doit meme pas etre appele quand la source est muette")


resultat = ag.synchroniser(service=ServiceInterdit(), lecteur=lecteur_muet)
verifier("source muette -> synchronisation refusee AVANT tout appel Google",
         not resultat["ok"] and "ne publie rien" in resultat["raison"])
verifier("et la phrase le dit a l'utilisateur", "pas pu" in ag.phrase(resultat))

# ── Resume parle du matin ────────────────────────────────────────────────
def lecteur_jour(entity_id, attribut=None):
    return COURS if entity_id.endswith("today_s_timetable") else None


dit, raison = ag.resume_du_jour(lecteur_jour)
verifier("le briefing annonce les annulations EN PREMIER", dit.startswith("Attention"))
verifier("il nomme les cours annules et leur heure",
         "PHYSIQUE-CHIMIE de 10h15" in dit and "SVT de 13h30" in dit)
verifier("il donne l'heure de debut et de fin reelles",
         "commencez a 08h00" in dit and "finissez a 09h00" in dit)

dit_vide, raison_vide = ag.resume_du_jour(lecteur_muet)
verifier("pas de cours -> phrase VIDE, le briefing n'en parle pas",
         dit_vide == "" and bool(raison_vide))


def lecteur_sans_annulation(entity_id, attribut=None):
    return [COURS[0]] if entity_id.endswith("today_s_timetable") else None


dit_calme, _ = ag.resume_du_jour(lecteur_sans_annulation)
verifier("journee normale -> pas d'alarme inutile",
         "Attention" not in dit_calme and "commencez a 08h00" in dit_calme)

# ── Comprehension de la demande parlee ───────────────────────────────────
verifier("« synchronise mon emploi du temps » declenche",
         ag.reconnait_demande("Jarvis, synchronise mon emploi du temps"))
verifier("« mets a jour mon agenda » declenche",
         ag.reconnait_demande("mets a jour mon agenda"))
verifier("« ouvre mon agenda » NE declenche PAS une ecriture",
         not ag.reconnait_demande("ouvre mon agenda"))
verifier("une phrase sans rapport ne declenche rien",
         not ag.reconnait_demande("quel temps fait-il demain ?"))

# ── Ouverture du panneau (distincte de la synchronisation) ──────────────
verifier("« montre le panneau scolaire » -> ouverture, pas sync",
         ag.reconnait_ouverture_panneau("montre le panneau scolaire")
         and not ag.reconnait_demande("montre le panneau scolaire"))
verifier("« ouvre mon emploi du temps » -> ouverture",
         ag.reconnait_ouverture_panneau("ouvre mon emploi du temps"))
verifier("« affiche mon agenda scolaire » -> ouverture, pas sync",
         ag.reconnait_ouverture_panneau("affiche mon agenda scolaire")
         and not ag.reconnait_demande("affiche mon agenda scolaire"))
verifier("« synchronise mon emploi du temps » reste dans reconnait_demande, pas ouverture",
         ag.reconnait_demande("synchronise mon emploi du temps")
         and not ag.reconnait_ouverture_panneau("synchronise mon emploi du temps"))
verifier("« ouvre mon agenda » (sans mot scolaire) ne declenche ni l'un ni l'autre",
         not ag.reconnait_ouverture_panneau("ouvre mon agenda")
         and not ag.reconnait_demande("ouvre mon agenda"))
verifier("phrase sans rapport -> aucun des deux",
         not ag.reconnait_ouverture_panneau("quel temps fait-il demain")
         and not ag.reconnait_demande("quel temps fait-il demain"))

# ── Devoirs / evaluations / notes ────────────────────────────────────────
# Cles verifiees dans delphiki/hass-pronote (pronote_formatter.py), pas
# devinees : format_homework/format_grade/format_evaluation.
DEVOIRS_BRUTS = [
    {"date": "2026-09-02", "subject": "MATHS", "short_description": "Ex 12-18",
     "description": "Exercices 12 a 18 page 47", "done": False},
    {"date": "2026-09-03", "subject": "ANGLAIS", "short_description": "Vocab",
     "description": "Vocabulaire unite 1", "done": True},
]
EVALS_BRUTES = [
    {"date": "2026-09-04", "subject": "ANGLAIS", "name": "Test vocabulaire",
     "coefficient": 1, "description": ""},
]
# Une note textuelle (« Absent ») : Pronote l'autorise, un devoir non fait
# aussi (done=False) — les deux DOIVENT survivre sans exception ni coercion.
NOTES_BRUTES = [
    {"date": "2026-08-30", "subject": "MATHS", "grade": "14", "out_of": "20",
     "coefficient": "2", "comment": ""},
    {"date": "2026-08-29", "subject": "SVT", "grade": "Absent", "out_of": "20",
     "coefficient": "1", "comment": "Absence justifiee"},
]


def lecteur_devoirs_ok(entite, attribut=None):
    if entite == ag.CAPTEUR_DEVOIRS: return DEVOIRS_BRUTS
    if entite == ag.CAPTEUR_EVALUATIONS: return EVALS_BRUTES
    if entite == ag.CAPTEUR_NOTES: return NOTES_BRUTES
    if entite == ag.CAPTEUR_MOYENNE: return "13,4"
    return None


donnees, raisons = ag.devoirs_evaluations_notes(lecteur_devoirs_ok)
verifier("les 2 devoirs sont exploitables", len(donnees["devoirs"]) == 2)
verifier("un devoir non fait garde fait=False", donnees["devoirs"][0]["fait"] is False)
verifier("un devoir fait garde fait=True", donnees["devoirs"][1]["fait"] is True)
verifier("l'evaluation est exploitable", len(donnees["evaluations"]) == 1
         and donnees["evaluations"][0]["nom"] == "Test vocabulaire")
verifier("les 2 notes sont exploitables", len(donnees["notes"]) == 2)
verifier("une note TEXTUELLE (Absent) reste une chaine, jamais convertie",
         donnees["notes"][1]["note"] == "Absent")
verifier("la moyenne generale est lue telle quelle", donnees["moyenne"] == "13,4")
verifier("les 4 sources historiques repondent : seules les 4 nouvelles manquent ici",
         len(raisons) == 4
         and all(("averages" in r or "absences" in r or "delays" in r
                  or "punishments" in r) for r in raisons))


def lecteur_devoirs_muet(entite, attribut=None):
    return "inconnu"     # ce que ha_get_etat renvoie VRAIMENT hors periode scolaire


donnees_m, raisons_m = ag.devoirs_evaluations_notes(lecteur_devoirs_muet)
verifier("source muette -> listes vides, jamais une exception",
         donnees_m["devoirs"] == [] and donnees_m["evaluations"] == []
         and donnees_m["notes"] == [] and donnees_m["moyenne"] is None
         and donnees_m["moyennes"] == [] and donnees_m["absences"] == []
         and donnees_m["retards"] == [] and donnees_m["punitions"] == [])
verifier("chaque source muette est nommee dans les raisons (8 sources)",
         len(raisons_m) == 8)


def lecteur_devoirs_partiel(entite, attribut=None):
    # Les devoirs repondent, le reste est muet : chaque source est
    # INDEPENDANTE, une panne partielle ne doit pas tout vider.
    if entite == ag.CAPTEUR_DEVOIRS: return DEVOIRS_BRUTS
    return "inconnu"


donnees_p, raisons_p = ag.devoirs_evaluations_notes(lecteur_devoirs_partiel)
verifier("une source qui repond survit meme si les autres sont muettes",
         len(donnees_p["devoirs"]) == 2 and donnees_p["evaluations"] == [])
verifier("les sources muettes sont quand meme signalees", len(raisons_p) == 7)


def lecteur_devoirs_leve(entite, attribut=None):
    raise OSError("Home Assistant injoignable")


donnees_e, raisons_e = ag.devoirs_evaluations_notes(lecteur_devoirs_leve)
verifier("Home Assistant injoignable -> raisons explicites, jamais une exception qui remonte",
         donnees_e["devoirs"] == [] and len(raisons_e) == 8)

# ── Plan de revision ─────────────────────────────────────────────────────
import datetime as _dt
AUJOURDHUI = _dt.date(2026, 9, 2)   # mercredi

DEVOIRS_PLAN = [
    {"date": "2026-09-03", "matiere": "MATHS",   "titre": "Ex 12-18",     "fait": False},
    {"date": "2026-09-03", "matiere": "ANGLAIS",  "titre": "Vocab",       "fait": False},
    {"date": "2026-08-30", "matiere": "SVT",      "titre": "En retard",   "fait": False},
    {"date": "2026-09-05", "matiere": "FRANCAIS", "titre": "Redaction",   "fait": True},
    {"date": "2026-09-20", "matiere": "HISTOIRE", "titre": "Trop loin",   "fait": False},
]
EVALS_PLAN = [
    {"date": "2026-09-04", "matiere": "MATHS",   "nom": "DS fonctions", "coefficient": "3"},
    {"date": "2026-09-06", "matiere": "ANGLAIS", "nom": "Test vocab",   "coefficient": "1"},
]

plan = ag.construire_plan(DEVOIRS_PLAN, EVALS_PLAN, minutes_par_soir=75, aujourdhui=AUJOURDHUI)
verifier("un devoir FAIT est exclu du plan (Redaction, FRANCAIS)",
         not any(b["matiere"] == "FRANCAIS" for j in plan["jours"] for b in j["blocs"]))
verifier("un devoir/eval hors fenetre (>7 jours) est compte, pas plante",
         plan["hors_fenetre"] == 1)
verifier("un devoir DEJA EN RETARD est place aujourd'hui, marque en surcharge",
         plan["jours"][0]["blocs"][0]["matiere"] == "SVT"
         and plan["jours"][0]["blocs"][0].get("deborde") is True)
verifier("une evaluation de coefficient >= 2 genere 3 seances de revision",
         sum(1 for j in plan["jours"] for b in j["blocs"]
             if b["type"] == "revision" and "DS fonctions" in b["titre"]) == 3)
verifier("une evaluation de coefficient < 2 genere 2 seances de revision",
         sum(1 for j in plan["jours"] for b in j["blocs"]
             if b["type"] == "revision" and "Test vocab" in b["titre"]) == 2)
verifier("aucun jour ne depasse sa capacite pour ce qui N'EST PAS en surcharge",
         all(j["utilise"] <= j["minutes"]
             for j in plan["jours"]
             if not any(b.get("deborde") for b in j["blocs"])))
verifier("ce qui ne rentre pas est marque en surcharge, JAMAIS efface du plan",
         plan["en_surcharge"] > 0
         and sum(len(j["blocs"]) for j in plan["jours"])
             == len(DEVOIRS_PLAN) - 2 + 3 + 2)  # -2 : fait + hors fenetre
verifier("le week-end a plus de capacite que la semaine (meme minutes_par_soir)",
         plan["jours"][3]["minutes"] > plan["jours"][1]["minutes"])  # samedi > jeudi
verifier("minutes_par_soir a un plancher (15) meme si on demande moins",
         ag.construire_plan([], [], minutes_par_soir=0, aujourdhui=AUJOURDHUI)["jours"][0]["minutes"] >= 15)
verifier("la duree estimee d'un devoir est rapportee au HUD, pas cachee",
         plan["duree_devoir_estimee"] == ag.DUREE_DEVOIR_PAR_DEFAUT_MIN)

plan_vide = ag.construire_plan([], [], minutes_par_soir=75, aujourdhui=AUJOURDHUI)
verifier("aucun devoir/evaluation -> plan vide, pas d'erreur",
         plan_vide["en_surcharge"] == 0 and plan_vide["hors_fenetre"] == 0
         and all(j["blocs"] == [] for j in plan_vide["jours"]))


def lecteur_plan_ok(entite, attribut=None):
    if entite == ag.CAPTEUR_DEVOIRS: return DEVOIRS_PLAN
    if entite == ag.CAPTEUR_EVALUATIONS: return EVALS_PLAN
    if entite == ag.CAPTEUR_NOTES: return []
    if entite == ag.CAPTEUR_MOYENNE: return "inconnu"
    return None


plan_reel, raisons_plan = ag.plan_revision(lecteur_plan_ok, minutes_par_soir=75,
                                           aujourdhui=AUJOURDHUI)
verifier("plan_revision() enchaine lecture HA + construction sans reimplementer",
         plan_reel["hors_fenetre"] == 1 and plan_reel["en_surcharge"] > 0)
verifier("plan_revision() remonte les raisons des sources muettes",
         any("moyenne" in r for r in raisons_plan))


def lecteur_plan_muet(entite, attribut=None):
    return "inconnu"


plan_muet, raisons_muet = ag.plan_revision(lecteur_plan_muet, minutes_par_soir=75)
verifier("Pronote muet -> plan vide et raisons explicites, jamais une exception",
         plan_muet["en_surcharge"] == 0 and len(raisons_muet) == 8)

# -- Question sur l-emploi du temps (lecture, pas synchro) ----------------
import datetime as _dt2
JEUDI = _dt2.date(2030, 1, 10)   # jeudi

def _q(texte):
    return ag.reconnait_question_emploi_du_temps(texte, aujourdhui=JEUDI)

verifier("une question simple est reconnue et vise aujourd-hui",
         _q("quel est mon emploi du temps")[0] == "2030-01-10")
verifier("« demain » vise le lendemain",
         _q("j-ai quoi comme cours demain")[0] == "2030-01-11")
verifier("« apres-demain » vise J+2",
         _q("mes cours apres-demain")[0] == "2030-01-12")
verifier("un nom de jour vise la prochaine occurrence",
         _q("les cours de lundi")[0] == "2030-01-14")
verifier("le jour courant nomme reste aujourd-hui (pas la semaine prochaine)",
         _q("emploi du temps de jeudi")[0] == "2030-01-10")

verifier("une demande de SYNCHRO n-est PAS traitee comme une question",
         _q("synchronise mon emploi du temps")[0] is None)
verifier("une demande d-AFFICHAGE du panneau n-est PAS traitee comme une question",
         _q("montre le panneau scolaire")[0] is None)
verifier("une phrase sans rapport n-est pas captee",
         _q("quel temps fait-il demain")[0] is None)
verifier("les trois routages restent exclusifs sur la meme phrase de synchro",
         ag.reconnait_demande("synchronise mon emploi du temps")
         and _q("synchronise mon emploi du temps")[0] is None)

COURS_JEUDI = [
    {"start_at": "2030-01-10T08:00:00", "end_at": "2030-01-10T08:55:00",
     "lesson": "MATIERE-ALPHA", "classroom": "SALLE-X1", "canceled": False},
    {"start_at": "2030-01-10T09:10:00", "end_at": "2030-01-10T10:05:00",
     "lesson": "MATIERE-BETA", "classroom": "SALLE-X2", "canceled": True},
    {"start_at": "2030-01-11T08:00:00", "end_at": "2030-01-11T08:55:00",
     "lesson": "MATIERE-GAMMA", "classroom": "SALLE-X3", "canceled": False},
]

def lecteur_jeudi(entite, attribut=None):
    return COURS_JEUDI if attribut == "lessons" else "inconnu"

fiches_j, raison_j = ag.cours_du_jour("2030-01-10", lecteur_jeudi)
verifier("cours_du_jour ne garde que la date demandee", len(fiches_j) == 2)
verifier("cours_du_jour trie par heure",
         fiches_j[0]["matiere"] == "MATIERE-ALPHA")
verifier("un autre jour renvoie ses propres cours",
         len(ag.cours_du_jour("2030-01-11", lecteur_jeudi)[0]) == 1)
verifier("un jour sans cours renvoie une liste vide, sans erreur",
         ag.cours_du_jour("2030-01-12", lecteur_jeudi) == ([], ""))

texte_j = ag.phrase_emploi_du_temps("aujourd'hui", fiches_j)
verifier("la reponse cite les VRAIES matieres", "MATIERE-ALPHA" in texte_j)
verifier("la reponse cite les VRAIES salles", "SALLE-X1" in texte_j and "SALLE-X2" in texte_j)
verifier("la reponse marque les cours annules", "ANNULE" in texte_j)
verifier("la reponse compte les cours", "2 cours" in texte_j)
verifier("aucun cours -> phrase honnete, pas de cours invente",
         ag.phrase_emploi_du_temps("demain", []) == "Aucun cours demain.")

def lecteur_muet_edt(entite, attribut=None):
    return "inconnu"

verifier("Pronote muet -> raison explicite, jamais une liste vide silencieuse",
         ag.cours_du_jour("2030-01-10", lecteur_muet_edt)[1] != "")

# -- Assiduite et moyennes par matiere ------------------------------------
MOY_BRUTES = [{"subject": "MATHEMATIQUES", "average": "14,5", "class": "11,2",
               "min": "3", "max": "19", "out_of": "20"}]
ABS_BRUTES = [{"from": "2030-01-08 08:00", "to": "2030-01-08 10:05",
               "hours": "2h", "justified": True, "reason": "Motif fictif"}]
RET_BRUTES = [{"date": "2030-01-09", "minutes": "10", "justified": False,
               "justification": ""}]
PUN_BRUTES = [{"date": "2030-01-09", "subject": "MATIERE-DELTA", "nature": "Sanction fictive",
               "reasons": "Motif de test", "giver": "PROF TEST"}]

def lecteur_complet(entite, attribut=None):
    if entite == ag.CAPTEUR_DEVOIRS: return []
    if entite == ag.CAPTEUR_EVALUATIONS: return []
    if entite == ag.CAPTEUR_NOTES: return []
    if entite == ag.CAPTEUR_MOYENNES: return MOY_BRUTES
    if entite == ag.CAPTEUR_ABSENCES: return ABS_BRUTES
    if entite == ag.CAPTEUR_RETARDS: return RET_BRUTES
    if entite == ag.CAPTEUR_PUNITIONS: return PUN_BRUTES
    if entite == ag.CAPTEUR_MOYENNE: return "12,8"
    return "inconnu"

don_c, rais_c = ag.devoirs_evaluations_notes(lecteur_complet)
verifier("les moyennes par matiere sont remontees",
         don_c["moyennes"] and don_c["moyennes"][0]["matiere"] == "MATHEMATIQUES")
verifier("la moyenne eleve ET la moyenne classe sont conservees",
         don_c["moyennes"][0]["eleve"] == "14,5" and don_c["moyennes"][0]["classe"] == "11,2")
verifier("les absences sont remontees avec leur motif",
         don_c["absences"] and don_c["absences"][0]["motif"] == "Motif fictif")
verifier("une absence justifiee est marquee comme telle",
         don_c["absences"][0]["justifiee"] is True)
verifier("les retards sont remontes",
         don_c["retards"] and don_c["retards"][0]["minutes"] == "10")
verifier("un retard non justifie n-est pas marque justifie",
         don_c["retards"][0]["justifie"] is False)
verifier("les punitions sont remontees avec nature et motif",
         don_c["punitions"] and don_c["punitions"][0]["nature"] == "Sanction fictive"
         and don_c["punitions"][0]["motif"] == "Motif de test")
verifier("aucune raison d-echec quand tout repond", rais_c == [])

def lecteur_assiduite_muette(entite, attribut=None):
    if entite in (ag.CAPTEUR_MOYENNES, ag.CAPTEUR_ABSENCES,
                  ag.CAPTEUR_RETARDS, ag.CAPTEUR_PUNITIONS):
        return "inconnu"
    if entite == ag.CAPTEUR_MOYENNE: return "12,8"
    return []

don_m, rais_m = ag.devoirs_assiduite_test = ag.devoirs_evaluations_notes(lecteur_assiduite_muette)
verifier("4 sources d-assiduite muettes -> 4 raisons nommees, pas un silence",
         len(rais_m) == 4)
verifier("les listes muettes restent des listes vides, jamais None",
         don_m["moyennes"] == [] and don_m["absences"] == []
         and don_m["retards"] == [] and don_m["punitions"] == [])

verifier("une cle absente cote Pronote ne fait pas planter la normalisation",
         ag.normaliser_moyenne({})["matiere"] == ""
         and ag.normaliser_absence({})["justifiee"] is False
         and ag.normaliser_retard({})["minutes"] == ""
         and ag.normaliser_punition({})["nature"] == "")

verifier("le nom de l-agenda cree ne presume pas du type d-etablissement",
         "lycee" not in ag.NOM_AGENDA.lower() and "college" not in ag.NOM_AGENDA.lower())

print()
if echecs:
    print("ÉCHECS : %d" % len(echecs))
    raise SystemExit(1)
print("Emploi du temps -> Google Agenda : conforme.")
