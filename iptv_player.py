"""
iptv_player.py — J.A.R.V.I.S IPTV & Video Player Backend v2
============================================================
Nouvelles fonctionnalités :
  - Serveur HTTP local (port 8766) pour streaming vidéo avec support Range
  - Transcoding AAC via ffmpeg pour les fichiers MKV/AVI/WMV (audio incompatible navigateur)
  - Détection des pistes audio via ffprobe
  - Sélection de piste audio dynamique
"""

import os
import re
import json
import asyncio
import subprocess
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
IPTV_SUPPORTED_VIDEO_EXTS   = {".mp4", ".mkv", ".avi", ".mov", ".wmv",
                                ".flv", ".webm", ".m4v", ".mpg", ".mpeg",
                                ".3gp", ".ts", ".m2ts"}
IPTV_SUPPORTED_PLAYLIST_EXTS = {".m3u", ".m3u8", ".xspf", ".pls"}

# Port du serveur HTTP vidéo local (différent du WS sur 8765)
IPTV_VIDEO_PORT = 8766

# ─── État du serveur HTTP ──────────────────────────────────────────────────
_video_server: HTTPServer | None = None
_video_server_thread: threading.Thread | None = None

# ─── Piste audio courante (par session) ───────────────────────────────────
_current_audio_track: int = 0


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe helpers
# ---------------------------------------------------------------------------

