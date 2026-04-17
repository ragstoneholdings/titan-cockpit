import Foundation

enum CockpitAPIError: Error, LocalizedError {
    case invalidURL
    case http(Int, String)
    case decode(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid API URL."
        case .http(let c, let b): return "HTTP \(c): \(b)"
        case .decode(let e): return "Decode: \(e.localizedDescription)"
        }
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

    func fetchCockpit(day: String?) async throws -> CockpitResponseDTO {
        var comp = URLComponents(url: base.appendingPathComponent("api/cockpit"), resolvingAgainstBaseURL: false)!
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
            return try dec.decode(CockpitResponseDTO.self, from: data)
        } catch {
            throw CockpitAPIError.decode(error)
        }
    }

    /// `GET /api/vanguard/ragstone-ledger` — merged bundle + computed KPIs.
    func fetchRagstoneLedger() async throws -> [String: AnyCodableJSON] {
        let url = base.appendingPathComponent("api/vanguard/ragstone-ledger")
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        do {
            return try JSONDecoder().decode([String: AnyCodableJSON].self, from: data)
        } catch {
            throw CockpitAPIError.decode(error)
        }
    }

    /// `GET /api/qbo/status` — OAuth remains server-side; this is a health/strategy signal only.
    func fetchQBOStatus() async throws -> QBOStatusDTO {
        let url = base.appendingPathComponent("api/qbo/status")
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        applyAuth(&req)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw CockpitAPIError.http(-1, "") }
        guard (200 ... 299).contains(http.statusCode) else {
            throw CockpitAPIError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(QBOStatusDTO.self, from: data)
    }

    func postOpportunityCost(title: String, notes: String, estimatedMinutes: Int?) async throws -> OpportunityCostResponseDTO {
        let url = base.appendingPathComponent("api/vanguard/opportunity-cost")
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

    /// `GET /api/todoist/power-trio`
    func fetchPowerTrio(day: String?) async throws -> PowerTrioViewDTO {
        var comp = URLComponents(url: base.appendingPathComponent("api/todoist/power-trio"), resolvingAgainstBaseURL: false)!
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

    /// `POST /api/vanguard/windshield-triage`
    func postWindshieldTriage(text: String, mode: String = "windshield") async throws -> WindshieldTriageResponseDTO {
        let url = base.appendingPathComponent("api/vanguard/windshield-triage")
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
}
