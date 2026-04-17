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
            } else if let err = error {
                Text(err).foregroundStyle(.red).font(.caption)
            } else if let t = trio {
                List {
                    Section("Recon \(t.recon_day.isEmpty ? "—" : t.recon_day)") {
                        Text("Tasks \(t.task_total) · ranked \(t.ranked_total)")
                            .font(.caption)
                        if !t.rank_warning.isEmpty {
                            Text(t.rank_warning).font(.caption2).foregroundStyle(.orange)
                        }
                    }
                    ForEach(Array(t.slots.enumerated()), id: \.offset) { _, slot in
                        Section(slot.label) {
                            Text(slot.title).font(.headline)
                            if !slot.description.isEmpty {
                                Text(slot.description).font(.caption)
                            }
                            if !slot.tactical_steps.isEmpty {
                                ForEach(slot.tactical_steps, id: \.self) { step in
                                    Text("• \(step)").font(.caption2)
                                }
                            }
                        }
                    }
                }
            } else {
                Text("No data").font(.caption).foregroundStyle(.secondary)
            }
        }
        .navigationTitle("Power Trio")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button("Reload") { Task { await load() } }
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
