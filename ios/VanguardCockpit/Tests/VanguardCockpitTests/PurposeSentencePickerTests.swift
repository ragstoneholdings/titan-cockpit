import XCTest
@testable import VanguardCockpit

final class PurposeSentencePickerTests: XCTestCase {
    func testSentencesEmptyAndWhitespace() {
        XCTAssertEqual(PurposeSentencePicker.sentences(from: ""), [])
        XCTAssertEqual(PurposeSentencePicker.sentences(from: "   \n"), [])
    }

    func testSentencesSingleChunkNoDelimiter() {
        XCTAssertEqual(PurposeSentencePicker.sentences(from: "Integrity under pressure"), ["Integrity under pressure"])
    }

    func testSentencesMultipleSplit() {
        let s = "First idea. Second idea. Third still."
        XCTAssertEqual(
            PurposeSentencePicker.sentences(from: s),
            ["First idea", "Second idea", "Third still."]
        )
    }

    func testRandomNilWhenEmpty() {
        XCTAssertNil(PurposeSentencePicker.randomSentence(from: ""))
        XCTAssertNil(PurposeSentencePicker.randomSentence(from: "   "))
    }

    func testRandomSingleReturnsThatSentence() {
        let one = "Only this."
        XCTAssertEqual(PurposeSentencePicker.randomSentence(from: one), "Only this.")
    }

    func testRandomOnlyReturnsSegments() {
        let purpose = "Alpha. Beta. Gamma"
        var rng = SplitMix64(seed: 0xDEADBEEF)
        for _ in 0 ..< 64 {
            guard let line = PurposeSentencePicker.randomSentence(from: purpose, using: &rng) else {
                return XCTFail("expected non-nil")
            }
            XCTAssertTrue(["Alpha", "Beta", "Gamma"].contains(line))
        }
    }
}

// MARK: - Test-only deterministic RNG

private struct SplitMix64: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        self.state = seed
    }

    mutating func next() -> UInt64 {
        state &+= 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }
}
