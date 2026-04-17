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
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                GroupBox("API auth (production)") {
                    VStack(alignment: .leading, spacing: 8) {
                        SecureField("COCKPIT_API_KEY", text: $apiKeyDraft)
                            .textContentType(.password)
                            .autocorrectionDisabled()
                        Button("Save to Keychain") {
                            CockpitKeychain.writeKey(apiKeyDraft)
                        }
                        Button("Clear Keychain key") {
                            CockpitKeychain.deleteKey()
                            apiKeyDraft = ""
                        }
                        .font(.caption)
                        Text("Xcode scheme env COCKPIT_API_KEY overrides Keychain. Required when server sets COCKPIT_API_KEY.")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                GroupBox("Screen Time") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(statusLine(fc.authorizationStatus))
                            .font(.caption)
                        Button("Request authorization") {
                            Task { await fc.requestAuthorization() }
                        }
                        .disabled(fc.authorizationStatus == .approved)
                        FamilyActivityPicker(selection: $fc.selection)
                            .frame(minHeight: 120)
                            .onChange(of: fc.selection) { _, new in
                                ScreenTimeSelectionStore.save(new)
                                vm.syncDistractionShields(shields: shields, selection: new)
                            }
                        Button("Apply shields to selection (manual)") {
                            shields.setShieldedApplications(fc.selection.applicationTokens)
                        }
                        .disabled(fc.authorizationStatus != .approved)
                        Button("Register daily DeviceActivity schedules") {
                            try? DeviceActivityScheduler.registerAll()
                        }
                        .disabled(fc.authorizationStatus != .approved)
                        Text("Distraction shields when server flags match local windows (inbox, identity, air gap, midday).")
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                    }
                }
                GroupBox("07:00 Inbox nudge") {
                    Toggle("Daily notification", isOn: $notificationsOn)
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
                            .foregroundStyle(.secondary)
                    }
                    Button("Mark alignment done today") {
                        IdentityAlignmentScheduler.acknowledgeToday()
                    }
                    .font(.caption)
                }
                GroupBox("Health (optional)") {
                    Button("Authorize & load steps") {
                        health.requestAndFetchBaselines()
                    }
                    if health.authorizationDenied {
                        Text("Health access denied")
                            .font(.caption)
                            .foregroundStyle(.orange)
                    }
                    if !health.lastSummaryLine.isEmpty {
                        Text(health.lastSummaryLine)
                            .font(.caption)
                    }
                }
                GroupBox("Location visits (optional)") {
                    Button("When-in-use authorization") {
                        doorway.requestWhenInUse()
                    }
                    Button("Start visit monitoring") {
                        doorway.startVisitMonitoringIfAllowed()
                    }
                    if !doorway.lastVisitNote.isEmpty {
                        Text(doorway.lastVisitNote)
                            .font(.caption)
                    }
                }
                GroupBox("Posture (foreground)") {
                    Text(posture.hunchedSubmissive ? "Hunched" : "OK")
                        .font(.caption)
                    Button("Start motion") { posture.startForegroundMonitoring() }
                    Button("Stop") { posture.stop() }
                }
                HStack {
                    Button("Haptic: deep work") { haptics.play(.deepWorkPulse) }
                    Button("Haptic: urgent") { haptics.play(.urgentEscalation) }
                }
                .font(.caption)
            }
            .padding()
        }
        .onAppear {
            apiKeyDraft = CockpitKeychain.readKey() ?? ""
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
