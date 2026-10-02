# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Hub de messagerie unifiée (Gmail + iCloud + Outlook + …)
=====================================================================
Relève plusieurs boîtes IMAP en une boîte unifiée, pour :
  • l'app webmail autonome (dossier webmail/, installable PC + téléphone) ;
  • la lecture / le résumé vocal par JARVIS.

Connexion par IMAP + mot de passe d'application (fourni par l'utilisateur dans
la config — JAMAIS saisi par l'assistant). Aucune dépendance externe (imaplib
et email sont dans la stdlib).

Configuration attendue dans jarvis_config.json :
  "email_accounts": [
    {"name": "Perso Gmail",   "provider": "gmail",   "user": "x@gmail.com",     "password": "MOT_DE_PASSE_APPLICATION"},
    {"name": "iCloud",        "provider": "icloud",  "user": "x@icloud.com",    "password": "MOT_DE_PASSE_APPLICATION"},
    {"name": "Boulot Outlook","provider": "outlook", "user": "x@outlook.com",   "password": "MOT_DE_PASSE_APPLICATION"}
  ]

Point d'entrée données : boite_unifiee(limit_par_compte)
Point d'entrée vocal   : resoudre_mail(texte)
"""

import os
import re
import json
import ssl
import imaplib
import email as _email
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

# Serveurs IMAP connus (host, port). Un compte peut aussi fournir son propre "host".
PROVIDERS = {
    "gmail":   ("imap.gmail.com", 993),
    "icloud":  ("imap.mail.me.com", 993),
    "outlook": ("outlook.office365.com", 993),
    "hotmail": ("outlook.office365.com", 993),
    "live":    ("outlook.office365.com", 993),
    "yahoo":   ("imap.mail.yahoo.com", 993),
    "gmx":     ("imap.gmx.com", 993),
    "orange":  ("imap.orange.fr", 993),
    "free":    ("imap.free.fr", 993),
    "laposte": ("imap.laposte.net", 993),
}


def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_config.json")


# Les mots de passe vivent dans .env. main2.py le charge deja, mais ce module
# est aussi importe par le webmail autonome : sans ce chargement defensif, les
# comptes seraient silencieusement ignores quand il tourne seul.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass


def _cle_env(user: str) -> str:
    """Nom de variable d'environnement portant le mot de passe d'un compte."""
    return "JARVIS_MAIL_PWD_" + re.sub(r"[^A-Za-z0-9]", "_", user or "").upper()


def charger_comptes():
    """Renvoie la liste des comptes e-mail configurés (ou [] si aucun).

    Les mots de passe viennent de l'ENVIRONNEMENT (.env), pas du JSON.
    Raison : jarvis_config.json est renvoyé tel quel au frontend via le message
    `settings_data` — un mot de passe qui y resterait partirait donc dans le
    navigateur, et sur le réseau dès qu'un tunnel est ouvert.

    Le repli sur le champ `password` du JSON n'existe que pour ne pas casser une
    installation pas encore migrée ; il émet un avertissement.
    """
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        comptes = cfg.get("email_accounts", [])
    except Exception:
        return []

    resultat = []
    for c in comptes:
        user = c.get("user")
        if not user:
            continue

        oauth = str(c.get("auth", "")).lower() == "oauth"
        mdp = os.environ.get(_cle_env(user))

        if not mdp and c.get("password"):
            mdp = c["password"]
            print(f"[EMAIL] Mot de passe encore dans jarvis_config.json pour {user}. "
                  f"Deplacez-le dans .env sous {_cle_env(user)}.")

        if oauth or mdp:
            # Copie : on n'ecrit jamais le mot de passe dans l'objet d'origine.
            compte = dict(c)
            if mdp:
                compte["password"] = mdp
            resultat.append(compte)

    return resultat


def _decode(valeur) -> str:
    if not valeur:
        return ""
    try:
        return str(make_header(decode_header(valeur)))
    except Exception:
        return str(valeur)


def _serveur(compte):
    """(host, port) pour un compte : champ 'host' explicite, sinon provider, sinon domaine."""
    if compte.get("host"):
        return compte["host"], int(compte.get("port", 993))
    prov = (compte.get("provider") or "").lower()
    if prov in PROVIDERS:
        return PROVIDERS[prov]
    # déduction depuis le domaine de l'adresse
    user = compte.get("user", "")
    dom = user.split("@")[-1].lower()
    for cle, (host, port) in PROVIDERS.items():
        if cle in dom:
            return host, port
    return f"imap.{dom}", 993


def relever_boite(compte, limit=8):
    """Relève les derniers messages d'un compte. Renvoie (messages, erreur|None)."""
    # Outlook / Microsoft en OAuth → API Graph (IMAP basique coupé par Microsoft)
    if str(compte.get("auth", "")).lower() == "oauth" or compte.get("provider") in ("outlook-oauth", "graph"):
        try:
            import outlook_graph
            return outlook_graph.relever(compte, limit)
        except Exception as e:
            return [], f"module Graph indisponible ({e})"

    host, port = _serveur(compte)
    msgs = []
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(host, port, ssl_context=ctx) as M:
            M.login(compte["user"], compte["password"])
            M.select("INBOX", readonly=True)
            typ, data = M.uid("search", None, "ALL")
            if typ != "OK" or not data or not data[0]:
                return [], None
            uids = data[0].split()[-limit:]
            for uid in reversed(uids):
                typ, d = M.uid("fetch", uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if typ != "OK" or not d or not d[0]:
                    continue
                hdr = _email.message_from_bytes(d[0][1])
                date_iso = ""
                try:
                    dt = parsedate_to_datetime(hdr.get("Date"))
                    date_iso = dt.isoformat() if dt else ""
                except Exception:
                    pass
                msgs.append({
                    "id": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "compte": compte.get("name") or compte["user"],
                    "de": _decode(hdr.get("From")),
                    "sujet": _decode(hdr.get("Subject")) or "(sans objet)",
                    "date": date_iso,
                })
        return msgs, None
    except imaplib.IMAP4.error as e:
        return [], f"authentification refusée ({e})"
    except Exception as e:
        return [], f"connexion impossible ({e})"


def _extraire_corps(msg) -> str:
    """Extrait le texte lisible d'un e-mail (text/plain prioritaire, sinon HTML nettoyé)."""
    import re as _re
    import html as _html

    def _decode_part(part):
        try:
            payload = part.get_payload(decode=True)
            if payload is None:
                return ""
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, "replace")
        except Exception:
            return ""

    plain, htmltxt = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if "attachment" in str(part.get("Content-Disposition") or ""):
                continue
            if ct == "text/plain" and not plain:
                plain = _decode_part(part)
            elif ct == "text/html" and not htmltxt:
                htmltxt = _decode_part(part)
    elif msg.get_content_type() == "text/html":
        htmltxt = _decode_part(msg)
    else:
        plain = _decode_part(msg)

    if plain.strip():
        return plain.strip()
    if htmltxt:
        t = _re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", htmltxt)
        t = _re.sub(r"(?s)<[^>]+>", " ", t)
        t = _html.unescape(t)
        t = _re.sub(r"[ \t]{2,}", " ", t)
        t = _re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()
    return "(corps vide)"


