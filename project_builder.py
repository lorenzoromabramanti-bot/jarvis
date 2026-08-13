import time
import threading
import os
import re
from developer_gui import JarvisDeveloperGUI
from dotenv import load_dotenv

# Charge les clés API (depuis .env ou l'environnement)
load_dotenv()

# Tente de charger les clients IA
api_gemini = os.environ.get("GEMINI_API_KEY")
api_anthropic = os.environ.get("ANTHROPIC_API_KEY")
api_grok = os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY")
api_openai = os.environ.get("OPENAI_API_KEY")


class ProjectBuilder:
    """
    Orchestrateur RÉEL de développement autonome.
    Génère du code via Gemini et l'écrit physiquement dans le dossier sélectionné.
    """
    def __init__(self, gui: JarvisDeveloperGUI):
        self.gui = gui
        self.project_path = None
        self.project_name = None
        self.run_id = None
        # Historique de conversation en session (multi-turn)
        # Format universel : [{"role": "user"|"assistant", "content": str}]
        self.conversation_history = []
        self._MAX_HISTORY = 20  # Limite aux 20 derniers échanges pour éviter la saturation de tokens

    def cancel_generation(self):
        self.run_id = None
        # Rendre l'UI immédiatement disponible
        if hasattr(self.gui, 'stop_button'): self.gui.stop_button.configure(state="disabled")
        if hasattr(self.gui, 'chat_input'): self.gui.chat_input.configure(state="normal")
        if hasattr(self.gui, 'send_button'): self.gui.send_button.configure(state="normal")
        self.gui.update_status("Annulé", color="#e74c3c", loading=False)

    def start_project(self, project_name, project_path):
        """Définit le dossier de travail."""
        self.project_path = project_path
        self.project_name = project_name
        self.gui.set_project_path(project_path)
        self.gui.show_dev_panel()
        self.gui.update_status(f"Dossier Prêt : {project_name}", color="#f39c12")
        self.gui.log_to_terminal(f"=== Dossier défini sur {project_path} ===")
        self.gui.log_to_terminal("En attente de vos instructions...")

    def load_existing_project(self, folder_path):
        """Ouvre un projet existant et peuple l'interface."""
        project_name = os.path.basename(folder_path)
        self.project_path = folder_path
        self.project_name = project_name
        
        self.gui.set_project_path(folder_path)
        self.gui.show_dev_panel()
        self.gui.update_status(f"Projet chargé : {project_name}", color="#2ecc71")
        self.gui.log_to_terminal(f"=== Ouverture du projet {folder_path} ===")
        
        # Scan du dossier pour construire l'arbre
        structure = self._scan_directory(folder_path)
        self.gui.update_file_tree(structure)
        
        # Tenter d'ouvrir index.html ou un fichier python/js en premier
        first_file = None
        for root, dirs, files in os.walk(folder_path):
            if '.git' in dirs: dirs.remove('.git')
            if 'node_modules' in dirs: dirs.remove('node_modules')
            if 'venv' in dirs: dirs.remove('venv')
            for f in files:
                if f.endswith('.html') or f.endswith('.py') or f.endswith('.js'):
                    first_file = os.path.relpath(os.path.join(root, f), folder_path).replace("\\", "/")
                    break
            if first_file: break
            
        if first_file:
            try:
                with open(os.path.join(folder_path, first_file), 'r', encoding='utf-8') as file:
                    content = file.read()
                    self.gui.update_code_viewer(first_file, content)
            except Exception as e:
                pass

    def _scan_directory(self, path, root_path=None):
        if root_path is None:
            root_path = path
        structure = {}
        try:
            for item in os.listdir(path):
                if item in ['.git', '__pycache__', 'venv', 'node_modules', '.env']:
                    continue
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path):
                    structure[item] = self._scan_directory(full_path, root_path)
                else:
                    structure[item] = "file"
        except Exception as e:
            pass
        return structure

    def handle_message(self, message, image_path=None):
        """Reçoit le message de l'utilisateur depuis l'interface."""
        if not self.project_path:
            self.gui.log_chat("Veuillez d'abord cliquer sur 'Créer Projet...' pour choisir un dossier.", sender="Système")
            return
            
        self.gui.log_chat("Analyse de votre demande en cours...", sender="Jarvis")
        
        # Désactiver UI
        if hasattr(self.gui, 'chat_input'): self.gui.chat_input.configure(state="disabled")
        if hasattr(self.gui, 'send_button'): self.gui.send_button.configure(state="disabled")
        
        # Ajouter le message utilisateur à l'historique de conversation
        self.conversation_history.append({"role": "user", "content": message})
        # Limiter la taille de l'historique
        if len(self.conversation_history) > self._MAX_HISTORY * 2:
            self.conversation_history = self.conversation_history[-(self._MAX_HISTORY * 2):]
        
        # Nouveau run_id
        import uuid
        self.run_id = uuid.uuid4().hex
        
        # On lance la génération dans un thread pour ne pas bloquer l'UI
        threading.Thread(target=self._generate_code_loop, args=(message, image_path, self.run_id), daemon=True).start()

    def _build_context(self):
        """Récupère le contenu des fichiers existants pour donner le contexte à l'IA."""
        context = ""
        if not self.project_path or not os.path.exists(self.project_path):
            return context
            
        files_found = []
        file_count = 0
        for root, dirs, files in os.walk(self.project_path):
            if '.git' in dirs: dirs.remove('.git')
            if 'node_modules' in dirs: dirs.remove('node_modules')
            if 'venv' in dirs: dirs.remove('venv')
            for file in files:
                if file_count >= 15: # On limite à 15 fichiers
                    break
                if file.endswith(('.html', '.css', '.js', '.py', '.json', '.txt')):
                    full_path = os.path.join(root, file)
                    # Ignore les fichiers trop gros (ex: > 100KB)
                    if os.path.getsize(full_path) > 100000:
                        continue
                    rel_path = os.path.relpath(full_path, self.project_path).replace("\\", "/")
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        files_found.append(f"--- Fichier existant : {rel_path} ---\n{content}\n")
                        file_count += 1
                    except:
                        pass
                        
        if files_found:
            context += "\nVoici l'état ACTUEL des fichiers du projet. Utilise ce contexte pour appliquer la demande de l'utilisateur. Tu DOIS toujours réécrire les fichiers complets avec tes modifications.\n"
            context += "\n".join(files_found)
        return context

    def _build_memory_context(self):
        """Charge et retourne le contexte de la mémoire persistante (jarvis_memoire.json)."""
        try:
            from memory_manager import construire_contexte_memoire
            return construire_contexte_memoire()
        except Exception as e:
            print(f"[DEV-MEMORY] Erreur chargement mémoire : {e}")
            return ""

    def _save_exchange_to_memory(self, user_text, model_text):
        """Sauvegarde l'échange dans jarvis_conversations.json ET dans ObsidianVault/Journal_Discussions.md."""
        try:
            from memory_manager import _sauvegarder_echange_conv
            _sauvegarder_echange_conv(user_text, model_text)
        except Exception as e:
            print(f"[DEV-MEMORY] Erreur sauvegarde échange : {e}")

    def _generate_code_loop(self, prompt, image_path=None, my_run_id=None):
        self.gui.update_status("Génération IA...", color="#3498db", loading=True)
        selected_model_name = self.gui.model_var.get()
        selected_image_model = self.gui.image_model_var.get()
        self.gui.log_to_terminal(f"> Demande à l'IA ({selected_model_name}) : {prompt}")
        
        if self.run_id != my_run_id:
            raise Exception("Annulé par l'utilisateur")
            
        base64_image = None
        mime_type = "image/jpeg"
        if image_path and os.path.exists(image_path):
            import base64
            import mimetypes
            try:
                with open(image_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode("utf-8")
                mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
                self.gui.log_to_terminal(f"> Image jointe détectée : {os.path.basename(image_path)}")
            except Exception as e:
                self.gui.log_to_terminal(f"> Erreur lecture image : {e}")
        
        # === MÉMOIRE OBSIDIAN : Chargement du contexte persistant ===
        mem_context = self._build_memory_context()
        mem_section = ""
        if mem_context:
            mem_section = f"\n\nMÉMOIRE PERSONNELLE (informations persistantes sur l'utilisateur) :\n{mem_context}\n"
        
        system_prompt = """Tu es Jarvis, un développeur IA expert et architecte logiciel. L'utilisateur veut créer un projet logiciel (web, mobile, script Python, jeu, etc.).
Tu te souviens de TOUTE la conversation depuis le début de la session. Utilise le contexte des messages précédents pour comprendre les modifications demandées.
Génère UNIQUEMENT le code des fichiers nécessaires sous ce format exact et strict, sans aucun blabla avant ou après :

---BEGIN_FILE: nom_du_fichier.ext---
[code complet du fichier ici]
---END_FILE---

Tu peux générer autant de fichiers que nécessaire (ex: main.py, app.js, index.html, pubspec.yaml).
Pour un site web simple, privilégie un seul fichier index.html. Pour une application ou un projet complexe, sépare correctement les fichiers selon les bonnes pratiques du langage demandé.
Sois professionnel, génère un code complet et fonctionnel. N'utilise pas les balises markdown ``` pour entourer le texte des fichiers.

IMPORTANT POUR LES ASSETS/IMAGES :
Si ton code a besoin de charger des images dynamiques, des logos ou des photos, tu DOIS utiliser ce tag spécial à l'endroit exact où le chemin du fichier est attendu :
[GENERATE_IMAGE: description ultra détaillée en anglais]
Exemples selon le langage :
HTML : <img src="[GENERATE_IMAGE: A cute cat, 4k, photorealistic]" alt="Cat">
Python (Tkinter/Pygame) : image_path = "[GENERATE_IMAGE: A futuristic city skyline]"
React : <Image source={{uri: '[GENERATE_IMAGE: App logo icon, minimalist]'}} />

Jarvis générera l'image en arrière-plan et remplacera ton tag uniquement par le chemin relatif du fichier image (ex: 'assets/img_1.jpg'). N'invente pas d'URLs internet ou de fichiers locaux qui n'existent pas.

IMPORTANT POUR LES VIDÉOS :
Si ton code a besoin d'une vidéo générée (fond animé, clip de démonstration, etc.), utilise ce tag :
[GENERATE_VIDEO: description ultra détaillée en anglais]
Exemple : HTML : <video src="[GENERATE_VIDEO: drone shot flying over a futuristic city at sunset]"></video>
ATTENTION : la génération vidéo est locale (ComfyUI, gratuite) mais LENTE (15-20 minutes par vidéo). N'utilise ce tag QUE si l'utilisateur demande explicitement une vidéo — jamais par défaut pour un simple visuel (utilise [GENERATE_IMAGE: ...] dans ce cas).

RÈGLE ABSOLUE POUR LES MODIFICATIONS DE CODE :
Si le code existant que l'utilisateur te fournit contient DÉJÀ des chemins d'images locales (ex: "assets/img_retro_pixel.jpg"), TU DOIS IMPÉRATIVEMENT LES CONSERVER TELS QUELS ! Ne les remplace SURTOUT PAS par un nouveau tag [GENERATE_IMAGE: ...] sauf si l'utilisateur te demande explicitement de changer le design ou les images. Si tu corriges un simple bug, laisse les chemins d'images intacts !"""

        # Injection de la mémoire persistante dans le prompt système
        if mem_section:
            system_prompt += mem_section
        self.gui.log_to_terminal("> Étape 1/4 : Analyse de vos fichiers existants...")
        existing_context = self._build_context()
        
        # ETAPE 1 : Amélioration du prompt (Optionnelle)
        is_new_project = not bool(existing_context)
        
        # Vérifie l'état de la checkbox "Prompt Auto"
        enrich_enabled = getattr(self.gui, 'enrich_prompt_var', None)
        if enrich_enabled is not None and not enrich_enabled.get():
            self.gui.log_to_terminal("> Étape 2/4 : Prompt brut envoyé (sans enrichissement auto).")
            if is_new_project:
                full_user_prompt = f"Demande de l'utilisateur :\n{prompt}"
            else:
                full_user_prompt = f"{existing_context}\n\nDemande de l'utilisateur (à appliquer ABSOLUMENT au code) :\n{prompt}"
        else:
            if is_new_project:
                self.gui.log_to_terminal("> Étape 2/4 : Amélioration de votre prompt (Création)...")
                enhanced_prompt = self._enhance_prompt(prompt, is_new=True, base64_image=base64_image, mime_type=mime_type, selected_model_name=selected_model_name)
                
                if enhanced_prompt and enhanced_prompt.strip():
                    full_user_prompt = f"Demande de l'utilisateur enrichie :\n{enhanced_prompt}"
                else:
                    self.gui.log_to_terminal("> (Avertissement) L'IA a renvoyé un prompt vide. Utilisation de votre demande brute.")
                    full_user_prompt = f"Demande de l'utilisateur :\n{prompt}"
            else:
                self.gui.log_to_terminal("> Étape 2/4 : Analyse de votre demande de modification...")
                # On passe l'historique de conversation pour que l'IA sache de quel projet on parle
                enhanced_prompt = self._enhance_prompt(prompt, is_new=False, base64_image=base64_image, mime_type=mime_type, selected_model_name=selected_model_name, conv_history=self.conversation_history)
                
                if enhanced_prompt and enhanced_prompt.strip():
                    full_user_prompt = f"{existing_context}\n\nDemande de l'utilisateur enrichie (à appliquer ABSOLUMENT au code) :\n{enhanced_prompt}"
                else:
                    self.gui.log_to_terminal("> (Avertissement) L'IA a renvoyé un prompt vide. Utilisation de votre demande brute.")
                    full_user_prompt = f"{existing_context}\n\nDemande de l'utilisateur (à appliquer ABSOLUMENT au code) :\n{prompt}"
        
        if self.run_id != my_run_id: raise Exception("Annulé par l'utilisateur")
        self.gui.log_to_terminal("> Étape 3/4 : Génération du code complet (cela prend généralement 30 à 60 secondes)...")
        self.gui.update_status("Création du code...", color="#3498db", loading=True)
        
        # === CONSTRUCTION DE L'HISTORIQUE MULTI-TURN ===
        # On récupère tout l'historique SAUF le dernier message user (déjà dans full_user_prompt)
        history_for_ai = self.conversation_history[:-1]  # Exclure le dernier (message actuel)
        
        try:
            raw_text = ""
            if "Gemini" in selected_model_name:
                import google.genai as genai
                if not api_gemini: raise Exception("GEMINI_API_KEY manquante.")
                client = genai.Client(api_key=api_gemini)
                model_id = "gemini-2.5-flash"
                if "3.5 Flash" in selected_model_name: model_id = "gemini-3.5-flash"
                elif "3.1 Pro" in selected_model_name: model_id = "gemini-3.1-pro-preview"
                elif "Pro" in selected_model_name: model_id = "gemini-2.5-pro"
                elif "1.5 Pro" in selected_model_name: model_id = "gemini-1.5-pro"
                
                # Construction des contents Gemini avec historique multi-turn
                contents = []
                # Injecter le system_prompt comme premier message user/model si historique vide
                if not history_for_ai:
                    contents.append({"role": "user", "parts": [{"text": system_prompt}]})
                    contents.append({"role": "model", "parts": [{"text": "Compris. Je suis prêt à générer votre projet."}]})
                else:
                    # Injecter system dans le premier message de l'historique
                    first_user = history_for_ai[0]
                    contents.append({"role": "user", "parts": [{"text": system_prompt + "\n\nPremier échange :\n" + first_user["content"]}]})
                    # Ajouter le reste de l'historique
                    for h in history_for_ai[1:]:
                        gemini_role = "model" if h["role"] == "assistant" else "user"
                        contents.append({"role": gemini_role, "parts": [{"text": h["content"]}]})
                
                # Message actuel
                current_parts = [{"text": full_user_prompt}]
                if base64_image:
                    current_parts.append({"inlineData": {"mimeType": mime_type, "data": base64_image}})
                contents.append({"role": "user", "parts": current_parts})
                
                response = client.models.generate_content(
                    model=model_id,
                    contents=contents
                )
                raw_text = response.text
                
            elif "Claude" in selected_model_name:
                import anthropic
                if not api_anthropic: raise Exception("ANTHROPIC_API_KEY manquante.")
                client = anthropic.Anthropic(api_key=api_anthropic)
                model_id = "claude-sonnet-5"
                if "Fable" in selected_model_name: model_id = "claude-fable-5"
                elif "Opus" in selected_model_name: model_id = "claude-opus-4-8"
                
                # Construction des messages Claude avec historique multi-turn
                claude_messages = []
                for h in history_for_ai:
                    claude_role = "assistant" if h["role"] == "assistant" else "user"
                    claude_messages.append({"role": claude_role, "content": h["content"]})
                
                # Message actuel (avec image éventuelle)
                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_image}}
                    ]
                claude_messages.append({"role": "user", "content": msg_content})
                
                response = client.messages.create(
                    model=model_id,
                    max_tokens=4000,
                    system=system_prompt,
                    messages=claude_messages
                )
                raw_text = response.content[0].text
                
            elif "Grok" in selected_model_name:
                import openai
                if not api_grok: raise Exception("XAI_API_KEY manquante.")
                client = openai.OpenAI(api_key=api_grok, base_url="https://api.x.ai/v1")
                model_id = "grok-4.5"
                if "4.20" in selected_model_name: model_id = "grok-4.20-0309-reasoning"
                
                # Construction des messages Grok (OpenAI-compatible) avec historique multi-turn
                grok_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    grok_messages.append({"role": h["role"], "content": h["content"]})
                
                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                grok_messages.append({"role": "user", "content": msg_content})
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=grok_messages
                )
                raw_text = response.choices[0].message.content

            elif "Omniroute" in selected_model_name:
                import openai
                api_omniroute = os.environ.get("EXTRA_LLM_1_KEY")
                if not api_omniroute: raise Exception("EXTRA_LLM_1_KEY manquante (Omniroute).")
                client = openai.OpenAI(api_key=api_omniroute, base_url=os.environ.get("EXTRA_LLM_1_URL", "http://localhost:20128/v1"))
                model_id = os.environ.get("EXTRA_LLM_1_MODEL", "freellm/mistral-large-3")

                omni_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    omni_messages.append({"role": h["role"], "content": h["content"]})

                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                omni_messages.append({"role": "user", "content": msg_content})

                response = client.chat.completions.create(
                    model=model_id,
                    messages=omni_messages
                )
                raw_text = response.choices[0].message.content

            elif "ChatGPT" in selected_model_name:
                import openai
                if not api_openai: raise Exception("OPENAI_API_KEY manquante.")
                client = openai.OpenAI(api_key=api_openai)
                
                model_id = "gpt-4o"
                if "(" in selected_model_name and ")" in selected_model_name:
                    model_id = selected_model_name.split("(")[1].split(")")[0]
                
                # IMPORTANT : Pour les modèles de raisonnement (o1, luna, etc.) qui ignorent le rôle "system",
                # on injecte de force les instructions de formatage dans le prompt utilisateur.
                # Construction de l'historique multi-turn pour ChatGPT/OpenAI
                openai_messages = []
                # Injecter system_prompt dans le premier message utilisateur
                if not history_for_ai:
                    combined_first = f"{system_prompt}\n\n{full_user_prompt}"
                    if base64_image:
                        msg_content = [
                            {"type": "text", "text": combined_first},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                        ]
                    else:
                        msg_content = combined_first
                    openai_messages.append({"role": "user", "content": msg_content})
                else:
                    # Premier message de l'historique : injecter system_prompt dedans
                    first_h = history_for_ai[0]
                    openai_messages.append({"role": "user", "content": f"{system_prompt}\n\n{first_h['content']}"})
                    for h in history_for_ai[1:]:
                        openai_messages.append({"role": h["role"], "content": h["content"]})
                    # Message actuel
                    msg_content = full_user_prompt
                    if base64_image:
                        msg_content = [
                            {"type": "text", "text": full_user_prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                        ]
                    openai_messages.append({"role": "user", "content": msg_content})
                
                try:
                    response = client.chat.completions.create(
                        model=model_id,
                        messages=openai_messages,
                        max_completion_tokens=8000
                    )
                    raw_text = response.choices[0].message.content
                except Exception as e1:
                    try:
                        response = client.chat.completions.create(
                            model=model_id,
                            messages=openai_messages,
                            max_tokens=8000
                        )
                        raw_text = response.choices[0].message.content
                    except Exception as e2:
                        try:
                            combined_prompt = f"{system_prompt}\n\n{full_user_prompt}"
                            response = client.completions.create(
                                model=model_id,
                                prompt=combined_prompt,
                                max_tokens=8000
                            )
                            raw_text = response.choices[0].text
                        except Exception:
                            raise e1
                
            elif "Mistral" in selected_model_name or "Codestral" in selected_model_name:
                import openai
                api_mistral = os.environ.get("MISTRAL_API_KEY")
                if not api_mistral: raise Exception("MISTRAL_API_KEY manquante.")
                client = openai.OpenAI(api_key=api_mistral, base_url="https://api.mistral.ai/v1")
                model_id = "mistral-large-latest"
                if "Codestral" in selected_model_name: model_id = "codestral-latest"
                
                # Construction des messages Mistral (OpenAI-compatible) avec historique multi-turn
                mistral_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    mistral_messages.append({"role": h["role"], "content": h["content"]})
                
                msg_content = full_user_prompt
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": full_user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                mistral_messages.append({"role": "user", "content": msg_content})
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=mistral_messages
                )
                raw_text = response.choices[0].message.content
                
            elif "(Local)" in selected_model_name:
                from local_agent_manager import JarvisLocalAgentManager
                
                ollama_tags = {
                    "Ornith-1.0 (Local)": "ornith:9b",
                    "Ornith-35b (Local)": "ornith:35b",
                    "Qwen2.5-Coder (Local)": "qwen2.5-coder:7b",
                    "DeepSeek-Coder (Local)": "deepseek-coder-v2"
                }
                target_model = ollama_tags.get(selected_model_name, "ornith:9b")
                
                agent = JarvisLocalAgentManager(model_name=target_model)
                
                is_ready, status = agent.check_system()
                if not is_ready:
                    self.gui.log_to_terminal("=== ERREUR AGENT LOCAL ===")
                    if status == "OLLAMA_NOT_RUNNING":
                        self.gui.log_to_terminal("❌ Ollama n'est pas lancé sur cette machine.")
                    else:
                        self.gui.log_to_terminal(f"❌ Le modèle '{agent.model}' n'est pas téléchargé.")
                        
                    self.gui.log_to_terminal("\n💡 GUIDE D'INSTALLATION :")
                    self.gui.log_to_terminal("1. Allez sur https://ollama.com et téléchargez Ollama.")
                    self.gui.log_to_terminal("2. Lancez l'application Ollama en arrière-plan.")
                    self.gui.log_to_terminal(f"3. Ouvrez un terminal Windows et tapez : ollama pull {agent.model}")
                    self.gui.log_to_terminal("4. Relancez ensuite cette requête dans JARVIS.")
                    self.gui.log_to_terminal("="*50)
                    raise Exception(f"Agent local indisponible ({status}).")
                
                if base64_image:
                    self.gui.log_to_terminal("> Attention: L'agent local (texte) ignore les images pour l'instant.")
                
                # Construction des messages Ollama avec historique multi-turn
                local_messages = [{"role": "system", "content": system_prompt}]
                for h in history_for_ai:
                    local_messages.append({"role": h["role"], "content": h["content"]})
                local_messages.append({"role": "user", "content": full_user_prompt})
                
                response_text = agent.generate_response(local_messages, strip_thinking=True)
                if response_text:
                    raw_text = response_text
                else:
                    raise Exception("L'agent local n'a renvoyé aucune réponse.")
                
            self.gui.log_to_terminal(f"> Code reçu de {selected_model_name} !")
            self.gui.update_status("Écriture...", color="#9b59b6")
            
            # ETAPE 2.5 : Traitement et génération des images natives
            self.gui.log_to_terminal("> Étape 4/4 : Traitement des images natives...")
            raw_text = self._process_images(raw_text, selected_model_name, selected_image_model, my_run_id)

            if self.run_id != my_run_id: raise Exception("Annulé par l'utilisateur")

            # ETAPE 2.6 : Traitement et génération des vidéos natives (ComfyUI local)
            raw_text = self._process_videos(raw_text, my_run_id)

            if self.run_id != my_run_id: raise Exception("Annulé par l'utilisateur")
            
            # Sauvegarder dans des fichiers
            self._parse_and_save_files(raw_text)
            
            # === MÉMOIRE OBSIDIAN : Sauvegarde de l'échange dans Journal_Discussions.md ===
            # Résumé de la réponse IA (limité pour le journal)
            _response_summary = raw_text[:1500] if raw_text else "(code généré)"
            self._save_exchange_to_memory(prompt, _response_summary)
            self.gui.log_to_terminal("> [Mémoire] Échange sauvegardé dans Obsidian (Journal_Discussions.md).")
            
            # === HISTORIQUE : Ajouter la réponse IA à l'historique de conversation ===
            # On stocke un résumé utile pour que les prochains messages aient du contexte
            self.conversation_history.append({"role": "assistant", "content": f"J'ai traité la demande '{prompt[:200]}' et généré le code correspondant dans le projet '{self.project_name}'."})
            
            self.gui.update_status("Terminé", color="#2ecc71", loading=False)
            self.gui.log_to_terminal("=== Projet généré avec succès ===")
            self.gui.log_chat("C'est fait ! J'ai généré votre projet dans le dossier. Vous pouvez cliquer sur 'Ouvrir Dossier' ou 'Ouvrir dans VS Code'.", sender="Jarvis")
            
        except Exception as e:
            if "Annulé par l'utilisateur" in str(e):
                self.gui.log_to_terminal("[STOP] : Génération annulée par l'utilisateur.")
                self.gui.update_status("Annulé", color="#e74c3c", loading=False)
                # Retirer le dernier message user de l'historique (annulé)
                if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                    self.conversation_history.pop()
            else:
                self.gui.log_to_terminal(f"[ERREUR API] : {str(e)}")
                self.gui.update_status("Erreur API", color="red", loading=False)
                self.gui.log_chat(f"Une erreur est survenue : {str(e)}\n(Consultez le terminal pour plus de détails)", sender="Jarvis")
                # Retirer le dernier message user de l'historique (erreur)
                if self.conversation_history and self.conversation_history[-1]["role"] == "user":
                    self.conversation_history.pop()
        finally:
            if hasattr(self.gui, 'chat_input'): self.gui.chat_input.configure(state="normal")
            if hasattr(self.gui, 'send_button'): self.gui.send_button.configure(state="normal")
            if hasattr(self.gui, 'stop_button'): self.gui.stop_button.configure(state="disabled")

    def _enhance_prompt(self, user_prompt, is_new=True, base64_image=None, mime_type="image/jpeg", selected_model_name="Gemini", conv_history=None):
        """Améliore le prompt en utilisant requests pour éviter les blocages du SDK."""
        if is_new:
            enhancement_prompt = f"""L'utilisateur veut créer un tout nouveau projet logiciel (Web, Mobile, Script Python, etc.) : '{user_prompt}'.
Rédige à sa place un prompt d'architecture et de conception ultra-détaillé.
CONSIGNES STRICTES :
- Si c'est un site web ou une app avec interface graphique : Exige un style ultra premium, moderne et élégant. Demande une excellente UX.
- Si c'est un script, un bot ou un outil CLI : Exige un code robuste, documenté, avec gestion des erreurs.
- Ne présume pas que c'est du web si l'utilisateur demande Python ou autre chose.
Réponds UNIQUEMENT par le prompt final brut sans fioriture."""
        else:
            # Construire un résumé de la conversation récente pour donner le contexte
            conv_context = ""
            if conv_history:
                # Prendre les 6 derniers échanges (pour ne pas surcharger)
                recent = conv_history[-6:]
                lines = []
                for h in recent:
                    role_label = "Utilisateur" if h["role"] == "user" else "Jarvis"
                    lines.append(f"{role_label}: {h['content'][:300]}")
                if lines:
                    conv_context = "\n\nCONTEXTE DE LA CONVERSATION EN COURS :\n" + "\n".join(lines) + "\n"
            
            enhancement_prompt = f"""L'utilisateur demande une modification sur un projet existant.{conv_context}
Nouvelle demande de l'utilisateur : '{user_prompt}'.
Analyse la demande en tenant compte du contexte de la conversation ci-dessus :
1. Si c'est une PETITE retouche (corriger un bug, ajuster l'interface) : Rédige un prompt technique précis. Interdis la refonte complète.
2. Si c'est une REFONTE MAJEURE ou l'ajout d'une grosse feature : Rédige un prompt qui autorise la modification de l'architecture et la génération de nouvelles images avec [GENERATE_IMAGE: description].
3. SI UNE IMAGE EST FOURNIE, analyse-la avec attention pour comprendre le bug visuel ou le modèle à reproduire.
4. IMPORTANT : Si la demande est vague ou courte, utilise le contexte de la conversation pour déduire sur quel élément précis l'utilisateur veut agir.

Rédige ce prompt final pour le développeur. Réponds UNIQUEMENT par le prompt brut, sans aucune phrase d'introduction."""
            
        api_gemini_key = os.environ.get("GEMINI_API_KEY")
        api_grok_key = os.environ.get("XAI_API_KEY")
        api_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        api_mistral_key = os.environ.get("MISTRAL_API_KEY")
        api_openai_key = os.environ.get("OPENAI_API_KEY")
        
        if "Grok" in selected_model_name and api_grok_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_grok_key, base_url="https://api.x.ai/v1")
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                else:
                    msg_content = enhancement_prompt
                response = client.chat.completions.create(
                    model="grok-4.5",
                    messages=[{"role": "user", "content": msg_content}],
                    temperature=0.7,
                    max_completion_tokens=4000
                )
                enhanced_prompt = response.choices[0].message.content
                self.gui.log_to_terminal(f"> Prompt Enrichi par Grok :\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Avertissement) L'amélioration Grok a échoué ({e}).")
                
        elif "Claude" in selected_model_name and api_anthropic_key:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_anthropic_key)
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": base64_image}}
                    ]
                else:
                    msg_content = enhancement_prompt
                response = client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": msg_content}]
                )
                enhanced_prompt = response.content[0].text
                self.gui.log_to_terminal(f"> Prompt Enrichi par Claude :\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Avertissement) L'amélioration Claude a échoué ({e}).")
                
        elif "ChatGPT" in selected_model_name and api_openai_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_openai_key)
                
                model_id = "gpt-4o"
                if "(" in selected_model_name and ")" in selected_model_name:
                    model_id = selected_model_name.split("(")[1].split(")")[0]
                    
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                else:
                    msg_content = enhancement_prompt
                try:
                    kwargs = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": msg_content}]
                    }
                    is_reasoning_model = any(keyword in model_id.lower() for keyword in ["luna", "sol", "terra", "o1", "o3"])
                    if not is_reasoning_model:
                        kwargs["max_completion_tokens"] = 4000
                        
                    response = client.chat.completions.create(**kwargs)
                    enhanced_prompt = response.choices[0].message.content
                except Exception as e1:
                    try:
                        kwargs.pop("max_completion_tokens", None)
                        if not is_reasoning_model:
                            kwargs["max_tokens"] = 4000
                        response = client.chat.completions.create(**kwargs)
                        enhanced_prompt = response.choices[0].message.content
                    except Exception as e2:
                        try:
                            comp_kwargs = {
                                "model": model_id,
                                "prompt": enhancement_prompt
                            }
                            if not is_reasoning_model:
                                comp_kwargs["max_tokens"] = 4000
                            response = client.completions.create(**comp_kwargs)
                            enhanced_prompt = response.choices[0].text
                        except Exception:
                            # Remonter l'erreur la plus pertinente (e1 ou e2) pour l'afficher
                            raise e1
                self.gui.log_to_terminal(f"> Prompt Enrichi par ChatGPT :\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Avertissement) L'amélioration ChatGPT a échoué ({e}).")
                
        elif ("Mistral" in selected_model_name or "Codestral" in selected_model_name) and api_mistral_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_mistral_key, base_url="https://api.mistral.ai/v1")
                if base64_image:
                    msg_content = [
                        {"type": "text", "text": enhancement_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                    ]
                else:
                    msg_content = enhancement_prompt
                response = client.chat.completions.create(
                    model="mistral-large-latest",
                    messages=[{"role": "user", "content": msg_content}],
                    temperature=0.7,
                    max_tokens=4000
                )
                enhanced_prompt = response.choices[0].message.content
                self.gui.log_to_terminal(f"> Prompt Enrichi par Mistral :\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Avertissement) L'amélioration Mistral a échoué ({e}).")
                
        elif api_gemini_key:
            try:
                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_gemini_key}"
                
                parts = [{"text": enhancement_prompt}]
                if base64_image:
                    parts.append({"inlineData": {"mimeType": mime_type, "data": base64_image}})
                
                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4000}
                }
                # Timeout strict de 30 secondes pour laisser le temps à Gemini 2.5 de 'réfléchir'
                response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
                response.raise_for_status()
                data = response.json()
                enhanced_prompt = data["candidates"][0]["content"]["parts"][0]["text"]
                self.gui.log_to_terminal(f"> Prompt Enrichi par Gemini :\n{enhanced_prompt}\n")
                return enhanced_prompt
            except Exception as e:
                self.gui.log_to_terminal(f"> (Avertissement) L'amélioration automatique a échoué ({e}).")
        
        # Fallback si erreur ou pas de clé
        return user_prompt + " (Design très moderne, avec animations fluides, belles ombres et couleurs premium)"

    def _process_images(self, text, selected_model_name, selected_image_model, my_run_id=None):
        import re
        import uuid
        import urllib.request
        from urllib.parse import quote
        import requests
        
        pattern = r"\[GENERATE_IMAGE:\s*(.*?)\]"
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            return text
            
        self.gui.log_to_terminal(f"> Détection de {len(matches)} images à générer...")
        self.gui.update_status("Génération Images...", color="#e74c3c", loading=True)
        
        assets_dir = os.path.join(self.project_path, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        
        for i, match in enumerate(matches):
            if self.run_id != my_run_id: raise Exception("Annulé par l'utilisateur")
            full_tag = match.group(0)
            prompt = match.group(1).strip()
            prompt_log = prompt[:30].replace('\n', ' ')
            self.gui.log_to_terminal(f"  - Génération image {i+1}/{len(matches)} : {prompt_log}...")
            filename = f"img_{uuid.uuid4().hex[:8]}.jpg"
            filepath = os.path.join(assets_dir, filename)
            rel_path = f"assets/{filename}"
            
            success = False
            
            use_grok = "Grok" in selected_image_model or ("Auto" in selected_image_model and "Grok" in selected_model_name)
            use_openai = "ChatGPT" in selected_image_model or ("Auto" in selected_image_model and "ChatGPT" in selected_model_name)
            use_gemini = "Gemini" in selected_image_model
            use_comfy = "ComfyUI" in selected_image_model
            use_pollinations = "Pollinations" in selected_image_model or ("Auto" in selected_image_model and not use_grok and not use_openai)
            
            # API OPENAI IMAGE NATIVE
            if use_openai and not success:
                api_openai_img = os.environ.get("OPENAI_API_KEY")
                if api_openai_img:
                    try:
                        import openai
                        import requests
                        client = openai.OpenAI(api_key=api_openai_img)
                        resp = client.images.generate(model="gpt-image-2", prompt=prompt, n=1)
                        img_url = resp.data[0].url
                        
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        img_resp = requests.get(img_url, headers=headers, timeout=30)
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Erreur OpenAI Image : {e}")
            
            # API GROK IMAGINE NATIVE
            if use_grok:
                api_grok = os.environ.get("XAI_API_KEY")
                if api_grok:
                    try:
                        import openai
                        import requests
                        client = openai.OpenAI(api_key=api_grok, base_url="https://api.x.ai/v1")
                        resp = client.images.generate(model="grok-imagine-image", prompt=prompt, n=1)
                        img_url = resp.data[0].url
                        
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        img_resp = requests.get(img_url, headers=headers, timeout=30)
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Erreur Grok Image : {e}")

            # COMFYUI LOCAL (SDXL Turbo, GPU local, gratuit et illimité — serveur Desktop sur :8000)
            if not success and use_comfy:
                try:
                    import requests
                    comfy_url = "http://127.0.0.1:8000"
                    requests.get(f"{comfy_url}/system_stats", timeout=3)
                    seed = int(time.time() * 1000) % (2**32)
                    workflow = {
                        "3": {"class_type": "KSampler", "inputs": {
                            "seed": seed, "steps": 4, "cfg": 1.0,
                            "sampler_name": "euler_ancestral", "scheduler": "sgm_uniform", "denoise": 1.0,
                            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]
                        }},
                        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_turbo_1.0_fp16.safetensors"}},
                        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
                        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
                        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
                        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
                        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "jarvis_dev", "images": ["8", 0]}},
                    }
                    resp = requests.post(f"{comfy_url}/prompt", json={"prompt": workflow}, timeout=15)
                    resp.raise_for_status()
                    prompt_id = resp.json()["prompt_id"]

                    img_info = None
                    for _ in range(60):  # jusqu'à ~2 min (chargement modèle inclus)
                        time.sleep(2)
                        hist = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=10).json()
                        if prompt_id in hist:
                            for node_out in hist[prompt_id].get("outputs", {}).values():
                                if node_out.get("images"):
                                    img_info = node_out["images"][0]
                                    break
                            break

                    if img_info:
                        params = f"filename={img_info['filename']}&subfolder={img_info.get('subfolder', '')}&type={img_info.get('type', 'output')}"
                        img_resp = requests.get(f"{comfy_url}/view?{params}", timeout=30)
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                    else:
                        self.gui.log_to_terminal("  Erreur ComfyUI : timeout génération (2 min).")
                except requests.exceptions.ConnectionError:
                    self.gui.log_to_terminal("  Erreur ComfyUI : serveur non lancé (http://127.0.0.1:8000). Ouvre l'appli ComfyUI d'abord.")
                except Exception as e:
                    self.gui.log_to_terminal(f"  Erreur ComfyUI : {e}")

            # API GEMINI 3.1 FLASH LITE IMAGE (imagen-4.0-generate-001 n'est plus dispo pour les nouveaux comptes)
            if not success and use_gemini:
                api_gemini = os.environ.get("GEMINI_API_KEY")
                if api_gemini:
                    try:
                        import google.genai as genai
                        from google.genai import types as genai_types
                        client = genai.Client(api_key=api_gemini)
                        resp = client.models.generate_content(
                            model='gemini-3.1-flash-lite-image',
                            contents=prompt,
                            config=genai_types.GenerateContentConfig(
                                response_modalities=[genai_types.Modality.TEXT, genai_types.Modality.IMAGE],
                            ),
                        )
                        image_bytes = None
                        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
                            for part in resp.candidates[0].content.parts:
                                if part.inline_data:
                                    image_bytes = part.inline_data.data
                                    break
                        if image_bytes:
                            with open(filepath, 'wb') as f:
                                f.write(image_bytes)
                            success = True
                        else:
                            self.gui.log_to_terminal("  Erreur Gemini Image : aucune image retournée.")
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Erreur Gemini Image : {e}")
            
            # FALLBACK HAUTE QUALITÉ FLUX (Pollinations API paramétrée)
            if not success and (use_pollinations or "Auto" in selected_image_model):
                import requests
                import time
                safe_prompt = quote(prompt)
                pollinations_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?model=flux&width=1024&height=1024&nologo=true"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                
                for attempt in range(3):
                    try:
                        img_resp = requests.get(pollinations_url, headers=headers, timeout=30)
                        if img_resp.status_code == 429:
                            self.gui.log_to_terminal(f"  - Serveur d'images surchargé (Anti-spam). Pause de 5s ({attempt+1}/3)...")
                            time.sleep(5)
                            continue
                        img_resp.raise_for_status()
                        with open(filepath, 'wb') as f:
                            f.write(img_resp.content)
                        success = True
                        time.sleep(1.5) # Petite pause bienveillante entre chaque image
                        break
                    except requests.exceptions.ReadTimeout:
                        self.gui.log_to_terminal(f"  - Le serveur d'images est lent, nouvel essai ({attempt+1}/3)...")
                        time.sleep(2)
                    except Exception as e:
                        self.gui.log_to_terminal(f"  Erreur Génération Image : {e}")
                        break
            
            if success:
                # Remplacer le tag par le chemin relatif brut (l'IA gère la balise HTML ou Python)
                text = text.replace(full_tag, rel_path)
            
        return text

    def _process_videos(self, text, my_run_id=None):
        """Génère les vidéos taguées [GENERATE_VIDEO: ...] via ComfyUI local (Wan 2.2 5B, texte->vidéo).
        Seule option vidéo dispo (locale, gratuite) — lente : ~15-20 min par vidéo sur un GPU 8 Go VRAM."""
        import re
        import uuid

        pattern = r"\[GENERATE_VIDEO:\s*(.*?)\]"
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if not matches:
            return text

        self.gui.log_to_terminal(f"> Détection de {len(matches)} vidéo(s) à générer (ComfyUI local, ~15-20 min chacune)...")
        self.gui.update_status("Génération Vidéo...", color="#e74c3c", loading=True)

        assets_dir = os.path.join(self.project_path, "assets")
        os.makedirs(assets_dir, exist_ok=True)

        for i, match in enumerate(matches):
            if self.run_id != my_run_id: raise Exception("Annulé par l'utilisateur")
            full_tag = match.group(0)
            prompt = match.group(1).strip()
            prompt_log = prompt[:40].replace('\n', ' ')
            self.gui.log_to_terminal(f"  - Génération vidéo {i+1}/{len(matches)} : {prompt_log}...")
            filename = f"vid_{uuid.uuid4().hex[:8]}.webm"
            filepath = os.path.join(assets_dir, filename)
            rel_path = f"assets/{filename}"

            try:
                import requests
                comfy_url = "http://127.0.0.1:8000"
                requests.get(f"{comfy_url}/system_stats", timeout=3)
                seed = int(time.time() * 1000) % (2**32)
                workflow = {
                    "37": {"class_type": "UNETLoader", "inputs": {"unet_name": "wan2.2_ti2v_5B_fp16.safetensors", "weight_dtype": "default"}},
                    "48": {"class_type": "ModelSamplingSD3", "inputs": {"shift": 8.0, "model": ["37", 0]}},
                    "38": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
                    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["38", 0]}},
                    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, static, worst quality", "clip": ["38", 0]}},
                    "39": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
                    "55": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"width": 1280, "height": 704, "length": 41, "batch_size": 1, "vae": ["39", 0]}},
                    "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 30, "cfg": 5, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1, "model": ["48", 0], "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["55", 0]}},
                    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["39", 0]}},
                    "47": {"class_type": "SaveWEBM", "inputs": {"filename_prefix": "jarvis_dev_video", "codec": "vp9", "fps": 24, "crf": 16, "images": ["8", 0]}},
                }
                resp = requests.post(f"{comfy_url}/prompt", json={"prompt": workflow}, timeout=15)
                resp.raise_for_status()
                r = resp.json()
                if r.get("node_errors"):
                    raise Exception(f"workflow invalide : {r['node_errors']}")
                prompt_id = r["prompt_id"]

                vid_info = None
                waited = 0
                while waited < 1800:  # jusqu'à 30 min
                    if self.run_id != my_run_id: raise Exception("Annulé par l'utilisateur")
                    time.sleep(10)
                    waited += 10
                    if waited % 60 == 0:
                        self.gui.log_to_terminal(f"    ... toujours en génération ({waited // 60} min écoulées)")
                    hist = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=10).json()
                    if prompt_id in hist:
                        for node_out in hist[prompt_id].get("outputs", {}).values():
                            if node_out.get("images"):
                                vid_info = node_out["images"][0]
                                break
                        break

                if vid_info:
                    params = f"filename={vid_info['filename']}&subfolder={vid_info.get('subfolder', '')}&type={vid_info.get('type', 'output')}"
                    vid_resp = requests.get(f"{comfy_url}/view?{params}", timeout=60)
                    vid_resp.raise_for_status()
                    with open(filepath, 'wb') as f:
                        f.write(vid_resp.content)
                    text = text.replace(full_tag, rel_path)
                    self.gui.log_to_terminal(f"  - Vidéo {i+1}/{len(matches)} terminée.")
                else:
                    self.gui.log_to_terminal("  Erreur ComfyUI : timeout génération vidéo (30 min).")
            except requests.exceptions.ConnectionError:
                self.gui.log_to_terminal("  Erreur ComfyUI : serveur non lancé (http://127.0.0.1:8000). Ouvre l'appli ComfyUI d'abord.")
            except Exception as e:
                self.gui.log_to_terminal(f"  Erreur génération vidéo : {e}")

        return text

    def _parse_and_save_files(self, raw_text):
        """Parse le retour de l'IA et écrit les fichiers sur le disque dur."""
        
        # S'assurer que le dossier du projet existe avant de faire quoi que ce soit
        os.makedirs(self.project_path, exist_ok=True)
        
        # Regex plus permissive : accepte si ---END_FILE--- est manquant (ex: génération coupée car trop longue)
        pattern = r"---BEGIN_FILE:\s*(.+?)---(.*?)(?=---END_FILE---|---BEGIN_FILE:|$)"
        matches = list(re.finditer(pattern, raw_text, re.DOTALL | re.IGNORECASE))
        
        if not matches:
            # Fallback 1: Extract markdown code blocks if the model ignored instructions (matches any language tag)
            md_blocks = re.findall(r"```[a-zA-Z0-9_-]*\s*(.*?)```", raw_text, re.DOTALL)
            if md_blocks:
                self.gui.log_to_terminal("> Format Markdown détecté (Mode Sauvetage)...")
                content = "\n\n".join(md_blocks)
                filename = "index.html"
                full_path = os.path.join(self.project_path, filename)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content.strip())
                self.gui.log_to_terminal(f"> Créé : {filename} (via mode sauvetage)")
                
                structure = {filename: "file"}
                self.gui.update_file_tree(structure)
                if os.path.exists(full_path):
                    self.gui.current_open_file = filename
                    self.gui.update_code_viewer(filename, content.strip())
                return
            
            # Fallback 2: Direct HTML tags
            if "<html" in raw_text.lower() or "<!doctype html>" in raw_text.lower():
                self.gui.log_to_terminal("> Format HTML brut détecté (Mode Sauvetage)...")
                start_idx = raw_text.lower().find("<html")
                if start_idx == -1:
                    start_idx = raw_text.lower().find("<!doctype")
                end_idx = raw_text.lower().rfind("</html>")
                
                if start_idx != -1 and end_idx != -1:
                    content = raw_text[start_idx:end_idx + 7]
                    filename = "index.html"
                    full_path = os.path.join(self.project_path, filename)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content.strip())
                    self.gui.log_to_terminal(f"> Créé : {filename} (via mode sauvetage)")
                    
                    structure = {filename: "file"}
                    self.gui.update_file_tree(structure)
                    if os.path.exists(full_path):
                        self.gui.current_open_file = filename
                        self.gui.update_code_viewer(filename, content.strip())
                    return

            # Fallback 3: Dumping raw text as response since everything else failed
            self.gui.log_to_terminal("> ⚠️ Erreur de formatage : L'IA a répondu en texte brut ou avec une erreur.")
            
            try:
                debug_path = os.path.join(self.project_path, "reponse_ia_brute.txt")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
                self.gui.log_to_terminal(f"> 📝 Le texte brut de l'IA a été sauvegardé dans {debug_path}.")
                
                # Update GUI to show the raw response
                structure = {"reponse_ia_brute.txt": "file"}
                self.gui.update_file_tree(structure)
                if os.path.exists(debug_path):
                    self.gui.current_open_file = "reponse_ia_brute.txt"
                    self.gui.update_code_viewer("reponse_ia_brute.txt", raw_text)
            except Exception as e:
                self.gui.log_to_terminal(f"> Impossible de sauvegarder le texte brut : {str(e)}")
            return

        structure = {}
        first_file_name = None
        first_file_content = None
        
        for match in matches:
            filename = match.group(1).strip()
            content = match.group(2).strip()
            
            # Empêche les sauts de chemin dangereux
            if ".." in filename:
                continue

            full_path = os.path.join(self.project_path, filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.gui.log_to_terminal(f"> Créé : {filename}")
            
            # Construction de l'arbre pour le mini-explorateur
            parts = filename.replace("\\", "/").split('/')
            current = structure
            for p in parts[:-1]:
                if p not in current:
                    current[p] = {}
                current = current[p]
            current[parts[-1]] = "file"
            
            if not first_file_name:
                first_file_name = filename
                first_file_content = content
                
        # Met à jour l'interface
        self.gui.update_file_tree(structure)
        if first_file_name:
            self.gui.update_code_viewer(first_file_name, first_file_content)


if __name__ == "__main__":
    app = JarvisDeveloperGUI()
    builder = ProjectBuilder(app)
    app.builder = builder  # Pour que le STOP et send_message fonctionnent
    
    # On connecte l'interface à l'orchestrateur IA
    app.on_new_project = lambda folder: builder.start_project(os.path.basename(folder), folder)
    app.on_open_project = lambda folder: builder.load_existing_project(folder)
    
    app.mainloop()
