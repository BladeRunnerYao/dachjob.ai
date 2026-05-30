import Foundation

struct JobPosting: Codable, Identifiable {
    let id: String
    let title: String
    let company: String?
    let location: String?
    let score: Double?
    let recommendation: String?
    let url: String?
    let rawJd: String?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title, company, location, score, recommendation, url
        case rawJd = "raw_jd"
        case createdAt = "created_at"
    }

    var scorePercent: Int? {
        guard let s = score else { return nil }
        return Int((min(max(s, 1), 5) / 5.0) * 100)
    }
}

struct PaginatedJobs: Codable {
    let items: [JobPosting]
    let total: Int
    let limit: Int
    let offset: Int
}

struct Application: Codable, Identifiable {
    let id: String
    let jobTitle: String
    let company: String
    let status: String

    enum CodingKeys: String, CodingKey {
        case id
        case jobTitle = "job_title"
        case company, status
    }
}

struct LLMRun: Codable, Identifiable {
    let id: String
    let task: String
    let provider: String
    let model: String
    let status: String
    let latencyMs: Int
    let createdAt: String
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case id, task, provider, model, status
        case latencyMs = "latency_ms"
        case createdAt = "created_at"
        case errorMessage = "error_message"
    }
}

struct PaginatedLLMRuns: Codable {
    let items: [LLMRun]
    let total: Int
}

struct CandidateProfile: Codable {
    let id: String
    let fullName: String?
    let headline: String?
    let location: String?
    let skills: [String]?

    enum CodingKeys: String, CodingKey {
        case id
        case fullName = "full_name"
        case headline, location, skills
    }
}

struct MatchReport: Codable, Identifiable {
    let id: String
    let jobId: String
    let overallScore: Double
    let recommendation: String
    let explanation: String?

    enum CodingKeys: String, CodingKey {
        case id
        case jobId = "job_id"
        case overallScore = "overall_score"
        case recommendation, explanation
    }
}

struct AuthResponse: Codable {
    let accessToken: String
    let tokenType: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
    }
}

struct JobImportResponse: Codable {
    let imported: [JobPosting]
    let errors: [ImportError]
}

struct ImportError: Codable {
    let url: String
    let error: String
}
