import FamilyControls
import SwiftData
import SwiftUI

struct ContentView: View {
    @Environment(\.modelContext) private var modelContext
    @State private var vm = CockpitViewModel()
    @State private var fc = FamilyControlsAuth()
    @State private var shields = ShieldManager()
    @State private var reconDayText = ""
    @State private var notificationsOn = false
    @StateObject private var health = HealthBaselineReader()
    @StateObject private var doorway = DoorwayGeofenceService()

    var body: some View {
        TabView {
            NavigationStack {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        if let err = vm.lastError {
                            Text(err)
                                .foregroundStyle(.red)
                                .font(.caption)
                        }
                        reconDayRow
                        DashboardView(cockpit: vm.cockpit, ragstoneLine: vm.ragstoneLine, qboLine: vm.qboLine, reconDay: vm.reconDay)
                    }
                    .padding()
                }
                .navigationTitle("Cockpit")
                .toolbar {
                    ToolbarItem(placement: .primaryAction) {
                        Button("Refresh") {
                            Task { await refreshCockpit() }
                        }
                    }
                }
            }
            .tabItem { Label("Dashboard", systemImage: "gauge.with.dots.needle.67percent") }

            ToolsFlowsView()
                .tabItem { Label("Tools", systemImage: "wrench.and.screwdriver") }

            SettingsFlowsView(
                vm: vm,
                fc: fc,
                shields: shields,
                notificationsOn: $notificationsOn,
                health: health,
                doorway: doorway
            )
            .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .task {
            fc.refreshStatus()
            await refreshCockpit()
            if fc.authorizationStatus == .approved {
                try? DeviceActivityScheduler.registerAll()
            }
        }
        .onChange(of: fc.authorizationStatus) { _, s in
            if s == .approved {
                try? DeviceActivityScheduler.registerAll()
            }
        }
        .onChange(of: vm.cockpit?.inbox_slaughter_gate_ok) { _, _ in
            vm.syncDistractionShields(shields: shields, selection: fc.selection)
        }
        .onReceive(Timer.publish(every: 60, on: .main, in: .common).autoconnect()) { _ in
            vm.syncDistractionShields(shields: shields, selection: fc.selection)
        }
    }

    private var reconDayRow: some View {
        HStack(spacing: 8) {
            TextField("Recon day (YYYY-MM-DD)", text: $reconDayText)
                .textFieldStyle(.roundedBorder)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Button("Today") {
                reconDayText = ""
                vm.reconDay = nil
                Task { await refreshCockpit() }
            }
            .font(.caption)
            Button("Load") {
                let t = reconDayText.trimmingCharacters(in: .whitespacesAndNewlines)
                vm.reconDay = t.isEmpty ? nil : t
                Task { await refreshCockpit() }
            }
            .font(.caption)
        }
    }

    private func refreshCockpit() async {
        await vm.refresh()
        if let c = vm.cockpit {
            vm.applyToSnapshot(modelContext, from: c)
        }
        vm.syncDistractionShields(shields: shields, selection: fc.selection)
    }
}

#Preview {
    let schema = Schema([SovereigntySnapshot.self])
    let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
    let container = try! ModelContainer(for: schema, configurations: [config])
    return ContentView()
        .modelContainer(container)
}
