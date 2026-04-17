import FamilyControls
import ManagedSettings

/// Applies shields via `ManagedSettingsStore`.
/// **Precedence:** shielding an entire **category** overrides individual app allowances inside that category.
/// For granular “allow Slack, block other Social,” use **application tokens** only, not category tokens.
@MainActor
final class ShieldManager {
    private let store = ManagedSettingsStore()

    /// Blocks listed apps when Screen Time APIs are authorized.
    func setShieldedApplications(_ tokens: Set<ApplicationToken>) {
        store.shield.applications = tokens
    }

    func setShieldedCategories(_ tokens: Set<ActivityCategoryToken>) {
        store.shield.applicationCategories = .specific(tokens)
    }

    func clearShields() {
        store.clearAllSettings()
    }
}
