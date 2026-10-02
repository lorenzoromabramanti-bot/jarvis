//
//  ContentView.swift
//  JarvisLocal
//
//  Pivot complet : ce n'est plus le POC Gemma local (un seul ecran, un
//  modele embarque). C'est un client du VRAI JARVIS qui tourne sur le PC,
//  par WebSocket (port 8765) — memes capacites que le HUD web : chat,
//  catalogue des 16 capacites avec retrait de protection apres
//  avertissement, cles API saisies a la main.
//
//  Le contrat reseau (JarvisClient.swift) a ete verifie contre le serveur
//  reel. Cette vue, elle, n'a jamais compile : pas de Mac/Xcode sur cette
//  machine. A verifier avant premiere utilisation.
//

import SwiftUI

struct ContentView: View {
  @StateObject private var client = JarvisClient()
  @AppStorage("jarvis_hote") private var hote = ""
  @AppStorage("jarvis_port") private var port = 8765
  @AppStorage("jarvis_jeton") private var jeton = ""

  var body: some View {
    Group {
      if client.etat == .connecte {
        TabView {
          DiscussionView(client: client)
            .tabItem { Label("Discussion", systemImage: "message") }
          CapacitesView(client: client)
            .tabItem { Label("Capacités", systemImage: "switch.2") }
          ReglagesView(client: client)
            .tabItem { Label("Réglages", systemImage: "key") }
        }
      } else {
        ConnexionView(client: client, hote: $hote, port: $port, jeton: $jeton)
      }
    }
  }
}

// MARK: - Connexion

private struct ConnexionView: View {
  @ObservedObject var client: JarvisClient
  @Binding var hote: String
  @Binding var port: Int
  @Binding var jeton: String

  var body: some View {
    NavigationStack {
      Form {
        Section("Serveur JARVIS") {
          TextField("Adresse (IP ou hôte Tailscale)", text: $hote)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
          TextField("Port", value: $port, format: .number)
            .keyboardType(.numberPad)
          SecureField("Jeton d'accès", text: $jeton)
        }

        if case .echec(let msg) = client.etat {
          Section {
            Text(msg).foregroundStyle(.red).font(.footnote)
          }
        }

        Section {
          Button {
            client.connecter(hote: hote, port: port, jeton: jeton)
          } label: {
            if client.etat == .connexion {
              ProgressView()
            } else {
              Text("Se connecter")
            }
          }
          .disabled(hote.isEmpty || jeton.isEmpty || client.etat == .connexion)
        }
      }
      .navigationTitle("JARVIS")
    }
  }
}

// MARK: - Discussion

private struct DiscussionView: View {
  @ObservedObject var client: JarvisClient
  @State private var texte = ""

  var body: some View {
    NavigationStack {
      VStack(spacing: 0) {
        ScrollViewReader { proxy in
          ScrollView {
            LazyVStack(alignment: .leading, spacing: 10) {
              ForEach(client.messages) { m in
                bulle(m).id(m.id)
              }
              if client.enAttenteReponse {
                ProgressView().padding(.leading, 8)
              }
            }
            .padding()
          }
          .onChange(of: client.messages.count) {
            if let dernier = client.messages.last {
              withAnimation { proxy.scrollTo(dernier.id, anchor: .bottom) }
            }
          }
        }

        if let refus = client.dernierRefus {
          Text(refus)
            .font(.footnote).foregroundStyle(.orange)
            .padding(.horizontal)
        }

        HStack {
          TextField("Parler à JARVIS", text: $texte, axis: .vertical)
            .textFieldStyle(.roundedBorder)
          Button {
            client.demander(texte)
            texte = ""
          } label: {
            Image(systemName: "paperplane.fill")
          }
          .disabled(texte.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .padding()
      }
      .navigationTitle("JARVIS")
    }
  }

  @ViewBuilder private func bulle(_ m: MessageChat) -> some View {
    HStack {
      if m.deJarvis { Spacer(minLength: 40) }
      Text(m.texte)
        .padding(10)
        .background(m.deJarvis ? Color(.systemGray5) : Color.accentColor.opacity(0.2),
                    in: RoundedRectangle(cornerRadius: 12))
      if !m.deJarvis { Spacer(minLength: 40) }
    }
  }
}

// MARK: - Capacités

private struct CapacitesView: View {
  @ObservedObject var client: JarvisClient
  @State private var enAttenteAvertissement: Capacite?

  var body: some View {
    NavigationStack {
      List(client.capacites) { c in
        VStack(alignment: .leading, spacing: 4) {
          HStack {
            VStack(alignment: .leading, spacing: 2) {
              Text(c.titre).font(.headline)
              Text(c.description).font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Toggle("", isOn: Binding(
              get: { c.activee },
              set: { _ in enAttenteAvertissement = c }
            ))
            .labelsHidden()
            .disabled(c.obligatoire)
          }
          if !c.disponible {
            Text("Indisponible : \(c.manques.joined(separator: ", "))")
              .font(.caption2).foregroundStyle(.red)
          }
        }
        .padding(.vertical, 4)
      }
      .navigationTitle("Capacités")
      .alert(
        enAttenteAvertissement?.activee == true ? "Retirer cette protection ?" : "Activer cette capacité ?",
        isPresented: Binding(
          get: { enAttenteAvertissement != nil },
          set: { if !$0 { enAttenteAvertissement = nil } }
        ),
        presenting: enAttenteAvertissement
      ) { c in
        Button("Annuler", role: .cancel) {}
        Button(c.activee ? "Retirer" : "Activer", role: c.activee ? .destructive : nil) {
          basculer(c)
        }
      } message: { c in
        Text(c.activee
             ? "\(c.titre) ne répondra plus une fois retirée. \(c.description)"
             : c.description)
      }
    }
  }

  private func basculer(_ cible: Capacite) {
    var cles = Set(client.capacites.filter(\.activee).map(\.cle))
    if cible.activee { cles.remove(cible.cle) } else { cles.insert(cible.cle) }
    client.definirCapacites(Array(cles))
  }
}

// MARK: - Réglages

private struct ReglagesView: View {
  @ObservedObject var client: JarvisClient
  @State private var nouvelleValeur: [String: String] = [:]

  private let clesConnues = [
    "GEMINI_API_KEY", "GROQ_API_KEY", "XAI_API_KEY", "YOUTUBE_API_KEY",
    "SERPAPI_API_KEY", "ANTHROPIC_API_KEY", "MISTRAL_API_KEY", "OPENAI_API_KEY",
  ]

  var body: some View {
    NavigationStack {
      Form {
        Section("Clés API") {
          ForEach(clesConnues, id: \.self) { nom in
            VStack(alignment: .leading, spacing: 4) {
              Text(nom).font(.caption).foregroundStyle(.secondary)
              HStack {
                SecureField(
                  client.cleApiMasquees[nom] ?? "non renseignée",
                  text: Binding(
                    get: { nouvelleValeur[nom] ?? "" },
                    set: { nouvelleValeur[nom] = $0 }
                  )
                )
                Button("Enregistrer") {
                  guard let v = nouvelleValeur[nom], !v.isEmpty else { return }
                  client.enregistrerCleApi(nom, v)
                  nouvelleValeur[nom] = ""
                }
                .disabled((nouvelleValeur[nom] ?? "").isEmpty)
              }
            }
          }
        }

        Section {
          Button("Se déconnecter", role: .destructive) { client.deconnecter() }
        }
      }
      .navigationTitle("Réglages")
      .onAppear { client.demanderParametres() }
    }
  }
}
