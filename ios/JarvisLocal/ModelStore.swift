//
//  ModelStore.swift
//  JarvisLocal
//
//  Télécharge et conserve le modèle Gemma 4 sur l'appareil.
//
//  POURQUOI PAS DANS LE BUNDLE DE L'APP :
//  L'exemple officiel de Google embarque le .litertlm dans l'app. Avec un
//  modèle de 2,6 Go, l'.ipa deviendrait ingérable — et surtout AltStore devrait
//  re-signer ces 2,6 Go chaque semaine. On télécharge donc au premier
//  lancement dans Application Support : l'.ipa reste minuscule, et le modèle
//  survit aux re-signatures (seule une désinstallation complète l'efface).
//

import Foundation

@MainActor
final class ModelStore: NSObject, ObservableObject {

  enum Etat: Equatable {
    case absent
    case telechargement(recu: Int64, total: Int64)
    case pret
    case echec(String)
  }

  @Published private(set) var etat: Etat = .absent

  /// Build « appareil » du modèle (≠ build `-web`, réservé aux navigateurs).
  private let url = URL(
    string: "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm"
  )!
  private let nomFichier = "gemma-4-E2B-it.litertlm"

  private var session: URLSession!
  private var tache: URLSessionDownloadTask?
  /// Permet de reprendre un téléchargement interrompu au lieu de tout refaire.
  private var reprise: Data?

  override init() {
    super.init()
    let config = URLSessionConfiguration.default
    config.allowsCellularAccess = false          // 2,6 Go : Wi-Fi uniquement
    config.waitsForConnectivity = true
    session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
    etat = existe ? .pret : .absent
  }

  /// Emplacement du modèle. Application Support survit aux re-signatures.
  var emplacement: URL {
    let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
    try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
    return base.appendingPathComponent(nomFichier)
  }

  var existe: Bool {
    FileManager.default.fileExists(atPath: emplacement.path)
  }

  var tailleSurDisque: Int64 {
    (try? FileManager.default.attributesOfItem(atPath: emplacement.path)[.size] as? Int64) as? Int64 ?? 0
  }

  func telecharger() {
    guard !existe else { etat = .pret; return }
    etat = .telechargement(recu: 0, total: 0)
    // Si une reprise est disponible, on repart de là ; sinon on démarre à zéro.
    if let reprise {
      tache = session.downloadTask(withResumeData: reprise)
    } else {
      tache = session.downloadTask(with: url)
    }
    tache?.resume()
  }

  func annuler() {
    tache?.cancel { [weak self] data in
      Task { @MainActor in
        self?.reprise = data           // conservé pour reprendre plus tard
        self?.etat = .absent
      }
    }
  }

  func supprimer() {
    try? FileManager.default.removeItem(at: emplacement)
    reprise = nil
    etat = .absent
  }
}

extension ModelStore: URLSessionDownloadDelegate {

  nonisolated func urlSession(
    _ session: URLSession, downloadTask: URLSessionDownloadTask,
    didWriteData bytesWritten: Int64, totalBytesWritten: Int64,
    totalBytesExpectedToWrite: Int64
  ) {
    Task { @MainActor in
      etat = .telechargement(recu: totalBytesWritten, total: totalBytesExpectedToWrite)
    }
  }

  nonisolated func urlSession(
    _ session: URLSession, downloadTask: URLSessionDownloadTask,
    didFinishDownloadingTo location: URL
  ) {
    // Ce fichier temporaire disparaît dès le retour de cette méthode : on le
    // déplace ici, de façon synchrone, avant toute chose.
    let destination = MainActor.assumeIsolated { self.emplacement }
    do {
      try? FileManager.default.removeItem(at: destination)
      try FileManager.default.moveItem(at: location, to: destination)
      // Un modèle re-téléchargeable n'a rien à faire dans iCloud.
      var url = destination
      var valeurs = URLResourceValues()
      valeurs.isExcludedFromBackup = true
      try? url.setResourceValues(valeurs)
      Task { @MainActor in self.etat = .pret }
    } catch {
      Task { @MainActor in self.etat = .echec("Déplacement impossible : \(error.localizedDescription)") }
    }
  }

  nonisolated func urlSession(
    _ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?
  ) {
    guard let error = error as NSError? else { return }
    let data = error.userInfo[NSURLSessionDownloadTaskResumeData] as? Data
    Task { @MainActor in
      self.reprise = data
      if error.code != NSURLErrorCancelled {
        self.etat = .echec(error.localizedDescription)
      }
    }
  }
}
