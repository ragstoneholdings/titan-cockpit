import Foundation

enum CockpitAPIError: Error, LocalizedError {
    case invalidURL
    case http(Int, String)
    case decodeCockpit(Error, responseSnippet: String?)
    case decodeRagstoneLedger(Error, responseSnippet: String?)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid API URL."
        case .http(let c, let b):
            if c == 404 {
                return "API route not found (HTTP 404). Verify backend includes /api/mobile/* routes and COCKPIT_API_BASE points to the same deployment."
            }
            if c == 401 || c == 403 {
                return "Auth rejected (HTTP \(c)). Verify COCKPIT_API_KEY / X-Cockpit-Key."
            }
            if c == 422 {
                return "Invalid request (HTTP 422). For recon day, use YYYY-MM-DD."
            }
            return "HTTP \(c): \(b)"
        case .decodeCockpit(let e, let snippet):
            return Self.decodeMessage(label: "cockpit", error: e, snippet: snippet)
        case .decodeRagstoneLedger(let e, let snippet):
            return Self.decodeMessage(label: "ragstone-ledger", error: e, snippet: snippet)
        }
    }

    private static func decodeMessage(label: String, error: Error, snippet: String?) -> String {
        var msg = "Decode (\(label)): \(error.localizedDescription)"
        #if DEBUG
        if let snippet, !snippet.isEmpty {
            msg += " — body: \(snippet)"
        }
        #endif
        return msg
    }
}

