import SwiftUI
import Observation

@Observable
@MainActor
class AuthService {
    var isAuthenticated = false
    var isLoading = false
    var errorMessage: String?

    private let api = APIClient.shared

    init() {
        isAuthenticated = api.isAuthenticated
    }

    func login(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        do {
            _ = try await api.login(email: email, password: password)
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func register(email: String, password: String, fullName: String) async {
        isLoading = true
        errorMessage = nil
        do {
            _ = try await api.register(email: email, password: password, fullName: fullName)
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func logout() {
        api.logout()
        isAuthenticated = false
    }
}
