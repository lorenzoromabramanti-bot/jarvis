# Vault de mémoire partagée — proposition

État au 2026-08-12. **Aucun code n'a été écrit.** Ce document est là pour être
discuté et corrigé avant.

## Le problème

`obsidian_helper.py` (130 lignes) applique `os.path.basename(titre)` à chaque
opération. C'est ce qui protège du path traversal — et c'est aussi ce qui rend
toute arborescence impossible : `projets/jarvis/notes.md` devient `notes.md`.
Le vault actuel contient **un seul fichier**.

Ce qui manque n'est pas du rangement, c'est un endroit où JARVIS et les agents
de code (Claude Code, OpenCode) déposent ce qu'ils apprennent, et où chacun
retrouve ce que l'autre a écrit.

## Ce que je propose

### 1. Un vault séparé, pas une extension de l'existant

```
C:\Program Files\JARVIS\
├── ObsidianVault\          ← inchangé : notes personnelles, JARVIS y écrit déjà
└── MemoirePartagee\        ← NOUVEAU
```

Séparé pour une raison simple : les notes personnelles et la mémoire technique
n'ont ni le même public, ni la même durée de vie, ni les mêmes règles
d'écriture. Les mélanger rendrait impossible de vider l'une sans toucher
l'autre.

### 2. Arborescence par nature, pas par date

```
MemoirePartagee\
├── INDEX.md              généré, jamais édité à la main
├── decisions\            « on a choisi X plutôt que Y, parce que »
├── pannes\               une panne constatée, sa cause, son correctif
├── conventions\          règles du projet qu'un agent doit connaître
├── etat\                 photographie d'un sous-système à un instant
└── brouillons\           en cours, rien de fiable
```

Cinq dossiers, pas plus. Une arborescence par date (`2026\08\`) répond à
« quand », or la question posée est toujours « quoi ». Un dossier de plus se
justifie le jour où l'un déborde, pas avant.

### 3. Format d'une note

```markdown
---
id: panne-vpn-ip-info
type: panne
source: jarvis          # jarvis | claude-code | opencode | humain
date: 2026-08-12
sujet: [vpn, websocket]
---

Le handler vpn_get_status référençait `ip_info`, variable définie nulle part.

**Cause :** NameError avant l'envoi, avalé par le handler.
**Correctif :** variable supprimée, get_status déporté en thread.
**Vérifié :** 45 s d'échec → 1,6 s de réponse.

Voir [[convention-appels-bloquants]].
```

`source` est le champ qui compte : il faut toujours pouvoir dire **qui** a
écrit une note. Une note produite par un agent n'a pas le même poids qu'une
note écrite par toi.

### 4. Concurrence — la partie qui casse si on la néglige

JARVIS tourne en permanence. Un agent de code peut écrire au même moment.
Trois règles, dans l'ordre d'importance :

1. **Un fichier a un seul auteur.** Le nom porte la source :
   `pannes/panne-vpn-ip-info.jarvis.md`. Un agent ne modifie jamais un
   fichier `.jarvis.md`, et réciproquement. Deux avis sur le même sujet font
   deux fichiers, pas un conflit.
2. **Écriture atomique** : écrire dans un `.tmp` puis `os.replace()`. Sans ça,
   un lecteur peut tomber sur un fichier à moitié écrit. `os.replace` est
   atomique sur Windows comme sur POSIX.
3. **L'INDEX est dérivé, jamais écrit à la main.** Il se régénère en relisant
   les frontmatters. Deux processus qui l'éditent en même temps, c'est la
   première chose qui casserait.

Pas de verrou de fichier : sur Windows ils fuient dès qu'un processus meurt
mal, et on a déjà vu des PowerShell orphelins sur cette machine.

### 5. Sécurité des chemins

`basename()` disparaît, remplacé par une vérification réelle :

```python
cible = (RACINE / dossier / nom).resolve()
if not cible.is_relative_to(RACINE.resolve()):
    raise ValueError("chemin hors du vault")
if dossier not in DOSSIERS_AUTORISES:
    raise ValueError("dossier inconnu")
```

Plus permissif qu'aujourd'hui — une arborescence devient possible — et plus
sûr : `..\..\..\.env` est refusé explicitement au lieu d'être silencieusement
transformé en `.env`.

### 6. Accès

| Qui | Comment |
|---|---|
| JARVIS | `memoire_partagee.py`, en direct |
| Le HUD | onglet DAILY → NOTES, avec un sélecteur de vault |
| Claude Code, OpenCode | via `outils_mcp.py` — deux outils MCP de plus |
| Toi | Obsidian, en ouvrant le dossier |

Le point d'entrée MCP est ce qui rend la mémoire réellement *partagée* : sans
lui, un agent ne peut ni lire ni écrire, et le vault redevient un carnet à
sens unique.

## Ce que je ne propose pas

- **Pas de recherche vectorielle.** Cinq dossiers et quelques dizaines de
  notes se parcourent avec `grep`. On ajoutera des embeddings le jour où la
  recherche par mot-clé échouera vraiment, pas par anticipation.
- **Pas de synchronisation temps réel** entre JARVIS et les agents. Un agent
  lit au démarrage, écrit à la fin. Suffisant, et ça évite tout protocole.
- **Pas de migration du vault existant.** `Journal_Discussions.md` reste où il
  est, il n'a rien à faire dans une mémoire technique.

## Décisions prises (implémenté le 2026-08-12)

L'utilisateur a laissé le choix. Voici ce que j'ai retenu, et pourquoi.

1. **Nom** : `MemoirePartagee`, tel que proposé.
2. **Emplacement** : `Documents/JARVIS/MemoirePartagee`, **pas** `Program Files`.
   Windows y refuse l'écriture sans élévation, et un vault doit s'ouvrir dans
   Obsidian d'un double-clic. Pas `%APPDATA%` non plus : ce sont des notes
   qu'on lit, pas un cache. **Sur cette machine, Documents est redirigé vers
   OneDrive** — le vault s'y trouve donc, et se synchronise dans le cloud.
   C'est le réglage Windows de l'utilisateur, signalé mais pas contourné :
   créer un dossier hors de la redirection aurait produit un Documents
   fantôme à côté du vrai.
3. **Les cinq dossiers** : conservés tels quels.
4. **Purge** : rien d'automatique. `lister()` expose la date de chaque note,
   de quoi écrire une commande de tri le jour où le grenier se remplit. En
   ajouter une maintenant serait deviner un besoin.

Non fait volontairement : le sélecteur de vault dans l'onglet NOTES du HUD.
Le panneau actuel sert le vault personnel via `obsidian_helper`, et mélanger
les deux demanderait de trancher lequel s'ouvre par défaut. À décider quand
le vault aura servi un peu.

## Ce qu'il fallait trancher avant que je code

1. **Le nom.** `MemoirePartagee` ou autre chose ?
2. **L'emplacement.** Dans `C:\Program Files\JARVIS\` — donc soumis aux droits
   d'écriture de Program Files — ou ailleurs, par exemple `Documents\` ? Le
   second est plus sain, surtout en vue de l'installeur.
3. **Les cinq dossiers** te conviennent-ils, ou il en manque un ?
4. **Qui purge, et quand ?** Une mémoire qui ne se vide jamais devient un
   grenier. Je propose : rien d'automatique, mais une commande qui liste les
   notes non relues depuis six mois.
