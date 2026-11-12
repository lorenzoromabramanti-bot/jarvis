# JARVIS 1.5.0

*Français plus bas.*

**The Glass Orb.** A new, calm view of JARVIS for every day: `frontend/verre.html`.

- The orb in the middle, what you said above it, JARVIS's answer below. Light by day (7 am to 8 pm),
  dark at night, or forced with the button in the corner. Works on desktop and on a phone.
- **A mic button**: press it and talk right away, without saying "Jarvis".
- **Glass cards** appear around the orb when you talk about them, and leave on their own after 90 seconds:
  - **weather**: the next ten hours as a curve, wind, rain, min/max;
  - **music**: what plays on your Home Assistant players, with previous, play/pause and next;
  - **devices**: the players, TVs and amps Home Assistant sees online;
  - **Pronote**: homework and tests, when you talk about school.
- The small floating orb on the desktop has the same glass look, light or dark.

To open it by default, set `"interface_page": "verre.html"` in `jarvis_config.json` (or the
`JARVIS_INTERFACE_PAGE` environment variable). Without it, nothing changes: the full dashboard opens as before.

Under the hood: the weather answer now also carries the hours, the rain chance and the min/max
(`get_meteo`); the interface gateway lets three `media_player` services through (previous, play/pause,
next) and a new level-1 message, `ecoute_directe`, for the mic button.

---

# JARVIS 1.5.0 (français)

**L'Orbe de verre.** Une nouvelle vue de JARVIS, calme, pour tous les jours : `frontend/verre.html`.

- L'orbe au milieu, ce que vous avez dit au-dessus, la réponse de JARVIS en dessous. Claire le jour
  (de 7 h à 20 h), sombre la nuit, ou forcée avec le bouton du coin. Sur ordinateur comme sur téléphone.
- **Un bouton micro** : appuyez et parlez tout de suite, sans dire « Jarvis ».
- **Des cartes de verre** apparaissent autour de l'orbe quand vous en parlez, et repartent seules au bout
  de 90 secondes :
  - **météo** : les dix prochaines heures en courbe, le vent, la pluie, le mini et le maxi ;
  - **musique** : ce qui joue sur vos lecteurs Home Assistant, avec précédent, lecture/pause et suivant ;
  - **appareils** : les lecteurs, télés et amplis que Home Assistant voit en ligne ;
  - **Pronote** : devoirs et contrôles, quand vous parlez d'école.
- La petite orbe flottante du bureau a le même aspect verre, claire ou sombre.

Pour l'ouvrir par défaut, mettez `"interface_page": "verre.html"` dans `jarvis_config.json` (ou la variable
d'environnement `JARVIS_INTERFACE_PAGE`). Sans ce réglage, rien ne change : le tableau de bord complet
s'ouvre comme avant.

En coulisses : la réponse météo porte maintenant aussi les heures, le risque de pluie et le mini/maxi
(`get_meteo`) ; la passerelle de l'interface laisse passer trois services `media_player` (précédent,
lecture/pause, suivant) et un nouveau message de niveau 1, `ecoute_directe`, pour le bouton micro.
