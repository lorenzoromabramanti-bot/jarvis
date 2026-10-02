# -*- coding: utf-8 -*-
"""Outil JARVIS : Mail Manager — tri, categorisation et pre-redaction.

Branche sur email_hub.py, le hub existant (IMAP direct + delegation Outlook
a outlook_graph). Aucune 6e connexion mail n'est creee.

Pour chaque message :
  1. construit l'objet JSON attendu par le prompt systeme
  2. appelle le LLM avec le prompt EXACT, non reformule
  3. parse la sortie en JSON strict, avec repli defensif
  4. agit : notification si HAUTE, brouillon, classement, journalisation

LIMITES REELLES (verifiees dans le code, pas supposees) :
  - Gmail  : scope OAuth = gmail.readonly -> l'API ne peut PAS ecrire.
             Le brouillon passe par IMAP APPEND (mot de passe application
             deja configure), ce qui evite tout re-consentement OAuth.
  - iCloud : idem, IMAP APPEND.
  - Outlook: Graph scope = Mail.Read, et pas de mot de passe application
             -> aucune ecriture possible. Signale, pas echoue en silence.
  - Les ecritures boite sont DESACTIVEES par defaut. Pour activer :
    jarvis_config.json -> "mail_manager": {"ecriture_boite": true}
"""

import json
import re

from . import outil

# Prompt systeme repris CARACTERE POUR CARACTERE du cahier des charges
# (extrait par script depuis JARVIS_MERGE_PROMPT.md, jamais retape).
# Ne pas reformuler, ne pas reindenter : la sortie JSON stricte en depend.
PROMPT_SYSTEME = r"""Tu es Jarvis, l'assistant exécutif IA personnel de l'utilisateur. Ton rôle est de gérer, trier et pré-rédiger les réponses pour l'ensemble de ses boîtes mail (Professionnelles et Personnelles) afin de lui faire gagner un temps précieux.

---

### CONTEXTE ET ENTRÉES
Tu vas recevoir un objet JSON contenant les détails d'un email entrant :
- type_compte : "PRO" ou "PERSO"
- expediteur_nom : Nom de l'expéditeur
- expediteur_email : Adresse email de l'expéditeur
- sujet : Objet du mail
- contenu : Corps du message
- historique : Échanges précédents (si disponible)

---

### DIRECTIVES DE TRI ET CATÉGORISATION

Analyse le contenu et attribue STRICTEMENT l'une des 4 catégories suivantes :

1. "1_URGENT" : Requiert une action, une décision ou une réponse humaine (ex: demandes clients, questions directes, relances, démarches administratives urgentes, demandes de rendez-vous).
2. "2_POUR_INFO" : Informations utiles ne nécessitant aucune réponse (ex: confirmations de commande, reçus, suivis de livraison, compte-rendus, notifications d'outils).
3. "3_VEILLE" : Contenus informatifs à lire plus tard (ex: newsletters pertinentes, articles spécialisés, veille sectorielle).
4. "4_PUB" : Démarchage non sollicité, publicités, offres commerciales B2B ou B2C, spams.

---

### CONSIGNES DE RÉDACTION DE BROUILLON (Uniquement pour "1_URGENT")

Si et seulement si la catégorie est "1_URGENT", génère une proposition de réponse dans le champ "brouillon" en respectant les consignes suivantes :

- Si type_compte == "PRO" :
  • Ton : Professionnel, courtois, synthétique et orienté solutions.
  • Structure : Salutation formelle, réponse directe au besoin, appel à l'action clair (ou proposition de créneau si demande de RDV), formule de politesse pro.
  • Ne prends aucun engagement financier ou contractuel ferme : indique que l'utilisateur valide l'information et revient vers eux rapidement si besoin.

- Si type_compte == "PERSO" :
  • Ton : Naturel, chaleureux, fluide et direct.
  • Structure : Adaptation selon l'interlocuteur (famille, ami, administration, prestataire).
  • Reste concis et précis.

---

### FORMAT DE SORTIE OBLIGATOIRE

Tu dois répondre EXCLUSIVEMENT sous la forme d'un objet JSON valide, sans aucun texte introductif ou explicatif avant ou après le JSON.

{
  "statut_traitement": "SUCCES",
  "type_compte": "PRO | PERSO",
  "categorie": "1_URGENT | 2_POUR_INFO | 3_VEILLE | 4_PUB",
  "priorite": "HAUTE | MOYENNE | BASSE",
  "resume_expresse": "Résumé synthétique de l'email en une seule phrase (max 15 mots).",
  "action_recommandee": "Description courte de l'action automatique à effectuer (ex: 'Créer brouillon + notifier', 'Archiver sous Pour Info', 'Déplacer dans Veille').",
  "brouillon": "Texte complet de la réponse proposée si 1_URGENT. Si autre catégorie, laisser une chaîne vide \"\"."
}"""

