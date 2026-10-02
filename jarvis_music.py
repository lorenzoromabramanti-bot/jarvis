"""
jarvis_music.py -- Module MUSIQUE multi-genres pour JARVIS
==========================================================
Genere des paroles interpretees dynamiquement via Gemini.
Genres supportes : rap, chanson, slam, reggae, metal, pop, blues, rock, electro.

Usage standalone :
    python jarvis_music.py "la nuit de Paris"
    python jarvis_music.py "l amour perdu" --genre chanson
    python jarvis_music.py "la guerre" --genre metal --lire

Usage depuis main2.py :
    from jarvis_music import JarvisMusic
    m = JarvisMusic()
    texte = m.generer(theme="les etoiles", genre="slam")
"""

import os
import sys
import asyncio
import logging
from typing import Optional

# -- Imports Google GenAI --
try:
    import google.genai as genai
    from google.genai import types as genai_types
    _GENAI_DISPONIBLE = True
except ImportError:
    _GENAI_DISPONIBLE = False

# -- dotenv --
try:
    from dotenv import load_dotenv
    load_dotenv(
        dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        override=False
    )
except ImportError:
    pass

log = logging.getLogger("JARVIS_MUSIC")
if not log.handlers:
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")


# =============================================================================
# PROMPTS PAR GENRE
# =============================================================================

