import SwiftUI

struct PowerTrioView: View {
    var reconDay: String?
    @State private var trio: PowerTrioViewDTO?
    @State private var error: String?
    @State private var loading = false

    private let api = CockpitAPIClient()

    var body: some View {
        Group {
            if loading {
                ProgressView()
                    .tint(CockpitTheme.industrialAmber)
            } else if let err = error {
                Text(err)
                    .foregroundStyle(CockpitTheme.industrialAmber)
                    .font(.caption)
            } else if let t = trio {
                List {
                    Section {
                        Text("Tasks \(t.task_total) · ranked \(t.ranked_total)")
                            .font(.caption)
                            .foregroundStyle(CockpitTheme.mistMuted)
                            .monospacedDigit()
                        if !t.rank_warning.isEmpty {
                            Text(t.rank_warning)
                                .font(.caption2)
                                .foregroundStyle(CockpitTheme.industrialAmber)
                        }
                    } header: {
                        Text("Recon \(t.recon_day.isEmpty ? "—" : t.recon_day)")
                            .cockpitKickerStyle()
                            .textCase(nil)
                            .foregroundStyle(CockpitTheme.mistMuted)
                    }
                    .listRowBackground(CockpitTheme.charcoal950)

                    ForEach(Array(t.slots.enumerated()), id: \.offset) { _, slot in
                        Section {
                            Text(slot.title)
                                .font(.headline)
                                .foregroundStyle(CockpitTheme.mist)
                            if !slot.description.isEmpty {
                                Text(slot.description)
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                            if !slot.tactical_steps.isEmpty {
                                ForEach(slot.tactical_steps, id: \.self) { step in
                                    Text("• \(step)")
                                        .font(.caption2)
                                        .foregroundStyle(CockpitTheme.mistMuted)
                                }
                            }
                        } header: {
                            Text(slot.label)
                                .cockpitKickerStyle()
                                .textCase(nil)
                                .foregroundStyle(CockpitTheme.mistMuted)
                        }
                        .listRowBackground(CockpitTheme.charcoal950)
                    }
                }
                .listStyle(.insetGrouped)
                .scrollContentBackground(.hidden)
            } else {
                Text("No data")
                    .cockpitBodySecondary()
            }
        }
        .cockpitRootBackground()
        .navigationTitle("Power Trio")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    Task { await load() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("Reload Power Trio")
            }
        }
    }

    private func load() async {
        loading = true
        error = nil
        defer { loading = false }
        do {
            trio = try await api.fetchPowerTrio(day: reconDay)
        } catch let err {
            error = err.localizedDescription
        }
    }
}
