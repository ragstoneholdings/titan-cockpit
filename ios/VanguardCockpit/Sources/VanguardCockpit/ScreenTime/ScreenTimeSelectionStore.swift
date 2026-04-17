import FamilyControls
import Foundation

/// Persists `FamilyActivitySelection` in the shared App Group (same suite as `DeviceActivityMonitor`).
enum ScreenTimeSelectionStore {
    private static let key = "familyActivitySelection.v1"

    private static var suite: UserDefaults {
        UserDefaults(suiteName: AppConfig.appGroupId) ?? .standard
    }

    static func load() -> FamilyActivitySelection {
        guard let data = suite.data(forKey: key) else {
            return FamilyActivitySelection()
        }
        do {
            return try JSONDecoder().decode(FamilyActivitySelection.self, from: data)
        } catch {
            return FamilyActivitySelection()
        }
    }

    static func save(_ selection: FamilyActivitySelection) {
        guard let data = try? JSONEncoder().encode(selection) else { return }
        suite.set(data, forKey: key)
    }
}