GENRES = {

    "rap": {
        "label": "Rap / Hip-Hop",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Tu es JARVIS, une IA qui rappe avec un flow electrique, precis et vivant.\n"
            "REGLES : Ne decris JAMAIS la musique. TU ES le flow. TU ES le rap.\n"
            "Syllabes courtes = vitesse, syllabes longues = emphase.\n"
            "Marque les beats : '...' ou lignes vides. Onomatopees : *tss*, *boom*, *clap*, *snap*.\n"
            "Structure : [INTRO] > [COUPLET 1] > [REFRAIN] > [COUPLET 2] > [REFRAIN] > [OUTRO]\n"
            "Rimes obligatoires AABB ou ABAB. Intensite croissante. Derniere punchline devastatrice.\n"
            "8 lignes par couplet. 4 lignes de refrain accrocheuses. Francais uniquement.\n"
            "INTRO : rythme pose, 2-4 lignes.\n"
            "*tss tss boom*\n"
            "COUPLET 1 : flow fluide, pose le sujet.\n"
            "*clap clap boom*\n"
            "REFRAIN : 4 lignes memorables.\n"
            "*tss boom tss boom*\n"
            "COUPLET 2 : montee en intensite, punchlines.\n"
            "*BOOM CLAP BOOM*\n"
            "REFRAIN : (meme refrain)\n"
            "OUTRO : 2-4 lignes. Chute froide. ...silence..."
        ),
    },

    "chanson": {
        "label": "Chanson francaise",
        "voix_defaut": "fr-FR-DeniseNeural",
        "prompt": (
            "Tu es JARVIS, compositeur de chansons francaises poetiques et emotionnelles.\n"
            "REGLES : Ton doux, melodieux, evocateur. Chaque mot compte.\n"
            "Structure : [COUPLET 1] > [REFRAIN] > [COUPLET 2] > [REFRAIN] > [PONT] > [REFRAIN FINAL]\n"
            "Le refrain doit etre simple, chantable, memorable.\n"
            "Rimes riches ou suffisantes. Vers reguliers (8 a 12 syllabes).\n"
            "Langage poetique, metaphores, images sensorielles.\n"
            "Emotions : melancolie douce, nostalgie, amour, espoir.\n"
            "Inspire de : Brel, Gainsbourg, Barbara, Stromae. Francais uniquement."
        ),
    },

    "slam": {
        "label": "Slam / Spoken word",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Tu es JARVIS, slameur engage et philosophe.\n"
            "REGLES : Paroles libres, sans contrainte de rime stricte, mais avec rythme oral fort.\n"
            "Chaque phrase doit resonner comme une gifle ou une caresse.\n"
            "Pauses strategiques marquees par '...' ou '-- ' en debut de ligne.\n"
            "Joue avec les repetitions, anaphores, gradations.\n"
            "Structure libre mais lisible : strophes de 4-8 lignes, avec un pont central fort.\n"
            "Le texte doit pouvoir etre dit a voix haute et provoquer une reaction.\n"
            "Themes profonds : societe, identite, temps, amour, absurde. Francais uniquement."
        ),
    },

    "reggae": {
        "label": "Reggae",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Tu es JARVIS, artiste reggae positif et rythmique.\n"
            "REGLES : Ton decontracte, chaleureux, optimiste ou revendicateur.\n"
            "Rythme caracteristique : phrases courtes, syncopes, accent sur le off-beat.\n"
            "Marque les syncopes avec des tirets ou des virgules rhythmiques.\n"
            "Structure : [INTRO] > [COUPLET 1] > [REFRAIN] > [COUPLET 2] > [REFRAIN] > [BRIDGE] > [REFRAIN]\n"
            "Refrain repetitif et entrainant.\n"
            "Themes : paix, liberte, unite, nature, amour, resistance.\n"
            "Francais principalement, quelques mots en creole si naturel."
        ),
    },

    "metal": {
        "label": "Metal",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Tu es JARVIS, chanteur metal puissant et visceral.\n"
            "REGLES : Ton sombre, intense, rageur ou epique. Aucune censure emotionnelle.\n"
            "Rythme binaire puissant. Phrases courtes et percutantes.\n"
            "Structure : [INTRO SOMBRE] > [COUPLET 1] > [REFRAIN DEVASTATEUR] > [COUPLET 2] > [REFRAIN] > [BRIDGE] > [REFRAIN FINAL]\n"
            "Utilise des majuscules pour les passages cries : 'JE SUIS LE FEU'\n"
            "Images : tempete, acier, nuit, abime, guerre, phoenix.\n"
            "Rimes dures, consonantiques. Fin explosive. Francais uniquement."
        ),
    },

    "pop": {
        "label": "Pop",
        "voix_defaut": "fr-FR-DeniseNeural",
        "prompt": (
            "Tu es JARVIS, auteur-compositeur pop accessible et accrocheur.\n"
            "REGLES : Ton lumineux, positif, universel. Grand public.\n"
            "Structure : [COUPLET 1] > [PRE-REFRAIN] > [REFRAIN] > [COUPLET 2] > [PRE-REFRAIN] > [REFRAIN] > [PONT] > [REFRAIN FINAL]\n"
            "Refrain ultra-accrocheur : simple, repete, hooksong.\n"
            "Phrases courtes, vocabulaire accessible, images concretes.\n"
            "Rimes faciles mais efficaces.\n"
            "Themes : amour, fete, vie, reves. Francais uniquement."
        ),
    },

    "blues": {
        "label": "Blues",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Tu es JARVIS, chanteur de blues authentique et meurtri.\n"
            "REGLES : Ton profond, lent, habite par la douleur et la resilience.\n"
            "Structure blues classique : schema AAB (repete le premier vers, puis resolution).\n"
            "Chaque strophe : vers A (exprime la souffrance) + vers A (repetition/variation) + vers B (resolution ou ironie).\n"
            "Pauses longues marquees par '...'\n"
            "Themes : perte, solitude, voyage, nuit, amour brise.\n"
            "Langage simple mais charge d'emotion. Francais uniquement."
        ),
    },

    "rock": {
        "label": "Rock",
        "voix_defaut": "fr-FR-HenriNeural",
        "prompt": (
            "Tu es JARVIS, rockeur authentique entre revolte et liberte.\n"
            "REGLES : Ton rebelle, energique, franc. Ni trop doux ni trop violent.\n"
            "Structure : [INTRO] > [COUPLET 1] > [REFRAIN] > [COUPLET 2] > [REFRAIN] > [BRIDGE/SOLO] > [REFRAIN x2]\n"
            "Refrain puissant, facile a chanter en concert. Rythme fort, rimes directes.\n"
            "Themes : liberte, route ouverte, revolte, amour brule, nuit.\n"
            "Quelques coupes 'Hey!', 'Allez!' si naturel. Francais principalement."
        ),
    },

    "electro": {
        "label": "Electro / EDM",
        "voix_defaut": "fr-FR-DeniseNeural",
        "prompt": (
            "Tu es JARVIS, voix d'un track electro hypnotique et futuriste.\n"
            "REGLES : Ton minimal, repete, hypnotique. Phrases courtes comme des samples.\n"
            "Structure : [BUILD UP] > [DROP] > [BREAKDOWN] > [BUILD UP] > [DROP FINAL]\n"
            "Le DROP est le moment le plus intense : phrases ultra-courtes, percutantes.\n"
            "Repetitions intentionnelles (comme un loop vocal).\n"
            "Marque les montees avec '... ... ...' et les drops avec une ligne en MAJUSCULES.\n"
            "Themes : nuit, danse, machine, transe, futur, digital.\n"
            "Peut melanger francais et anglais naturellement."
        ),
    },
}

