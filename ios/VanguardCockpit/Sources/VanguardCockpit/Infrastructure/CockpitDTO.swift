import CoreFoundation
import Foundation

/// Mirrors `SovereigntyPayload` / `CockpitResponse` subset from FastAPI.
struct SovereigntyPayloadDTO: Codable, Sendable {
    var sovereignty_quotient_percent: Double = 0
    var sovereignty_quotient_blended_percent: Double = 0
    var deep_work_sessions_logged: Int = 0
    var execution_mix_total: Int = 0
    var utility_tagged_open_count: Int = 0
    var sovereignty_line: String = ""
    var operational_authority_line: String = ""
    var financial_sovereignty_line: String = ""
    var physical_baseline_line: String = ""
}

struct VanguardExecutedDTO: Codable, Sendable {
    var deep: Int = 0
    var mixed: Int = 0
    var shallow: Int = 0
}

struct DeadBugAlertDTO: Codable, Sendable {
    var project_id: String = ""
    var project_name: String = ""
    var title_hint: String = ""
}

struct RunwayPayloadDTO: Codable, Sendable {
    var notification_markdown: String = ""
    var prep_gap_minutes: Int = 0
    var default_wake_iso: String = ""
    var runway_conflict: Bool = false
    var operator_display: String = "You"
    var conflict_summary: String?
}

/// Subset of server `schedule_day_signals` (daily schedule read).
struct ScheduleDaySignalsDTO: Codable, Sendable {
    var summary_line: String = ""
    var meeting_load_warning: Bool = false
    var fragmented_day: Bool = false
}

struct CockpitResponseDTO: Codable, Sendable {
    var date: String
    /// Full purpose text from `identity.json`; client may show one random sentence on launch.
    var identity_purpose: String = ""
    var google_calendar_connected: Bool = false
    var executive_score_percent: Double = 0
    var execution_day_summary: String = ""
    var vanguard_executed: VanguardExecutedDTO = .init()
    var runway: RunwayPayloadDTO = .init()
    var sovereignty: SovereigntyPayloadDTO = .init()
    var air_gap_active: Bool = false
    var midday_shield_active: Bool = false
    var identity_alignment_window_active: Bool = false
    var todoist_inbox_open_count: Int = 0
    var inbox_slaughter_gate_ok: Bool = false
    var dead_bug_alerts: [DeadBugAlertDTO] = []
    var firefighting_signals: [String] = []
    var firewall_audit_summary: String = ""
    var schedule_day_signals: ScheduleDaySignalsDTO = .init()
    var integrity_sentry_state: String = "NOMINAL"
    var ragstone_ledger: [String: AnyCodableJSON] = [:]
}

struct MobileDashboardDTO: Codable, Sendable {
    var cockpit: CockpitResponseDTO
    var ragstone_line: String = ""
    var qbo_line: String = ""
}

struct PowerTrioSlotDTO: Codable, Sendable {
    var slot: Int = 0
    var label: String = ""
    var task_id: String = ""
    var title: String = ""
    var description: String = ""
    var project_name: String = ""
    var priority: Int = 1
    var tactical_steps: [String] = []
}

struct PowerTrioViewDTO: Codable, Sendable {
    var slots: [PowerTrioSlotDTO] = []
    var ranked_total: Int = 0
    var task_total: Int = 0
    var rank_warning: String = ""
    var merge_note: String = ""
    var last_sync_iso: String = ""
    var last_rank_iso: String = ""
    var recon_day: String = ""
}

struct MobileReadinessDTO: Codable, Sendable {
    var ok: Bool = true
    var api_ready: Bool = true
    var mobile_routes_ready: Bool = true
    var api_key_required: Bool = false
    var gemini_configured: Bool = false
    var google_calendar_connected: Bool = false
    var personal_calendar_configured: Bool = false
    var personal_calendar_mode: String = "none"
}

