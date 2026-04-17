import XCTest
@testable import VanguardCockpit

final class ScheduleMathTests: XCTestCase {
    func testInboxSlaughterWindow() throws {
        var cal = Calendar.current
        cal.timeZone = TimeZone(secondsFromGMT: 0)!
        let day = cal.date(from: DateComponents(year: 2026, month: 4, day: 16))!
        let t0730 = cal.date(byAdding: .minute, value: 30, to: cal.date(bySettingHour: 7, minute: 0, second: 0, of: day)!)!
        XCTAssertTrue(ShieldScheduleLogic.inboxSlaughterActive(now: t0730, day: day, calendar: cal))
        let t0830 = cal.date(bySettingHour: 8, minute: 30, second: 0, of: day)!
        XCTAssertFalse(ShieldScheduleLogic.inboxSlaughterActive(now: t0830, day: day, calendar: cal))
    }

    func testAirGapWindow() throws {
        var cal = Calendar.current
        cal.timeZone = TimeZone(secondsFromGMT: 0)!
        let day = cal.date(from: DateComponents(year: 2026, month: 4, day: 16))!
        let t0830 = cal.date(byAdding: .minute, value: 30, to: cal.date(bySettingHour: 8, minute: 0, second: 0, of: day)!)!
        XCTAssertTrue(ShieldScheduleLogic.airGapActive(now: t0830, day: day, calendar: cal))
    }
}