def lire_message(compte_name, msg_id):
    """Récupère le corps d'un message précis, par nom de compte + id. Renvoie un dict."""
    compte = next((c for c in charger_comptes()
                   if (c.get("name") or c.get("user")) == compte_name), None)
    if not compte:
        return {"error": "Compte introuvable."}

    # Outlook / Microsoft en OAuth → Graph
    if str(compte.get("auth", "")).lower() == "oauth" or compte.get("provider") in ("outlook-oauth", "graph"):
        try:
            import outlook_graph
            return outlook_graph.lire_message(compte, msg_id)
        except Exception as e:
            return {"error": f"Graph indisponible ({e})"}

    # IMAP : refetch par UID
    host, port = _serveur(compte)
    try:
        ctx = ssl.create_default_context()
        with imaplib.IMAP4_SSL(host, port, ssl_context=ctx) as M:
            M.login(compte["user"], compte["password"])
            M.select("INBOX", readonly=True)
            typ, d = M.uid("fetch", str(msg_id), "(BODY.PEEK[])")
            if typ != "OK" or not d or not d[0]:
                return {"error": "Message introuvable."}
            msg = _email.message_from_bytes(d[0][1])
            date_iso = ""
            try:
                dt = parsedate_to_datetime(msg.get("Date"))
                date_iso = dt.isoformat() if dt else ""
            except Exception:
                pass
            return {
                "compte": compte.get("name") or compte["user"],
                "de": _decode(msg.get("From")),
                "sujet": _decode(msg.get("Subject")) or "(sans objet)",
                "date": date_iso,
                "corps": _extraire_corps(msg),
                # Necessaires pour qu'une reponse atterrisse dans le bon fil
                # de discussion plutot que d'ouvrir une conversation isolee.
                "message_id": (msg.get("Message-ID") or "").strip(),
                "references": (msg.get("References") or "").strip(),
            }
    except Exception as e:
        return {"error": str(e)}


