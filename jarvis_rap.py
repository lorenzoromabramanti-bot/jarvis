"""
jarvis_rap.py — Module RAP / FLOW pour JARVIS
==============================================
Génère un rap interprété de manière dynamique via Gemini.
Utilise le client Google GenAI déjà configuré dans l'écosystème JARVIS.

Usage standalone :
    python jarvis_rap.py "la technologie et l'IA"

Usage depuis main2.py / jarvis_agent.py :
    from jarvis_rap import JarvisRap
    rap = JarvisRap()
    texte = rap.generer(theme="la nuit de Paris")
    print(texte)
"""

import os
import sys
import asyncio
import logging
from typing import Optional

# ── Imports Google GenAI ──────────────────────────────────────────────────────
try:
    import google.genai as genai
    from google.genai import types as genai_types
    _GENAI_DISPONIBLE = True
except ImportError:
    _GENAI_DISPONIBLE = False

# ── Import dotenv (optionnel) ─────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(
        dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        override=False
    )
except ImportError:
    pass

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger("JARVIS_RAP")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT SYSTÈME — le coeur du flow
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT_RAP = """
Tu es JARVIS, une IA qui rappe avec un flow électrique, précis et vivant.

RÈGLES ABSOLUES :
- Ne décris JAMAIS la musique. TU ES le flow. TU ES le rap.
- Adopte un rythme naturel : syllabes courtes = vitesse, syllabes longues = emphase.
- Marque les beats avec des pauses visuelles : "..." ou "—" ou des lignes vides.
- Utilise des onomatopées de percussion quand ça colle : *tss*, *boom*, *clap*, *snap*.
- Structure en 3 parties : [INTRO] → [COUPLET] × 2 → [REFRAIN] × 2 → [OUTRO]
- Rime obligatoire : au moins AABB ou ABAB par strophe.
- Intensité croissante : commence calme, monte en puissance sur le 2e couplet.
- Termine avec une chute forte, une dernière punchline qui claque.
- Français uniquement, argot et jeux de mots bienvenus.

STRUCTURE À RESPECTER :
[INTRO]
  2-4 lignes d'accroche, rythme posé, ambiance installée.

*tss tss boom*

[COUPLET 1]
  8 lignes, flow fluide, on pose le sujet.

*clap — clap — boom*

[REFRAIN]
  4 lignes accrocheuses, répétées deux fois, mémorables.

*tss boom tss boom*

[COUPLET 2]
  8 lignes, montée en intensité, punchlines percutantes.

*BOOM — CLAP — BOOM*

[REFRAIN]
  (même refrain)

[OUTRO]
  2-4 lignes, chute froide, dernière punchline dévastatrice.
  ...silence...
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLASSE PRINCIPALE
# ─────────────────────────────────────────────────────────────────────────────
class JarvisRap:
    """
    Génère un rap interprété dynamiquement via l'API Gemini.

    Paramètres
    ----------
    api_key : str, optionnel
        Clé API Gemini. Si absente, lit GEMINI_API_KEY dans l'environnement.
    model : str
        Modèle Gemini à utiliser. Défaut : gemini-2.5-flash.
    temperature : float
        Créativité (0.0–2.0). Défaut : 1.0 pour un flow maximal.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
    ):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError(
                "Le package 'google-genai' n'est pas installé.\n"
                "  → pip install google-genai"
            )

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Aucune clé GEMINI_API_KEY trouvée.\n"
                "  → Ajoute GEMINI_API_KEY dans ton fichier .env ou passe-la en paramètre."
            )

        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)
        log.info("JarvisRap initialisé — modèle : %s | température : %.1f", model, temperature)

    # ── Génération du rap ─────────────────────────────────────────────────────
    def generer(self, theme: str, contexte: str = "") -> str:
        """
        Génère un rap complet sur le thème demandé.

        Paramètres
        ----------
        theme : str
            Le sujet du rap. Ex : "la nuit de Paris", "l'IA qui dépasse l'humain".
        contexte : str, optionnel
            Contexte supplémentaire : ambiance souhaitée, style, etc.

        Retourne
        --------
        str : Le texte du rap formaté avec le flow.
        """
        if not theme.strip():
            raise ValueError("Le thème ne peut pas être vide.")

        prompt_user = f"Crée un rap complet sur le thème : « {theme} »"
        if contexte.strip():
            prompt_user += f"\nContexte / ambiance souhaitée : {contexte}"

        log.info("Génération du rap pour le thème : « %s »", theme)

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt_user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT_RAP,
                    temperature=self.temperature,
                    max_output_tokens=2048,
                ),
            )
            texte = response.text.strip() if response and response.text else ""

            if not texte:
                raise RuntimeError("Réponse vide reçue de l'API Gemini.")

            log.info("Rap généré avec succès (%d caractères).", len(texte))
            return texte

        except Exception as exc:
            log.error("Erreur lors de la génération du rap : %s", exc)
            raise

    # ── Rendu TTS via edge-tts (optionnel) ───────────────────────────────────
    async def _tts_async(self, texte: str, fichier_sortie: str, voix: str) -> None:
        """Synthèse vocale asynchrone via edge-tts."""
        try:
            import edge_tts
        except ImportError:
            log.warning("edge-tts non installé. TTS ignoré. → pip install edge-tts")
            return

        communicate = edge_tts.Communicate(texte, voice=voix, rate="+15%", pitch="-5Hz")
        await communicate.save(fichier_sortie)
        log.info("Audio TTS sauvegardé : %s", fichier_sortie)

    def lire_rap(
        self,
        texte: str,
        fichier_sortie: Optional[str] = None,
        voix: str = "fr-FR-HenriNeural",
    ) -> Optional[str]:
        """
        Convertit le rap en audio via edge-tts et le joue via pygame.

        Paramètres
        ----------
        texte : str
            Texte du rap à lire.
        fichier_sortie : str, optionnel
            Chemin du fichier MP3. Sinon, fichier temporaire horodaté.
        voix : str
            Voix edge-tts. Défaut : fr-FR-HenriNeural (voix masculine française).

        Retourne
        --------
        str : chemin du fichier audio généré, ou None si échec.
        """
        if fichier_sortie is None:
            import time
            ts = int(time.time() * 1000)
            fichier_sortie = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"jarvis_rap_{ts}.mp3"
            )

        try:
            asyncio.run(self._tts_async(texte, fichier_sortie, voix))
        except Exception as exc:
            log.error("Erreur TTS : %s", exc)
            return None

        # Lecture via pygame si disponible
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(fichier_sortie)
            pygame.mixer.music.play()
            log.info("Lecture audio en cours...")
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as exc:
            log.warning("Impossible de lire l'audio via pygame : %s", exc)
            log.info("Fichier audio disponible ici : %s", fichier_sortie)

        return fichier_sortie

    # ── Raccourci tout-en-un ─────────────────────────────────────────────────
    def generer_et_lire(
        self,
        theme: str,
        contexte: str = "",
        voix: str = "fr-FR-HenriNeural",
    ) -> str:
        """
        Génère le rap ET le lit à voix haute.
        Retourne le texte du rap.
        """
        texte = self.generer(theme, contexte)
        print("\n" + "=" * 60)
        print(texte)
        print("=" * 60 + "\n")
        self.lire_rap(texte, voix=voix)
        return texte


