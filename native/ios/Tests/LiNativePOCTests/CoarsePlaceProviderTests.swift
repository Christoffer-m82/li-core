import XCTest
@testable import LiNativePOC

final class CoarsePlaceProviderTests: XCTestCase {
    func testPayloadHasNoCoordinateOrHardwareFields() throws {
        let payload = CoarsePlaceSubmission(
            installationId: UUID(), updateId: UUID(), countryCode: "MT",
            townCity: "Valletta", observedAt: Date(), permission: .init(checkedAt: Date())
        )
        let text = String(data: try JSONEncoder().encode(payload), encoding: .utf8)!
        XCTAssertFalse(text.localizedCaseInsensitiveContains("latitude"))
        XCTAssertFalse(text.localizedCaseInsensitiveContains("longitude"))
        XCTAssertFalse(text.localizedCaseInsensitiveContains("deviceId"))
        XCTAssertTrue(text.contains("device_coarse"))
    }

    func testOvernightRequiresCrossingLocalCalendarDay() {
        let calendar = Calendar(identifier: .gregorian)
        let first = Date(timeIntervalSince1970: 1_700_000_000)
        XCTAssertFalse(OvernightClassifier.event(first: first, last: first.addingTimeInterval(3600), calendar: calendar))
        XCTAssertTrue(OvernightClassifier.event(first: first, last: first.addingTimeInterval(86_400), calendar: calendar))
    }

    func testDeniedAndRestrictedNeverBecomeGranted() {
        XCTAssertEqual(PlacePermission.from(.denied), .denied)
        XCTAssertEqual(PlacePermission.from(.restricted), .restricted)
        XCTAssertNotEqual(PlacePermission.from(.notDetermined), .granted)
    }
}
