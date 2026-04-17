import Foundation
import UserNotifications

/// Daily 07:00 local nudge for Inbox Slaughter; completion flag lives in App Group for extension visibility.
enum IdentityAlignmentScheduler {
    private static let nudgeId = "vanguard.inbox_slaughter.0700"
    private static let completedKey = "identity_alignment_ack_date"

    private static var suite: UserDefaults {
        UserDefaults(suiteName: AppConfig.appGroupId) ?? .standard
    }

    /// ISO date string (YYYY-MM-DD) when the user marked alignment done, or nil.
    static func lastAcknowledgedDay() -> String? {
        suite.string(forKey: completedKey)
    }

    static func acknowledgeToday(calendar: Calendar = .current) {
        let d = calendar.startOfDay(for: Date())
        let comps = calendar.dateComponents([.year, .month, .day], from: d)
        if let y = comps.year, let m = comps.month, let day = comps.day {
            suite.set(String(format: "%04d-%02d-%02d", y, m, day), forKey: completedKey)
        }
    }

    static func requestAuthorizationIfNeeded() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            return try await center.requestAuthorization(options: [.alert, .sound])
        } catch {
            return false
        }
    }

    /// Repeating calendar trigger at 07:00 local.
    static func scheduleDailyNudge() {
        let content = UNMutableNotificationContent()
        content.title = "Inbox Slaughter"
        content.body = "Process capture inbox to zero before opening distraction apps."
        var dc = DateComponents()
        dc.hour = 7
        dc.minute = 0
        let trigger = UNCalendarNotificationTrigger(dateMatching: dc, repeats: true)
        let req = UNNotificationRequest(identifier: nudgeId, content: content, trigger: trigger)
        UNUserNotificationCenter.current().add(req, withCompletionHandler: nil)
    }

    static func removeScheduledNudge() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [nudgeId])
    }
}
