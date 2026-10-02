# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Tri du courrier et brouillons de réponse
======================================================
Range les messages relevés par email_hub en catégories, et rédige un
brouillon de réponse pour ceux qui en appellent une.

**Ce module n'envoie JAMAIS rien.** Il propose, l'humain dispose. L'envoi est
une action irréversible et adressée à un tiers : elle passe par une
validation explicite, comme les propositions d'amélioration.

CATÉGORIES
    publicite     newsletter, promotion, démarchage
    notification  automatique mais utile (reçu, alerte, code, livraison)
    a_repondre    une personne attend une réponse
    important     à lire sans tarder, sans réponse attendue
    autre         le reste

COMMENT
Un SEUL appel au modèle pour tout le lot, pas un par message : classer
trente messages ne doit pas coûter trente requêtes. Si le modèle est
indisponible, on retombe sur des règles simples et on le DIT (`source`),
plutôt que de faire passer une heuristique pour une analyse.

    venv\\Scripts\\python.exe mail_tri.py
"""

import io
import json
import os
import re
import sys

CATEGORIES = ("publicite", "notification", "a_repondre", "important", "autre")

# Indices lisibles sans ouvrir le message. Servent de repli, et de garde-fou :
# un expéditeur no-reply ne peut pas attendre de réponse, quoi qu'en dise
# le modèle.
_MOTS_PUB = ("newsletter", "promo", "solde", "offre", "réduction", "reduction",
             "-50%", "black friday", "désabonn", "desabonn", "unsubscribe",
             "publicité", "publicite", "deal", "exclusif")
_MOTS_NOTIF = ("confirmation", "reçu", "recu", "facture", "commande",
               "livraison", "code de vérification", "code de verification",
               "verification code", "réinitialisation", "reinitialisation",
               "sécurité", "securite", "alerte")
_EXP_AUTOMATIQUE = ("no-reply", "noreply", "ne-pas-repondre", "donotreply",
                    "notification", "mailer-daemon", "postmaster")


def _adresse(de):
    m = re.search(r"[\w\.\-\+]+@[\w\.\-]+", de or "")
    return (m.group(0) if m else (de or "")).lower()


def _heuristique(msg):
    """Classement sans modèle. Renvoie (categorie, raison)."""
    sujet = (msg.get("sujet") or "").lower()
    exp = _adresse(msg.get("de"))
    if any(x in exp for x in _EXP_AUTOMATIQUE):
        if any(m in sujet for m in _MOTS_PUB):
            return "publicite", "expéditeur automatique, sujet promotionnel"
        return "notification", "expéditeur automatique (no-reply)"
    if any(m in sujet for m in _MOTS_PUB):
        return "publicite", "vocabulaire promotionnel dans le sujet"
    if any(m in sujet for m in _MOTS_NOTIF):
        return "notification", "message transactionnel"
    return "autre", "aucun indice net sans lire le corps"


def _client_modele():
    """Client Gemini, ou None. Réutilise la clé déjà présente dans .env."""
    cle = os.getenv("GEMINI_API_KEY", "")
    if not cle:
        try:
            for ligne in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           ".env"), encoding="utf-8", errors="replace"):
                m = re.match(r"\s*GEMINI_API_KEY\s*=\s*(.*)", ligne)
                if m:
                    cle = m.group(1).strip().strip("\"'")
                    break
        except Exception:
            return None
    if not cle:
        return None
    try:
        import google.genai as genai
        return genai.Client(api_key=cle)
    except Exception:
        return None


_MODELE = "gemini-2.5-flash"

_CONSIGNE = """Tu classes des e-mails. Pour CHAQUE message, donne une categorie et une raison courte.

Categories autorisees, exactement :
  publicite     newsletter, promotion, demarchage commercial
  notification  automatique mais utile : recu, facture, code, livraison, alerte
  a_repondre    une PERSONNE attend une reponse de la part du destinataire
  important     a lire sans tarder, mais aucune reponse attendue
  autre         le reste

Regles :
- Un expediteur no-reply ne peut jamais etre 'a_repondre'.
- 'a_repondre' seulement si quelqu'un pose une question ou attend une action.
- La raison fait moins de 12 mots, en francais.

