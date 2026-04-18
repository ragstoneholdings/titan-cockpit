import FamilyControls
import SwiftData
import SwiftUI

struct ContentView: View {
    @Environment(\.modelContext) private var modelContext
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var vm = CockpitViewModel()
    @State private var fc = FamilyControlsAuth()
    @State private var shields = ShieldManager()
    @State private var reconDayText = ""
    @State private var notificationsOn = false
    @StateObject private var health = HealthBaselineReader()
    @StateObject private var doorway = DoorwayGeofenceService()
    @State private var purposeSplashSessionHandled = false
    @State private var purposeSplashLine = ""
    @State private var purposeSplashOpacity: Double = 0
    @State private var purposeSplashScale: Double = 1.0

    var body: some View {
        ZStack {
            TabView {
                NavigationStack {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 16) {
                            if let err = vm.lastError {
                                Text(err)
                                    .font(.caption)
                                    .foregroundStyle(Color.orange)
                            }
                            reconDayRow
                            DashboardView(cockpit: vm.cockpit, ragstoneLine: vm.ragstoneLine, qboLine: vm.qboLine, reconDay: vm.reconDay)
                        }
                        .padding()
                    }
                    .scrollContentBackground(.hidden)
                    .navigationTitle("Cockpit")
                    .toolbar {
                        ToolbarItem(placement: .primaryAction) {
                            Button {
                                Task { await refreshCockpit() }
                            } label: {
                                Image(systemName: "arrow.clockwise")
                            }
                            .help("Refresh cockpit data")
                        }
                        ToolbarItem(placement: .automatic) {
                            Menu {
                                Button("Today") {
                                    reconDayText = ""
                                    vm.reconDay = nil
                                    Task { await refreshCockpit() }
                                }
                                Button("Load recon date") {
                                    let t = reconDayText.trimmingCharacters(in: .whitespacesAndNewlines)
                                    vm.reconDay = t.isEmpty ? nil : t
                                    Task { await refreshCockpit() }
                                }
                            } label: {
                                Image(systemName: "ellipsis.circle")
                            }
                            .help("Recon day actions")
                        }
                    }
                }
                .tabItem { Label("Dashboard", systemImage: "scope") }

                ToolsFlowsView()
                    .tabItem { Label("Tools", systemImage: "wrench.and.screwdriver.fill") }

                SettingsFlowsView(
                    vm: vm,
                    fc: fc,
                    shields: shields,
                    notificationsOn: $notificationsOn,
                    health: health,
                    doorway: doorway
                )
                .tabItem { Label("Settings", systemImage: "gearshape.2") }
            }
            .tint(CockpitTheme.industrialAmber)

            if !purposeSplashLine.isEmpty {
                CockpitTheme.charcoal1000
                    .ignoresSafeArea()
                    .overlay {
                        ZStack {
                            RadialGradient(
                                colors: [CockpitTheme.industrialAmber.opacity(0.08), .clear],
                                center: .center,
                                startRadius: 8,
                                endRadius: 220
                            )
                            .ignoresSafeArea()

                            Text(purposeSplashLine)
                                .font(.system(size: 26, weight: .semibold, design: .serif))
                                .italic()
                                .lineLimit(1)
                                .minimumScaleFactor(0.72)
                                .truncationMode(.tail)
                                .multilineTextAlignment(.center)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(.horizontal, 26)
                                .scaleEffect(purposeSplashScale)
                        }
                    }
                    .opacity(purposeSplashOpacity)
                    .allowsHitTesting(purposeSplashOpacity > 0.05)
                    .accessibilityAddTraits(.isStaticText)
            }
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
        .onChange(of: vm.isLoading) { wasLoading, loading in
            if wasLoading, !loading {
                evaluatePurposeSplashAfterLoad()
            }
        }
    }

    private var reconDayRow: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Recon")
                .cockpitKickerStyle()
            TextField("YYYY-MM-DD (optional)", text: $reconDayText)
                .textFieldStyle(.plain)
                .font(.body.monospacedDigit())
                .foregroundStyle(CockpitTheme.mist)
                .padding(10)
                .background(CockpitTheme.charcoal850)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .stroke(CockpitTheme.divider, lineWidth: 1)
                )
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
        }
    }

    private func refreshCockpit() async {
        await vm.refresh()
        if let c = vm.cockpit {
            vm.applyToSnapshot(modelContext, from: c)
        }
        vm.syncDistractionShields(shields: shields, selection: fc.selection)
    }

    /// One full-screen purpose line after the first successful dashboard load each app launch; no repeat on refresh.
    private func evaluatePurposeSplashAfterLoad() {
        guard !purposeSplashSessionHandled else { return }
        guard vm.lastError == nil else { return }
        purposeSplashSessionHandled = true
        guard let line = PurposeSentencePicker.randomSentence(from: vm.cockpit?.identity_purpose ?? "") else { return }
        purposeSplashLine = line
        purposeSplashScale = 1.0
        purposeSplashOpacity = 1
        let rm = reduceMotion
        Task { @MainActor in
            let holdNs: UInt64 = rm ? 90_000_000 : 1_350_000_000
            try? await Task.sleep(nanoseconds: holdNs)
            let fadeSeconds = rm ? 0.08 : 0.38
            withAnimation(.easeOut(duration: fadeSeconds)) {
                purposeSplashOpacity = 0
                purposeSplashScale = rm ? 1.0 : 1.01
            }
            try? await Task.sleep(nanoseconds: UInt64(fadeSeconds * 1_000_000_000))
            purposeSplashLine = ""
        }
    }
}

#Preview {
    let schema = Schema([SovereigntySnapshot.self])
    let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: true)
    let container = try! ModelContainer(for: schema, configurations: [config])
    return ContentView()
        .modelContainer(container)
        .preferredColorScheme(.dark)
        .cockpitRootBackground()
}
