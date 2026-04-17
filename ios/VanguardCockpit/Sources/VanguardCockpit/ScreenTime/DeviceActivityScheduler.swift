import DeviceActivity
import Foundation

/// Registers named schedules for the monitor extension. Keep names in sync with `DeviceActivityMonitorExtension`.
enum VanguardActivityNames {
    static let inboxSlaughter = DeviceActivityName("inboxSlaughter")
    static let airGap = DeviceActivityName("airGap")
    static let middayShield = DeviceActivityName("middayShield")
}

enum DeviceActivityScheduler {
    /// Daily 07:00–08:00 (local) — Inbox Slaughter window.
    static let inboxSchedule = DeviceActivitySchedule(
        intervalStart: DateComponents(hour: 7, minute: 0),
        intervalEnd: DateComponents(hour: 8, minute: 0),
        repeats: true
    )

    /// Daily 08:00–09:00 — 60-minute air gap.
    static let airGapSchedule = DeviceActivitySchedule(
        intervalStart: DateComponents(hour: 8, minute: 0),
        intervalEnd: DateComponents(hour: 9, minute: 0),
        repeats: true
    )

    /// Daily 12:00–13:00 — midday windshield.
    static let middaySchedule = DeviceActivitySchedule(
        intervalStart: DateComponents(hour: 12, minute: 0),
        intervalEnd: DateComponents(hour: 13, minute: 0),
        repeats: true
    )

    static func registerAll() throws {
        let center = DeviceActivityCenter()
        try center.startMonitoring(VanguardActivityNames.inboxSlaughter, during: inboxSchedule)
        try center.startMonitoring(VanguardActivityNames.airGap, during: airGapSchedule)
        try center.startMonitoring(VanguardActivityNames.middayShield, during: middaySchedule)
    }
}
