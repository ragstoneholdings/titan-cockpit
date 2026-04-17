import Foundation

/// Pure helpers for schedule windows (unit-tested). Real enforcement uses `DeviceActivity` + monitor extension.
enum ShieldScheduleLogic {
    /// Returns true when `now` falls in [start, end) on the same calendar day as `anchor`.
    static func isWithinDailyWindow(
        now: Date,
        anchorDay: Date,
        startHour: Int,
        startMinute: Int,
        endHour: Int,
        endMinute: Int,
        calendar: Calendar = .current
    ) -> Bool {
        guard calendar.isDate(now, inSameDayAs: anchorDay) else { return false }
        var s = calendar.dateComponents(in: calendar.timeZone, from: anchorDay)
        s.hour = startHour
        s.minute = startMinute
        s.second = 0
        guard let start = calendar.date(from: s) else { return false }
        s.hour = endHour
        s.minute = endMinute
        guard let end = calendar.date(from: s) else { return false }
        return now >= start && now < end
    }

    /// Inbox Slaughter example: 07:00–08:00 local.
    static func inboxSlaughterActive(now: Date, day: Date, calendar: Calendar = .current) -> Bool {
        isWithinDailyWindow(now: now, anchorDay: day, startHour: 7, startMinute: 0, endHour: 8, endMinute: 0, calendar: calendar)
    }

    /// Identity alignment window (defaults match server `IDENTITY_ALIGNMENT_*` env).
    static func identityAlignmentActive(now: Date, day: Date, calendar: Calendar = .current) -> Bool {
        isWithinDailyWindow(now: now, anchorDay: day, startHour: 7, startMinute: 0, endHour: 8, endMinute: 0, calendar: calendar)
    }

    /// 60-minute air gap example: 08:00–09:00 local.
    static func airGapActive(now: Date, day: Date, calendar: Calendar = .current) -> Bool {
        isWithinDailyWindow(now: now, anchorDay: day, startHour: 8, startMinute: 0, endHour: 9, endMinute: 0, calendar: calendar)
    }

    /// Midday shield example: 12:00–13:00 local.
    static func middayShieldActive(now: Date, day: Date, calendar: Calendar = .current) -> Bool {
        isWithinDailyWindow(now: now, anchorDay: day, startHour: 12, startMinute: 0, endHour: 13, endMinute: 0, calendar: calendar)
    }
}
