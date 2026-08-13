# -*- coding: utf-8 -*-
"""
Test du Mail Manager (passe 3). Prefixe _ => ignore par l'auto-decouverte.

Aucune boite mail reelle n'est touchee : le LLM et email_hub sont remplaces
par des doubles. Verifie :
  - integrite du prompt systeme (hash contre le cahier des charges)
  - construction de l'objet JSON d'entree
  - parsing strict + tous les replis defensifs
  - regles metier du prompt (brouillon vide hors 1_URGENT)
  - garde-fous d'ecriture (opt-in, comptes OAuth exclus)
  - non-regression des 5 chemins mail existants

Lancer :  python tools/_test_mail_manager.py
"""

import hashlib
import io
import json
import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

# Copie de reference du prompt du cahier des charges. Sert de temoin :
# si quelqu'un reformule PROMPT_SYSTEME dans mail_manager.py, le test tombe.
PROMPT_SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "prompt_mail_reference.txt")

CHEMINS_MAIL = ["email_hub.py", "google_services.py", "outlook_graph.py",
                "mail_mcp.py", "mail_server.py"]

_echecs = []


def verifier(condition, libelle, detail=""):
    if condition:
        print("  ok   %s" % libelle)
    else:
        print("  ECHEC %s %s" % (libelle, detail))
        _echecs.append(libelle)


def test_prompt_intact(mm):
    """Le prompt doit etre celui du cahier des charges, au caractere pres."""
    if not os.path.exists(PROMPT_SOURCE):
        print("  (source du prompt absente, controle d'integrite saute)")
        return
    origine = io.open(PROMPT_SOURCE, encoding="utf-8").read().rstrip()
    h_src = hashlib.sha256(origine.encode("utf-8")).hexdigest()
    h_mod = hashlib.sha256(mm.PROMPT_SYSTEME.encode("utf-8")).hexdigest()
    verifier(h_src == h_mod, "prompt systeme identique au cahier des charges",
             "%s != %s" % (h_src[:12], h_mod[:12]))
    verifier('\\"\\"' in mm.PROMPT_SYSTEME,
             "les echappements \\\" du prompt sont preserves")


def test_expediteur(mm):
    cas = [
        ('Jean Dupont <jean@exemple.fr>', ("Jean Dupont", "jean@exemple.fr")),
        ('"Marie Curie" <marie@labo.fr>', ("Marie Curie", "marie@labo.fr")),
        ('contact@boutique.com', ("contact", "contact@boutique.com")),
        ('<seul@domaine.fr>', ("seul", "seul@domaine.fr")),
        ('', ("", "")),
    ]
    for entree, attendu in cas:
        obtenu = mm.scinder_expediteur(entree)
        verifier(obtenu == attendu, "scinder %r" % entree, "-> %r" % (obtenu,))


def test_entree(mm):
    message = {"id": "42", "compte": "Gmail", "de": "Client X <client@societe.fr>",
               "sujet": "Devis urgent", "corps": "Bonjour, pouvez-vous m'envoyer un devis ?"}
    e = mm.construire_entree({"name": "Gmail", "type_compte": "PRO"}, message, "echange precedent")
    attendu = {"type_compte", "expediteur_nom", "expediteur_email",
               "sujet", "contenu", "historique"}
    verifier(set(e) == attendu, "objet d'entree : exactement les 6 champs du prompt",
             "-> %s" % sorted(e))
    verifier(e["type_compte"] == "PRO", "type_compte lu depuis la config")
    verifier(e["expediteur_email"] == "client@societe.fr", "email extrait")
    verifier(mm.type_compte({"name": "X"}) == "PERSO",
             "type_compte absent -> PERSO (pas de devinette sur le domaine)")


def _repondeur(charge):
    """Fabrique un faux LLM qui renvoie toujours la meme chose."""
    def _f(prompt_systeme, entree):
        assert prompt_systeme, "le prompt systeme doit etre transmis"
        return charge
    return _f


def test_analyse_nominale(mm):
    import builtins
    valide = json.dumps({
        "statut_traitement": "SUCCES", "type_compte": "PRO",
        "categorie": "1_URGENT", "priorite": "HAUTE",
        "resume_expresse": "Client demande un devis rapidement.",
        "action_recommandee": "Creer brouillon + notifier",
        "brouillon": "Bonjour, je reviens vers vous rapidement.",
    }, ensure_ascii=False)
    builtins._mail_manager_llm = _repondeur(valide)
    r = mm.analyser_email({"type_compte": "PRO", "sujet": "Devis"})
    verifier(r["statut_traitement"] == "SUCCES", "JSON valide -> SUCCES")
    verifier(r["categorie"] == "1_URGENT", "categorie conservee")
    verifier(r["brouillon"].startswith("Bonjour"), "brouillon conserve pour 1_URGENT")


