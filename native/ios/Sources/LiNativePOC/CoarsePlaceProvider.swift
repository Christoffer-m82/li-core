import CoreLocation
import Foundation

public struct CoarsePlace: Equatable, Sendable {
    public let countryCode: String
    public let townCity: String?
    public init(countryCode: String, townCity: String?) {
        self.countryCode = countryCode
        self.townCity = townCity
    }
}

public enum PlacePermission: Equatable, Sendable {
    case notRequested, granted, denied, restricted

    static func from(_ status: CLAuthorizationStatus) -> PlacePermission {
        switch status {
        case .authorizedAlways, .authorizedWhenInUse: .granted
        case .denied: .denied
        case .restricted: .restricted
        default: .notRequested
        }
    }
}

public protocol CoarseResolving: Sendable {
    func resolve(_ location: CLLocation) async throws -> CoarsePlace
}

public struct AppleCoarseResolver: CoarseResolving {
    public init() {}
    public func resolve(_ location: CLLocation) async throws -> CoarsePlace {
        let marks = try await CLGeocoder().reverseGeocodeLocation(location)
        guard let mark = marks.first, let code = mark.isoCountryCode?.uppercased() else {
            throw CLError(.geocodeFoundNoResult)
        }
        return CoarsePlace(countryCode: code, townCity: mark.locality)
    }
}

public struct CoarsePlaceSubmission: Codable, Equatable, Sendable {
    public let contractVersion = "1.0"
    public let installationId: UUID
    public let updateId: UUID
    public let countryCode: String
    public let townCity: String?
    public let source = "device_coarse"
    public let observedAt: Date
    public let permission: Permission

    public struct Permission: Codable, Equatable, Sendable {
        public let state = "granted"
        public let checkedAt: Date
        enum CodingKeys: String, CodingKey { case state; case checkedAt = "checked_at" }
    }
    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version", installationId = "installation_id"
        case updateId = "update_id", countryCode = "country_code", townCity = "town_city"
        case source, observedAt = "observed_at", permission
    }
}

@MainActor
public final class CoarsePlaceProvider: NSObject, CLLocationManagerDelegate {
    private let manager: CLLocationManager
    private let resolver: CoarseResolving
    private var installationId: UUID?
    public var submit: (@Sendable (CoarsePlaceSubmission) async throws -> Void)?
    public var permissionChanged: ((PlacePermission) -> Void)?
    public var manualFallbackRequested: (() -> Void)?

    public init(manager: CLLocationManager = CLLocationManager(),
                resolver: CoarseResolving = AppleCoarseResolver()) {
        self.manager = manager
        self.resolver = resolver
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyThreeKilometers
        manager.distanceFilter = 50_000
    }

    public func configure(installationId: UUID) { self.installationId = installationId }

    public func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }

    public func requestCoarseObservation() {
        guard manager.authorizationStatus == .authorizedAlways ||
                manager.authorizationStatus == .authorizedWhenInUse else {
            manualFallbackRequested?()
            return
        }
        manager.requestLocation()
    }

    public func startSignificantChangesOptIn() {
        // Call only after a separate user opt-in. This is not continuous tracking.
        manager.startMonitoringSignificantLocationChanges()
    }

    public func stopSignificantChanges() { manager.stopMonitoringSignificantLocationChanges() }

    public func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let permission = PlacePermission.from(manager.authorizationStatus)
        permissionChanged?(permission)
        if permission == .denied || permission == .restricted { manualFallbackRequested?() }
    }

    public func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let transient = locations.last, let installationId else { return }
        let observedAt = transient.timestamp
        Task {
            // The CLLocation remains local to this scope and is released after geocoding.
            let coarse = try await resolver.resolve(transient)
            let payload = CoarsePlaceSubmission(
                installationId: installationId, updateId: UUID(),
                countryCode: coarse.countryCode, townCity: coarse.townCity,
                observedAt: observedAt, permission: .init(checkedAt: Date())
            )
            try await submit?(payload)
        }
    }

    public func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        manualFallbackRequested?()
    }
}

public enum OvernightClassifier {
    public static func event(first: Date, last: Date, calendar: Calendar = .current) -> Bool {
        last > first && !calendar.isDate(first, inSameDayAs: last)
    }
}