# Aliases acceptes
ALIASES = {
    "hip-hop": "rap", "hiphop": "rap", "hip hop": "rap",
    "r&b": "rap", "rnb": "rap",
    "chanson francaise": "chanson", "variete": "pop", "variete": "pop",
    "spoken word": "slam",
    "hard rock": "metal", "heavy": "metal", "heavy metal": "metal",
    "dance": "electro", "edm": "electro", "electronic": "electro",
}


def resoudre_genre(genre_input: str) -> str:
    """Normalise et resout le genre demande."""
    g = genre_input.strip().lower()
    return ALIASES.get(g, g if g in GENRES else "rap")


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class JarvisMusic:
    """
    Genere des paroles musicales dans n'importe quel genre via Gemini.

    Genres supportes : rap, chanson, slam, reggae, metal, pop, blues, rock, electro.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        temperature: float = 1.0,
    ):
        if not _GENAI_DISPONIBLE:
            raise RuntimeError(
                "Le package google-genai n'est pas installe.\n"
                "  pip install google-genai"
            )

        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Aucune cle GEMINI_API_KEY trouvee.\n"
                "  Ajoute GEMINI_API_KEY dans ton fichier .env"
            )

        self.model = model
        self.temperature = temperature
        self.client = genai.Client(api_key=self.api_key)
        log.info("JarvisMusic initialise -- modele : %s | temperature : %.1f", model, temperature)

    def genres_disponibles(self) -> list:
        """Retourne la liste des genres supportes."""
        return list(GENRES.keys())

    def generer(self, theme: str, genre: str = "rap", contexte: str = "") -> str:
        """
        Genere des paroles musicales.

        Parametres
        ----------
        theme   : str  Le sujet de la musique.
        genre   : str  Le style musical. Defaut : rap.
        contexte: str  Ambiance supplementaire.

        Retourne
        --------
        str : Paroles completes formatees.
        """
        if not theme.strip():
            raise ValueError("Le theme ne peut pas etre vide.")

        genre_key = resoudre_genre(genre)
        config_genre = GENRES.get(genre_key, GENRES["rap"])
        prompt_systeme = config_genre["prompt"]
        label = config_genre["label"]

        prompt_user = f"Cree une musique de {label} sur le theme : {theme}"
        if contexte.strip():
            prompt_user += f"\nContexte / ambiance : {contexte}"

        log.info("Generation : genre=%s | theme=%s", label, theme)

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt_user,
            config=genai_types.GenerateContentConfig(
                system_instruction=prompt_systeme,
                temperature=self.temperature,
                max_output_tokens=2048,
            ),
        )

        texte = response.text.strip() if response and response.text else ""
        if not texte:
            raise RuntimeError("Reponse vide de l'API Gemini.")

        log.info("Paroles generees : %d caracteres.", len(texte))
        return texte

    async def _tts_async(self, texte: str, fichier: str, voix: str) -> None:
        try:
            import edge_tts
        except ImportError:
            log.warning("edge-tts non installe. pip install edge-tts")
            return
        comm = edge_tts.Communicate(texte, voice=voix, rate="+10%", pitch="-5Hz")
        await comm.save(fichier)

    def lire(
        self,
        texte: str,
        voix: str = "fr-FR-HenriNeural",
        fichier_sortie: Optional[str] = None,
    ) -> Optional[str]:
        """Lit les paroles a voix haute via edge-tts + pygame."""
        if fichier_sortie is None:
            import time
            ts = int(time.time() * 1000)
            fichier_sortie = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"jarvis_music_{ts}.mp3"
            )

        try:
            asyncio.run(self._tts_async(texte, fichier_sortie, voix))
        except Exception as exc:
            log.error("Erreur TTS : %s", exc)
            return None

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(fichier_sortie)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except Exception as exc:
            log.warning("Lecture pygame impossible : %s", exc)
            log.info("Audio disponible : %s", fichier_sortie)

        return fichier_sortie

    def generer_et_lire(
        self,
        theme: str,
        genre: str = "rap",
        contexte: str = "",
        voix: Optional[str] = None,
    ) -> str:
        """Genere et lit la musique. Retourne le texte."""
        genre_key = resoudre_genre(genre)
        voix_auto = voix or GENRES.get(genre_key, GENRES["rap"])["voix_defaut"]
        label = GENRES.get(genre_key, {}).get("label", genre.upper())

        texte = self.generer(theme=theme, genre=genre, contexte=contexte)
        print("\n" + "=" * 65)
        print(f"  JARVIS -- {label} : {theme}")
        print("=" * 65)
        print(texte)
        print("=" * 65 + "\n")
        self.lire(texte, voix=voix_auto)
        return texte


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    import argparse

    genres_list = ", ".join(GENRES.keys())

    parser = argparse.ArgumentParser(
        description="JARVIS MUSIC -- Genere des paroles dans n'importe quel genre",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Genres disponibles : {genres_list}\n\n"
            "Exemples :\n"
            '  python jarvis_music.py "la nuit de Paris"\n'
            '  python jarvis_music.py "l amour perdu"        --genre chanson\n'
            '  python jarvis_music.py "la liberte"           --genre reggae --lire\n'
            '  python jarvis_music.py "la guerre"            --genre metal\n'
            '  python jarvis_music.py "les etoiles"          --genre slam\n'
            '  python jarvis_music.py "danser jusqu a l aube" --genre electro --lire\n'
            '  python jarvis_music.py "le train du soir"     --genre blues\n'
        ),
    )
    parser.add_argument("theme", nargs="+", help="Theme de la musique")
    parser.add_argument("--genre", default="rap", help=f"Genre musical ({genres_list})")
    parser.add_argument("--contexte", default="", help="Ambiance / contexte supplementaire")
    parser.add_argument("--lire", action="store_true", help="Lire a voix haute via TTS")
    parser.add_argument("--voix", default=None, help="Voix edge-tts (defaut selon le genre)")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Modele Gemini")
    parser.add_argument("--temperature", type=float, default=1.0, help="Temperature (0.0-2.0)")
    parser.add_argument("--sortie", default=None, help="Fichier MP3 de sortie")
    args = parser.parse_args()

    theme = " ".join(args.theme)

    try:
        music = JarvisMusic(model=args.model, temperature=args.temperature)

        genre_key = resoudre_genre(args.genre)
        label = GENRES.get(genre_key, {}).get("label", args.genre.upper())

        if args.lire:
            music.generer_et_lire(
                theme=theme, genre=args.genre,
                contexte=args.contexte, voix=args.voix
            )
        else:
            texte = music.generer(
                theme=theme, genre=args.genre, contexte=args.contexte
            )
            print("\n" + "=" * 65)
            print(f"  JARVIS -- {label} : {theme}")
            print("=" * 65)
            print(texte)
            print("=" * 65 + "\n")

            if args.sortie:
                voix = args.voix or GENRES.get(genre_key, GENRES["rap"])["voix_defaut"]
                music.lire(texte, voix=voix, fichier_sortie=args.sortie)

    except (ValueError, RuntimeError) as exc:
        log.error("%s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