def boite_unifiee(limit_par_compte=8):
    """Agrège toutes les boîtes configurées. Renvoie un dict prêt pour l'API/UI."""
    comptes = charger_comptes()
    if not comptes:
        return {"configured": False, "accounts": [], "messages": [],
                "message": "Aucun compte e-mail configuré."}
    tous, etats = [], []
    for c in comptes:
        m, err = relever_boite(c, limit_par_compte)
        etats.append({"name": c.get("name") or c["user"], "ok": err is None,
                      "count": len(m), "error": err})
        tous.extend(m)
    tous.sort(key=lambda x: x.get("date") or "", reverse=True)
    return {"configured": True, "accounts": etats, "messages": tous,
            "total": len(tous)}


def resume_vocal():
    """Résumé parlé de la boîte unifiée pour JARVIS."""
    data = boite_unifiee(limit_par_compte=5)
    if not data["configured"]:
        return ("Aucune boîte mail n'est encore connectée. Ajoutez vos comptes dans "
                "la configuration de la messagerie, puis je pourrai relever vos e-mails.")
    if data["total"] == 0:
        actifs = [a for a in data["accounts"] if a["ok"]]
        if not actifs:
            details = " ; ".join(f"{a['name']} : {a['error']}" for a in data["accounts"])
            return f"Je n'ai pas pu relever vos boîtes. {details}."
        return "Aucun nouvel e-mail dans vos boîtes, tout est calme."
    sujets = [f"« {m['sujet']} » de {m['de'].split('<')[0].strip()}" for m in data["messages"][:4]]
    n = data["total"]
    return (f"Vous avez {n} e-mail{'s' if n > 1 else ''} au total sur {len(data['accounts'])} "
            f"boîte{'s' if len(data['accounts']) > 1 else ''}. Les plus récents : " + " ; ".join(sujets) + ".")


def resoudre_mail(texte):
    """Résolveur vocal. Renvoie str ou None (appels réseau : via run_in_executor)."""
    if not texte:
        return None
    t = texte.lower()
    déclencheurs = [
        "relève mes mails", "releve mes mails", "relève mes e-mails", "releve mes emails",
        "relève mes emails", "mes mails", "mes e-mails", "mes emails", "lis mes mails",
        "lis mes emails", "nouveaux mails", "nouveaux emails", "ma messagerie",
        "messagerie unifiée", "messagerie unifiee", "tous mes mails", "boîte mail", "boite mail",
    ]
    if any(k in t for k in déclencheurs):
        return resume_vocal()
    return None


if __name__ == "__main__":
    import sys
    if not sys.stdout.encoding or sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("Comptes configurés :", [c.get("name") for c in charger_comptes()])
    print("\nresoudre_mail('relève mes mails') →")
    print(resoudre_mail("relève mes mails"))
    print("\nboite_unifiee() →")
    print(json.dumps(boite_unifiee(), ensure_ascii=False, indent=2))
    # Test résolution serveur (hors ligne, sans connexion)
    for prov in ("gmail", "icloud", "outlook"):
        print(f"serveur {prov} :", _serveur({"provider": prov, "user": f"x@{prov}.com"}))
