import Foundation
import SwiftData

/// Persisted local snapshot; server truth is optional via `CockpitAPIClient`.
@Model
final class SovereigntySnapshot {
    var capturedAt: Date
    var sovereigntyQuotientPercent: Double
    var sovereigntyQuotientBlendedPercent: Double
    var sovereigntyLine: String
    var operationalAuthorityLine: String
    var financialSovereigntyLine: String
    var physicalBaselineLine: String

    init(
        capturedAt: Date = Date(),
        sovereigntyQuotientPercent: Double = 0,
        sovereigntyQuotientBlendedPercent: Double = 0,
        sovereigntyLine: String = "",
        operationalAuthorityLine: String = "",
        financialSovereigntyLine: String = "",
        physicalBaselineLine: String = ""
    ) {
        self.capturedAt = capturedAt
        self.sovereigntyQuotientPercent = sovereigntyQuotientPercent
        self.sovereigntyQuotientBlendedPercent = sovereigntyQuotientBlendedPercent
        self.sovereigntyLine = sovereigntyLine
        self.operationalAuthorityLine = operationalAuthorityLine
        self.financialSovereigntyLine = financialSovereigntyLine
        self.physicalBaselineLine = physicalBaselineLine
    }
}
