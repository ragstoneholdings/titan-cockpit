import Foundation

/// Calls FastAPI `POST /api/vanguard/opportunity-cost` (Gemini-backed when configured).
struct AdversarialCoachService {
    private let api = CockpitAPIClient()

    func opportunityCost(title: String, notes: String = "", estimatedMinutes: Int? = nil) async throws -> OpportunityCostResponseDTO {
        try await api.postOpportunityCost(title: title, notes: notes, estimatedMinutes: estimatedMinutes)
    }
}