def test_replis_defensifs(mm):
    import builtins
    cas = [
        ("JSON entoure de texte",
         'Voici le resultat :\n{"statut_traitement":"SUCCES","type_compte":"PERSO",'
         '"categorie":"3_VEILLE","priorite":"BASSE","resume_expresse":"x",'
         '"action_recommandee":"y","brouillon":""}\nVoila.', "SUCCES"),
        ("JSON en bloc markdown",
         '```json\n{"statut_traitement":"SUCCES","type_compte":"PERSO",'
         '"categorie":"4_PUB","priorite":"BASSE","resume_expresse":"pub",'
         '"action_recommandee":"z","brouillon":""}\n```', "SUCCES"),
        ("categorie inventee",
         '{"categorie":"5_INCONNU","priorite":"HAUTE"}', "ECHEC"),
        ("priorite invalide",
         '{"categorie":"1_URGENT","priorite":"CRITIQUE"}', "ECHEC"),
        ("reponse vide", "", "ECHEC"),
        ("charabia", "je ne sais pas repondre", "ECHEC"),
        ("liste au lieu d'un objet", "[1,2,3]", "ECHEC"),
    ]
    for libelle, charge, attendu in cas:
        builtins._mail_manager_llm = _repondeur(charge)
        r = mm.analyser_email({"type_compte": "PERSO"})
        verifier(r["statut_traitement"] == attendu, "repli : %s -> %s" % (libelle, attendu),
                 "-> %s" % r["statut_traitement"])

    # panne totale du LLM : doit rendre un ECHEC propre, pas remonter l'exception
    def _explose(p, e):
        raise RuntimeError("provider indisponible")
    builtins._mail_manager_llm = _explose
    r = mm.analyser_email({"type_compte": "PRO"})
    verifier(r["statut_traitement"] == "ECHEC", "LLM en panne -> ECHEC propre, pas d'exception")


def test_regle_brouillon(mm):
    import builtins
    builtins._mail_manager_llm = _repondeur(json.dumps({
        "statut_traitement": "SUCCES", "type_compte": "PERSO",
        "categorie": "4_PUB", "priorite": "BASSE", "resume_expresse": "pub",
        "action_recommandee": "archiver",
        "brouillon": "reponse que le prompt interdit ici",
    }))
    r = mm.analyser_email({"type_compte": "PERSO"})
    verifier(r["brouillon"] == "",
             "brouillon force a vide hors 1_URGENT (regle du prompt)")


def test_garde_fous_ecriture(mm):
    outlook = {"name": "Outlook", "provider": "outlook", "auth": "oauth",
               "user": "x@outlook.com"}
    possible, raison = mm.peut_ecrire(outlook)
    verifier(not possible, "compte OAuth Outlook : ecriture refusee")
    verifier("Mail.Read" in raison or "OAuth" in raison,
             "la raison du refus est explicite", "-> %r" % raison)

    sans_mdp = {"name": "Gmail", "provider": "gmail", "user": "inexistant@gmail.com"}
    possible2, raison2 = mm.peut_ecrire(sans_mdp)
    verifier(not possible2, "sans mot de passe application : ecriture refusee")

    verifier(mm._ecriture_autorisee() is False,
             "ecriture boite DESACTIVEE par defaut (opt-in explicite requis)")


def test_brouillon_mime(mm):
    entree = {"expediteur_email": "client@societe.fr", "sujet": "Devis urgent"}
    msg = mm.construire_brouillon({"user": "moi@gmail.com"}, entree, "Bonjour,\nCordialement.")
    verifier(msg["To"] == "client@societe.fr", "destinataire = expediteur d'origine")
    verifier(msg["Subject"] == "Re: Devis urgent", "sujet prefixe Re:")
    msg2 = mm.construire_brouillon({"user": "moi@gmail.com"},
                                   dict(entree, sujet="Re: Deja repondu"), "x")
    verifier(msg2["Subject"] == "Re: Deja repondu", "pas de double prefixe Re:")


def test_notification(mm):
    import builtins
    recus = []
    builtins.send_web_text = lambda t: recus.append(t)
    verifier(mm.notifier({"priorite": "HAUTE", "resume_expresse": "urgent"},
                         {"expediteur_nom": "Client"}) is True,
             "priorite HAUTE -> notification envoyee")
    verifier(mm.notifier({"priorite": "BASSE", "resume_expresse": "x"},
                         {"expediteur_nom": "y"}) is False,
             "priorite BASSE -> pas de notification")
    verifier(len(recus) == 1, "exactement une notification emise")