Reponds UNIQUEMENT par un tableau JSON, un objet par message, dans le meme
ordre, de la forme : [{"i": 0, "categorie": "...", "raison": "..."}]"""


def classer(messages, utiliser_modele=True):
    """
    Range les messages. Ajoute `categorie`, `raison` et `source` à chacun.

    `source` vaut 'modele' ou 'heuristique' : on doit toujours pouvoir dire
    d'où vient un classement, surtout quand il est faux.
    """
    if not messages:
        return []
    # Repli d'abord : ainsi chaque message a TOUJOURS une catégorie, même si
    # le modèle répond de travers ou pas du tout.
    for m in messages:
        cat, raison = _heuristique(m)
        m["categorie"], m["raison"], m["source"] = cat, raison, "heuristique"

    client = _client_modele() if utiliser_modele else None
    if client is None:
        return messages

    liste = "\n".join(
        "%d. DE: %s | SUJET: %s" % (i, (m.get("de") or "")[:90], (m.get("sujet") or "")[:120])
        for i, m in enumerate(messages))
    try:
        rep = client.models.generate_content(
            model=_MODELE, contents=_CONSIGNE + "\n\nMESSAGES :\n" + liste)
        texte = (rep.text or "").strip()
        brut = re.search(r"\[.*\]", texte, re.S)
        if not brut:
            return messages
        for entree in json.loads(brut.group(0)):
            i = entree.get("i")
            cat = entree.get("categorie")
            if isinstance(i, int) and 0 <= i < len(messages) and cat in CATEGORIES:
                # Garde-fou : le modele n'a pas le droit de faire attendre une
                # reponse a une machine.
                if cat == "a_repondre" and any(
                        x in _adresse(messages[i].get("de")) for x in _EXP_AUTOMATIQUE):
                    continue
                messages[i]["categorie"] = cat
                messages[i]["raison"] = (entree.get("raison") or "")[:90]
                messages[i]["source"] = "modele"
    except Exception as e:
        print("[MAIL TRI] classement par modele indisponible : %r" % (e,))
    return messages


def par_categorie(messages):
    """{categorie: [messages]}, dans l'ordre d'importance pour l'affichage."""
    ordre = ("a_repondre", "important", "notification", "publicite", "autre")
    groupes = {c: [] for c in ordre}
    for m in messages:
        groupes.setdefault(m.get("categorie", "autre"), []).append(m)
    return {c: v for c, v in groupes.items() if v}


def _prenom():
    """Le prénom de l'utilisateur, pour signer. 'Prénom' en dur partirait tel quel."""
    try:
        import json as _j
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "jarvis_config.json")
        with io.open(chemin, encoding="utf-8") as f:
            nom = (_j.load(f).get("user_name") or "").strip()
        return nom[:1].upper() + nom[1:] if nom else ""
    except Exception:
        return ""


_SALUTATIONS = ("bonjour", "bonsoir", "madame", "monsieur", "cher", "chère",
                "chere", "salut", "hello")


def nettoyer_brouillon(texte):
    """
    Retire le raisonnement que le modèle place avant la réponse.

    Observé sur un vrai message : « Brouillon : » suivi d'une analyse, puis
    d'un séparateur `---`, puis seulement de l'e-mail. Affiché tel quel dans
    le champ éditable, ce préambule part avec le message.

    Le critère est la SALUTATION, pas la longueur : un `---` en fin de texte
    est une signature légitime, et une réponse peut tenir en trois mots. On ne
    coupe que quand la partie basse s'ouvre sur une salutation et pas la
    haute — le seul cas où l'on sait lequel des deux est l'e-mail. Sinon on
    laisse tel quel : mieux vaut un préambule visible qu'un message tronqué.
    """
    t = (texte or "").strip()
    morceaux = re.split(r"(?m)^\s*-{3,}\s*$", t)
    if len(morceaux) < 2:
        return t
    haut, bas = morceaux[0].strip(), "\n".join(morceaux[1:]).strip()
    salue = lambda s: any(m in s[:200].lower() for m in _SALUTATIONS)
    if salue(bas) and not salue(haut):
        return bas
    return t


def proposer_reponse(message, corps="", consigne=""):
    """
    Rédige un brouillon de réponse. **N'envoie rien.**

    Renvoie {ok, brouillon, modele} — le texte est destiné à être affiché et
    validé, jamais transmis directement.
    """
    client = _client_modele()
    if client is None:
        return {"ok": False, "erreur": "aucun modele disponible (GEMINI_API_KEY absente)"}
    prenom = _prenom()
    invite = (
        "Redige une reponse courte, polie et directe a cet e-mail, en francais.\n"
        "N'ecris QUE le corps de l'e-mail : pas de preambule, pas d'explication\n"
        "de ta demarche, pas de separateur, pas de ligne 'Brouillon :'.\n"
        "Pas de formule creuse. %s\n"
        "Si une information manque pour repondre, dis-le DANS le brouillon plutot\n"
        "que de l'inventer.\n\n"
        "DE : %s\nSUJET : %s\n\nCORPS :\n%s\n\n%s"
        % (("Signe du seul prenom : %s." % prenom) if prenom
           else "Termine par le prenom seul.",
           message.get("de", ""), message.get("sujet", ""),
           (corps or "(corps non charge)")[:3000],
           ("CONSIGNE DE L'UTILISATEUR : " + consigne) if consigne else "")
    )
    try:
        rep = client.models.generate_content(model=_MODELE, contents=invite)
        return {"ok": True, "brouillon": nettoyer_brouillon(rep.text or ""),
                "modele": _MODELE}
    except Exception as e:
        return {"ok": False, "erreur": repr(e)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import email_hub
    data = email_hub.boite_unifiee(8)
    msgs = classer(data.get("messages", []))
    groupes = par_categorie(msgs)
    print()
    print("=" * 78)
    print("COURRIER — %d message(s), %d categorie(s)" % (len(msgs), len(groupes)))
    print("=" * 78)
    for cat, liste in groupes.items():
        print("\n  %s (%d)" % (cat.upper().replace("_", " "), len(liste)))
        for m in liste:
            print("    %-40s %s" % ((m.get("de") or "")[:40], (m.get("sujet") or "")[:44]))
            print("       %-10s %s" % (m.get("source", ""), m.get("raison", "")))
    print("=" * 78)
