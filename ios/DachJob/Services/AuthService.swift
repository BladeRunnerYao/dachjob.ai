import SwiftUI

@MainActor
class AuthService: ObservableObject {
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let api = APIClient.shared

    init() {
        isAuthenticated = api.isAuthenticated
    }

    @MainActor
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

    @MainActor
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
