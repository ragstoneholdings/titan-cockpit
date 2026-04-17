import FamilyControls
import Foundation

/// Combines inbox slaughter with server cockpit shield flags and local schedule windows.
@MainActor
enum DistractionShieldPolicy {
    static func shouldApplyDistractionShields(
        cockpit: CockpitResponseDTO?,
        now: Date = Date(),
        calendar: Calendar = .current
    ) -> Bool {
        guard let c = cockpit else { return false }
        let day = calendar.startOfDay(for: now)
        if !c.inbox_slaughter_gate_ok, ShieldScheduleLogic.inboxSlaughterActive(now: now, day: day, calendar: calendar) {
            return true
        }
        if c.identity_alignment_window_active, ShieldScheduleLogic.identityAlignmentActive(now: now, day: day, calendar: calendar) {
            return true
        }
        if c.air_gap_active, ShieldScheduleLogic.airGapActive(now: now, day: day, calendar: calendar) {
            return true
        }
        if c.midday_shield_active, ShieldScheduleLogic.middayShieldActive(now: now, day: day, calendar: calendar) {
            return true
        }
        return false
    }

    static func apply(
        shouldApply: Bool,
        selection: FamilyActivitySelection,
        shields: ShieldManager
    ) {
        InboxShieldCoordinator.apply(shouldApply: shouldApply, selection: selection, shields: shields)
    }
}
