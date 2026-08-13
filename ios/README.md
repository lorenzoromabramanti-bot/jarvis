# JARVIS local — app iOS native

App iOS minimale qui fait tourner **Gemma 4 E2B en natif** sur iPhone, via l'API
Swift officielle de LiteRT-LM.

## Pourquoi une app native

Dans un navigateur, les poids du modèle doivent tenir **entièrement** dans la
mémoire WebAssembly — un bloc unique, que iOS plafonne bien en dessous de la RAM
de l'appareil. D'où l'onglet tué sur iPhone 17 *et* iPhone 15 Pro Max, alors
qu'un iPad Pro y arrive (iPadOS est plus généreux).

Une app native fait du **mmap** : les poids restent sur le disque, le système ne
charge que les pages utiles. C'est exactement le mécanisme d'AI Edge Gallery et
de PocketPal — d'où le fait qu'ils tournent là où Safari échoue.

## Étape 1 : ce que fait cette app

Un seul écran : télécharger le modèle, le charger, poser des questions.
Rien d'autre, volontairement. **Le but est de répondre à une question :
Gemma 4 se charge-t-il nativement sur l'iPhone ?**

L'intégration JARVIS complète (WebSocket, domotique, orbe, thèmes) ne vaut la
peine que si la réponse est oui.

## Compilation — sur le MacBook Air

### 1. Créer le projet

Xcode → **File > New > Project** → **iOS > App**

| Champ | Valeur |
|---|---|
| Product Name | `JarvisLocal` |
| Interface | SwiftUI |
| Language | Swift |
| Minimum Deployment | **iOS 17.0** |

### 2. Ajouter LiteRT-LM

**File > Add Package Dependencies…** → coller :

```
https://github.com/google-ai-edge/LiteRT-LM.git
```

→ **Add Package** → cocher la cible `JarvisLocal` → **Finish**.

> Si Xcode affiche `no such module LiteRTLM` : sélectionner le projet → cible
> `JarvisLocal` → onglet **General** → **Frameworks, Libraries, and Embedded
> Content** → **+** → **LiteRTLM Package > LiteRTLM** → **Add**.

### 3. Ajouter les sources

Glisser les 4 fichiers du dossier `JarvisLocal/` dans le navigateur de projet
Xcode, en cochant la cible. Remplacer `ContentView.swift` et
`JarvisLocalApp.swift` générés par le modèle.

### 4. Signer

Onglet **Signing & Capabilities** → cocher **Automatically manage signing** →
choisir ton équipe (ton Apple ID suffit).

### 5. Installer

iPhone branché en USB → le sélectionner comme destination → **⌘R**.

Au premier lancement : Réglages → Général → VPN et gestion de l'appareil →
faire confiance au certificat développeur.

## Garder l'app installée sans corvée

Un Apple ID gratuit signe pour **7 jours**. TrollStore, qui installait de façon
permanente, ne fonctionne que jusqu'à iOS 17.0 — inutilisable ici.

La bonne méthode : **AltStore + AltServer sur le PC**, qui re-signe
automatiquement en tâche de fond tant que l'iPhone est sur le même Wi-Fi. Comme
le PC tourne déjà en permanence pour JARVIS, c'est transparent.

Contrairement à Ksign et aux certificats d'entreprise partagés, le certificat
est le tien : Apple ne peut pas le révoquer.

**Le modèle est stocké hors du bundle de l'app**, dans Application Support. Il
survit donc aux re-signatures — seule une désinstallation complète l'efface.
C'est aussi pour ça que l'`.ipa` reste minuscule au lieu de peser 2,6 Go.

## Si le chargement échoue

Dans `LocalEngine.swift`, remplacer `backend: .gpu` par `backend: .cpu()`.
Plus lent, mais nettement moins exigeant en mémoire.

## Le modèle

`gemma-4-E2B-it.litertlm` — **2,6 Go**, téléchargé au premier lancement.

Attention : c'est le build **appareil**, à ne pas confondre avec
`gemma-4-E2B-it-web.litertlm` (2,0 Go) utilisé par la version navigateur de
JARVIS. Les deux ne sont pas interchangeables.
