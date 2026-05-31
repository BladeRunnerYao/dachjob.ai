import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case unauthorized
    case serverError(Int, String)
    case networkError(Error)
    case decodingError(Error)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .unauthorized:
            return "Session expired. Please log in again."
        case .serverError(let code, let message):
            if code == 429 {
                return "Too many requests. Please wait a moment and try again."
            }
            return "Server error (\(code)): \(message)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .decodingError(let error):
            return "Data error: \(error.localizedDescription)"
        case .cancelled:
            return "Request cancelled"
        }
    }

    var isCancelled: Bool {
        if case .cancelled = self { return true }
        return false
    }

    var isRateLimited: Bool {
        if case .serverError(let code, _) = self, code == 429 { return true }
        return false
    }
}

private struct CVMarkdownUpload: Encodable {
    let rawCvMd: String

    enum CodingKeys: String, CodingKey {
        case rawCvMd = "raw_cv_md"
    }
}

private struct ResumeGenerateRequest: Encodable {
    let confirmedSkills: [String]
    let style: ResumeStyle

    enum CodingKeys: String, CodingKey {
        case confirmedSkills = "confirmed_skills"
        case style
    }
}

private struct PasswordResetRequest: Encodable {
    let email: String
}

private struct JobStatusUpdateRequest: Encodable {
    let status: String?
    let saved: Bool?
}

@MainActor
class APIClient {
    static let shared = APIClient()

    private var baseURL: String {
        // Migrate old AWS default → GCP default
        if let saved = UserDefaults.standard.string(forKey: "api_base_url"),
           saved == "https://d3ktpumdo7sly4.cloudfront.net" {
            UserDefaults.standard.removeObject(forKey: "api_base_url")
        }
        return UserDefaults.standard.string(forKey: "api_base_url") ?? "https://dachjob-dev-api-qxugiew36a-ew.a.run.app"
    }

    private var authToken: String? {
        get { KeychainHelper.load(key: "auth_token") }
        set {
            if let token = newValue {
                KeychainHelper.save(key: "auth_token", value: token)
            } else {
                KeychainHelper.delete(key: "auth_token")
            }
        }
    }

    var isAuthenticated: Bool {
        authToken != nil
    }

    // MARK: - Auth

    func login(email: String, password: String) async throws -> AuthResponse {
        let body: [String: String] = ["email": email, "password": password]
        let response: AuthResponse = try await post("/api/auth/login", body: body)
        authToken = response.token
        return response
    }

    func register(email: String, password: String, fullName: String) async throws -> AuthResponse {
        let body: [String: String] = ["email": email, "password": password, "name": fullName]
        let response: AuthResponse = try await post("/api/auth/register", body: body)
        authToken = response.token
        return response
    }

    func requestPasswordReset(email: String) async throws -> PasswordResetResponse {
        return try await post("/api/auth/forgot-password", body: PasswordResetRequest(email: email))
    }

    func getCurrentUser() async throws -> UserAccount {
        return try await get("/api/auth/me")
    }

    func logout() {
        authToken = nil
    }

    // MARK: - Jobs

    func getJobs(limit: Int = 50, offset: Int = 0, status: String? = nil) async throws -> PaginatedJobs {
        var path = "/api/jobs?limit=\(limit)&offset=\(offset)"
        if let status {
            path += "&status=\(status)"
        }
        let result: PaginatedJobs = try await get(path)
        // Filter out smoke test jobs
        let filtered = result.items.filter { job in
            !(job.title.range(of: "smoke\\s*test", options: [.regularExpression, .caseInsensitive]) != nil)
        }
        return PaginatedJobs(items: filtered, total: result.total - (result.items.count - filtered.count), limit: result.limit, offset: result.offset)
    }

    func getJob(id: String) async throws -> JobPosting {
        return try await get("/api/jobs/\(id)")
    }

    func importJobs(urls: [String]) async throws -> JobImportResponse {
        let body: [String: [String]] = ["urls": urls]
        return try await post("/api/jobs/import", body: body)
    }

    func updateJobStatus(id: String, status: String? = nil, saved: Bool? = nil) async throws -> JobPosting {
        let body = JobStatusUpdateRequest(status: status, saved: saved)
        return try await patch("/api/jobs/\(id)/status", body: body)
    }

