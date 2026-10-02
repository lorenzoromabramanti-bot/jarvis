# -*- coding: utf-8 -*-
"""
J.A.R.V.I.S — Bot Discord (texte, commandes complètes)
==========================================================
Même pipeline que la voix (traiter_reponse_ia dans main2.py), avec deux
garde-fous que la voix n'a jamais eu besoin d'avoir : la voix suppose une
présence physique devant la machine, Discord non.

1. SEUL l'utilisateur autorisé (DISCORD_USER_ID) peut déclencher une
   action — n'importe qui d'autre dans le salon est ignoré.
2. Un message qui ressemble à une action irréversible (désinstaller,
   supprimer, formater, éteindre le PC...) exige une confirmation
   explicite avant d'être exécuté — même logique que le garde-fou déjà
   en place pour le HUD/mobile (passerelle du HUD).

PLAFOND CONNU (ponytail) : filtre par mots-clés sur le texte reçu, pas par
outil réellement invoqué par le modèle — le pipeline texte libre de
main2.py n'a pas de registre par outil comme catalogue.py. Un message qui
ne contient aucun de ces mots peut en théorie encore faire choisir au
modèle un outil sensible ; ce filtre est un filet, pas une garantie
totale. À durcir si un vrai registre par outil est construit côté
main2.py — jusque-là, mieux que l'absence totale de garde-fou.
"""

import asyncio
import os
import re
import time

_MOTS_RISQUES = re.compile(
    r"d[ée]sinstall|supprim|efface|d[ée]trui|formate|"
    r"[ée]teins?\s+(?:le\s+|l')?(?:pc|ordinateur)|"
    r"red[ée]marre\s+(?:le\s+|l')?(?:pc|ordinateur)|"
    r"d[ée]verrouill|d[ée]sarm|alarme|"
    r"vide(?:r)?\s+la\s+corbeille|reset\s*usine",
    re.IGNORECASE)

TIMEOUT_CONFIRMATION = 120  # secondes avant qu'une confirmation en attente expire

_EN_ATTENTE = {}  # (user_id, salon_id) -> {"texte": str, "depuis": float}

_MOTS_CONFIRMATION = ("confirme", "confirmé", "oui", "vas-y", "vas y")

# Photo caméra : commande dediee, ne passe pas par traiter_reponse_ia. Simple,
# lecture seule (aucune action physique), pas besoin du filtre de risque ni
# de deviner si le modele va bien choisir l'outil vision depuis du texte libre.
_MOTIF_PHOTO = re.compile(
    r"montre[- ]moi\s+(?:mon\s+|le\s+|ton\s+)?"
    r"(?:bureau|la\s+cam[ée]ra|la\s+webcam|ce\s+que\s+tu\s+vois)",
    re.IGNORECASE)

# Activer/désactiver la surveillance webcam — lecture seule sur l'état,
# jamais couvert par le filtre de risque (ce n'est pas une action physique
# irréversible), mais dédié pour ne pas dépendre du choix d'outil du modèle.
_MOTIF_SURVEILLANCE_ON = re.compile(
    r"\bactive\s+la\s+surveillance", re.IGNORECASE)
_MOTIF_SURVEILLANCE_OFF = re.compile(
    r"d[ée]sactive\s+la\s+surveillance", re.IGNORECASE)

# Vocal Discord natif (gratuit — pas de téléphonie payante). Rejoindre exige
# que l'utilisateur soit déjà dans un salon vocal (pas de choix ambigu de
# salon à deviner).
_MOTIF_REJOINDRE_VOCAL = re.compile(
    r"rejoins?(?:[- ]moi)?\s+(?:le\s+|dans\s+le\s+)?(?:salon\s+|canal\s+)?vocal"
    r"|viens\s+dans\s+le\s+(?:salon\s+|canal\s+)?vocal",
    re.IGNORECASE)
_MOTIF_QUITTER_VOCAL = re.compile(
    r"quitte\s+le\s+(?:salon\s+|canal\s+)?vocal|d[ée]connecte[- ]toi\s+du\s+(?:salon\s+|canal\s+)?vocal",
    re.IGNORECASE)