/// Read-only client for Titan Cockpit FastAPI (`docs/COCKPIT_DEV.md`).
actor CockpitAPIClient {
    private let base: URL
    private let session: URLSession

    init(baseURL: URL = AppConfig.apiBaseURL, session: URLSession = .shared) {
        self.base = baseURL
        self.session = session
    }

    private func applyAuth(_ req: inout URLRequest) {
        if let k = AppConfig.apiKey, !k.isEmpty {
            req.setValue(k, forHTTPHeaderField: "X-Cockpit-Key")
        }
    }

    func fetchMobileDashboard(day: String?) async throws -> MobileDashboardDTO {
        var comp = URLComponents(url: base.appendingPathComponent("api/mobile/dashboard"), resolvingAgainstBaseURL: false)!
        var q: [URLQueryItem] = []
        if let day {
            q.append(URLQueryItem(name: "day", value: day))
        }
        if !q.isEmpty { comp.queryItems = q }
        guard let url = comp.url else { throw CockpitAPIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        do {
            let dec = JSONDecoder()
            return try dec.decode(MobileDashboardDTO.self, from: data)
        } catch let first {
            if let recovered = try? Self.decodeMobileDashboardWithCockpitRecovery(data: data) {
                return recovered
            }
            throw CockpitAPIError.decodeCockpit(first, responseSnippet: Self.debugResponseSnippet(data))
        }
    }

    func postOpportunityCost(title: String, notes: String, estimatedMinutes: Int?) async throws -> OpportunityCostResponseDTO {
        let url = base.appendingPathComponent("api/mobile/opportunity-cost")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = ["title": title, "notes": notes]
        if let estimatedMinutes {
            body["estimated_minutes"] = estimatedMinutes
        }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(OpportunityCostResponseDTO.self, from: data)
    }

    /// `GET /api/mobile/power-trio`
    func fetchPowerTrio(day: String?) async throws -> PowerTrioViewDTO {
        var comp = URLComponents(url: base.appendingPathComponent("api/mobile/power-trio"), resolvingAgainstBaseURL: false)!
        if let day, !day.isEmpty {
            comp.queryItems = [URLQueryItem(name: "day", value: day)]
        }
        guard let url = comp.url else { throw CockpitAPIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(PowerTrioViewDTO.self, from: data)
    }

    /// `POST /api/device/register` — stores token for server push (requires API key when configured).
    func registerDevicePushToken(hex: String) async throws {
        let url = base.appendingPathComponent("api/device/register")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["device_token_hex": hex, "platform": "ios", "label": ""]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
    }

    /// `POST /api/mobile/windshield-triage`
    func postWindshieldTriage(text: String, mode: String = "windshield") async throws -> WindshieldTriageResponseDTO {
        let url = base.appendingPathComponent("api/mobile/windshield-triage")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["text": text, "mode": mode]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(WindshieldTriageResponseDTO.self, from: data)
    }

    /// `GET /api/mobile/readiness` capability signal.
    func fetchMobileReadiness() async throws -> MobileReadinessDTO {
        let url = base.appendingPathComponent("api/mobile/readiness")
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(MobileReadinessDTO.self, from: data)
    }

    /// `POST /api/mobile/day-plan/generate`
    func generateDayPlan(day: String?, objective: String) async throws -> MobileDayPlanDTO {
        let url = base.appendingPathComponent("api/mobile/day-plan/generate")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = ["objective": objective]
        if let day, !day.isEmpty { body["day"] = day }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(MobileDayPlanDTO.self, from: data)
    }

    /// `POST /api/mobile/day-plan/replan`
    func replanDay(day: String?, reason: String) async throws -> MobileDayPlanDTO {
        let url = base.appendingPathComponent("api/mobile/day-plan/replan")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = ["reason": reason]
        if let day, !day.isEmpty { body["day"] = day }
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(MobileDayPlanDTO.self, from: data)
    }

    /// `POST /api/mobile/day-plan/accept`
    func acceptDayPlan(day: String, planId: String) async throws {
        let url = base.appendingPathComponent("api/mobile/day-plan/accept")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["day": day, "plan_id": planId]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
    }

    /// `GET /api/mobile/day-plan`
    func fetchDayPlan(day: String?) async throws -> MobileDayPlanDTO {
        var comp = URLComponents(url: base.appendingPathComponent("api/mobile/day-plan"), resolvingAgainstBaseURL: false)!
        if let day, !day.isEmpty {
            comp.queryItems = [URLQueryItem(name: "day", value: day)]
        }
        guard let url = comp.url else { throw CockpitAPIError.invalidURL }
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(MobileDayPlanDTO.self, from: data)
    }

    /// `POST /api/mobile/day-plan/event`
    func postDayPlanEvent(day: String, blockId: String, status: String, reason: String = "") async throws {
        let url = base.appendingPathComponent("api/mobile/day-plan/event")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["day": day, "block_id": blockId, "status": status, "reason": reason]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
    }

    nonisolated private static func debugResponseSnippet(_ data: Data) -> String? {
        #if DEBUG
        let prefix = data.prefix(1024)
        guard let s = String(data: prefix, encoding: .utf8), !s.isEmpty else { return nil }
        return s
        #else
        return nil
        #endif
    }

    /// Tries to decode mobile dashboard by recovering nested cockpit payload from loose JSON.
    nonisolated private static func decodeMobileDashboardWithCockpitRecovery(data: Data) throws -> MobileDashboardDTO {
        guard var root = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Mobile dashboard JSON root is not an object.")
            )
        }
        let ragLine = String(describing: root["ragstone_line"] ?? "")
        let qboLine = String(describing: root["qbo_line"] ?? "")
        guard var cockpitObj = root["cockpit"] as? [String: Any] else {
            throw DecodingError.dataCorrupted(
                DecodingError.Context(codingPath: [], debugDescription: "Missing cockpit object in mobile dashboard.")
            )
        }
        let ragRaw = cockpitObj.removeValue(forKey: "ragstone_ledger")
        let trimmedCockpit = try JSONSerialization.data(withJSONObject: cockpitObj)
        var cockpit = try JSONDecoder().decode(CockpitResponseDTO.self, from: trimmedCockpit)
        if let d = ragRaw as? [String: Any] {
            cockpit.ragstone_ledger = d.mapValues { AnyCodableJSON(jsonValue: $0) }
        }
        return MobileDashboardDTO(cockpit: cockpit, ragstone_line: ragLine, qbo_line: qboLine)
    }
}