    func createResumeArtifact(jobId: String, style: ResumeStyle, confirmedSkills: [String]) async throws -> ResumeArtifact {
        return try await post(
            "/api/jobs/\(jobId)/resume",
            body: ResumeGenerateRequest(confirmedSkills: confirmedSkills, style: style)
        )
    }

    // MARK: - Profile

    func getProfile() async throws -> CandidateProfile? {
        return try await get("/api/profile")
    }

    func uploadCvMarkdown(_ rawCvMd: String) async throws -> CandidateProfile {
        return try await post("/api/profile/cv", body: CVMarkdownUpload(rawCvMd: rawCvMd))
    }

    func importProfileFromPdf(fileURL: URL) async throws -> CandidateProfile {
        let didAccess = fileURL.startAccessingSecurityScopedResource()
        defer {
            if didAccess {
                fileURL.stopAccessingSecurityScopedResource()
            }
        }
        let data = try Data(contentsOf: fileURL)
        return try await postMultipart(
            "/api/profile/import-pdf",
            fieldName: "file",
            fileName: fileURL.lastPathComponent,
            mimeType: "application/pdf",
            fileData: data
        )
    }

    func importProfileFromUrl(_ url: String) async throws -> CandidateProfile {
        let body: [String: String] = ["url": url]
        return try await post("/api/profile/import-url", body: body)
    }

    // MARK: - Match

    func getMatchReport(jobId: String) async throws -> MatchReport? {
        return try await get("/api/jobs/\(jobId)/match")
    }

    // MARK: - LLM Runs

    func getLLMRuns(limit: Int = 50, offset: Int = 0) async throws -> PaginatedLLMRuns {
        return try await get("/api/llm-runs?limit=\(limit)&offset=\(offset)")
    }

    // MARK: - Applications

    func getApplications() async throws -> [Application] {
        return try await get("/api/applications")
    }

    // MARK: - Private helpers

    private func get<T: Codable>(_ path: String) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        return try await execute(request)
    }

    private func post<T: Codable, B: Encodable>(_ path: String, body: B) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try JSONEncoder().encode(body)

        return try await execute(request)
    }

    private func patch<T: Codable, B: Encodable>(_ path: String, body: B) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try JSONEncoder().encode(body)

        return try await execute(request)
    }

    private func postMultipart<T: Codable>(
        _ path: String,
        fieldName: String,
        fileName: String,
        mimeType: String,
        fileData: Data
    ) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(path)") else {
            throw APIError.invalidURL
        }

        let boundary = "Boundary-\(UUID().uuidString)"
        var body = Data()
        append("--\(boundary)\r\n", to: &body)
        append("Content-Disposition: form-data; name=\"\(fieldName)\"; filename=\"\(fileName)\"\r\n", to: &body)
        append("Content-Type: \(mimeType)\r\n\r\n", to: &body)
        body.append(fileData)
        append("\r\n--\(boundary)--\r\n", to: &body)

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = body

        return try await execute(request)
    }

    private func append(_ string: String, to data: inout Data) {
        data.append(Data(string.utf8))
    }

    private func execute<T: Codable>(_ request: URLRequest) async throws -> T {
        let (data, response): (Data, URLResponse)
        do {
            var timedRequest = request
            timedRequest.timeoutInterval = 15
            (data, response) = try await URLSession.shared.data(for: timedRequest)
        } catch {
            if isCancellation(error) {
                throw APIError.cancelled
            }
            throw APIError.networkError(error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(NSError(domain: "Invalid response", code: 0))
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            if httpResponse.statusCode == 401 {
                authToken = nil
                // Try to extract the detail message from the server error
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let detail = json["detail"] as? String {
                    throw APIError.serverError(401, detail)
                }
                throw APIError.unauthorized
            }
            throw APIError.serverError(httpResponse.statusCode, message)
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }

    private func isCancellation(_ error: Error) -> Bool {
        if error is CancellationError {
            return true
        }
        if let urlError = error as? URLError, urlError.code == .cancelled {
            return true
        }
        return false
    }
}
