import FamilyControls
import Observation
import SwiftUI

/// Screen Time authorization + selection. Category shields override per-app exemptions in ManagedSettings — prefer application tokens for granular blocks.
@Observable
@MainActor
final class FamilyControlsAuth {
    var authorizationStatus: AuthorizationStatus = .notDetermined
    var selection: FamilyActivitySelection

    init() {
        selection = ScreenTimeSelectionStore.load()
    }

    func refreshStatus() {
        authorizationStatus = AuthorizationCenter.shared.authorizationStatus
    }

    func requestAuthorization() async {
        do {
            try await AuthorizationCenter.shared.requestAuthorization(for: .individual)
        } catch {
            authorizationStatus = AuthorizationCenter.shared.authorizationStatus
            return
        }
        authorizationStatus = AuthorizationCenter.shared.authorizationStatus
    }
}
