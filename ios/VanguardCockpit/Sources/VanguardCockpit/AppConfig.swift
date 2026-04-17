import Foundation

enum AppConfig {
    /// Base URL for Titan Cockpit API (no trailing slash). Override in scheme env e.g. `COCKPIT_API_BASE`.
    /// Production example: `https://ragstone-titan-cockpit.fly.dev` (see root README).
    static var apiBaseURL: URL {
        if let raw = ProcessInfo.processInfo.environment["COCKPIT_API_BASE"], let u = URL(string: raw), !raw.isEmpty {
            return u
        }
        return URL(string: "http://127.0.0.1:8000")!
    }

    /// Optional API key for `X-Cockpit-Key` when `COCKPIT_API_KEY` is set on the server. Scheme env overrides Keychain.
    static var apiKey: String? {
        if let raw = ProcessInfo.processInfo.environment["COCKPIT_API_KEY"]?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty {
            return raw
        }
        return CockpitKeychain.readKey()
    }

    static let appGroupId = "group.com.ragstone.vanguard.cockpit"
}
