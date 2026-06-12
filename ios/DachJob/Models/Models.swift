import Foundation

struct JobPosting: Codable, Identifiable {
    let id: String
    let title: String
    let company: String?
    let location: String?
    let score: Double?
    let recommendation: String?
    let status: String?
    let saved: Bool?
    let applicationStatus: String?
    let applicationAppliedAt: String?
    let url: String?
    let rawJd: String?
    let parsedJson: ParsedJobDescription?
    let createdAt: String?
    let pipelineAddedAt: String?

    enum CodingKeys: String, CodingKey {
        case id, title, company, location, score, recommendation, status, saved, url
        case applicationStatus = "application_status"
        case applicationAppliedAt = "application_applied_at"
        case rawJd = "raw_jd"
        case parsedJson = "parsed_json"
        case createdAt = "created_at"
        case pipelineAddedAt = "pipeline_added_at"
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

    var needsParsing: Bool {
        rawJd?.isEmpty == false && !hasQualificationDetails
    }

    var displayApplicationStatus: String? {
        applicationStatus ?? (["applied", "interview", "rejected", "offer"].contains(status ?? "") ? status : nil)
    }

    var isSaved: Bool {
        saved == true || status == "saved"
    }

    var addedDateText: String? {
        formatShortDate(pipelineAddedAt ?? createdAt)
    }

    var appliedDateText: String? {
        formatShortDate(applicationAppliedAt)
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

struct JobFilterOptions: Codable {
    let companies: [JobFilterOption]
    let statuses: [JobFilterOption]
}

struct JobFilterOption: Codable, Identifiable {
    let value: String
    let count: Int

    var id: String { value }
}

extension JobFilterOptions {
    func count(forStatus status: String) -> Int {
        statuses.first { $0.value.lowercased() == status.lowercased() }?.count ?? 0
    }
}

struct Application: Codable, Identifiable {
    let id: String
    let jobId: String
    let jobTitle: String
    let company: String
    let status: String
    let score: Double?
    let notes: String?
    let addedAt: String?
    let appliedAt: String?
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id
        case jobId = "job_id"
        case jobTitle = "job_title"
        case company, status, score, notes
        case addedAt = "added_at"
        case appliedAt = "applied_at"
        case createdAt = "created_at"
    }

    var scorePercent: Int? {
        guard let score else { return nil }
        return Int((min(max(score, 1), 5) / 5.0) * 100)
    }

    var addedDateText: String? {
        formatShortDate(addedAt ?? createdAt)
    }

    var appliedDateText: String? {
        formatShortDate(appliedAt)
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

struct JobParseResponse: Codable {
    let jobId: String
    let status: String
    let parsedJson: ParsedJobDescription?

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
        case parsedJson = "parsed_json"
    }
}

struct AuthResponse: Codable {
    let token: String
    let userId: String
    let email: String
    let name: String
    let tenantId: String?
    let passwordNeedsReset: Bool?

    enum UserKeys: String, CodingKey {
        case id, email, name
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        token = try container.decode(String.self, forKey: .token)
        tenantId = try container.decodeIfPresent(String.self, forKey: .tenantId)
        passwordNeedsReset = try container.decodeIfPresent(Bool.self, forKey: .passwordNeedsReset)

        if container.contains(.userId) {
            userId = try container.decode(String.self, forKey: .userId)
            email = try container.decode(String.self, forKey: .email)
            name = try container.decode(String.self, forKey: .name)
            return
        }

        let user = try container.nestedContainer(keyedBy: UserKeys.self, forKey: .user)
        userId = try user.decode(String.self, forKey: .id)
        email = try user.decode(String.self, forKey: .email)
        name = try user.decode(String.self, forKey: .name)
    }

    enum CodingKeys: String, CodingKey {
        case token
        case userId = "user_id"
        case email
        case name
        case user
        case tenantId = "tenant_id"
        case passwordNeedsReset = "password_needs_reset"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(token, forKey: .token)
        try container.encode(userId, forKey: .userId)
        try container.encode(email, forKey: .email)
        try container.encode(name, forKey: .name)
        try container.encodeIfPresent(tenantId, forKey: .tenantId)
        try container.encodeIfPresent(passwordNeedsReset, forKey: .passwordNeedsReset)
    }
}

struct UserAccount: Codable {
    let id: String
    let email: String
    let name: String
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

func formatShortDate(_ isoDate: String?) -> String? {
    guard let date = parseISODate(isoDate) else { return nil }
    return date.formatted(date: .abbreviated, time: .omitted)
}

func parseISODate(_ isoDate: String?) -> Date? {
    guard let isoDate else { return nil }
    let formatter = ISO8601DateFormatter()
    formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    var date = formatter.date(from: isoDate)
    if date == nil {
        formatter.formatOptions = [.withInternetDateTime]
        date = formatter.date(from: isoDate)
    }
    return date
}