# guild_id -> {"voice_client":..., "sink":..., "tache":...}
_CONNEXIONS_VOCALES = {}


def est_risque(texte):
    """True si le texte contient un mot-clé d'action potentiellement irréversible."""
    return bool(_MOTS_RISQUES.search(texte or ""))


def demande_confirmation(user_id, texte):
    _EN_ATTENTE[user_id] = {"texte": texte, "depuis": time.time()}


def confirmation_en_attente(user_id):
    """Texte en attente de confirmation pour cet utilisateur, ou None (absent/expiré)."""
    etat = _EN_ATTENTE.get(user_id)
    if not etat:
        return None
    if time.time() - etat["depuis"] > TIMEOUT_CONFIRMATION:
        del _EN_ATTENTE[user_id]
        return None
    return etat["texte"]


def annuler_confirmation(user_id):
    _EN_ATTENTE.pop(user_id, None)


def est_confirmation(texte):
    return (texte or "").strip().lower() in _MOTS_CONFIRMATION


def resoudre_confirmation(cle, texte):
    """
    (consomme, demande). Si une demande attend pour `cle` (utilisateur,
    salon), ce message la tranche : `demande` est le texte MIS EN ATTENTE
    s'il confirme, None s'il annule. Le mot « confirme » ne part jamais au
    pipeline : il y validerait une autre confirmation en attente dans main2.
    """
    attente = confirmation_en_attente(cle)
    if attente is None:
        return False, None
    annuler_confirmation(cle)
    return True, (attente if est_confirmation(texte) else None)


async def _executer_et_repondre(message, texte=None):
    """Lance traiter_reponse_ia sur `texte` (par défaut celui du message), renvoie la réponse dans le salon."""
    import main2
    sink = []
    jeton = main2.DISCORD_SINK.set(sink)
    try:
        await main2.traiter_reponse_ia(texte or message.content.strip(), canal="texte")
    finally:
        main2.DISCORD_SINK.reset(jeton)
    reponse = "\n".join(sink).strip() or "(pas de réponse)"
    await message.channel.send(reponse[:2000])


async def _envoyer_photo(message):
    """Capture une image caméra et l'envoie dans le salon, avec sa description."""
    import discord
    import main2
    import vision_module

    sink = []
    jeton = main2.DISCORD_SINK.set(sink)
    chemin = None
    try:
        description, chemin = await vision_module.jarvis_vision_camera(
            "Décris ce que tu vois, en particulier s'il y a quelqu'un.",
            garder_fichier=True)
        texte = "\n".join(sink + [description]).strip()
        if chemin and os.path.exists(chemin):
            await message.channel.send(texte[:2000], file=discord.File(chemin))
        else:
            await message.channel.send(texte[:2000] or "(pas d'image obtenue)")
    except Exception as e:
        await message.channel.send(f"Échec de la capture caméra : {e}")
    finally:
        main2.DISCORD_SINK.reset(jeton)
        if chemin and os.path.exists(chemin):
            os.remove(chemin)


