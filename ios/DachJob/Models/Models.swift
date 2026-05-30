import Foundation

struct JobPosting: Codable, Identifiable {
    let id: String
    let title: String
    let company: String?
    let location: String?
    let score: Double?
    let recommendation: String?
    let status: String?
    let url: String?
    let rawJd: String?
    let parsedJson: ParsedJobDescription?
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title, company, location, score, recommendation, status, url
        case rawJd = "raw_jd"
        case parsedJson = "parsed_json"
        case createdAt = "created_at"
    }

    var scorePercent: Int? {
        guard let s = score else { return nil }
        return Int((min(max(s, 1), 5) / 5.0) * 100)
    }

    var hasQualificationDetails: Bool {
        guard let parsedJson else { return false }
        return !parsedJson.responsibilities.isEmpty
            || !parsedJson.mustHaveSkills.isEmpty
            || !parsedJson.niceToHaveSkills.isEmpty
            || !parsedJson.requiredQualifications.isEmpty
            || !parsedJson.preferredQualifications.isEmpty
    }
}

struct ParsedJobDescription: Codable {
    let responsibilities: [String]
    let mustHaveSkills: [String]
    let niceToHaveSkills: [String]
    let requiredQualifications: [String]
    let preferredQualifications: [String]
    let experienceYears: Double?

    enum CodingKeys: String, CodingKey {
        case responsibilities
        case mustHaveSkills = "must_have_skills"
        case niceToHaveSkills = "nice_to_have_skills"
        case requiredQualifications = "required_qualifications"
        case preferredQualifications = "preferred_qualifications"
        case experienceYears = "experience_years"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        responsibilities = try container.decodeIfPresent([String].self, forKey: .responsibilities) ?? []
        mustHaveSkills = try container.decodeIfPresent([String].self, forKey: .mustHaveSkills) ?? []
        niceToHaveSkills = try container.decodeIfPresent([String].self, forKey: .niceToHaveSkills) ?? []
        requiredQualifications = try container.decodeIfPresent([String].self, forKey: .requiredQualifications) ?? []
        preferredQualifications = try container.decodeIfPresent([String].self, forKey: .preferredQualifications) ?? []
        experienceYears = try container.decodeIfPresent(Double.self, forKey: .experienceYears)
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

enum ResumeStyle: String, Codable, CaseIterable, Identifiable {
    case american
    case german

    var id: String { rawValue }

    var title: String {
        switch self {
        case .american: return "American CV"
        case .german: return "German CV"
        }
    }
}

struct ResumeArtifact: Codable, Identifiable {
    let id: String
    let jobId: String
    let htmlObjectKey: String
    let pdfObjectKey: String?

    enum CodingKeys: String, CodingKey {
        case id
        case jobId = "job_id"
        case htmlObjectKey = "html_object_key"
        case pdfObjectKey = "pdf_object_key"
    }
}

struct CandidateProfile: Codable {
    let id: String
    let fullName: String?
    let headline: String?
    let location: String?
    let rawCvMd: String
    let skills: [String]?

    enum CodingKeys: String, CodingKey {
        case id
        case fullName = "full_name"
        case headline, location, skills
        case rawCvMd = "raw_cv_md"
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

    var scorePercent: Int {
        Int((min(max(overallScore, 1), 5) / 5.0) * 100)
    }
}

struct AuthResponse: Codable {
    let token: String
    let userId: String
    let email: String
    let name: String
    let tenantId: String?
    let passwordNeedsReset: Bool?

    enum CodingKeys: String, CodingKey {
        case token
        case userId = "user_id"
        case email
        case name
        case tenantId = "tenant_id"
        case passwordNeedsReset = "password_needs_reset"
    }
}

struct PasswordResetResponse: Codable {
    let message: String
    let resetLink: String?

    enum CodingKeys: String, CodingKey {
        case message
        case resetLink = "reset_link"
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