def _ffmpeg_available() -> bool:
    """Vérifie si ffmpeg est disponible dans le PATH."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def _ffprobe_available() -> bool:
    """Vérifie si ffprobe est disponible dans le PATH."""
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=3)
        return True
    except Exception:
        return False


def probe_file_info(file_path: str) -> dict:
    """
    Utilise ffprobe pour extraire les pistes audio, durée et codec vidéo.
    Retourne {"audio_tracks": [...], "duration": float, "video_codec": str, "error": str|None}
    """
    if not os.path.exists(file_path):
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": "Fichier introuvable"}

    if not _ffprobe_available():
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": "ffprobe non disponible"}

    try:
        result = subprocess.run([
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            file_path
        ], capture_output=True, text=True, timeout=10,
           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        fmt     = data.get("format", {})

        audio_tracks = []
        video_codec  = ""

        for s in streams:
            ctype = s.get("codec_type", "")
            if ctype == "audio":
                idx     = len(audio_tracks)
                lang    = s.get("tags", {}).get("language", f"piste {idx + 1}")
                codec   = s.get("codec_name", "?")
                title   = s.get("tags", {}).get("title", "")
                ch      = s.get("channels", 2)
                ch_name = {1: "Mono", 2: "Stéréo", 6: "5.1", 8: "7.1"}.get(ch, f"{ch}ch")
                label   = title or f"{lang.upper()} — {codec.upper()} {ch_name}"
                audio_tracks.append({"index": idx, "label": label,
                                     "codec": codec, "lang": lang, "channels": ch})
            elif ctype == "video" and not video_codec:
                video_codec = s.get("codec_name", "")

        duration = float(fmt.get("duration", 0))
        return {
            "audio_tracks": audio_tracks,
            "duration": duration,
            "video_codec": video_codec,
            "error": None
        }
    except Exception as e:
        print(f"[IPTV] Erreur ffprobe : {e}")
        return {"audio_tracks": [], "duration": 0, "video_codec": "", "error": str(e)}


# ---------------------------------------------------------------------------
# Serveur HTTP vidéo local
# ---------------------------------------------------------------------------

class _IPTVVideoHandler(BaseHTTPRequestHandler):
    """Handler HTTP pour servir les vidéos locales avec support Range et transcoding ffmpeg."""

    def log_message(self, fmt, *args):
        pass  # Silence les logs HTTP

    def do_OPTIONS(self):
        self.send_response(200)
        self._add_cors()
        self.end_headers()

    def _add_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range")

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == "/video":
                fpath  = urllib.parse.unquote(params.get("path", [""])[0])
                aidx   = int(params.get("audio", ["0"])[0])
                self._serve_video(fpath, aidx)
            elif parsed.path == "/probe":
                fpath = urllib.parse.unquote(params.get("path", [""])[0])
                info  = probe_file_info(fpath)
                body  = json.dumps(info).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self._add_cors()
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)
        except Exception as e:
            print(f"[IPTV-HTTP] Erreur requête : {e}")

    # ── Dispatcher ─────────────────────────────────────────────────────────
    def _serve_video(self, file_path: str, audio_idx: int = 0):
        if not file_path or not os.path.exists(file_path):
            self.send_error(404, "Fichier introuvable")
            return
        ext = os.path.splitext(file_path)[1].lower()

        # Pour les formats qui peuvent avoir des codecs audio incompatibles
        needs_transcode = ext in (".mkv", ".avi", ".wmv", ".flv", ".mov", ".mpg", ".mpeg", ".ts", ".m2ts")
        # MP4/WebM → servir directement avec support Range (seek natif)
        if not needs_transcode or not _ffmpeg_available():
            self._serve_direct(file_path)
        else:
            self._serve_ffmpeg(file_path, audio_idx)

    # ── Transcoding ffmpeg ──────────────────────────────────────────────────
    def _serve_ffmpeg(self, file_path: str, audio_idx: int = 0):
        """Stream le fichier transcoded en MP4/AAC via ffmpeg."""
        cmd = [
            "ffmpeg", "-loglevel", "quiet",
            "-i", file_path,
            "-map", "0:v:0",
            "-map", f"0:a:{audio_idx}",
            "-c:v", "copy",            # copie vidéo sans re-encoder (rapide)
            "-c:a", "aac",             # transcode audio → AAC (compatible navigateur)
            "-b:a", "192k",
            "-f", "mp4",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",
            "pipe:1"
        ]
        cf = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self._add_cors()
            self.end_headers()

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=cf
            )
            try:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        break
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()
        except Exception as e:
            print(f"[IPTV-HTTP] Erreur ffmpeg : {e}")
            # Fallback : essai direct
            try:
                self._serve_direct(file_path)
            except Exception:
                pass

    # ── Direct file serving (avec Range support pour le seek) ──────────────
    def _serve_direct(self, file_path: str):
        """Sert le fichier directement avec support des requêtes Range."""
        try:
            file_size = os.path.getsize(file_path)
            ext = os.path.splitext(file_path)[1].lower()
            ctype_map = {
                ".mp4": "video/mp4", ".m4v": "video/mp4",
                ".webm": "video/webm",
                ".mkv":  "video/x-matroska",
                ".avi":  "video/avi",
                ".mov":  "video/quicktime",
                ".ts":   "video/mp2t",
            }
            ctype = ctype_map.get(ext, "application/octet-stream")

            range_hdr = self.headers.get("Range", "")
            if range_hdr:
                m = re.match(r"bytes=(\d+)-(\d*)", range_hdr)
                if m:
                    start = int(m.group(1))
                    end   = int(m.group(2)) if m.group(2) else file_size - 1
                    end   = min(end, file_size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self._add_cors()
                    self.end_headers()
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            data = f.read(min(65536, remaining))
                            if not data:
                                break
                            try:
                                self.wfile.write(data)
                            except (BrokenPipeError, OSError):
                                break
                            remaining -= len(data)
                    return

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self._add_cors()
            self.end_headers()
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(65536)
                    if not data:
                        break
                    try:
                        self.wfile.write(data)
                    except (BrokenPipeError, OSError):
                        break
        except Exception as e:
            print(f"[IPTV-HTTP] Erreur serve_direct : {e}")


# ---------------------------------------------------------------------------
# Démarrage / arrêt du serveur HTTP
# ---------------------------------------------------------------------------

def start_video_server() -> bool:
    """Lance le serveur HTTP vidéo sur IPTV_VIDEO_PORT (idempotent)."""
    global _video_server, _video_server_thread
    if _video_server is not None:
        return True
    try:
        _video_server = HTTPServer(("127.0.0.1", IPTV_VIDEO_PORT), _IPTVVideoHandler)
        _video_server_thread = threading.Thread(
            target=_video_server.serve_forever,
            daemon=True,
            name="IPTV-HTTP-Server"
        )
        _video_server_thread.start()
        print(f"[IPTV] Serveur HTTP vidéo démarré sur http://127.0.0.1:{IPTV_VIDEO_PORT}")
        return True
    except Exception as e:
        print(f"[IPTV] Erreur démarrage serveur HTTP : {e}")
        _video_server = None
        return False


def stop_video_server():
    """Arrête le serveur HTTP vidéo."""
    global _video_server, _video_server_thread
    if _video_server:
        _video_server.shutdown()
        _video_server = None
        _video_server_thread = None
        print("[IPTV] Serveur HTTP vidéo arrêté.")


# Démarrage automatique à l'import du module
start_video_server()


# ---------------------------------------------------------------------------
# Parsing M3U / M3U8
# ---------------------------------------------------------------------------

def _parse_m3u_content(content: str) -> list:
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            meta = line[len("#EXTINF:"):]
            name, logo, group = "", "", ""
            if "," in meta:
                attrs_part, name = meta.rsplit(",", 1)
                name = name.strip()
            else:
                attrs_part = meta
            logo_m  = re.search(r'tvg-logo="([^"]*)"',   attrs_part)
            tvgn_m  = re.search(r'tvg-name="([^"]*)"',   attrs_part)
            group_m = re.search(r'group-title="([^"]*)"', attrs_part)
            if logo_m:  logo  = logo_m.group(1)
            if tvgn_m and not name: name = tvgn_m.group(1)
            if group_m: group = group_m.group(1)
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
                i += 1
            if i < len(lines):
                url = lines[i].strip()
                if url:
                    channels.append({"name": name or url, "url": url, "logo": logo, "group": group})
        i += 1
    return channels


def _parse_xspf_content(content: str) -> list:
    channels = []
    try:
        root = ET.fromstring(content)
        ns = {"xspf": "http://xspf.org/ns/0/"}
        tracklist = root.find("xspf:trackList", ns) or root.find("trackList")
        if tracklist is None:
            return channels
        for track in tracklist:
            loc   = track.find("{http://xspf.org/ns/0/}location") or track.find("location")
            title = track.find("{http://xspf.org/ns/0/}title")   or track.find("title")
            img   = track.find("{http://xspf.org/ns/0/}image")   or track.find("image")
            url   = loc.text.strip()   if loc   is not None and loc.text   else ""
            name  = title.text.strip() if title is not None and title.text else url
            logo  = img.text.strip()   if img   is not None and img.text   else ""
            if url:
                channels.append({"name": name, "url": url, "logo": logo, "group": ""})
    except Exception as e:
        print(f"[IPTV] Erreur parsing XSPF : {e}")
    return channels


def _parse_pls_content(content: str) -> list:
    channels = []
    files, titles = {}, {}
    for line in content.splitlines():
        fm = re.match(r'^File(\d+)=(.+)$', line.strip(), re.IGNORECASE)
        tm = re.match(r'^Title(\d+)=(.+)$', line.strip(), re.IGNORECASE)
        if fm: files[fm.group(1)]  = fm.group(2).strip()
        if tm: titles[tm.group(1)] = tm.group(2).strip()
    for idx, url in files.items():
        channels.append({"name": titles.get(idx, url), "url": url, "logo": "", "group": ""})
    return channels


def parse_playlist_file(file_path: str) -> dict:
    try:
        if not os.path.exists(file_path):
            return {"success": False, "channels": [], "error": "Fichier introuvable"}
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        if ext in (".m3u", ".m3u8"):
            channels = _parse_m3u_content(content)
        elif ext == ".xspf":
            channels = _parse_xspf_content(content)
        elif ext == ".pls":
            channels = _parse_pls_content(content)
        else:
            return {"success": False, "channels": [], "error": f"Format non supporté : {ext}"}
        print(f"[IPTV] Playlist parsée : {len(channels)} chaîne(s)")
        return {"success": True, "channels": channels, "error": None}
    except Exception as e:
        return {"success": False, "channels": [], "error": str(e)}


def parse_playlist_url(url: str) -> dict:
    try:
        import requests
        resp = requests.get(url, headers={"User-Agent": "JARVIS/8.0"}, timeout=15)
        resp.raise_for_status()
        content = resp.text
        content_lower = content.strip().lower()
        url_lower = url.lower().split("?")[0]
        if "#extm3u" in content_lower[:1000] or "#extinf" in content_lower or url_lower.endswith(".m3u") or url_lower.endswith(".m3u8"):
            channels = _parse_m3u_content(content)
        elif "<tracklist" in content_lower or "xspf" in content_lower[:500]:
            channels = _parse_xspf_content(content)
        elif "[playlist]" in content_lower[:200]:
            channels = _parse_pls_content(content)
        else:
            channels = _parse_m3u_content(content)
        return {"success": True, "channels": channels, "error": None}
    except Exception as e:
        return {"success": False, "channels": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Détection du type de stream
# ---------------------------------------------------------------------------

def detect_stream_type(url: str) -> str:
    u = url.lower().split("?")[0]
    if u.endswith(".m3u8") or "m3u8" in u: return "hls"
    if u.endswith(".mpd"):                  return "dash"
    if any(u.endswith(e) for e in (".mp4", ".m4v", ".webm")): return "mp4"
    if u.startswith("rtsp://") or u.startswith("rtmp://"):     return "rtsp"
    return "direct"


def get_video_stream_url(file_path: str, audio_track: int = 0) -> str:
    """Retourne l'URL HTTP locale pour streamer le fichier vidéo."""
    encoded = urllib.parse.quote(file_path, safe="")
    return f"http://127.0.0.1:{IPTV_VIDEO_PORT}/video?path={encoded}&audio={audio_track}"


