import CoreLocation
import Foundation

/// Visit / region hooks for doorway posture checks (foreground-friendly; no continuous background IMU).
final class DoorwayGeofenceService: NSObject, ObservableObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    @Published var authorizationStatus: CLAuthorizationStatus = .notDetermined
    @Published var lastVisitNote: String = ""

    override init() {
        super.init()
        manager.delegate = self
        authorizationStatus = manager.authorizationStatus
    }

    func requestWhenInUse() {
        manager.requestWhenInUseAuthorization()
    }

    /// Registers significant location or visit monitoring when authorized (best-effort).
    func startVisitMonitoringIfAllowed() {
        guard authorizationStatus == .authorizedAlways || authorizationStatus == .authorizedWhenInUse else { return }
        manager.startMonitoringVisits()
    }

    func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        authorizationStatus = manager.authorizationStatus
    }

    func locationManager(_ manager: CLLocationManager, didVisit visit: CLVisit) {
        let arrival = visit.arrivalDate.formatted(date: .abbreviated, time: .shortened)
        lastVisitNote = "Visit \(arrival)"
    }
}