CATEGORIES = ("1_URGENT", "2_POUR_INFO", "3_VEILLE", "4_PUB")
PRIORITES = ("HAUTE", "MOYENNE", "BASSE")

# Dossier IMAP de classement par categorie (Gmail expose ses labels en IMAP).
DOSSIERS = {
    "1_URGENT": "JARVIS/Urgent",
    "2_POUR_INFO": "JARVIS/Pour info",
    "3_VEILLE": "JARVIS/Veille",
    "4_PUB": "JARVIS/Pub",
}


# --------------------------------------------------------------------------
# Entrees
# --------------------------------------------------------------------------

_RE_EXPEDITEUR = re.compile(r'^\s*(?:"?(?P<nom>[^"<]*?)"?\s*)?<?(?P<mail>[^<>\s]+@[^<>\s]+)>?\s*$')


def scinder_expediteur(de):
    """'Jean Dupont <jean@x.fr>' -> ('Jean Dupont', 'jean@x.fr'). Ne leve jamais."""
    de = (de or "").strip()
    m = _RE_EXPEDITEUR.match(de)
    if not m:
        return de, ""
    nom = (m.group("nom") or "").strip()
    mail = (m.group("mail") or "").strip()
    return (nom or mail.split("@")[0]), mail


def type_compte(compte):
    """
    PRO / PERSO, lu depuis le champ 'type_compte' du compte dans
    jarvis_config.json. Absent -> PERSO. On ne devine PAS depuis le domaine :
    se tromper donnerait un ton professionnel sur du courrier prive.
    """
    valeur = str((compte or {}).get("type_compte", "")).strip().upper()
    return valeur if valeur in ("PRO", "PERSO") else "PERSO"


def construire_entree(compte, message, historique=""):
    """Objet JSON d'entree du prompt, a partir d'un message email_hub."""
    nom, adresse = scinder_expediteur(message.get("de", ""))
    return {
        "type_compte": type_compte(compte),
        "expediteur_nom": nom,
        "expediteur_email": adresse,
        "sujet": message.get("sujet", "") or "(sans objet)",
        "contenu": message.get("corps", "") or message.get("apercu", "") or "",
        "historique": historique or "",
    }


# --------------------------------------------------------------------------
# Appel LLM + parsing defensif
# --------------------------------------------------------------------------

def _appeler_llm(entree_json):
    """
    Envoie le prompt EXACT + l'objet JSON, renvoie le texte brut du modele.
    Ordre : callable injecte (tests) -> client Gemini publie par main2.
    """
    import builtins
    injecte = getattr(builtins, "_mail_manager_llm", None)
    if callable(injecte):
        return injecte(PROMPT_SYSTEME, entree_json)

    client = getattr(builtins, "client", None)
    if client is None:
        raise RuntimeError("aucun client LLM disponible (builtins.client est None)")

    from google.genai import types as _gtypes
    modeles = getattr(builtins, "CHOSEN_MODELS", {}) or {}
    reponse = client.models.generate_content(
        model=modeles.get("Gemini", "gemini-3.5-flash"),
        contents=PROMPT_SYSTEME + "\n\n" + json.dumps(entree_json, ensure_ascii=False),
        config=_gtypes.GenerateContentConfig(
            # le prompt exige un JSON strict : on l'impose cote provider
            response_mime_type="application/json",
        ),
    )
    return getattr(reponse, "text", "") or ""


def _extraire_json(brut):
    """
    Parse la sortie. Le prompt interdit tout texte autour du JSON, mais on ne
    fait pas confiance : repli sur le premier objet {...} trouve.
    """
    brut = (brut or "").strip()
    if brut.startswith("```"):
        brut = re.sub(r"^```[a-zA-Z]*\s*", "", brut)
        brut = re.sub(r"\s*```$", "", brut)
    try:
        return json.loads(brut)
    except Exception:
        pass
    debut, fin = brut.find("{"), brut.rfind("}")
    if debut != -1 and fin > debut:
        return json.loads(brut[debut:fin + 1])
    raise ValueError("aucun JSON exploitable dans la reponse du modele")


