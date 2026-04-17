import FamilyControls
import Foundation
import Observation
import SwiftData

@Observable
@MainActor
final class CockpitViewModel {
    var isLoading = false
    var lastError: String?
    var cockpit: CockpitResponseDTO?
    var ragstoneLine: String = ""
    /// One line from `GET /api/qbo/status` when available.
    var qboLine: String = ""
    /// `nil` = server default (usually today).
    var reconDay: String?

    private let api = CockpitAPIClient()

    func refresh(day: String? = nil) async {
        isLoading = true
        lastError = nil
        defer { isLoading = false }
        let d = day ?? reconDay
        qboLine = ""
        do {
            cockpit = try await api.fetchCockpit(day: d)
            let ledger = try await api.fetchRagstoneLedger()
            ragstoneLine = Self.formatLedgerLine(ledger)
            if let q = try? await api.fetchQBOStatus() {
                let msg = q.message.trimmingCharacters(in: .whitespacesAndNewlines)
                qboLine = msg.isEmpty ? q.status : "\(q.status): \(msg)"
            }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func syncDistractionShields(shields: ShieldManager, selection: FamilyActivitySelection) {
        let should = DistractionShieldPolicy.shouldApplyDistractionShields(cockpit: cockpit)
        DistractionShieldPolicy.apply(shouldApply: should, selection: selection, shields: shields)
    }

    func applyToSnapshot(_ context: ModelContext, from dto: CockpitResponseDTO) {
        let s = dto.sovereignty
        let snap = SovereigntySnapshot(
            capturedAt: Date(),
            sovereigntyQuotientPercent: s.sovereignty_quotient_percent,
            sovereigntyQuotientBlendedPercent: s.sovereignty_quotient_blended_percent,
            sovereigntyLine: s.sovereignty_line,
            operationalAuthorityLine: s.operational_authority_line,
            financialSovereigntyLine: s.financial_sovereignty_line,
            physicalBaselineLine: s.physical_baseline_line
        )
        context.insert(snap)
        try? context.save()
    }

    private static func formatLedgerLine(_ ledger: [String: AnyCodableJSON]) -> String {
        func num(_ k: String) -> String {
            guard let v = ledger[k] else { return "—" }
            switch v {
            case .double(let d): return String(format: "%.1f", d)
            case .int(let i): return "\(i)"
            default: return "—"
            }
        }
        let runway = num("cash_runway_months")
        let yoy = num("yoy_revenue_growth_percent")
        return "Runway \(runway) mo · YoY \(yoy)%"
    }
}