def test_declencheurs(mm):
    declenchants = ["trie mes mails", "gere ma boite mail", "classe mes mails",
                    "JARVIS trie mes emails s'il te plait"]
    inertes = ["quelle heure est-il", "envoie un mail a paul",
               "traduis bonjour en anglais", ""]
    import builtins
    builtins._mail_manager_llm = _repondeur("{}")

    class _FauxHub(object):
        appels = []
        @staticmethod
        def charger_comptes():
            _FauxHub.appels.append("charger_comptes")
            return [{"name": "Gmail", "user": "x@gmail.com"}]
        @staticmethod
        def boite_unifiee(n=5):
            _FauxHub.appels.append("boite_unifiee")
            return []
        @staticmethod
        def lire_message(c, i):
            return {}
    sys.modules["email_hub"] = _FauxHub

    for t in declenchants:
        del _FauxHub.appels[:]
        r = mm.mail_manager(t)
        verifier(r is not None and "boite_unifiee" in _FauxHub.appels,
                 "declencheur actif : %r" % t, "-> %r" % r)
    for t in inertes:
        del _FauxHub.appels[:]
        verifier(mm.mail_manager(t) is None and not _FauxHub.appels,
                 "inerte (aucun appel boite) : %r" % t)
    del sys.modules["email_hub"]


def test_non_regression_chemins_mail():
    """Les 5 chemins mail existants ne doivent pas avoir ete modifies."""
    modifies = subprocess.run(
        ["git", "-C", RACINE, "diff", "--name-only", "07265f7", "HEAD", "--"] + CHEMINS_MAIL,
        capture_output=True, text=True).stdout.split()
    verifier(not modifies, "les 5 chemins mail sont intacts depuis la sauvegarde",
             "-> modifies : %s" % modifies)
    projet = {c[:-3] for c in CHEMINS_MAIL}
    for chemin in CHEMINS_MAIL:
        nom = chemin[:-3]
        try:
            __import__(nom)
            print("  ok   %s importable" % nom)
        except ModuleNotFoundError as e:
            manquant = (e.name or "").split(".")[0]
            if manquant in projet:
                print("  ECHEC %s : module du projet introuvable (%s)" % (nom, manquant))
                _echecs.append("import %s" % nom)
            else:
                # dependance tierce absente de CET interpreteur (ex: google-auth
                # hors venv). Ce n'est pas une regression du code.
                print("  --   %s : dependance tierce '%s' absente de cet interpreteur "
                      "(lancer avec venv/Scripts/python.exe)" % (nom, manquant))
        except Exception as e:
            print("  ECHEC %s non importable : %r" % (nom, e))
            _echecs.append("import %s" % nom)


def test_place_dans_la_chaine():
    import tools
    tools.charger_outils()
    par_nom = {o["nom"]: o for o in tools.lister_outils()}
    verifier("mail_manager" in par_nom, "mail_manager enregistre dans le registre")
    if "mail_manager" in par_nom:
        p = par_nom["mail_manager"]["priorite"]
        verifier(p == 115, "priorite 115 : apres web_change(110), avant mail(120)")
        verifier(par_nom["mail_manager"]["mode"] == "bloquant",
                 "mode bloquant (IMAP + LLM font du reseau)")
        verifier(81 <= p, "tombe dans la tranche depuis=81 deja appelee par main2 "
                          "-> aucune modification de main2.py necessaire")


def main():
    import builtins
    builtins.get_user_name = lambda: "Lorenzo"
    import tools.mail_manager as mm

    print("-- integrite du prompt");        test_prompt_intact(mm)
    print("-- expediteur");                 test_expediteur(mm)
    print("-- objet d'entree");             test_entree(mm)
    print("-- analyse nominale");           test_analyse_nominale(mm)
    print("-- replis defensifs");           test_replis_defensifs(mm)
    print("-- regle brouillon");            test_regle_brouillon(mm)
    print("-- garde-fous d'ecriture");      test_garde_fous_ecriture(mm)
    print("-- brouillon MIME");             test_brouillon_mime(mm)
    print("-- notification");               test_notification(mm)
    print("-- declencheurs");               test_declencheurs(mm)
    print("-- non-regression chemins mail"); test_non_regression_chemins_mail()
    print("-- place dans la chaine");       test_place_dans_la_chaine()

    print("")
    if _echecs:
        print("RESULTAT : %d ECHEC(S) -> %s" % (len(_echecs), _echecs))
        return 1
    print("RESULTAT : tout passe, aucune boite mail reelle touchee")
    return 0


if __name__ == "__main__":
    sys.exit(main())