def _valider(donnees):
    """Verifie la forme imposee par le prompt. Leve si non conforme."""
    if not isinstance(donnees, dict):
        raise ValueError("la reponse n'est pas un objet JSON")
    cat = donnees.get("categorie")
    if cat not in CATEGORIES:
        raise ValueError("categorie invalide : %r" % (cat,))
    if donnees.get("priorite") not in PRIORITES:
        raise ValueError("priorite invalide : %r" % (donnees.get("priorite"),))
    if cat != "1_URGENT" and donnees.get("brouillon"):
        donnees["brouillon"] = ""  # le prompt impose "" hors 1_URGENT
    for cle, defaut in (("statut_traitement", "SUCCES"), ("resume_expresse", ""),
                        ("action_recommandee", ""), ("brouillon", "")):
        donnees.setdefault(cle, defaut)
    return donnees


def analyser_email(entree_json):
    """
    Analyse un email. Ne leve JAMAIS : en cas de probleme, renvoie un objet de
    meme forme avec statut_traitement="ECHEC", pour que l'appelant signale
    l'echec au lieu de faire tomber tout l'outil.
    """
    try:
        return _valider(_extraire_json(_appeler_llm(entree_json)))
    except Exception as e:
        return {
            "statut_traitement": "ECHEC",
            "type_compte": entree_json.get("type_compte", ""),
            "categorie": "2_POUR_INFO",
            "priorite": "BASSE",
            "resume_expresse": "Analyse impossible : %s" % (e,),
            "action_recommandee": "Aucune action automatique (echec d'analyse)",
            "brouillon": "",
            "_erreur": repr(e),
        }


# --------------------------------------------------------------------------
# Actions
# --------------------------------------------------------------------------

def _ecriture_autorisee():
    """Les ecritures boite sont opt-in explicite dans jarvis_config.json."""
    try:
        import email_hub
        cfg = json.load(open(email_hub._config_path(), encoding="utf-8"))
        return bool((cfg.get("mail_manager") or {}).get("ecriture_boite", False))
    except Exception:
        return False


def peut_ecrire(compte):
    """
    (possible, raison). Ecriture = IMAP APPEND, donc mot de passe application
    requis. Les comptes OAuth (Outlook/Graph, scope Mail.Read) sont exclus.
    """
    if (compte or {}).get("auth", "").lower() == "oauth":
        return False, ("compte OAuth (%s) : Graph est en Mail.Read seul, "
                       "aucune ecriture possible sans re-consentement"
                       % compte.get("name", "?"))
    import email_hub
    import os
    if not os.environ.get(email_hub._cle_env(compte.get("user", ""))):
        return False, "aucun mot de passe application pour %s" % compte.get("user", "?")
    return True, ""


def construire_brouillon(compte, entree, texte_brouillon):
    """Message MIME de reponse. Construit sans rien envoyer ni ecrire."""
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = compte.get("user", "")
    msg["To"] = entree.get("expediteur_email", "")
    sujet = entree.get("sujet", "")
    msg["Subject"] = sujet if sujet.lower().startswith("re:") else "Re: " + sujet
    msg.set_content(texte_brouillon)
    return msg


def deposer_brouillon(compte, msg):
    """
    IMAP APPEND dans le dossier Brouillons. Ecriture reelle : n'est appelee
    que si _ecriture_autorisee() et peut_ecrire() sont vrais.
    """
    import imaplib
    import os
    import ssl
    import email_hub
    host, port = email_hub._serveur(compte)
    mdp = os.environ.get(email_hub._cle_env(compte.get("user", "")))
    ctx = ssl.create_default_context()
    with imaplib.IMAP4_SSL(host, port, ssl_context=ctx) as srv:
        srv.login(compte["user"], mdp)
        dossier = compte.get("dossier_brouillons") or "Drafts"
        srv.append(dossier, "\\Draft", None, msg.as_bytes())
    return dossier


def journaliser(compte, entree, resultat):
    """Trace en memoire long terme, pour 'resume mes mails urgents de la semaine'."""
    try:
        import memory_manager
        cle = "mail:%s:%s" % (compte.get("name", "?"), entree.get("sujet", "")[:40])
        memory_manager.ajouter_memoire(cle, json.dumps({
            "categorie": resultat.get("categorie"),
            "priorite": resultat.get("priorite"),
            "resume_expresse": resultat.get("resume_expresse"),
            "expediteur": entree.get("expediteur_email"),
            "type_compte": entree.get("type_compte"),
        }, ensure_ascii=False))
        return True
    except Exception as e:
        print("[MAIL_MANAGER] journalisation impossible : %r" % (e,))
        return False