async def _boucle_ecoute(guild_id, voice_client, sink, texte_channel):
    """
    Consomme les segments de parole (queue thread-safe alimentée par le
    sink audio) et fait tourner le pipeline complet pour chacun :
    transcription -> traiter_reponse_ia -> synthèse -> lecture dans le
    salon vocal. S'arrête proprement dès que la connexion est retirée de
    _CONNEXIONS_VOCALES (déconnexion demandée).
    """
    import discord
    import discord_voice
    import main2

    boucle = asyncio.get_running_loop()
    while _CONNEXIONS_VOCALES.get(guild_id, {}).get("sink") is sink:
        segment = await boucle.run_in_executor(None, sink._queue.get)
        if _CONNEXIONS_VOCALES.get(guild_id, {}).get("sink") is not sink:
            break  # deconnecte pendant l'attente

        texte = discord_voice.transcrire_pcm(segment)
        if not texte:
            continue
        print(f"[VOCAL DISCORD] Entendu : {texte}")

        collecte = []
        jeton = main2.DISCORD_SINK.set(collecte)
        try:
            await main2.traiter_reponse_ia(texte, canal="texte")
        except Exception as e:
            collecte.append(f"Erreur : {e}")
        finally:
            main2.DISCORD_SINK.reset(jeton)
        reponse = "\n".join(collecte).strip()
        if not reponse:
            continue

        await texte_channel.send(f"🎙️ *{texte}*\n{reponse[:1900]}")

        chemin_audio = None
        sink.suspendre(True)  # anti-echo : ne pas s'ecouter soi-meme
        try:
            chemin_audio = await discord_voice.synthetiser(reponse[:2000])
            if voice_client.is_connected():
                termine = asyncio.Event()
                voice_client.play(discord.FFmpegPCMAudio(chemin_audio),
                                   after=lambda err: boucle.call_soon_threadsafe(termine.set))
                await termine.wait()
        except Exception as e:
            print(f"[VOCAL DISCORD] Erreur lecture reponse : {e}")
        finally:
            sink.suspendre(False)
            if chemin_audio and os.path.exists(chemin_audio):
                os.remove(chemin_audio)


async def _brancher_vocal(salon, user_id, texte_channel):
    """Rejoint `salon` et ecoute `user_id` ; les reponses ecrites vont dans `texte_channel`."""
    import queue as _queue_mod
    import discord_voice
    from discord.ext import voice_recv

    guild_id = salon.guild.id
    ancienne = _CONNEXIONS_VOCALES.get(guild_id)
    if ancienne:
        ancienne["tache"].cancel()
        await ancienne["voice_client"].disconnect(force=True)
        del _CONNEXIONS_VOCALES[guild_id]

    voice_client = await salon.connect(cls=voice_recv.VoiceRecvClient)
    sink = discord_voice.EcouteurUtilisateur(
        user_id_autorise=user_id, segments_queue=_queue_mod.Queue())
    voice_client.listen(sink)

    tache = asyncio.create_task(_boucle_ecoute(guild_id, voice_client, sink, texte_channel))
    _CONNEXIONS_VOCALES[guild_id] = {"voice_client": voice_client, "sink": sink, "tache": tache}


async def _rejoindre_vocal(message):
    voix = getattr(message.author, "voice", None)  # absent en message privé
    if not voix or not voix.channel:
        await message.channel.send("Tu n'es dans aucun salon vocal.")
        return
    salon = message.author.voice.channel
    await _brancher_vocal(salon, message.author.id, message.channel)
    await message.channel.send(f"🎙️ J'ai rejoint **{salon.name}**. Je t'écoute.")


async def _deconnecter(guild_id):
    connexion = _CONNEXIONS_VOCALES.pop(guild_id, None)
    if not connexion:
        return False
    connexion["tache"].cancel()
    await connexion["voice_client"].disconnect(force=True)
    return True


async def _quitter_vocal(message):
    if message.guild is None:  # message privé : pas de serveur, on quitte tout
        await message.channel.send(await _quitter_tout())
        return
    if await _deconnecter(message.guild.id):
        await message.channel.send("👋 Déconnecté du vocal.")
    else:
        await message.channel.send("Je ne suis dans aucun salon vocal.")


# ── Depuis JARVIS (voix, HUD) plutot que depuis un message Discord ────────
# Demande reelle de l'utilisateur, 4 fois dans jarvis_conversations.json
# (« rejoin le salon vocal », « rejoins le salon vocal discord »...) : elle
# partait au modele, qui ne peut rien faire. Le bot tourne sur la boucle du
# serveur WebSocket ; ces fonctions sont appelees depuis un thread d'outil
# (tools/pc_controle.py, mode « bloquant ») et y soumettent la coroutine.
_CLIENT = None
_USER_ID = None


def _sur_la_boucle_du_bot(coro, delai=25):
    client = _CLIENT
    if client is None or not client.is_ready():
        coro.close()
        return None
    try:
        courante = asyncio.get_running_loop()
    except RuntimeError:
        courante = None
    if courante is client.loop:  # attendre ici bloquerait la boucle qui doit executer coro
        coro.close()
        raise RuntimeError("appel bloquant depuis la boucle du bot : passer par un thread")
    return asyncio.run_coroutine_threadsafe(coro, client.loop).result(delai)


