import CoreMotion
import Foundation
import Observation

/// Uses **device motion attitude** (not raw accelerometer) for pitch/yaw while active.
/// Continuous background IMU is restricted — this service is intended for **foreground** use.
@Observable
@MainActor
final class PostureMotionService {
    private let motion = CMMotionManager()
    private(set) var hunchedSubmissive: Bool = false
    private(set) var lastPitchDegrees: Double = 0

    /// Threshold for “hunched” forward posture (degrees); tune per device mount.
    var pitchThresholdDegrees: Double = 15

    func startForegroundMonitoring() {
        guard motion.isDeviceMotionAvailable else { return }
        motion.deviceMotionUpdateInterval = 1.0 / 20.0
        motion.startDeviceMotionUpdates(to: OperationQueue.main) { [weak self] data, _ in
            guard let self, let att = data?.attitude else { return }
            let pitchDeg = att.pitch * 180 / .pi
            Task { @MainActor in
                self.lastPitchDegrees = pitchDeg
                self.hunchedSubmissive = abs(pitchDeg) > self.pitchThresholdDegrees
            }
        }
    }

    func stop() {
        motion.stopDeviceMotionUpdates()
    }
}
