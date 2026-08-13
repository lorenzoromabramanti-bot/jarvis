//
//  ContentView.swift
//  JarvisLocal
//
//  Écran unique : télécharger le modèle, le charger, poser des questions.
//  Volontairement minimal — l'objectif de cette première étape est de savoir
//  si Gemma 4 se charge nativement sur l'iPhone. L'intégration JARVIS
//  (WebSocket, domotique, orbe) viendra seulement si cette réponse est oui.
//

import SwiftUI

struct ContentView: View {
  @StateObject private var store = ModelStore()
  @StateObject private var moteur = LocalEngine()
  @State private var question = "Quelle est la capitale de la France ?"

  var body: some View {
    NavigationStack {
      VStack(spacing: 16) {
        carteModele

        if case .pret = moteur.etat {
          zoneDiscussion
        } else if case .chargement(let etape) = moteur.etat {
          ProgressView(etape).padding()
        } else if case .echec(let msg) = moteur.etat {
          Text("Échec du chargement : \(msg)")
            .font(.footnote).foregroundStyle(.red)
            .frame(maxWidth: .infinity, alignment: .leading)
        }

        Spacer()
      }
      .padding()
      .navigationTitle("JARVIS local")
    }
  }

  // MARK: - Modèle

  @ViewBuilder private var carteModele: some View {
    VStack(alignment: .leading, spacing: 10) {
      switch store.etat {

      case .absent:
        Text("Gemma 4 E2B — 2,6 Go à télécharger une seule fois.")
          .font(.subheadline).foregroundStyle(.secondary)
        Text("En Wi-Fi. Le modèle reste installé même quand l'app est re-signée.")
          .font(.caption).foregroundStyle(.secondary)
        Button("Télécharger le modèle") { store.telecharger() }
          .buttonStyle(.borderedProminent)

      case .telechargement(let recu, let total):
        let fraction = total > 0 ? Double(recu) / Double(total) : 0
        ProgressView(value: fraction) {
          Text("Téléchargement…").font(.subheadline)
        } currentValueLabel: {
          Text(total > 0
               ? "\(go(recu)) / \(go(total))  —  \(Int(fraction * 100)) %"
               : go(recu))
            .font(.caption).monospacedDigit()
        }
        Button("Annuler", role: .cancel) { store.annuler() }

      case .pret:
        Label("Modèle installé (\(go(store.tailleSurDisque)))", systemImage: "checkmark.circle.fill")
          .foregroundStyle(.green).font(.subheadline)
        HStack {
          if case .inactif = moteur.etat {
            Button("Charger en mémoire") {
              Task { await moteur.charger(modele: store.emplacement) }
            }
            .buttonStyle(.borderedProminent)
          }
          Button("Supprimer", role: .destructive) { store.supprimer() }
        }

      case .echec(let msg):
        Text("Échec : \(msg)").font(.footnote).foregroundStyle(.red)
        Button("Réessayer") { store.telecharger() }
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding()
    .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 12))
  }

  // MARK: - Discussion

  @ViewBuilder private var zoneDiscussion: some View {
    VStack(alignment: .leading, spacing: 12) {
      HStack {
        TextField("Pose ta question", text: $question, axis: .vertical)
          .textFieldStyle(.roundedBorder)
        Button {
          Task { await moteur.demander(question) }
        } label: {
          Image(systemName: "paperplane.fill")
        }
        .disabled(moteur.genere || question.isEmpty)
      }

      ScrollView {
        Text(moteur.reponse.isEmpty && moteur.genere ? "…" : moteur.reponse)
          .textSelection(.enabled)
          .frame(maxWidth: .infinity, alignment: .leading)
      }
      .frame(maxHeight: 320)

      Button("Nouvelle conversation") { moteur.reinitialiser() }
        .font(.caption)
    }
  }

  private func go(_ octets: Int64) -> String {
    String(format: "%.2f Go", Double(octets) / 1e9)
  }
}
