import DeviceActivity
import Foundation
import ManagedSettings

/// Background callbacks for `DeviceActivity` schedules. Shares state via App Group for the host app.
final class DeviceActivityMonitorExtension: DeviceActivityMonitor {
    private let suite = UserDefaults(suiteName: "group.com.ragstone.vanguard.cockpit")

    override func intervalDidStart(for activity: DeviceActivityName) {
        super.intervalDidStart(for: activity)
        suite?.set(String(describing: activity), forKey: "lastIntervalStart")
        suite?.set(Date().timeIntervalSince1970, forKey: "lastIntervalStartTs")
    }

    override func intervalDidEnd(for activity: DeviceActivityName) {
        super.intervalDidEnd(for: activity)
        suite?.set(String(describing: activity), forKey: "lastIntervalEnd")
    }
}