# ─────────────────────────────────────────────────────────────────────────────
# CLI — python jarvis_rap.py "le thème ici"
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="JARVIS RAP — Génère un rap via Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python jarvis_rap.py "la nuit de Paris"
  python jarvis_rap.py "l IA qui dépasse l humain" --contexte "ambiance sombre, futuriste"
  python jarvis_rap.py "le code qui bug" --lire --voix fr-FR-HenriNeural
  python jarvis_rap.py "vivre sa vie" --temperature 1.4
        """,
    )
    parser.add_argument("theme", nargs="+", help="Thème du rap")
    parser.add_argument("--contexte", default="", help="Contexte / ambiance souhaitée")
    parser.add_argument("--lire", action="store_true", help="Lire le rap à voix haute via TTS")
    parser.add_argument("--voix", default="fr-FR-HenriNeural", help="Voix edge-tts")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Modèle Gemini")
    parser.add_argument("--temperature", type=float, default=1.0, help="Température (0.0–2.0)")
    parser.add_argument("--sortie", default=None, help="Fichier MP3 de sortie (optionnel)")
    args = parser.parse_args()

    theme = " ".join(args.theme)

    try:
        rap = JarvisRap(model=args.model, temperature=args.temperature)

        if args.lire:
            rap.generer_et_lire(theme=theme, contexte=args.contexte, voix=args.voix)
        else:
            texte = rap.generer(theme=theme, contexte=args.contexte)
            print("\n" + "=" * 60)
            print(texte)
            print("=" * 60 + "\n")

            if args.sortie:
                rap.lire_rap(texte, fichier_sortie=args.sortie, voix=args.voix)

    except (ValueError, RuntimeError) as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