struct MobileDayPlanBlockDTO: Codable, Sendable, Hashable {
    var id: String = ""
    var title: String = ""
    var start_label: String = ""
    var end_label: String = ""
    var reason: String = ""
    var status: String = "planned"
}

struct MobileDayPlanDTO: Codable, Sendable {
    var plan_id: String = ""
    var day: String = ""
    var summary: String = ""
    var reason: String = ""
    var generated_by: String = "fallback"
    var blocks: [MobileDayPlanBlockDTO] = []
    var accepted: Bool = false
    var updated_at: String = ""
}

/// Decodes arbitrary JSON object values for `ragstone_ledger` and similar dicts.
enum AnyCodableJSON: Codable, Sendable, Equatable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case object([String: AnyCodableJSON])
    case array([AnyCodableJSON])
    case null

    /// Bridges `JSONSerialization` / Python payloads that may not match strict `JSONDecoder` expectations.
    init(jsonValue: Any) {
        switch jsonValue {
        case is NSNull:
            self = .null
        case let b as Bool:
            self = .bool(b)
        case let n as NSNumber:
            if CFGetTypeID(n) == CFBooleanGetTypeID() {
                self = .bool(n.boolValue)
                return
            }
            let d = n.doubleValue
            if d.isNaN || d.isInfinite {
                self = .double(d)
                return
            }
            let rounded = d.rounded()
            if abs(d - rounded) < 1e-9, d >= Double(Int.min), d <= Double(Int.max) {
                self = .int(Int(rounded))
            } else {
                self = .double(d)
            }
        case let i as Int:
            self = .int(i)
        case let d as Double:
            self = .double(d)
        case let s as String:
            self = .string(s)
        case let arr as [Any]:
            self = .array(arr.map { AnyCodableJSON(jsonValue: $0) })
        case let dict as [String: Any]:
            self = .object(dict.mapValues { AnyCodableJSON(jsonValue: $0) })
        default:
            self = .string(String(describing: jsonValue))
        }
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() {
            self = .null
            return
        }
        if let v = try? c.decode(Bool.self) {
            self = .bool(v)
            return
        }
        // Prefer Double before Int so fractional JSON numbers decode; whole numbers map to `.int` for display.
        if let v = try? c.decode(Double.self) {
            if !v.isNaN, !v.isInfinite {
                let rounded = v.rounded()
                if abs(v - rounded) < 1e-9, v >= Double(Int.min), v <= Double(Int.max) {
                    self = .int(Int(rounded))
                    return
                }
            }
            self = .double(v)
            return
        }
        if let v = try? c.decode(Int.self) {
            self = .int(v)
            return
        }
        if let v = try? c.decode(String.self) {
            self = .string(v)
            return
        }
        if let v = try? c.decode([String: AnyCodableJSON].self) {
            self = .object(v)
            return
        }
        if let v = try? c.decode([AnyCodableJSON].self) {
            self = .array(v)
            return
        }
        throw DecodingError.dataCorruptedError(in: c, debugDescription: "Unsupported JSON")
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .string(let s): try c.encode(s)
        case .int(let i): try c.encode(i)
        case .double(let d): try c.encode(d)
        case .bool(let b): try c.encode(b)
        case .object(let o): try c.encode(o)
        case .array(let a): try c.encode(a)
        case .null: try c.encodeNil()
        }
    }
}

struct RagstoneLedgerResponseDTO: Codable, Sendable {
    var version: Int?
    var revenue_ytd_usd: Double?
    var cash_balance_usd: Double?
    var monthly_burn_usd: Double?
    var cash_runway_months: Double?
    var yoy_revenue_growth_percent: Double?
}

struct OpportunityCostResponseDTO: Codable, Sendable {
    var ok: Bool
    var error: String
    var narrative: String
    var cuts: [String]
}

struct QBOStatusDTO: Codable, Sendable {
    var status: String
    var message: String
}

struct WindshieldTriageResponseDTO: Codable, Sendable {
    var ok: Bool
    var error: String
    var verdict: String
    var one_line_reason: String
}
