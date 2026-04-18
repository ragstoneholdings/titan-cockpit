import FamilyControls
import SwiftUI

struct SettingsFlowsView: View {
    var vm: CockpitViewModel
    @Bindable var fc: FamilyControlsAuth
    var shields: ShieldManager
    @Binding var notificationsOn: Bool
    @ObservedObject var health: HealthBaselineReader
    @ObservedObject var doorway: DoorwayGeofenceService
    @State private var posture = PostureMotionService()
    @State private var haptics = HapticSovereigntyEngine()
    @State private var apiKeyDraft = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    CockpitPanel(kicker: "API", title: "Production auth") {
                        VStack(alignment: .leading, spacing: 10) {
                            SecureField("COCKPIT_API_KEY", text: $apiKeyDraft)
                                .textContentType(.password)
                                .autocorrectionDisabled()
                                .textFieldStyle(.plain)
                                .foregroundStyle(CockpitTheme.mist)
                                .padding(10)
                                .background(CockpitTheme.charcoal850)
                                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                                        .stroke(CockpitTheme.divider, lineWidth: 1)
                                )
                            Button("Save to Keychain") {
                                CockpitKeychain.writeKey(apiKeyDraft)
                            }
                            .cockpitPrimaryButtonStyle()
                            Button("Clear Keychain key") {
                                CockpitKeychain.deleteKey()
                                apiKeyDraft = ""
                            }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                            Text("Xcode scheme env COCKPIT_API_KEY overrides Keychain. Required when server sets COCKPIT_API_KEY.")
                                .font(.caption2)
                                .foregroundStyle(CockpitTheme.mistMuted)
                        }
                    }

                    CockpitPanel(kicker: "Screen Time", title: "Shields & selection") {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(statusLine(fc.authorizationStatus))
                                .font(.caption)
                                .foregroundStyle(CockpitTheme.mistMuted)
                            Button("Request authorization") {
                                Task { await fc.requestAuthorization() }
                            }
                            .cockpitPrimaryButtonStyle()
                            .disabled(fc.authorizationStatus == .approved)
                            .help(fc.authorizationStatus == .approved ? "Already authorized" : "Request Screen Time access")

                            FamilyActivityPicker(selection: $fc.selection)
                                .frame(minHeight: 120)
                                .onChange(of: fc.selection) { _, new in
                                    ScreenTimeSelectionStore.save(new)
                                    vm.syncDistractionShields(shields: shields, selection: new)
                                }
                            Button("Apply shields to selection (manual)") {
                                shields.setShieldedApplications(fc.selection.applicationTokens)
                            }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                            .disabled(fc.authorizationStatus != .approved)
                            .help(fc.authorizationStatus != .approved ? "Authorize Screen Time first" : "Apply current shield set")

                            Button("Register daily DeviceActivity schedules") {
                                try? DeviceActivityScheduler.registerAll()
                            }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                            .disabled(fc.authorizationStatus != .approved)
                            .help(fc.authorizationStatus != .approved ? "Authorize Screen Time first" : "Register schedules")

                            Text("Distraction shields when server flags match local windows (inbox, identity, air gap, midday).")
                                .font(.caption2)
                                .foregroundStyle(CockpitTheme.mistMuted)
                        }
                    }

                    CockpitPanel(kicker: "07:00", title: "Inbox nudge") {
                        VStack(alignment: .leading, spacing: 10) {
                            Toggle("Daily notification", isOn: $notificationsOn)
                                .tint(CockpitTheme.industrialAmber)
                                .onChange(of: notificationsOn) { _, on in
                                    Task {
                                        if on {
                                            _ = await IdentityAlignmentScheduler.requestAuthorizationIfNeeded()
                                            IdentityAlignmentScheduler.scheduleDailyNudge()
                                        } else {
                                            IdentityAlignmentScheduler.removeScheduledNudge()
                                        }
                                    }
                                }
                            if let ack = IdentityAlignmentScheduler.lastAcknowledgedDay() {
                                Text("Last alignment ack: \(ack)")
                                    .font(.caption2)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                            Button("Mark alignment done today") {
                                IdentityAlignmentScheduler.acknowledgeToday()
                            }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                        }
                    }

                    CockpitPanel(kicker: "Health", title: "Optional baselines") {
                        VStack(alignment: .leading, spacing: 10) {
                            Button("Authorize & load steps") {
                                health.requestAndFetchBaselines()
                            }
                            .cockpitPrimaryButtonStyle()
                            if health.authorizationDenied {
                                Text("Health access denied")
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.industrialAmber)
                            }
                            if !health.lastSummaryLine.isEmpty {
                                Text(health.lastSummaryLine)
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                        }
                    }

                    CockpitPanel(kicker: "Location", title: "Visits (optional)") {
                        VStack(alignment: .leading, spacing: 10) {
                            Button("When-in-use authorization") {
                                doorway.requestWhenInUse()
                            }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                            Button("Start visit monitoring") {
                                doorway.startVisitMonitoringIfAllowed()
                            }
                            .cockpitPrimaryButtonStyle()
                            if !doorway.lastVisitNote.isEmpty {
                                Text(doorway.lastVisitNote)
                                    .font(.caption)
                                    .foregroundStyle(CockpitTheme.mistMuted)
                            }
                        }
                    }

                    CockpitPanel(kicker: "Posture", title: "Foreground motion") {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(posture.hunchedSubmissive ? "Hunched" : "OK")
                                .font(.caption)
                                .foregroundStyle(CockpitTheme.mistMuted)
                            HStack(spacing: 10) {
                                Button("Start motion") { posture.startForegroundMonitoring() }
                                    .buttonStyle(CockpitSecondaryButtonStyle())
                                Button("Stop") { posture.stop() }
                                    .buttonStyle(CockpitSecondaryButtonStyle())
                            }
                        }
                    }

                    HStack(spacing: 10) {
                        Button("Haptic: deep work") { haptics.play(.deepWorkPulse) }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                        Button("Haptic: urgent") { haptics.play(.urgentEscalation) }
                            .buttonStyle(CockpitSecondaryButtonStyle())
                    }
                    .font(.caption)
                }
                .padding()
            }
            .scrollContentBackground(.hidden)
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Section("Keychain") {
                            Button("Save to Keychain") {
                                CockpitKeychain.writeKey(apiKeyDraft)
                            }
                            Button("Clear Keychain key") {
                                CockpitKeychain.deleteKey()
                                apiKeyDraft = ""
                            }
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                    .help("Quick settings actions")
                }
            }
            .onAppear {
                apiKeyDraft = CockpitKeychain.readKey() ?? ""
            }
        }
    }

    private func statusLine(_ s: AuthorizationStatus) -> String {
        switch s {
        case .notDetermined: return "Not determined"
        case .denied: return "Denied"
        case .approved: return "Approved"
        @unknown default: return "Unknown"
        }
    }
}
