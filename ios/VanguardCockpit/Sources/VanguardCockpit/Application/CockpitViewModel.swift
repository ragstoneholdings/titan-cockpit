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
    /// One line from mobile dashboard payload when available.
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
            let dashboard = try await api.fetchMobileDashboard(day: d)
            cockpit = dashboard.cockpit
            ragstoneLine = dashboard.ragstone_line
            qboLine = dashboard.qbo_line
        } catch {
            lastError = error.localizedDescription
            return
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

}
