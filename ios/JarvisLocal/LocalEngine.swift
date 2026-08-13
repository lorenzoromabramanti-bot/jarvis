//
//  LocalEngine.swift
//  JarvisLocal
//
//  Enveloppe autour de l'API Swift LiteRT-LM.
//
//  L'INTÉRÊT DE LA VERSION NATIVE :
//  Dans un navigateur, les poids doivent tenir intégralement dans la mémoire
//  WebAssembly — un bloc unique que iOS plafonne bien en dessous de la RAM de
//  l'appareil. C'est ce qui tuait l'onglet Safari avec Gemma 4 (2 Go) sur
//  iPhone 17 comme sur iPhone 15 Pro Max, alors qu'un iPad Pro y arrivait.
//  Une app native, elle, fait du mmap : les poids restent sur le disque et le
//  système ne charge que les pages utiles. C'est exactement ce que font
//  AI Edge Gallery et PocketPal.
//

import Foundation
import LiteRTLM

@MainActor
final class LocalEngine: ObservableObject {

  enum Etat: Equatable {
    case inactif
    case chargement(String)
    case pret
    case echec(String)
  }

  @Published private(set) var etat: Etat = .inactif
  @Published private(set) var reponse: String = ""
  @Published private(set) var genere: Bool = false

  private var engine: Engine?
  private var conversation: Conversation?

  private static let consigne = """
    Tu es JARVIS, l'assistant personnel de Lorenzo, en mode hors-ligne sur son téléphone.
    RÈGLES :
    1. Réponds en français, de façon brève et directe.
    2. Tu ne peux commander aucun appareil : ni lumière, ni volet, ni musique. \
    Si on te demande une action, dis que tu es hors-ligne et qu'il faut le PC pour la domotique.
    3. N'invente jamais avoir fait quelque chose.
    4. Si tu ne sais pas, dis-le.
    """

  func charger(modele: URL) async {
    guard engine == nil else { return }
    etat = .chargement("Préparation du moteur…")
    do {
      let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]

      // backend .gpu = Metal. Bascule sur .cpu() si le chargement échoue sur
      // un appareil ancien : c'est plus lent mais nettement moins exigeant.
      let config = try EngineConfig(
        modelPath: modele.path,
        backend: .gpu,
        maxNumTokens: 2048,
        cacheDir: caches.path
      )

      let moteur = Engine(engineConfig: config)
      etat = .chargement("Chargement du modèle…")
      try await moteur.initialize()

      let conv = try moteur.createConversation(
        with: ConversationConfig(
          systemMessage: Message(Self.consigne, role: .system),
          samplerConfig: SamplerConfig(topK: 40, topP: 0.95, temperature: 0.3, seed: 0)
        )
      )

      engine = moteur
      conversation = conv
      etat = .pret
    } catch {
      etat = .echec(error.localizedDescription)
    }
  }

  func demander(_ texte: String) async {
    guard let conversation else { return }
    reponse = ""
    genere = true
    defer { genere = false }
    do {
      for try await morceau in conversation.sendMessageStream(Message(texte)) {
        for contenu in morceau.contents {
          if case .text(let t) = contenu { reponse += t }
        }
      }
    } catch {
      reponse = "Erreur de génération : \(error.localizedDescription)"
    }
  }

  /// Repart d'une conversation vierge (efface le contexte).
  func reinitialiser() {
    guard let engine else { return }
    conversation = try? engine.createConversation(
      with: ConversationConfig(
        systemMessage: Message(Self.consigne, role: .system),
        samplerConfig: SamplerConfig(topK: 40, topP: 0.95, temperature: 0.3, seed: 0)
      )
    )
    reponse = ""
  }
}
