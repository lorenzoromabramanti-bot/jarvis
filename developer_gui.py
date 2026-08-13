import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import os
import subprocess
import threading
import json
try:
    from tkinterweb import HtmlFrame
except ImportError:
    HtmlFrame = None

# Configuration de base du thème
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Thèmes: "blue" (standard), "green", "dark-blue"

class JarvisDeveloperGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Masquer la console Windows en arrière-plan
        if os.name == 'nt':
            import ctypes
            hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd_console:
                ctypes.windll.user32.ShowWindow(hwnd_console, 0)

        self.title("Jarvis Developer UI")
        self.geometry("1400x900")
        self.minsize(800, 600)
        
        # === LAYOUT PRINCIPAL ===
        self.grid_columnconfigure(0, weight=1) # Chat panel (s'étend par défaut)
        self.grid_columnconfigure(1, weight=0) # Dev panel (rétracté par défaut)
        self.grid_rowconfigure(0, weight=1)
        
        self.current_project_path = ""
        self.current_open_file = None
        self.dev_panel_visible = False
        
        self.recent_projects_file = "recent_projects.json"
        self.recent_projects = self._load_recent_projects()

        self._build_chat_panel()
        self._build_dev_panel()
        
        # On cache le panel dev au démarrage
        self.dev_frame.grid_remove()

    def _build_chat_panel(self):
        # --- PANNEAU DE GAUCHE : CHAT ---
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.chat_frame.grid_rowconfigure(1, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)
        
        # En-tête du Chat (Sélecteur de Modèle)
        self.chat_header = ctk.CTkFrame(self.chat_frame, height=50, fg_color="transparent")
        self.chat_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.header_label = ctk.CTkLabel(self.chat_header, text="Jarvis Assistant", font=ctk.CTkFont(size=20, weight="bold"))
        self.header_label.pack(side="left")

        # Crédit Tech en Clair
        self.credit_label = ctk.CTkLabel(self.chat_header, text="créé par www.techenclair.fr - Projet OpenSource (Interdit à la revente)", font=ctk.CTkFont(size=12, slant="italic"), text_color="#7f8c8d")
        self.credit_label.pack(side="left", padx=(15, 0), pady=(4, 0))

        # Sélecteur visuel de Modèle
        self.model_var = ctk.StringVar(value="Gemini 2.5 Flash")
        self.model_selector = ctk.CTkOptionMenu(
            self.chat_header, 
            values=["Gemini 3.5 Flash", "Gemini 3.1 Pro", "Gemini 2.5 Flash", "Gemini 2.5 Pro", "Claude 5 Sonnet", "Claude 5 Fable", "Claude 4.8 Opus", "Grok 4.5", "Grok 4.20", "Mistral Large", "Codestral", "Omniroute", "Ornith-1.0 (Local)", "Ornith-35b (Local)", "Qwen2.5-Coder (Local)", "DeepSeek-Coder (Local)"],
            variable=self.model_var,
            command=self.on_model_change
        )
        self.model_selector.pack(side="right")
        
        self.model_label = ctk.CTkLabel(self.chat_header, text="Modèle :")
        self.model_label.pack(side="right", padx=10)

        # Sélecteur de Moteur d'Images
        self.image_model_var = ctk.StringVar(value="Images: Auto")
        self.image_model_selector = ctk.CTkOptionMenu(
            self.chat_header,
            values=["Images: Auto", "Images: ComfyUI", "Images: Pollinations", "Images: Gemini", "Images: Grok"],
            variable=self.image_model_var,
            width=160,
            fg_color="#2c3e50",
            button_color="#34495e",
            button_hover_color="#2c3e50"
        )
        self.image_model_selector.pack(side="right", padx=(0, 10))
        
        # Checkbox "Prompt Auto"
        self.enrich_prompt_var = ctk.BooleanVar(value=True)
        self.enrich_prompt_checkbox = ctk.CTkCheckBox(
            self.chat_header,
            text="Prompt Auto",
            variable=self.enrich_prompt_var,
            font=ctk.CTkFont(size=12)
        )
        self.enrich_prompt_checkbox.pack(side="right", padx=(0, 15))

        # Historique du Chat
        self.chat_history = ctk.CTkTextbox(self.chat_frame, wrap="word", font=ctk.CTkFont(size=14))
        self.chat_history.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        self.chat_history.insert("0.0", "Jarvis: Bonjour ! Je suis prêt. Que souhaitez-vous développer aujourd'hui ?\n\n")
        self.chat_history.configure(state="disabled")
        
        # Zone de saisie
        self.chat_input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.chat_input_frame.grid(row=2, column=0, sticky="ew")
        self.chat_input_frame.grid_columnconfigure(0, weight=1)
        
        self.attached_image_path = None
        self.attachment_label = ctk.CTkLabel(self.chat_input_frame, text="", text_color="#f39c12", font=ctk.CTkFont(size=12, slant="italic"))
        self.attachment_label.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))
        
        self.chat_input = ctk.CTkTextbox(self.chat_input_frame, height=80, wrap="word", font=ctk.CTkFont(size=14))
        self.chat_input.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        
        # Gestion de l'appui sur Entrée pour envoyer (sans faire de saut de ligne)
        def _on_enter(event):
            self.send_message()
            return "break"
            
        self.chat_input.bind("<Return>", _on_enter)
        # Shift+Entrée fera un vrai saut de ligne par défaut
        self.chat_input.bind("<Shift-Return>", lambda e: None)
        
        self.attach_button = ctk.CTkButton(self.chat_input_frame, text="📎", width=40, height=40, fg_color="#34495e", hover_color="#2c3e50", command=self.attach_image)
        self.attach_button.grid(row=1, column=1, padx=(0, 10))
        
        self.send_button = ctk.CTkButton(self.chat_input_frame, text="Envoyer", width=90, height=40, command=self.send_message)
        self.send_button.grid(row=1, column=2)
        
        self.stop_button = ctk.CTkButton(self.chat_input_frame, text="🛑 STOP", width=90, height=40, fg_color="#e74c3c", hover_color="#c0392b", command=self.on_stop_clicked)
        self.stop_button.grid(row=1, column=3, padx=(10, 0))
        self.stop_button.configure(state="disabled") # Désactivé par défaut

        self.new_proj_button = ctk.CTkButton(self.chat_input_frame, text="Créer Projet...", width=120, height=40, fg_color="#27ae60", hover_color="#2ecc71", command=self.ask_new_project_directory)
        self.new_proj_button.grid(row=1, column=4, padx=(10, 5))
        
        self.recent_menu = ctk.CTkOptionMenu(
            self.chat_input_frame, 
            values=["Aucun projet"], 
            width=130, 
            height=40, 
            command=self.on_recent_selected
        )
        self.recent_menu.grid(row=1, column=5, padx=(5, 0))
        self.recent_menu.set("Récents...")
        self._update_recent_menu()

    def attach_image(self):
        file_path = ctk.filedialog.askopenfilename(
            title="Joindre une image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")]
        )
        if file_path:
            self.attached_image_path = file_path
            filename = os.path.basename(file_path)
            self.attachment_label.configure(text=f"📎 Image jointe : {filename}")

    def on_stop_clicked(self):
        if hasattr(self, 'builder') and self.builder:
            self.builder.cancel_generation()
            self.log_chat("Annulation demandée...", sender="Système")

    def send_message(self):
        try:
            with open("DEBUG_ALIVE.txt", "a") as f: f.write("send_message a demarre!\n")
        except: pass
        
        try:
            msg = self.chat_input.get("1.0", "end-1c")
            if not msg.strip(): return
            
            self.log_chat(msg, sender="Vous")
            self.chat_input.delete("1.0", "end")
            
            img_path = getattr(self, 'attached_image_path', None)
            self.attached_image_path = None
            if hasattr(self, 'attachment_label'): self.attachment_label.configure(text="")
            
            if hasattr(self, 'stop_button'): self.stop_button.configure(state="normal")
            
            if hasattr(self, 'builder') and self.builder:
                self.builder.handle_message(msg, img_path)
            else:
                self.log_chat(f"Erreur interne : 'builder' est manquant ou invalide. (hasattr={hasattr(self, 'builder')})", sender="Erreur")
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            try:
                self.log_chat(f"CRASH COMPLET dans send_message:\n{err}", sender="Erreur Critique")
            except:
                with open("CRASH_LOG.txt", "w") as f:
                    f.write(err)

    def _load_recent_projects(self):
        if os.path.exists(self.recent_projects_file):
            try:
                with open(self.recent_projects_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return []

    def _save_recent_project(self, path):
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10] # Garde les 10 derniers
        try:
            with open(self.recent_projects_file, "w", encoding="utf-8") as f:
                json.dump(self.recent_projects, f)
        except:
            pass
        self._update_recent_menu()
        
    def _update_recent_menu(self):
        if hasattr(self, 'recent_menu'):
            if self.recent_projects:
                names = [os.path.basename(p) for p in self.recent_projects if os.path.exists(p)]
                if names:
                    self.recent_menu.configure(values=names)
                else:
                    self.recent_menu.configure(values=["Aucun projet"])
            else:
                self.recent_menu.configure(values=["Aucun projet"])
            self.recent_menu.set("Récents...")

    def on_recent_selected(self, choice):
        if choice == "Aucun projet" or choice == "Récents...":
            return
        # Retrouver le chemin complet
        path = next((p for p in self.recent_projects if os.path.basename(p) == choice), None)
        if path and os.path.exists(path):
            self._save_recent_project(path)
            self.log_chat(f"Ouverture du projet existant : {path}", sender="Vous")
            if hasattr(self, 'on_open_project'):
                self.on_open_project(path)
        else:
            self.log_chat(f"Le dossier du projet semble introuvable ou a été supprimé.", sender="Système")

    def ask_new_project_directory(self):
        folder_selected = ctk.filedialog.askdirectory(title="Choisir le dossier du nouveau projet")
        if folder_selected:
            self._save_recent_project(folder_selected)
            self.log_chat(f"Création d'un projet dans : {folder_selected}", sender="Vous")
            if hasattr(self, 'on_new_project'):
                self.on_new_project(folder_selected)
            else:
                self.log_chat("La fonction de création n'est pas connectée.", sender="Système")

    def _build_dev_panel(self):
        # --- PANNEAU DE DROITE : DEV PANEL ---
        self.dev_frame = ctk.CTkFrame(self, width=700, corner_radius=10)
        self.dev_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        
        # Configuration des lignes du Dev Panel
        self.dev_frame.grid_columnconfigure(0, weight=1)
        self.dev_frame.grid_rowconfigure(1, weight=1) # Zone explorateur + code (prend tout l'espace)
        
        # 1. En-tête du Dev Panel (Status & Actions)
        self.dev_header = ctk.CTkFrame(self.dev_frame, height=50, fg_color="transparent")
        self.dev_header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Indicateur d'état
        self.status_indicator = ctk.CTkLabel(
            self.dev_header, 
            text="🟢 Prêt", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#2ecc71"
        )
        self.status_indicator.pack(side="left", padx=10)
        
        # Barre de progression animée
        self.progress_bar = ctk.CTkProgressBar(self.dev_header, mode="indeterminate", width=150)
        # Non affichée par défaut
        
        # Boutons d'action rapide
        self.btn_vscode = ctk.CTkButton(self.dev_header, text="Ouvrir dans VS Code", width=140, command=self.open_in_vscode)
        self.btn_vscode.pack(side="right", padx=5)
        
        self.btn_folder = ctk.CTkButton(self.dev_header, text="Ouvrir Dossier", width=120, command=self.open_folder)
        self.btn_folder.pack(side="right", padx=5)
        
        # 2. Zone Centrale: Explorateur & Code Viewer
        self.dev_main_split = ctk.CTkFrame(self.dev_frame, fg_color="transparent")
        self.dev_main_split.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.dev_main_split.grid_columnconfigure(0, weight=1) # Explorateur (étroit)
        self.dev_main_split.grid_columnconfigure(1, weight=4) # Code Viewer (large)
        self.dev_main_split.grid_rowconfigure(0, weight=1)
        
        # Mini-Explorateur
        self.explorer_frame = ctk.CTkFrame(self.dev_main_split, corner_radius=5)
        self.explorer_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        
        self.explorer_label = ctk.CTkLabel(self.explorer_frame, text="Fichiers", font=ctk.CTkFont(weight="bold"))
        self.explorer_label.pack(pady=5, padx=10, anchor="w")
        
        # Style pour le Treeview (Tkinter classique intégré dans CustomTkinter)
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0, font=("Segoe UI", 11))
        style.map('Treeview', background=[('selected', '#1f538d')])
        
        self.file_tree = ttk.Treeview(self.explorer_frame, show="tree")
        self.file_tree.pack(expand=True, fill="both", padx=5, pady=5)
        self.file_tree.bind("<Double-1>", self.on_tree_double_click)
        
        # Code Viewer & Preview avec onglets
        self.tabs = ctk.CTkTabview(self.dev_main_split, corner_radius=5)
        self.tabs.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        self.tab_code = self.tabs.add("Code")
        self.tab_preview = self.tabs.add("Rendu Visuel")
        
        # Zone Code
        self.tab_code.grid_columnconfigure(0, weight=1)
        self.tab_code.grid_rowconfigure(1, weight=1)
        
        self.save_btn = ctk.CTkButton(self.tab_code, text="💾 Sauvegarder", fg_color="#27ae60", hover_color="#2ecc71", command=self.save_current_code)
        self.save_btn.grid(row=0, column=0, pady=(5, 0), sticky="e", padx=5)
        
        self.code_viewer = ctk.CTkTextbox(self.tab_code, font=ctk.CTkFont(family="Consolas", size=13), wrap="none")
        self.code_viewer.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        # Zone Rendu Visuel
        self.tab_preview.grid_columnconfigure(0, weight=1)
        self.tab_preview.grid_rowconfigure(1, weight=1)
        
        self.browser_btn = ctk.CTkButton(self.tab_preview, text="🌐 Ouvrir dans mon Vrai Navigateur (Recommandé)", fg_color="#e67e22", hover_color="#d35400", command=self.open_in_browser)
        self.browser_btn.grid(row=0, column=0, pady=(5, 5), sticky="ew", padx=10)
        
        if HtmlFrame:
            self.web_preview = HtmlFrame(self.tab_preview)
            self.web_preview.grid(row=1, column=0, sticky="nsew")
        else:
            lbl = ctk.CTkLabel(self.tab_preview, text="tkinterweb n'est pas installé.")
            lbl.grid(row=1, column=0, sticky="nsew")



    def on_model_change(self, choice):
        self.log_chat(f"Modèle changé pour : {choice}", sender="Système")
        
        if "(Local)" in choice:
            from local_agent_manager import JarvisLocalAgentManager
            
            # Mapping entre le nom d'affichage et le tag Ollama exact
            ollama_tags = {
                "Ornith-1.0 (Local)": "ornith:9b",
                "Ornith-35b (Local)": "ornith:35b",
                "Qwen2.5-Coder (Local)": "qwen2.5-coder:7b",
                "DeepSeek-Coder (Local)": "deepseek-coder-v2"
            }
            
            target_model = ollama_tags.get(choice, "ornith:9b")
            agent = JarvisLocalAgentManager(model_name=target_model)
            
            is_ready, status = agent.check_system()
            if not is_ready:
                self._show_ollama_onboarding(agent, status)

    def _show_ollama_onboarding(self, agent, status):
        onboarding_win = ctk.CTkToplevel(self)
        onboarding_win.title("Agent Local Non Détecté")
        onboarding_win.geometry("600x400")
        onboarding_win.attributes("-topmost", True)
        onboarding_win.grab_set() 
        
        lbl_title = ctk.CTkLabel(onboarding_win, text="🤖 Installation de l'Agent Local", font=ctk.CTkFont(size=20, weight="bold"))
        lbl_title.pack(pady=(20, 10))
        
        info_text = "L'agent local 100% privé et gratuit nécessite Ollama.\n\n"
        if status == "OLLAMA_NOT_RUNNING":
            info_text += "❌ Ollama n'est pas installé ou n'est pas lancé.\n\n"
            info_text += "Étape 1 : Téléchargez et installez Ollama sur votre PC.\n"
            info_text += "Étape 2 : Lancez l'application Ollama en arrière-plan.\n"
            info_text += f"Étape 3 : Revenez ici et sélectionnez à nouveau le modèle."
        else:
            info_text += f"❌ Le modèle requis ({agent.model}) n'est pas encore téléchargé.\n\n"
            info_text += "Vous avez bien Ollama ! Il suffit de télécharger le modèle (~5.6 Go).\n"
            info_text += f"Voulez-vous que JARVIS télécharge le modèle pour vous ?"
            
        lbl_info = ctk.CTkLabel(onboarding_win, text=info_text, justify="left", font=ctk.CTkFont(size=14))
        lbl_info.pack(padx=20, pady=20)
        
        btn_frame = ctk.CTkFrame(onboarding_win, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        if status == "OLLAMA_NOT_RUNNING":
            def open_website():
                import webbrowser
                webbrowser.open("https://ollama.com/download")
            btn_web = ctk.CTkButton(btn_frame, text="Télécharger Ollama", command=open_website)
            btn_web.pack(side="left", padx=10)
        else:
            def auto_install():
                self.log_chat(f"Lancement du téléchargement de {agent.model}... Veuillez patienter.", sender="Système")
                onboarding_win.destroy()
                import threading
                import requests
                import json
                
                def pull_task():
                    try:
                        self.update_status("Téléchargement en cours...", color="#f39c12", loading=True)
                        response = requests.post(
                            "http://127.0.0.1:11434/api/pull", 
                            json={"name": agent.model},
                            stream=True
                        )
                        
                        last_progress = -1
                        for line in response.iter_lines():
                            if line:
                                data = json.loads(line.decode('utf-8'))
                                if 'completed' in data and 'total' in data and data['total'] > 0:
                                    percent = int((data['completed'] / data['total']) * 100)
                                    if percent % 10 == 0 and percent != last_progress:
                                        # Use after to safely update GUI from thread
                                        self.after(0, lambda p=percent: self.log_chat(f"⏳ Téléchargement : {p}%", sender="Système"))
                                        last_progress = percent
                        
                        self.after(0, lambda: self.log_chat(f"✅ Modèle {agent.model} téléchargé avec succès ! Vous pouvez l'utiliser.", sender="Système"))
                    except Exception as e:
                        self.after(0, lambda err=e: self.log_chat(f"❌ Erreur inattendue : {err}", sender="Système"))
                    finally:
                        self.after(0, lambda: self.update_status("Prêt", color="white", loading=False))
                        
                threading.Thread(target=pull_task, daemon=True).start()
                
            btn_install = ctk.CTkButton(btn_frame, text="Télécharger le modèle automatiquement", command=auto_install, fg_color="#27ae60", hover_color="#2ecc71")
            btn_install.pack(side="left", padx=10)
            
        btn_close = ctk.CTkButton(btn_frame, text="Fermer", command=onboarding_win.destroy, fg_color="#e74c3c", hover_color="#c0392b")
        btn_close.pack(side="left", padx=10)

    def update_status(self, text, color="white", loading=False):
        def _do_update():
            if hasattr(self, 'status_indicator'):
                self.status_indicator.configure(text=text, text_color=color)
                
            if hasattr(self, 'progress_bar'):
                if loading:
                    self.progress_bar.pack(side="left", padx=10)
                    self.progress_bar.start()
                else:
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
        self.after(0, _do_update)

    def log_to_terminal(self, message):
        def _do_log():
            self.chat_history.configure(state="normal")
            self.chat_history.insert("end", f"> 💻 Terminal: {message}\n\n")
            self.chat_history.see("end")
            self.chat_history.configure(state="disabled")
        self.after(0, _do_log)

    def log_chat(self, text, sender="Jarvis"):
        def _do_chat():
            self.chat_history.configure(state="normal")
            self.chat_history.insert("end", f"{sender}: {text}\n\n")
            self.chat_history.configure(state="disabled")
            self.chat_history.see("end")
        self.after(0, _do_chat)

    # === FONCTIONS POUR L'ORCHESTRATEUR (Project Builder) ===

    def show_dev_panel(self):
        if not self.dev_panel_visible:
            self.dev_frame.grid()
            # On redimensionne les poids pour que les deux colonnes s'affichent bien
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)
            self.dev_panel_visible = True

    def hide_dev_panel(self):
        if self.dev_panel_visible:
            self.dev_frame.grid_remove()
            self.grid_columnconfigure(1, weight=0)
            self.dev_panel_visible = False



    def update_code_viewer(self, filename, code_content):
        """Met à jour la zone de code central et le navigateur si c'est du web."""
        self.current_open_file = filename
        self.tabs.set("Code")
        self.code_viewer.delete("0.0", "end")
        self.code_viewer.insert("0.0", code_content)
        
        # Mettre à jour l'aperçu si fichier web
        if filename.endswith(".html"):
            if hasattr(self, 'web_preview') and HtmlFrame:
                full_path = os.path.join(self.current_project_path, filename)
                if os.path.exists(full_path):
                    try:
                        base_uri = f"file:///{self.current_project_path.replace(os.sep, '/')}/"
                        self.web_preview.load_html(code_content, base_url=base_uri)
                    except:
                        self.web_preview.load_file(f"file:///{full_path.replace(os.sep, '/')}")
                    self.tabs.set("Rendu Visuel")
            
            self.browser_btn.configure(text="🌐 Ouvrir dans mon Vrai Navigateur (Recommandé)", command=self.open_in_browser)
            if hasattr(self, 'python_warning_lbl'): self.python_warning_lbl.grid_remove()
            if hasattr(self, 'web_preview'): self.web_preview.grid(row=1, column=0, sticky="nsew")
            
        elif filename.endswith(".py"):
            full_path = os.path.join(self.current_project_path, filename)
            self.browser_btn.configure(text="🚀 Exécuter ce Script Python", command=lambda p=full_path: self.run_python_script(p))
            
            if hasattr(self, 'web_preview'): self.web_preview.grid_remove()
            if not hasattr(self, 'python_warning_lbl'):
                self.python_warning_lbl = ctk.CTkLabel(self.tab_preview, text="")
            self.python_warning_lbl.configure(text="Aperçu visuel non disponible pour les scripts Python.\nCliquez sur le bouton au-dessus pour l'exécuter.")
            self.python_warning_lbl.grid(row=1, column=0, sticky="nsew")
            
        else:
            self.browser_btn.configure(text="📁 Ouvrir le dossier du projet", command=self.open_folder)
            
            if hasattr(self, 'web_preview'): self.web_preview.grid_remove()
            if not hasattr(self, 'python_warning_lbl'):
                self.python_warning_lbl = ctk.CTkLabel(self.tab_preview, text="")
            self.python_warning_lbl.configure(text="Aperçu visuel non disponible pour ce type de fichier.")
            self.python_warning_lbl.grid(row=1, column=0, sticky="nsew")

    def set_project_path(self, path):
        """Définit le dossier racine du projet courant."""
        self.current_project_path = path

    def update_file_tree(self, structure_dict, parent=""):
        """
        Met à jour l'arbre de fichiers.
        Exemple de structure_dict : {'src': {'main.py': 'file'}, 'README.md': 'file'}
        """
        if parent == "":
            self.file_tree.delete(*self.file_tree.get_children())
            
        for name, content in structure_dict.items():
            node = self.file_tree.insert(parent, "end", text=name, open=True)
            if isinstance(content, dict):
                self.update_file_tree(content, node)

    def on_tree_double_click(self, event):
        item_id = self.file_tree.selection()
        if not item_id:
            return
        
        # Reconstruire le chemin
        item = item_id[0]
        path_parts = [self.file_tree.item(item, "text")]
        parent = self.file_tree.parent(item)
        while parent:
            path_parts.insert(0, self.file_tree.item(parent, "text"))
            parent = self.file_tree.parent(parent)
            
        rel_path = "/".join(path_parts)
        full_path = os.path.join(self.current_project_path, rel_path)
        
        if os.path.isfile(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.update_code_viewer(rel_path, content)
            except Exception as e:
                self.log_to_terminal(f"Impossible d'ouvrir le fichier : {e}")

    def save_current_code(self):
        if not self.current_open_file or not self.current_project_path:
            return
        full_path = os.path.join(self.current_project_path, self.current_open_file)
        try:
            content = self.code_viewer.get("0.0", "end-1c")
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.log_to_terminal(f"> Fichier sauvegardé : {self.current_open_file}")
            # Si c'est un fichier web, on recharge l'aperçu
            if self.current_open_file.endswith(".html") and hasattr(self, 'web_preview'):
                try:
                    self.web_preview.load_html(content)
                except:
                    self.web_preview.load_file(f"file:///{full_path.replace(os.sep, '/')}")
        except Exception as e:
            self.log_to_terminal(f"Erreur de sauvegarde : {e}")

    # === ACTIONS RAPIDES ===

    def open_in_browser(self):
        import webbrowser
        if self.current_project_path:
            index_path = os.path.join(self.current_project_path, "index.html")
            if os.path.exists(index_path):
                webbrowser.open("file://" + index_path)
            else:
                self.log_to_terminal("Erreur: index.html non trouvé pour le navigateur.")

    def run_python_script(self, filepath):
        import subprocess
        import threading
        import sys
        
        self.log_to_terminal(f"> Lancement du script : {filepath} ...")
        
        def run_thread():
            try:
                # Utiliser sys.executable pour prendre le Python courant (avec toutes les dépendances de Jarvis)
                process = subprocess.Popen([sys.executable, filepath], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=os.path.dirname(filepath))
                for line in iter(process.stdout.readline, ''):
                    if line:
                        self.log_to_terminal(f"[Script] {line.strip()}")
                process.stdout.close()
                process.wait()
                self.log_to_terminal(f"> Script terminé (Code de retour : {process.returncode})")
            except Exception as e:
                self.log_to_terminal(f"> Erreur lors de l'exécution : {e}")
                
        threading.Thread(target=run_thread, daemon=True).start()

    def open_folder(self):
        if not self.current_project_path or not os.path.exists(self.current_project_path):
            self.log_to_terminal("Erreur: Dossier du projet non défini ou introuvable.")
            return
        
        if os.name == 'nt': # Windows
            os.startfile(self.current_project_path)
        elif os.name == 'posix': # Mac/Linux
            subprocess.call(('open', self.current_project_path))

    def open_in_vscode(self):
        if not self.current_project_path or not os.path.exists(self.current_project_path):
            self.log_to_terminal("Erreur: Dossier du projet non défini ou introuvable.")
            return
        
        try:
            subprocess.Popen(["code", self.current_project_path], shell=True)
            self.log_to_terminal("> Ouverture de VS Code...")
        except Exception as e:
            self.log_to_terminal(f"> Erreur lors de l'ouverture de VS Code: {e}")

if __name__ == "__main__":
    app = JarvisDeveloperGUI()
    app.mainloop()
