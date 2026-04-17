import SwiftUI

/// Windshield triage + opportunity cost (thin clients to FastAPI).
struct ToolsFlowsView: View {
    @State private var coachTitle = ""
    @State private var coachNotes = ""
    @State private var coachMinutes: Int?
    @State private var coachResult: String?
    @State private var windshieldText = ""
    @State private var windshieldResult: String?
    @State private var windshieldLoading = false

    private let api = CockpitAPIClient()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                GroupBox("Windshield triage") {
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("Paste distraction or request", text: $windshieldText, axis: .vertical)
                            .lineLimit(3 ... 6)
                        Button("Classify") {
                            Task {
                                windshieldLoading = true
                                windshieldResult = nil
                                defer { windshieldLoading = false }
                                do {
                                    let r = try await api.postWindshieldTriage(text: windshieldText, mode: "windshield")
                                    windshieldResult = r.ok
                                        ? "\(r.verdict): \(r.one_line_reason)"
                                        : (r.error.isEmpty ? "Error" : r.error)
                                } catch {
                                    windshieldResult = error.localizedDescription
                                }
                            }
                        }
                        .disabled(windshieldText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || windshieldLoading)
                        if let windshieldResult {
                            Text(windshieldResult)
                                .font(.caption)
                        }
                    }
                }
                GroupBox("Opportunity cost") {
                    VStack(alignment: .leading, spacing: 8) {
                        TextField("Task title", text: $coachTitle)
                        TextField("Notes (optional)", text: $coachNotes, axis: .vertical)
                            .lineLimit(2 ... 4)
                        HStack {
                            Text("Minutes")
                            TextField("—", value: $coachMinutes, format: .number)
                                .keyboardType(.numberPad)
                                .frame(maxWidth: 80)
                        }
                        Button("Analyze") {
                            Task {
                                do {
                                    let r = try await api.postOpportunityCost(
                                        title: coachTitle,
                                        notes: coachNotes,
                                        estimatedMinutes: coachMinutes
                                    )
                                    coachResult = r.ok ? r.narrative : r.error
                                } catch {
                                    coachResult = error.localizedDescription
                                }
                            }
                        }
                        .disabled(coachTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        if let coachResult {
                            Text(coachResult)
                                .font(.caption)
                        }
                    }
                }
            }
            .padding()
        }
    }
}
