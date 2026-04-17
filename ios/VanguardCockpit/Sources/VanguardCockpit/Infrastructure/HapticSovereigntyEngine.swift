import CoreHaptics
import Foundation

/// Semantic haptics via AHAP bundles. Simulator has limited support — feature-detect `CHHapticEngine`.
final class HapticSovereigntyEngine {
    private var engine: CHHapticEngine?

    enum Pattern: String {
        case deepWorkPulse = "DeepWorkPulse"
        case transitionWarning = "TransitionWarning"
        case doorwayKnock = "DoorwayKnock"
        case urgentEscalation = "UrgentEscalation"
    }

    init() {
        guard CHHapticEngine.capabilitiesForHardware().supportsHaptics else { return }
        do {
            let eng = try CHHapticEngine()
            try eng.start()
            engine = eng
        } catch {
            engine = nil
        }
    }

    func play(_ pattern: Pattern) {
        guard let url = Bundle.main.url(forResource: pattern.rawValue, withExtension: "ahap", subdirectory: "Haptics") else {
            return
        }
        do {
            let pat = try CHHapticPattern(contentsOf: url)
            let player = try engine?.makePlayer(with: pat)
            try player?.start(atTime: 0)
        } catch {
            return
        }
    }
}
