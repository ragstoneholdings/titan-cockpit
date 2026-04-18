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
    @State private var planDayText = ""
    @State private var planObjective = ""
    @State private var planReason = ""
    @State private var planResult: String?
    @State private var dayPlan: MobileDayPlanDTO?
    @State private var readiness: MobileReadinessDTO?
    @State private var assistantBusy = false

    private let api = CockpitAPIClient()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    CockpitPanel(kicker: "Windshield", title: "Triage") {
                        VStack(alignment: .leading, spacing: 10) {
                            TextField("Paste distraction or request", text: $windshieldText, axis: .vertical)
                                .lineLimit(3 ... 6)
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
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
                            .cockpitPrimaryButtonStyle()
                            .disabled(windshieldText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || windshieldLoading)
                            .help(windshieldText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                ? "Enter text to classify"
                                : (windshieldLoading ? "Classifying…" : "Send to cockpit API"))

                            if let windshieldResult {
                                Text(windshieldResult)
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                        }
                    }

                    CockpitPanel(kicker: "Coach", title: "Opportunity cost") {
                        VStack(alignment: .leading, spacing: 10) {
                            TextField("Task title", text: $coachTitle)
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
                            TextField("Notes (optional)", text: $coachNotes, axis: .vertical)
                                .lineLimit(2 ... 4)
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
                            HStack {
                                Text("Minutes")
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                                TextField("—", value: $coachMinutes, format: .number)
                                    .keyboardType(.numberPad)
                                    .frame(maxWidth: 80)
                                    .textFieldStyle(.plain)
                                    .foregroundStyle(CockpitTheme.mist)
                                    .multilineTextAlignment(.trailing)
                                    .padding(8)
                                    .background(CockpitTheme.charcoal850)
                                    .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: 8, style: .continuous)
                                            .stroke(CockpitTheme.divider, lineWidth: 1)
                                    )
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
                            .cockpitPrimaryButtonStyle()
                            .disabled(coachTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                            .help(coachTitle.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                ? "Enter a task title"
                                : "Request opportunity cost narrative")

                            if let coachResult {
                                Text(coachResult)
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                        }
                    }

                    CockpitPanel(kicker: "Assistant", title: "Calendar plan") {
                        VStack(alignment: .leading, spacing: 10) {
                            TextField("Recon day YYYY-MM-DD (optional)", text: $planDayText)
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
                            TextField("Primary objective", text: $planObjective, axis: .vertical)
                                .lineLimit(1 ... 3)
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
                            TextField("Replan reason (optional)", text: $planReason, axis: .vertical)
                                .lineLimit(1 ... 2)
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
                            HStack(spacing: 8) {
                                Button("Readiness") {
                                    Task { await loadReadiness() }
                                }
                                .buttonStyle(CockpitSecondaryButtonStyle())
                                .disabled(assistantBusy)
                                Button("Generate") {
                                    Task { await generatePlan() }
                                }
                                .cockpitPrimaryButtonStyle()
                                .disabled(assistantBusy)
                                Button("Replan") {
                                    Task { await replanNow() }
                                }
                                .buttonStyle(CockpitSecondaryButtonStyle())
                                .disabled(assistantBusy)
                            }
                            if let readiness {
                                Text("Gemini \(readiness.gemini_configured ? "on" : "off") · Google \(readiness.google_calendar_connected ? "on" : "off") · Personal \(readiness.personal_calendar_mode)")
                                    .font(.caption2)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                            if let planResult {
                                Text(planResult)
                                    .font(.caption2)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                            if let plan = dayPlan {
                                Text("Plan \(plan.day) · \(plan.accepted ? "accepted" : "pending")")
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mist)
                                if !plan.summary.isEmpty {
                                    Text(plan.summary)
                                        .font(.caption2)
                                        .foregroundStyle(CockpitTheme.mistMuted)
                                }
                                HStack(spacing: 8) {
                                    Button("Accept") {
                                        Task { await acceptPlan(plan) }
                                    }
                                    .buttonStyle(CockpitSecondaryButtonStyle())
                                    .disabled(assistantBusy || plan.plan_id.isEmpty)
                                    Button("Refresh plan") {
                                        Task { await fetchPlan() }
                                    }
                                    .buttonStyle(CockpitSecondaryButtonStyle())
                                    .disabled(assistantBusy)
                                }
                                ForEach(plan.blocks, id: \.id) { block in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text("\(block.start_label)–\(block.end_label) \(block.title)")
                                            .font(.caption)
                                            .foregroundStyle(CockpitTheme.mist)
                                        if !block.reason.isEmpty {
                                            Text(block.reason)
                                                .font(.caption2)
                                                .foregroundStyle(CockpitTheme.mistMuted)
                                        }
                                        HStack(spacing: 8) {
                                            Button("Done") {
                                                Task { await markBlock(block, status: "completed") }
                                            }
                                            .buttonStyle(CockpitSecondaryButtonStyle())
                                            .disabled(assistantBusy)
                                            Button("Skip") {
                                                Task { await markBlock(block, status: "skipped") }
                                            }
                                            .buttonStyle(CockpitSecondaryButtonStyle())
                                            .disabled(assistantBusy)
                                        }
                                    }
                                    .padding(.vertical, 4)
                                }
                            }
                        }
                    }
                }
                .padding()
            }
            .scrollContentBackground(.hidden)
            .navigationTitle("Tools")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button("Clear fields") {
                            clearFields()
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .help("Tools actions")
                }
            }
        }
    }

    private func clearFields() {
        coachTitle = ""
        coachNotes = ""
        coachMinutes = nil
        coachResult = nil
        windshieldText = ""
        windshieldResult = nil
        planDayText = ""
        planObjective = ""
        planReason = ""
        planResult = nil
        dayPlan = nil
        readiness = nil
    }

    private func normalizedDay() -> String? {
        let t = planDayText.trimmingCharacters(in: .whitespacesAndNewlines)
        return t.isEmpty ? nil : t
    }

    private func effectiveDay() -> String {
        if let d = normalizedDay() { return d }
        return String(Date.now.ISO8601Format().prefix(10))
    }

    private func loadReadiness() async {
        assistantBusy = true
        defer { assistantBusy = false }
        do {
            readiness = try await api.fetchMobileReadiness()
            planResult = nil
        } catch {
            planResult = error.localizedDescription
        }
    }

    private func fetchPlan() async {
        assistantBusy = true
        defer { assistantBusy = false }
        do {
            dayPlan = try await api.fetchDayPlan(day: normalizedDay())
            planResult = nil
        } catch {
            planResult = error.localizedDescription
        }
    }

    private func generatePlan() async {
        assistantBusy = true
        defer { assistantBusy = false }
        do {
            dayPlan = try await api.generateDayPlan(day: normalizedDay(), objective: planObjective)
            planResult = "Plan generated."
        } catch {
            planResult = error.localizedDescription
        }
    }

    private func replanNow() async {
        assistantBusy = true
        defer { assistantBusy = false }
        do {
            dayPlan = try await api.replanDay(day: normalizedDay(), reason: planReason)
            planResult = "Replan ready."
        } catch {
            planResult = error.localizedDescription
        }
    }

    private func acceptPlan(_ plan: MobileDayPlanDTO) async {
        assistantBusy = true
        defer { assistantBusy = false }
        do {
            try await api.acceptDayPlan(day: plan.day, planId: plan.plan_id)
            dayPlan = try await api.fetchDayPlan(day: plan.day)
            planResult = "Plan accepted."
        } catch {
            planResult = error.localizedDescription
        }
    }

    private func markBlock(_ block: MobileDayPlanBlockDTO, status: String) async {
        assistantBusy = true
        defer { assistantBusy = false }
        do {
            try await api.postDayPlanEvent(day: effectiveDay(), blockId: block.id, status: status, reason: planReason)
            dayPlan = try await api.fetchDayPlan(day: normalizedDay())
            planResult = "\(status.capitalized) \(block.title)"
        } catch {
            planResult = error.localizedDescription
        }
    }
}
