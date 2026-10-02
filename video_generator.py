"""
video_generator.py — pont JARVIS <-> ComfyUI (Wan2.1 T2V 1.3B GGUF).

Cote core JARVIS. Demarre ComfyUI s'il dort, soumet un workflow Wan, suit le job
sans bloquer l'event-loop WS, pousse la progression au frontend.

Wiring dans main2.py (deja fait) :
    from video_generator import handle_video_ws_message, demarrer_generation_video
    elif data.get("type") in ("video_generate", "video_status"):
        await handle_video_ws_message(data, websocket, CONNECTED_CLIENTS)

Messages pousses au frontend :
    {"type":"video_progress","job_id":..,"state":"queued|running"}
    {"type":"video_ready","job_id":..,"url":"http://127.0.0.1:8188/view?...","path":..}
    {"type":"video_error","job_id":..,"error":..}

Le frontend lit la video via l'URL /view de ComfyUI (webm vp9, joue dans le webview).
"""
import os
import sys
import json
import asyncio
import urllib.parse
import urllib.request

# comfy_client vit dans video_gen/, un dossier que git ignore : il contient
# une installation ComfyUI et ses modeles, bien trop lourds pour un depot.
#
# Ce fichier-ci EST publie, lui. Dans un clone neuf l'import echouait donc en
# ModuleNotFoundError, sans que rien n'explique pourquoi. On laisse le module
# se charger et on dit la raison au premier usage — meme principe que
# config.ModuleAbsent pour les modules Windows.
_VIDEO_GEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_gen")
if _VIDEO_GEN_DIR not in sys.path:
    sys.path.insert(0, _VIDEO_GEN_DIR)
try:
    import comfy_client as comfy   # noqa: E402
except ImportError:
    from config import ModuleAbsent
    comfy = ModuleAbsent(
        "comfy_client",
        "le dossier video_gen/ (ComfyUI et ses modeles) n'est pas dans ce depot")

_POLL_SEC = 3

# Reglages par defaut adaptes 8GB VRAM / 16GB RAM. length doit etre 4n+1.
DEFAULTS = {"width": 480, "height": 480, "length": 33, "steps": 20, "cfg": 6.0, "fps": 16.0}


def _translate_fr_en(text):
    """Traduit FR->EN via endpoint gratuit (sans cle). Wan rend mieux en anglais.
    Independant du FreeLLMAPI (peu fiable). Fallback: texte original si echec/offline."""
    if not text or not text.strip():
        return text
    try:
        q = urllib.parse.quote(text)
        url = ("https://translate.googleapis.com/translate_a/single"
               f"?client=gtx&sl=fr&tl=en&dt=t&q={q}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
        segs = data[0] or []
        out = "".join(seg[0] for seg in segs if seg and seg[0]).strip()
        return out or text
    except Exception as e:
        print(f"[video_generator] traduction FR->EN echouee ({e}), prompt original garde")
        return text


def _opts_from(data):
    o = dict(DEFAULTS)
    for k in ("width", "height", "length", "steps", "cfg", "fps", "seed", "negative"):
        if data.get(k) is not None:
            o[k] = data[k]
    return o


async def _broadcast(targets, msg):
    if not isinstance(targets, (list, set, tuple)):
        targets = [targets]
    payload = json.dumps(msg)
    for ws in list(targets):
        try:
            await ws.send(payload)
        except Exception:
            pass


async def _poll_until_done(prompt_id, targets):
    await _broadcast(targets, {"type": "video_progress", "job_id": prompt_id, "state": "running"})
    while True:
        try:
            res = await asyncio.to_thread(comfy.poll_once, prompt_id)
        except Exception as e:
            await _broadcast(targets, {"type": "video_error", "job_id": prompt_id, "error": str(e)})
            return
        if res:
            await _broadcast(targets, {"type": "video_ready", "job_id": prompt_id,
                                       "url": res["url"], "path": res["path"],
                                       "filename": res["filename"]})
            return
        await asyncio.sleep(_POLL_SEC)


async def _launch(prompt, targets, opts):
    """Demarre ComfyUI (si besoin) + soumet. Retourne prompt_id ou leve.
    Traduit le prompt FR->EN avant l'envoi (Wan rend mieux en anglais)."""
    prompt = await asyncio.to_thread(_translate_fr_en, prompt)
    await asyncio.to_thread(comfy.ensure_server)
    # comfy.submit(prompt, width=..., height=..., length=..., steps=..., cfg=..., seed=..., fps=...)
    kw = {k: opts[k] for k in ("width", "height", "length", "steps", "cfg", "fps") if k in opts}
    if "seed" in opts:
        kw["seed"] = opts["seed"]
    if "negative" in opts:
        kw["negative"] = opts["negative"]
    return await asyncio.to_thread(lambda: comfy.submit(prompt, **kw))


# ------------------------------------------------------------- API publique WS
async def handle_video_ws_message(data, websocket, connected_clients):
    t = data.get("type")
    if t == "video_generate":
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            await websocket.send(json.dumps({"type": "video_error", "error": "prompt vide"}))
            return
        try:
            pid = await _launch(prompt, websocket, _opts_from(data))
        except Exception as e:
            await websocket.send(json.dumps({"type": "video_error", "error": str(e)}))
            return
        await websocket.send(json.dumps({"type": "video_progress", "job_id": pid, "state": "queued"}))
        asyncio.ensure_future(_poll_until_done(pid, websocket))

    elif t == "video_status":
        pid = data.get("job_id")
        try:
            res = await asyncio.to_thread(comfy.poll_once, pid)
            await websocket.send(json.dumps({
                "type": "video_status_result", "job_id": pid,
                "state": "done" if res else "running",
                "url": res["url"] if res else None,
            }))
        except Exception as e:
            await websocket.send(json.dumps({"type": "video_error", "job_id": pid, "error": str(e)}))


# ---------------------------------------------- API pour la voix / intent layer
async def demarrer_generation_video(prompt, targets=None, **opts):
    """
    A appeler depuis le pipeline NL (ex: 'genere une video de ...').
    Renvoie une phrase courte a dire tout de suite ; la video arrive via 'video_ready'
    pousse aux 'targets' (websockets). targets = CONNECTED_CLIENTS conseille.
    """
    merged = dict(DEFAULTS)
    merged.update(opts)
    try:
        pid = await _launch(prompt.strip(), targets or [], merged)
    except Exception as e:
        return f"Impossible de lancer la generation video : {e}"
    if targets is not None:
        asyncio.ensure_future(_poll_until_done(pid, targets))
    return "Je genere la video avec Wan. Environ une minute, je te previens quand c'est pret."
