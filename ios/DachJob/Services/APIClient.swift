import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case unauthorized
    case serverError(Int, String)
    case networkError(Error)
    case decodingError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL"
        case .unauthorized:
            return "Session expired. Please log in again."
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message)"
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .decodingError(let error):
            return "Data error: \(error.localizedDescription)"
        }
    }
}

class APIClient {
    static let shared = APIClient()

    private var baseURL: String {
        UserDefaults.standard.string(forKey: "api_base_url") ?? "https://d3ktpumdo7sly4.cloudfront.net"
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
        authToken = response.accessToken
        return response
    }

    func register(email: String, password: String, fullName: String) async throws -> AuthResponse {
        let body: [String: String] = ["email": email, "password": password, "full_name": fullName]
        let response: AuthResponse = try await post("/api/auth/register", body: body)
        authToken = response.accessToken
        return response
    }

    func logout() {
        authToken = nil
    }

    // MARK: - Jobs

    func getJobs(limit: Int = 50, offset: Int = 0) async throws -> PaginatedJobs {
        let result: PaginatedJobs = try await get("/api/jobs?limit=\(limit)&offset=\(offset)")
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

    // MARK: - Profile

    func getProfile() async throws -> CandidateProfile {
        return try await get("/api/profile")
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

    private func execute<T: Codable>(_ request: URLRequest) async throws -> T {
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw APIError.networkError(error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(NSError(domain: "Invalid response", code: 0))
        }

        if httpResponse.statusCode == 401 {
            authToken = nil
            throw APIError.unauthorized
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw APIError.serverError(httpResponse.statusCode, message)
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
}