# ---------------------------------------------------------------------------
# WebSocket Message Handler
# ---------------------------------------------------------------------------

async def handle_iptv_ws_message(data: dict, websocket, connected_clients: set) -> bool:
    global _current_audio_track
    msg_type = data.get("type", "")

    # ── Ouvrir le panneau ─────────────────────────────────────────────────
    if msg_type == "iptv_open":
        await _broadcast(connected_clients, {"type": "iptv_open"})
        return True

    # ── Parser une playlist locale ────────────────────────────────────────
    if msg_type == "iptv_parse_m3u":
        file_path = data.get("path", "")
        if not file_path:
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "Chemin manquant"}))
            return True
        result = await asyncio.to_thread(parse_playlist_file, file_path)
        await websocket.send(json.dumps({
            "type": "iptv_playlist",
            "success": result["success"],
            "channels": result["channels"],
            "source_path": file_path,
            "source_name": os.path.basename(file_path),
            "stream_type": detect_stream_type(file_path),
            "error": result.get("error")
        }))
        return True

    # ── Parser une playlist depuis une URL ────────────────────────────────
    if msg_type == "iptv_parse_url":
        url = data.get("url", "")
        if not url:
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "URL manquante"}))
            return True
        
        # Tentative de parsing en tant que playlist d'abord
        result = await asyncio.to_thread(parse_playlist_url, url)
        if result["success"] and len(result["channels"]) > 0:
            await websocket.send(json.dumps({
                "type": "iptv_playlist",
                "success": True,
                "channels": result["channels"],
                "source_path": url,
                "source_name": url.split("/")[-1].split("?")[0] or "Playlist IPTV",
                "stream_type": detect_stream_type(url),
                "error": None
            }))
        elif result.get("error"):
            # L'URL n'a pas pu etre lue du tout (hote injoignable, 404,
            # delai depasse...). Ce n'est PAS un flux direct.
            #
            # Avant, ce cas tombait dans le repli ci-dessous : une URL morte
            # etait annoncee comme un flux direct valide, en deux secondes,
            # sans que personne ne l'ait jamais contactee avec succes.
            # L'utilisateur ne decouvrait le probleme qu'au moment ou la
            # lecture echouait, sans savoir pourquoi. L'erreur reelle etait
            # dans result["error"] et partait a la poubelle.
            await websocket.send(json.dumps({
                "type": "iptv_playlist_error",
                "error": "URL illisible : %s" % result["error"],
            }))
        else:
            # Repli en flux direct : l'URL a bien repondu, mais son contenu
            # n'est pas une playlist. Un vrai flux, donc.
            await websocket.send(json.dumps({
                "type": "iptv_direct_stream",
                "url": url,
                "stream_type": detect_stream_type(url),
                "name": url.split("/")[-1].split("?")[0] or "Stream direct"
            }))
        return True

    # ── Ouvrir un fichier vidéo ou playlist locale ────────────────────────
    if msg_type == "iptv_open_file":
        file_path = data.get("path", "")
        if not file_path:
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "Chemin manquant"}))
            return True
        ext = os.path.splitext(file_path)[1].lower()

        if ext in IPTV_SUPPORTED_PLAYLIST_EXTS:
            result = await asyncio.to_thread(parse_playlist_file, file_path)
            await websocket.send(json.dumps({
                "type": "iptv_playlist",
                "success": result["success"],
                "channels": result["channels"],
                "source_path": file_path,
                "source_name": os.path.basename(file_path),
                "stream_type": "m3u",
                "error": result.get("error")
            }))
        elif ext in IPTV_SUPPORTED_VIDEO_EXTS:
            _current_audio_track = 0
            stream_url = get_video_stream_url(file_path, 0)

            # Probe des pistes audio en arrière-plan
            file_info = await asyncio.to_thread(probe_file_info, file_path)

            await websocket.send(json.dumps({
                "type": "iptv_stream_ready",
                "url": stream_url,
                "stream_type": "mp4",  # ffmpeg output est toujours mp4
                "name": os.path.basename(file_path),
                "local_path": file_path,
                "audio_tracks": file_info.get("audio_tracks", []),
                "video_codec": file_info.get("video_codec", ""),
                "ffmpeg_available": _ffmpeg_available(),
                "duration": file_info.get("duration", 0)
            }))
        else:
            await websocket.send(json.dumps({
                "type": "iptv_playlist_error",
                "error": f"Format non supporté : {ext}"
            }))
        return True

    # ── Changer la piste audio ────────────────────────────────────────────
    if msg_type == "iptv_set_audio_track":
        file_path   = data.get("path", "")
        audio_track = int(data.get("audio_track", 0))
        _current_audio_track = audio_track

        if not file_path or not os.path.exists(file_path):
            await websocket.send(json.dumps({"type": "iptv_playlist_error", "error": "Fichier introuvable"}))
            return True

        stream_url = get_video_stream_url(file_path, audio_track)
        await websocket.send(json.dumps({
            "type": "iptv_stream_ready",
            "url": stream_url,
            "stream_type": "mp4",
            "name": os.path.basename(file_path),
            "local_path": file_path,
            "audio_track_changed": True,
            "audio_track": audio_track
        }))
        return True

    return False


async def _broadcast(clients: set, message: dict):
    if not clients:
        return
    msg = json.dumps(message)
    try:
        await asyncio.gather(*[c.send(msg) for c in clients], return_exceptions=True)
    except Exception as e:
        print(f"[IPTV] Erreur broadcast : {e}")
