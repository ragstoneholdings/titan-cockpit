import FamilyControls
import Foundation

/// Applies `ManagedSettings` when Inbox Slaughter is active and the server reports the gate is not clear.
/// Uses **application tokens only** from the saved selection (category shields override per-app rules).
@MainActor
enum InboxShieldCoordinator {
    /// True when shields should block the saved distraction apps during the slaughter window.
    static func shouldApplyInboxShields(
        inboxSlaughterGateOk: Bool?,
        now: Date = Date(),
        calendar: Calendar = .current
    ) -> Bool {
        guard let gateOk = inboxSlaughterGateOk else { return false }
        if gateOk { return false }
        let day = calendar.startOfDay(for: now)
        return ShieldScheduleLogic.inboxSlaughterActive(now: now, day: day, calendar: calendar)
    }

    /// When `shouldApply` is false, clears shields. When true, applies `selection.applicationTokens` (ignores category tokens for this policy).
    static func apply(
        shouldApply: Bool,
        selection: FamilyActivitySelection,
        shields: ShieldManager
    ) {
        if shouldApply {
            let apps = selection.applicationTokens
            if apps.isEmpty {
                shields.clearShields()
            } else {
                shields.setShieldedApplications(apps)
            }
        } else {
            shields.clearShields()
        }
    }
}
