import Foundation

/// Splits stored life-purpose prose into sentences (on `". "`) for one-line splash display.
enum PurposeSentencePicker {
    /// Non-empty trimmed segments after splitting on `". "`.
    static func sentences(from purpose: String) -> [String] {
        let trimmed = purpose.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return [] }
        return trimmed
            .components(separatedBy: ". ")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    /// Picks one segment uniformly at random, or `nil` if there is no usable text.
    static func randomSentence(from purpose: String) -> String? {
        var g = SystemRandomNumberGenerator()
        return randomSentence(from: purpose, using: &g)
    }

    static func randomSentence<R: RandomNumberGenerator>(from purpose: String, using rng: inout R) -> String? {
        let parts = sentences(from: purpose)
        guard let pick = parts.randomElement(using: &rng) else { return nil }
        return pick
    }
}
