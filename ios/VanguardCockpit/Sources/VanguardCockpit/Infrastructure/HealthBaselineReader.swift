import Combine
import Foundation
import HealthKit
import SwiftUI

/// Optional HealthKit reads for physical baseline lines on the dashboard (foreground).
@MainActor
final class HealthBaselineReader: ObservableObject {
    private let store = HKHealthStore()
    @Published var authorizationDenied = false
    @Published var lastSummaryLine: String = ""

    func requestAndFetchBaselines() {
        guard HKHealthStore.isHealthDataAvailable() else {
            lastSummaryLine = "Health data not available"
            return
        }
        guard let stepType = HKObjectType.quantityType(forIdentifier: .stepCount) else {
            lastSummaryLine = "—"
            return
        }
        let types: Set<HKObjectType> = [stepType]
        store.requestAuthorization(toShare: nil, read: types) { [weak self] ok, _ in
            Task { @MainActor in
                guard let self else { return }
                if !ok {
                    self.authorizationDenied = true
                    return
                }
                self.lastSummaryLine = await self.fetchStepsLine()
            }
        }
    }

    private func fetchStepsLine() async -> String {
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            return "—"
        }
        let cal = Calendar.current
        let start = cal.startOfDay(for: Date())
        let pred = HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate)
        return await withCheckedContinuation { cont in
            let q = HKStatisticsQuery(quantityType: stepType, quantitySamplePredicate: pred, options: .cumulativeSum) { _, stats, _ in
                let steps = stats?.sumQuantity()?.doubleValue(for: HKUnit.count()) ?? 0
                cont.resume(returning: "Steps today: \(Int(steps))")
            }
            self.store.execute(q)
        }
    }
}