async def _rejoindre_utilisateur():
    uid = int(_USER_ID)
    for guild in _CLIENT.guilds:
        for salon in list(guild.voice_channels) + list(getattr(guild, "stage_channels", [])):
            if any(m.id == uid for m in salon.members):
                # Le salon vocal a son propre fil de discussion : les reponses
                # ecrites y arrivent, a cote de la voix.
                await _brancher_vocal(salon, uid, salon)
                return f"J'ai rejoint le salon vocal « {salon.name} » sur Discord."
    return "Tu n'es dans aucun salon vocal Discord pour l'instant. Rejoins-en un, puis redemande-moi."


async def _quitter_tout():
    n = 0
    for guild_id in list(_CONNEXIONS_VOCALES):
        n += await _deconnecter(guild_id)
    return "J'ai quitté le vocal Discord." if n else "Je ne suis dans aucun salon vocal Discord."


def rejoindre_vocal_depuis_jarvis():
    r = _sur_la_boucle_du_bot(_rejoindre_utilisateur())
    return r or "Le bot Discord n'est pas connecté : vérifie DISCORD_BOT_TOKEN dans le .env et relance JARVIS."


def quitter_vocal_depuis_jarvis():
    r = _sur_la_boucle_du_bot(_quitter_tout())
    return r or "Le bot Discord n'est pas connecté."


async def demarrer_bot_discord():
    """
    Lance le bot en arrière-plan si DISCORD_BOT_TOKEN et DISCORD_USER_ID
    sont configurés. Sans eux, désactivé silencieusement (comme
    notifications.envoyer sans DISCORD_WEBHOOK_URL) — pas une erreur, un
    module optionnel non configuré.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN")
    user_autorise = os.environ.get("DISCORD_USER_ID")
    if not token or not user_autorise:
        print("[DISCORD BOT] DISCORD_BOT_TOKEN / DISCORD_USER_ID absents — bot désactivé.")
        return

    import discord

    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True  # necessaire pour connaitre le salon vocal de l'utilisateur
    client = discord.Client(intents=intents)
    global _CLIENT, _USER_ID
    _CLIENT, _USER_ID = client, user_autorise

    @client.event
    async def on_ready():
        print(f"[DISCORD BOT] Connecté en tant que {client.user}.")

    @client.event
    async def on_message(message):
        if message.author.bot:
            return
        if str(message.author.id) != str(user_autorise):
            return
        if not message.content or not message.content.strip():
            return

        texte = message.content.strip()

        cle = (message.author.id, message.channel.id)
        consomme, demande = resoudre_confirmation(cle, texte)
        if consomme:
            if demande:
                await _executer_et_repondre(message, demande)
            else:
                await message.channel.send("Annulé.")
            return

        if _MOTIF_PHOTO.search(texte):
            await _envoyer_photo(message)
            return

        if _MOTIF_SURVEILLANCE_ON.search(texte) or _MOTIF_SURVEILLANCE_OFF.search(texte):
            import surveillance_bureau
            actif = bool(_MOTIF_SURVEILLANCE_ON.search(texte))
            surveillance_bureau.activer(actif)
            await message.channel.send(
                "🟢 Surveillance activée." if actif else "🔴 Surveillance désactivée.")
            return

        if _MOTIF_REJOINDRE_VOCAL.search(texte):
            await _rejoindre_vocal(message)
            return

        if _MOTIF_QUITTER_VOCAL.search(texte):
            await _quitter_vocal(message)
            return

        if est_risque(texte):
            demande_confirmation(cle, texte)
            await message.channel.send(
                "⚠️ Action potentiellement irréversible détectée. "
                "Réponds « confirme » pour l'exécuter, autre chose pour annuler.")
            return

        await _executer_et_repondre(message)

    try:
        await client.start(token)
    except Exception as e:
        print(f"[DISCORD BOT] Démarrage impossible : {e}")
