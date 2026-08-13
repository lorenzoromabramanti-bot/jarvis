//
//  JarvisClient.swift
//  JarvisLocal
//
//  Client du VRAI protocole JARVIS (port 8765, main2.py) — pas une
//  reimplementation devinee. Chaque type de message ci-dessous a ete
//  verifie contre le serveur qui tourne (round-trip reel, pas une lecture
//  de code sans test). Ce que le Swift ne peut PAS verifier ici (absence
//  de Xcode sur cette machine) : que ça compile et que l'UI se comporte
//  comme prevu. Le reste — le contrat reseau — est confirme.
//

import Foundation

struct Capacite: Codable, Identifiable {
  let cle: String
  let titre: String
  let description: String
  let disponible: Bool
  let manques: [String]
  let niveau: Int
  let defaut: Bool
  let obligatoire: Bool
  let comptes: String
  let reglages: [String]
  let activee: Bool

  var id: String { cle }
}

struct MessageChat: Identifiable {
  let id = UUID()
  let texte: String
  let deJarvis: Bool
  let date = Date()
}

enum EtatConnexion: Equatable {
  case deconnecte
  case connexion
  case connecte
  case echec(String)
}

@MainActor
final class JarvisClient: ObservableObject {
  @Published private(set) var etat: EtatConnexion = .deconnecte
  @Published private(set) var mode = "avance"
  @Published private(set) var capacites: [Capacite] = []
  @Published private(set) var messages: [MessageChat] = []
  @Published private(set) var enAttenteReponse = false
  @Published private(set) var cleApiMasquees: [String: String] = [:]
  @Published private(set) var dernierRefus: String?

  private var tache: URLSessionWebSocketTask?

  func connecter(hote: String, port: Int, jeton: String) {
    tache?.cancel()
    etat = .connexion

    guard let url = URL(string: "ws://\(hote):\(port)") else {
      etat = .echec("Adresse invalide")
      return
    }
    let t = URLSession.shared.webSocketTask(with: url)
    tache = t
    t.resume()
    envoyerBrut(["token": jeton])
    ecouter()
  }

  func deconnecter() {
    tache?.cancel(with: .goingAway, reason: nil)
    tache = nil
    etat = .deconnecte
  }

  // MARK: - Envoi

  func demander(_ texte: String, versLePC: Bool = false) {
    guard !texte.trimmingCharacters(in: .whitespaces).isEmpty else { return }
    messages.append(MessageChat(texte: texte, deJarvis: false))
    enAttenteReponse = true
    envoyerBrut(["type": "mobile_command", "text": texte, "target_pc": versLePC])
  }

  func demanderCatalogue() {
    envoyerBrut(["type": "get_catalogue"])
  }

  /// Active/desactive une capacite. L'appelant (l'UI) doit deja avoir
  /// montre l'avertissement avant d'appeler ceci — le client ne le fait
  /// pas a la place de l'ecran, pour rester la source unique de cette
  /// decision cote UI.
  func definirCapacites(_ cles: [String]) {
    envoyerBrut(["type": "set_capacites", "cles": cles, "mode": mode])
  }

  func demanderParametres() {
    envoyerBrut(["type": "get_settings"])
  }

  func enregistrerCleApi(_ nom: String, _ valeur: String) {
    envoyerBrut(["type": "update_settings", "settings": ["api_keys": [nom: valeur]]])
  }

  private func envoyerBrut(_ objet: [String: Any]) {
    guard let data = try? JSONSerialization.data(withJSONObject: objet),
          let texte = String(data: data, encoding: .utf8) else { return }
    tache?.send(.string(texte)) { [weak self] erreur in
      if let erreur {
        Task { @MainActor in self?.etat = .echec(erreur.localizedDescription) }
      }
    }
  }

  // MARK: - Reception

  private func ecouter() {
    tache?.receive { [weak self] resultat in
      guard let self else { return }
      Task { @MainActor in
        switch resultat {
        case .failure(let erreur):
          self.etat = .echec(erreur.localizedDescription)
        case .success(let message):
          if case .string(let texte) = message {
            self.traiter(texte)
          }
          self.ecouter()
        }
      }
    }
  }

  private func traiter(_ texte: String) {
    guard let data = texte.data(using: .utf8),
          let objet = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

    switch objet["type"] as? String {
    case "auth_ok":
      etat = .connecte
      demanderCatalogue()
    case "auth_failed":
      etat = .echec("Jeton refuse")
    case "catalogue", "capacites_definies":
      if let m = objet["mode"] as? String { mode = m }
      if let brut = objet["capacites"] as? [[String: Any]],
         let d = try? JSONSerialization.data(withJSONObject: brut),
         let liste = try? JSONDecoder().decode([Capacite].self, from: d) {
        capacites = liste
      }
    case "capacite_desactivee":
      dernierRefus = objet["message"] as? String
    case "settings_data":
      if let d = objet["data"] as? [String: Any],
         let cles = d["api_keys"] as? [String: String] {
        cleApiMasquees = cles
      }
    default:
      // Messages sans "type" mais avec "action" : diffusions du HUD
      // (etat de l'orbe, stats systeme...). La reponse texte de JARVIS
      // arrive ainsi, pas comme reponse directe a mobile_command.
      if objet["action"] as? String == "jarvis_text", let t = objet["text"] as? String {
        messages.append(MessageChat(texte: t, deJarvis: true))
        enAttenteReponse = false
      }
    }
  }
}
