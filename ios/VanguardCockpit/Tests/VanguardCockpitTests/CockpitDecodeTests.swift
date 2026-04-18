import XCTest
@testable import VanguardCockpit

final class CockpitDecodeTests: XCTestCase {
    func testDecodeMinimalCockpitWithRagstoneLedger() throws {
        let json = """
        {
          "date": "2026-04-11",
          "ragstone_ledger": {
            "version": 1,
            "cash_runway_months": 4.25,
            "yoy_revenue_growth_percent": 12.3,
            "revenue_ytd_usd": null,
            "note": "ok"
          }
        }
        """
        let data = Data(json.utf8)
        let dto = try JSONDecoder().decode(CockpitResponseDTO.self, from: data)
        XCTAssertEqual(dto.date, "2026-04-11")
        XCTAssertEqual(dto.ragstone_ledger["cash_runway_months"], .double(4.25))
        switch dto.ragstone_ledger["yoy_revenue_growth_percent"] {
        case .double(let d): XCTAssertEqual(d, 12.3, accuracy: 0.0001)
        case .int(let i): XCTAssertEqual(i, 12)
        default: XCTFail("expected numeric yoy")
        }
        XCTAssertEqual(dto.ragstone_ledger["revenue_ytd_usd"], .null)
        XCTAssertEqual(dto.ragstone_ledger["note"], .string("ok"))
    }

    func testAnyCodableJSONFromJSONObject() {
        let raw: [String: Any] = [
            "b": true,
            "n": NSNumber(value: 42.7),
            "whole": NSNumber(value: 7),
            "s": "x",
            "nil": NSNull(),
            "nested": ["a": 1],
        ]
        let m = raw.mapValues { AnyCodableJSON(jsonValue: $0) }
        XCTAssertEqual(m["b"], .bool(true))
        XCTAssertEqual(m["whole"], .int(7))
        switch m["n"] {
        case .double(let d): XCTAssertEqual(d, 42.7, accuracy: 0.0001)
        default: XCTFail("expected double")
        }
        XCTAssertEqual(m["s"], .string("x"))
        XCTAssertEqual(m["nil"], .null)
        if case .object(let o) = m["nested"] {
            XCTAssertEqual(o["a"], .int(1))
        } else {
            XCTFail("expected nested object")
        }
    }

    func testAnyCodableJSONDecoderPrefersDoubleForFractionalNumbers() throws {
        let json = #"{"v":3.14}"#
        let data = Data(json.utf8)
        let decoded = try JSONDecoder().decode([String: AnyCodableJSON].self, from: data)
        switch decoded["v"] {
        case .double(let d): XCTAssertEqual(d, 3.14, accuracy: 0.0001)
        default: XCTFail("expected double for fractional JSON number")
        }
    }
}
