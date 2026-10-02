# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Outlook / Microsoft via Microsoft Graph (OAuth device-code)
=========================================================================
Microsoft ayant coupé l'IMAP basique pour les comptes personnels, on passe par
l'API officielle Microsoft Graph avec OAuth (aucun mot de passe partagé).

Setup (une fois) :
  1. https://entra.microsoft.com → Identité → Applications → Inscriptions
     → Nouvelle inscription. Type : comptes perso + pro. Redirection : aucune.
  2. Autoriser le « flux client public » (Authentification → Autoriser les flux
     clients publics = Oui).
  3. Copier l'ID d'application (client_id) dans jarvis_config.json :
       "outlook_client_id": "xxxxxxxx-....",
     et ajouter un compte :
       {"name": "Outlook", "provider": "outlook", "auth": "oauth", "user": "x@outlook.com"}
  4. Lancer une fois :  python outlook_graph.py <client_id>
     → aller sur l'URL affichée, entrer le code, approuver. Le jeton est mis en
     cache ; ensuite JARVIS relève Outlook silencieusement.
"""

import os
import json
import urllib.request

try:
    import msal
    _MSAL_OK = True
except Exception:
    _MSAL_OK = False

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read"]
_AUTHORITY = "https://login.microsoftonline.com/common"
# ID client PUBLIC officiel Microsoft (« Microsoft Graph Command Line Tools ») :
# multi-tenant + comptes personnels, device-code OK, pré-consenti pour Mail.Read.
# Évite toute inscription d'app Azure côté utilisateur.
_DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"


def _dir():
    return os.path.dirname(os.path.abspath(__file__))


def _cache_file():
    return os.path.join(_dir(), "token_outlook.json")


def _client_id(explicite=None):
    if explicite:
        return explicite
    try:
        with open(os.path.join(_dir(), "jarvis_config.json"), "r", encoding="utf-8") as f:
            cfg_id = (json.load(f).get("outlook_client_id") or "").strip()
        if cfg_id:
            return cfg_id
    except Exception:
        pass
    return _DEFAULT_CLIENT_ID  # ID public Microsoft → aucune inscription Azure requise


def _app(client_id):
    cache = msal.SerializableTokenCache()
    p = _cache_file()
    if os.path.exists(p):
        try:
            cache.deserialize(open(p, "r", encoding="utf-8").read())
        except Exception:
            pass
    app = msal.PublicClientApplication(client_id, authority=_AUTHORITY, token_cache=cache)
    return app, cache


def _sauver_cache(cache):
    if cache.has_state_changed:
        with open(_cache_file(), "w", encoding="utf-8") as f:
            f.write(cache.serialize())


def token_silencieux(client_id=None):
    """Jeton depuis le cache (refresh silencieux). None si pas encore connecté."""
    if not _MSAL_OK:
        return None
    cid = _client_id(client_id)
    if not cid:
        return None
    app, cache = _app(cid)
    accounts = app.get_accounts()
    if not accounts:
        return None
    res = app.acquire_token_silent(SCOPES, account=accounts[0])
    _sauver_cache(cache)
    return res.get("access_token") if res else None


def connecter(client_id=None, afficher=print):
    """Connexion interactive (device-code). Bloque jusqu'à approbation. Renvoie (ok, message)."""
    if not _MSAL_OK:
        return False, "Le module msal n'est pas installé (pip install msal)."
    cid = _client_id(client_id)
    if not cid:
        return False, "Aucun client_id Outlook. Renseignez 'outlook_client_id' dans la config."
    app, cache = _app(cid)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        return False, f"Échec du flux device-code : {flow.get('error_description', flow)}"
    afficher(flow["message"])  # « Rendez-vous sur https://microsoft.com/devicelogin et entrez le code XXXX »
    res = app.acquire_token_by_device_flow(flow)  # bloque
    _sauver_cache(cache)
    if "access_token" in res:
        return True, "Outlook connecté avec succès."
    return False, res.get("error_description", "Authentification échouée.")


def relever(compte, limit=8):
    """Relève les derniers messages Outlook via Graph. Renvoie (messages, erreur|None)."""
    tok = token_silencieux(compte.get("client_id"))
    if not tok:
        return [], "Outlook non connecté (lancez : python outlook_graph.py <client_id>)"
    try:
        url = (f"{GRAPH}/me/messages?$top={int(limit)}"
               "&$select=id,subject,from,receivedDateTime&$orderby=receivedDateTime%20desc")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        msgs = []
        for m in data.get("value", []):
            exp = (m.get("from") or {}).get("emailAddress", {})
            nom = exp.get("name") or exp.get("address") or "?"
            msgs.append({
                "id": m.get("id"),
                "compte": compte.get("name") or "Outlook",
                "de": nom,
                "sujet": m.get("subject") or "(sans objet)",
                "date": m.get("receivedDateTime") or "",
            })
        return msgs, None
    except Exception as e:
        return [], f"erreur Graph ({e})"


def lire_message(compte, msg_id):
    """Récupère un message Outlook complet (corps) via Graph. Renvoie un dict."""
    import re
    import html as _html
    import urllib.parse
    tok = token_silencieux(compte.get("client_id"))
    if not tok:
        return {"error": "Outlook non connecté"}
    try:
        mid = urllib.parse.quote(str(msg_id), safe="")
        url = f"{GRAPH}/me/messages/{mid}?$select=subject,from,receivedDateTime,body"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            m = json.loads(r.read().decode("utf-8", "replace"))
        body = m.get("body") or {}
        contenu = body.get("content") or ""
        if (body.get("contentType") or "").lower() == "html":
            contenu = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", contenu)
            contenu = re.sub(r"(?s)<[^>]+>", " ", contenu)
            contenu = _html.unescape(contenu)
            contenu = re.sub(r"[ \t]{2,}", " ", contenu)
            contenu = re.sub(r"\n{3,}", "\n\n", contenu).strip()
        exp = (m.get("from") or {}).get("emailAddress", {})
        return {
            "compte": compte.get("name") or "Outlook",
            "de": exp.get("name") or exp.get("address") or "?",
            "sujet": m.get("subject") or "(sans objet)",
            "date": m.get("receivedDateTime") or "",
            "corps": contenu or "(corps vide)",
        }
    except Exception as e:
        return {"error": f"erreur Graph ({e})"}


if __name__ == "__main__":
    import sys
    cid = sys.argv[1] if len(sys.argv) > 1 else None
    ok, msg = connecter(cid)
    print(("[OK] " if ok else "[ERREUR] ") + msg)
