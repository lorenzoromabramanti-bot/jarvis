import os
import re
import requests
from urllib.parse import urlparse
from typing import Optional, Tuple, List, Dict, Any
from openai import OpenAI

class JarvisLocalAgentManager:
    """
    Gestionnaire pour l'agent local basé sur le modèle Ornith (via Ollama).
    Permet une intégration optionnelle (opt-in), privée et gratuite dans JARVIS.
    """

    def __init__(self, model_name=None):
        # Configuration dynamique via variables d'environnement ou paramètre
        self.base_url: str = os.environ.get("JARVIS_OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.model: str = model_name if model_name else os.environ.get("JARVIS_OLLAMA_MODEL", "ornith:9b")
        
        # Initialisation du client OpenAI (100% compatible avec l'API v1 d'Ollama)
        # Une clé d'API factice est requise par le SDK. On met un timeout long (5 minutes) pour les modèles locaux lents.
        self.client = OpenAI(
            base_url=self.base_url,
            api_key="ollama-local",
            timeout=300.0
        )

    def _get_ollama_tags_url(self) -> str:
        """Construit l'URL de diagnostic native d'Ollama à partir de la base_url OpenAI."""
        parsed = urlparse(self.base_url)
        # L'API native d'Ollama pour lister les modèles est toujours sur /api/tags
        return f"{parsed.scheme}://{parsed.netloc}/api/tags"

    def check_system(self) -> Tuple[bool, str]:
        """
        Vérifie rapidement si Ollama tourne et si le modèle requis est téléchargé.
        Retourne un tuple (Est_Pret, Code_Erreur).
        """
        api_url = self._get_ollama_tags_url()
        
        try:
            # Timeout court pour ne pas bloquer l'interface utilisateur
            response = requests.get(api_url, timeout=3.0)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            # Le serveur Ollama ne répond pas (non lancé ou non installé)
            return False, "OLLAMA_NOT_RUNNING"
            
        try:
            data = response.json()
            # Récupère la liste des noms de modèles installés (ex: ['ornith:9b', 'deepseek-coder-v2:latest'])
            models = [m.get("name") for m in data.get("models", [])]
            
            # Ollama ajoute souvent le tag ':latest' si aucun n'est précisé (ex: deepseek-coder-v2 -> deepseek-coder-v2:latest)
            model_found = False
            for m in models:
                if m == self.model or m == f"{self.model}:latest" or self.model == m + ":latest":
                    model_found = True
                    break
            
            if not model_found:
                return False, "MODEL_NOT_PULLED"
                
        except ValueError:
            return False, "INVALID_RESPONSE"
            
        return True, "OK"

    def display_onboarding(self, status: str) -> None:
        """
        Affiche un écran d'onboarding textuel pédagogique si le diagnostic échoue.
        """
        print("\n" + "="*70)
        print(" 🤖 INITIALISATION DE L'AGENT LOCAL (ORNITH-1.0) ".center(70, "="))
        print("="*70)
        
        if status == "OLLAMA_NOT_RUNNING":
            print("\n ❌ Ollama ne semble pas être lancé ou installé sur cette machine.")
        elif status == "MODEL_NOT_PULLED":
            print(f"\n ❌ Le modèle '{self.model}' n'est pas encore téléchargé sur votre machine.")
        else:
            print("\n ❌ Une erreur inconnue est survenue avec le service local.")
            
        print("\n 💡 Pourquoi utiliser cet agent local optionnel ?")
        print("    • 100% Privé  : Toutes vos données et calculs restent sur votre machine.")
        print("    • 100% Gratuit: Aucune clé d'API, aucun abonnement requis.")
        print("    • Autonome    : L'IA utilise votre carte graphique ou votre processeur.")
        
        print(f"\n 📦 Espace requis : ~5.6 Go pour la version recommandée ({self.model}).")
        
        print("\n 🚀 GUIDE D'INSTALLATION PAS-À-PAS :")
        print("    1. Allez sur https://ollama.com et téléchargez Ollama pour votre système.")
        print("    2. Installez et lancez l'application Ollama en arrière-plan.")
        print("    3. Ouvrez un nouveau terminal (ou invite de commandes) et tapez exactement :")
        print(f"       > ollama pull {self.model}")
        print("    4. Patientez pendant le téléchargement du modèle.")
        print("    5. Relancez JARVIS. C'est tout !")
        print("\n" + "="*70 + "\n")

    def clean_thinking(self, text: str, strip_thinking: bool = True) -> str:
        """
        Nettoie la sortie pour extraire ou supprimer la réflexion de l'IA (balises <think>).
        """
        if not text:
            return ""
            
        if strip_thinking:
            # Supprime le bloc complet <think> ... </think> et les sauts de ligne autour
            cleaned = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL)
            
            # Sécurité : Si l'IA a été coupée avant la balise fermante ou a oublié de la mettre,
            # on supprime juste la balise <think> d'ouverture pour ne pas effacer tout le code HTML qui suit !
            cleaned = cleaned.replace("<think>", "").replace("</think>", "")
            
            return cleaned.strip()
            
        return text.strip()

    def generate_response(self, messages: List[Dict[str, str]], strip_thinking: bool = True) -> Optional[str]:
        """
        Appelle l'agent local avec l'historique des messages.
        Utilise les paramètres optimaux pour la réflexion de l'IA.
        """
        # 1. Vérification silencieuse (fail-fast)
        is_ok, status = self.check_system()
        if not is_ok:
            self.display_onboarding(status)
            return None
            
        try:
            # 2. Appel à l'API native d'Ollama (pour pouvoir forcer la taille du contexte 'num_ctx')
            # L'API OpenAI par défaut ne permet pas de changer num_ctx facilement, limitant à 2048 tokens !
            from urllib.parse import urlparse
            import requests
            
            parsed = urlparse(self.base_url)
            api_url = f"{parsed.scheme}://{parsed.netloc}/api/chat"
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.6,
                    "num_predict": -1,     # -1 = Aucune limite stricte, génère jusqu'à avoir fini (ou jusqu'à num_ctx)
                    "num_ctx": 32768       # Contexte géant pour les gros prompts et longs codes
                }
            }
            
            # Timeout infini (None) car un gros modèle (ex: 35b) générant 10000 tokens peut prendre 10 à 20 minutes sur un PC classique.
            response = requests.post(api_url, json=payload, timeout=None)
            response.raise_for_status()
            
            data = response.json()
            raw_text = data.get("message", {}).get("content", "")
            
            # 3. Traitement de la réflexion
            return self.clean_thinking(raw_text, strip_thinking=strip_thinking)
            
        except Exception as e:
            # On propage l'erreur pour que l'interface graphique (project_builder) puisse l'afficher
            raise Exception(f"Erreur avec l'agent local : {str(e)}")