def notifier(resultat, entree):
    """Notification si priorite HAUTE. Best-effort, jamais bloquant."""
    if resultat.get("priorite") != "HAUTE":
        return False
    texte = "Mail urgent de %s : %s" % (
        entree.get("expediteur_nom", "?"), resultat.get("resume_expresse", ""))
    import builtins
    envoye = False
    for nom in ("send_web_text", "parler"):
        fn = getattr(builtins, nom, None)
        if callable(fn):
            try:
                r = fn(texte)
                if hasattr(r, "__await__"):
                    import asyncio
                    asyncio.ensure_future(r)
                envoye = True
                break
            except Exception as e:
                print("[MAIL_MANAGER] notification via %s impossible : %r" % (nom, e))
    return envoye


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def traiter_message(compte, message, historique=""):
    """Chaine complete pour UN message. Renvoie un compte rendu, ne leve pas."""
    entree = construire_entree(compte, message, historique)
    resultat = analyser_email(entree)
    rapport = {
        "compte": compte.get("name"),
        "sujet": entree["sujet"],
        "categorie": resultat.get("categorie"),
        "priorite": resultat.get("priorite"),
        "statut": resultat.get("statut_traitement"),
        "notifie": notifier(resultat, entree),
        "journalise": journaliser(compte, entree, resultat),
        "brouillon": "non",
        "classement": "non",
    }
    if resultat.get("statut_traitement") != "SUCCES":
        rapport["erreur"] = resultat.get("resume_expresse")
        return rapport

    if resultat.get("brouillon"):
        possible, raison = peut_ecrire(compte)
        if not _ecriture_autorisee():
            rapport["brouillon"] = "desactive (mail_manager.ecriture_boite=false)"
        elif not possible:
            rapport["brouillon"] = "impossible : %s" % raison
        else:
            try:
                msg = construire_brouillon(compte, entree, resultat["brouillon"])
                rapport["brouillon"] = "depose dans %s" % deposer_brouillon(compte, msg)
            except Exception as e:
                rapport["brouillon"] = "echec : %r" % (e,)
    return rapport


def resume_rapports(rapports):
    """Phrase de synthese vocale a partir des comptes rendus."""
    if not rapports:
        return "Aucun message a trier."
    total = len(rapports)
    urgents = sum(1 for r in rapports if r.get("categorie") == "1_URGENT")
    echecs = sum(1 for r in rapports if r.get("statut") != "SUCCES")
    phrase = "%d message%s trie%s" % (total, "s" if total > 1 else "", "s" if total > 1 else "")
    phrase += ", %d urgent%s" % (urgents, "s" if urgents > 1 else "")
    if echecs:
        phrase += ", %d analyse%s en echec" % (echecs, "s" if echecs > 1 else "")
    return phrase + "."


_DECLENCHEURS = (
    "trie mes mails", "trie mes emails", "tri de mes mails",
    "gere ma boite mail", "gère ma boîte mail", "gere mes mails",
    "mail manager", "classe mes mails", "trie ma boite mail",
    "trie ma boîte mail",
)


@outil(nom="mail_manager", priorite=115, mode="bloquant",
       description="Trie, categorise et pre-redige les reponses aux emails")
def mail_manager(texte):
    """
    Declenche le tri de la boite. Mode bloquant : IMAP + LLM font du reseau,
    exactement comme jarvis_web et email_hub que main2 deportait deja dans un
    executor. Priorite 115 : apres web_change(110), avant mail(120).
    """
    t = (texte or "").lower().strip()
    if not any(d in t for d in _DECLENCHEURS):
        return None
    try:
        import email_hub
        comptes = {c.get("name") or c.get("user"): c for c in email_hub.charger_comptes()}
        messages = email_hub.boite_unifiee(5)
    except Exception as e:
        return "Impossible d'ouvrir la boite mail : %s" % (e,)

    rapports = []
    for message in messages or []:
        compte = comptes.get(message.get("compte"), {})
        try:
            complet = email_hub.lire_message(message.get("compte"), message.get("id"))
            if isinstance(complet, dict) and not complet.get("error"):
                message = dict(message, **complet)
        except Exception:
            pass  # on analyse alors sur l'apercu, sans faire tomber le tri
        rapports.append(traiter_message(compte, message))
    return resume_rapports(rapports)
