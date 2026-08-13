# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Envoi d'e-mail
============================
La seule action de tout le projet qui soit **irréversible ET adressée à un
tiers**. Un message parti ne se rattrape pas, et il engage l'utilisateur
auprès de quelqu'un d'autre. Tout ce fichier est écrit autour de ça.

TROIS VERROUS, DANS CET ORDRE
  1. `envoyer()` refuse sans `confirme=True`. Pas de valeur par défaut
     permissive, pas de raccourci « juste pour tester ».
  2. Côté passerelle du HUD, le message est en **niveau 7** (send_email sur
     l'échelle adoptée) : au-dessus du plafond d'autonomie, donc soumis à un
     accord explicite de l'utilisateur à chaque envoi.
  3. Le brouillon complet est affiché avant. `mail_tri.proposer_reponse()`
     rédige, ce module expédie — jamais les deux d'un coup.

CE QUI EST POSSIBLE, ET CE QUI NE L'EST PAS
  Gmail, iCloud   mot de passe d'application -> SMTP, opérationnel.
  Outlook         le jeton Graph de ce projet porte SCOPES = ["Mail.Read"].
                  Envoyer exigerait Mail.Send, donc un nouveau consentement
                  de l'utilisateur. On REFUSE explicitement plutôt que de
                  tenter un appel qui échouerait avec un message obscur.

    venv\\Scripts\\python.exe mail_envoi.py     (vérifie la connexion, n'envoie rien)
"""

import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import email_hub

# (hôte, port). 587 + STARTTLS partout : accepté par les deux fournisseurs et
# moins souvent filtré que le 465.
SMTP = {
    "gmail":   ("smtp.gmail.com", 587),
    "icloud":  ("smtp.mail.me.com", 587),
    "yahoo":   ("smtp.mail.yahoo.com", 587),
    "gmx":     ("mail.gmx.com", 587),
    "orange":  ("smtp.orange.fr", 587),
}


def _compte(nom):
    for c in email_hub.charger_comptes():
        if (c.get("name") or c.get("user")) == nom or c.get("user") == nom:
            return c
    return None


def peut_envoyer(compte):
    """(possible, raison). Dit NON clairement plutôt que d'échouer en vol."""
    if not compte:
        return False, "compte introuvable"
    prov = (compte.get("provider") or "").lower()
    if (compte.get("auth") or "password").lower() == "oauth":
        return False, ("compte OAuth : le jeton de ce projet porte la seule "
                       "portée Mail.Read. L'envoi exige Mail.Send, donc un "
                       "nouveau consentement — à faire volontairement, pas "
                       "au détour d'un envoi.")
    if not compte.get("password"):
        return False, "aucun mot de passe d'application enregistré"
    if prov not in SMTP and not compte.get("smtp_host"):
        return False, "serveur SMTP inconnu pour le fournisseur %r" % prov
    return True, ""


def _adresse_seule(valeur):
    m = re.search(r"[\w\.\-\+]+@[\w\.\-]+", valeur or "")
    return m.group(0) if m else (valeur or "").strip()


def envoyer(nom_compte, destinataire, sujet, corps,
            repondre_a=None, confirme=False):
    """
    Expédie un message. **Refuse tant que confirme n'est pas True.**

    `repondre_a` : le dict renvoyé par email_hub.lire_message. Sert à poser
    In-Reply-To et References pour que la réponse atterrisse dans le fil
    existant au lieu d'ouvrir une conversation isolée.
    """
    compte = _compte(nom_compte)
    possible, raison = peut_envoyer(compte)
    if not possible:
        return {"ok": False, "erreur": raison}

    dest = _adresse_seule(destinataire)
    if "@" not in dest:
        return {"ok": False, "erreur": "destinataire invalide : %r" % destinataire}
    if not (corps or "").strip():
        return {"ok": False, "erreur": "corps vide — rien à envoyer"}

    if not confirme:
        # Le refus renvoie EXACTEMENT ce qui partirait, pour que l'accord
        # porte sur le contenu reel et pas sur une intention resumee.
        return {
            "ok": False, "confirmation_requise": True,
            "apercu": {"de": compte["user"], "a": dest, "sujet": sujet,
                       "corps": corps},
            "message": "Rien n'a été envoyé. Relis le message ci-dessus, puis "
                       "rappelle avec confirme=True.",
        }

    msg = EmailMessage()
    msg["From"] = formataddr((compte.get("name") or "", compte["user"]))
    msg["To"] = dest
    msg["Subject"] = sujet or "(sans objet)"
    msg["Message-ID"] = make_msgid()
    if repondre_a and repondre_a.get("message_id"):
        msg["In-Reply-To"] = repondre_a["message_id"]
        refs = (repondre_a.get("references") or "").split()
        refs.append(repondre_a["message_id"])
        msg["References"] = " ".join(refs[-10:])
    msg.set_content(corps)

    hote = compte.get("smtp_host") or SMTP[(compte.get("provider") or "").lower()][0]
    port = int(compte.get("smtp_port")
               or SMTP.get((compte.get("provider") or "").lower(), ("", 587))[1])
    try:
        with smtplib.SMTP(hote, port, timeout=30) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(compte["user"], compte["password"])
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        return {"ok": False, "erreur": "authentification refusée par %s — un "
                "mot de passe d'application est requis, pas le mot de passe "
                "du compte (%s)" % (hote, e.smtp_code)}
    except Exception as e:
        return {"ok": False, "erreur": "%s : %r" % (hote, e)}

    return {"ok": True, "de": compte["user"], "a": dest, "sujet": msg["Subject"],
            "message_id": msg["Message-ID"]}


def verifier_connexions():
    """
    Teste l'authentification SMTP de chaque compte, SANS rien envoyer.

    On se connecte, on s'authentifie, on raccroche. C'est le seul moyen de
    savoir si l'envoi marchera sans expédier un vrai message à quelqu'un.
    """
    resultats = []
    for c in email_hub.charger_comptes():
        nom = c.get("name") or c.get("user")
        possible, raison = peut_envoyer(c)
        if not possible:
            resultats.append({"compte": nom, "ok": False, "raison": raison})
            continue
        hote = c.get("smtp_host") or SMTP[(c.get("provider") or "").lower()][0]
        port = int(c.get("smtp_port")
                   or SMTP.get((c.get("provider") or "").lower(), ("", 587))[1])
        try:
            with smtplib.SMTP(hote, port, timeout=25) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(c["user"], c["password"])
            resultats.append({"compte": nom, "ok": True,
                              "raison": "authentification acceptée par %s" % hote})
        except Exception as e:
            resultats.append({"compte": nom, "ok": False,
                              "raison": "%s : %r" % (hote, e)})
    return resultats


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print()
    print("=" * 74)
    print("ENVOI D'E-MAIL — test de connexion (AUCUN message n'est expédié)")
    print("=" * 74)
    for r in verifier_connexions():
        print("  %s %-10s %s" % ("OK   " if r["ok"] else "NON  ", r["compte"], r["raison"][:100]))
    print("=" * 74)