# ==============================================================================
# EXEMPLE D'INTÉGRATION DANS LA BOUCLE PRINCIPALE JARVIS (FAUX MENU TERMINAL)
# ==============================================================================
if __name__ == "__main__":
    import time

    def main_jarvis_loop():
        print("="*50)
        print(" 🧠 JARVIS DEVELOPER OS - Menu Principal")
        print("="*50)
        print(" [1] Discuter avec l'agent Cloud (OpenAI/Gemini)")
        print(" [2] Discuter avec l'agent Local (Ornith-1.0)")
        print(" [3] Quitter")
        
        choix = input("\n Sélectionnez une option : ").strip()
        
        if choix == "2":
            # Initialisation (Légère, ne bloque pas si non utilisée)
            local_agent = JarvisLocalAgentManager()
            
            print("\n[Système] Vérification des prérequis locaux...")
            time.sleep(0.5) # Simule un petit chargement
            
            # Vérifie et bloque si le système n'est pas prêt
            is_ready, status = local_agent.check_system()
            if not is_ready:
                local_agent.display_onboarding(status)
                return # Retour au menu ou sortie
                
            print("✅ Agent local prêt. Vous pouvez discuter (tapez 'exit' pour quitter).")
            
            # Boucle de chat
            messages = [{"role": "system", "content": "Tu es JARVIS, un assistant IA expert."}]
            
            while True:
                user_input = input("\nVous : ").strip()
                if user_input.lower() == 'exit':
                    break
                if not user_input:
                    continue
                    
                messages.append({"role": "user", "content": user_input})
                print("\nJARVIS réfléchit (local)... ⏳")
                
                # Génération de la réponse (strip_thinking=True par défaut pour ne pas polluer l'UX)
                response_text = local_agent.generate_response(messages, strip_thinking=True)
                
                if response_text:
                    print(f"\nJARVIS (Ornith) : {response_text}")
                    messages.append({"role": "assistant", "content": response_text})
                else:
                    # L'écran d'erreur a déjà été affiché par generate_response si nécessaire
                    break

    main_jarvis_loop()
