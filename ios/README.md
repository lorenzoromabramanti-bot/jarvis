# JARVIS — app iOS native

Client natif du **vrai JARVIS** qui tourne sur le PC : mêmes capacités que le
HUD web (`mobile/`), par WebSocket direct sur le port 8765 (`main2.py`).
Ce n'est plus un modèle embarqué sur le téléphone — c'est un écran de plus
pour parler au JARVIS qui tourne déjà.

## Ce que fait cette app

- **Discussion** — chat texte avec JARVIS, comme le HUD web.
- **Capacités** — les 16 capacités du catalogue (`catalogue.py`), avec la
  possibilité d'en retirer une (protection) ou d'en activer une, toujours
  après un avertissement affiché à l'écran.
- **Réglages** — saisie manuelle des clés API (Gemini, Groq, Anthropic…),
  envoyées chiffrées sur le fil et jamais réaffichées en clair — seule une
  version masquée (`••••abcd`) revient du serveur.

Trois fichiers dans `JarvisLocal/` :

| Fichier | Rôle |
|---|---|
| `JarvisClient.swift` | Le contrat réseau — connexion, auth, catalogue, chat, réglages |
| `ContentView.swift` | Les trois écrans (connexion, puis les 3 onglets) |
| `JarvisLocalApp.swift` | Point d'entrée SwiftUI |

## Le protocole (vérifié, pas deviné)

Chaque message ci-dessous a été testé par un round-trip réel contre le
serveur qui tourne — pas lu dans le code puis supposé correct.

1. À la connexion : `{"token": "…"}` → `{"type": "auth_ok"}` ou `"auth_failed"`.
2. `{"type": "get_catalogue"}` → la liste réelle des capacités, avec pour
   chacune `disponible` (la config nécessaire est là) et `activee` (choix
   actuel de l'utilisateur) — deux choses différentes.
3. `{"type": "set_capacites", "cles": [...], "mode": "avance"}` pour changer
   ce qui est actif.
4. `{"type": "mobile_command", "text": "…"}` pour parler. La réponse
   n'arrive **pas** en retour direct : elle arrive plus tard, en diffusion,
   sous la forme `{"action": "jarvis_text", "text": "…"}`.
5. `{"type": "update_settings", "settings": {"api_keys": {"NOM": "valeur"}}}`
   pour écrire une clé API dans `.env` côté serveur, à chaud.

Ce que le Swift, lui, n'a **pas** été vérifié : il n'a jamais compilé, faute
de Mac disponible sur cette machine. À tester en premier avant tout le reste.

## Se connecter à JARVIS

Il faut que le téléphone puisse atteindre le PC sur le port 8765 :

- **Même Wi-Fi** : l'IP locale du PC (`ipconfig` → IPv4).
- **À distance** : passer par le même mécanisme Tailscale déjà utilisé pour
  Home Assistant (voir la doc HA) — évite d'ouvrir le port sur Internet.

Le jeton d'accès est `JARVIS_ACCESS_TOKEN` dans le `.env` du PC.

## Compilation — sur un Mac (Xcode)

### 1. Créer le projet

Xcode → **File > New > Project** → **iOS > App**

| Champ | Valeur |
|---|---|
| Product Name | `JarvisLocal` |
| Interface | SwiftUI |
| Language | Swift |
| Minimum Deployment | iOS 17.0 |

### 2. Ajouter les sources

Glisser les 3 fichiers du dossier `JarvisLocal/` dans le navigateur de projet
Xcode, en cochant la cible. Remplacer `ContentView.swift` et
`JarvisLocalApp.swift` générés par le modèle. Aucune dépendance externe —
`URLSessionWebSocketTask` est dans le SDK iOS de base.

### 3. Signer

Onglet **Signing & Capabilities** → **Automatically manage signing** →
choisir son équipe (un Apple ID gratuit suffit).

### 4. Installer

iPhone branché en USB → le sélectionner comme destination → **⌘R**.

Au premier lancement : Réglages → Général → VPN et gestion de l'appareil →
faire confiance au certificat développeur.

## Garder l'app installée sans corvée

Un Apple ID gratuit signe pour **7 jours**. La méthode qui tient dans la
durée : **AltStore + AltServer sur le PC**, qui re-signe automatiquement en
tâche de fond tant que l'iPhone est sur le même Wi-Fi — transparent, puisque
le PC tourne déjà en permanence pour JARVIS.

Le certificat est le tien, contrairement aux certificats d'entreprise
partagés : Apple ne peut pas le révoquer.
