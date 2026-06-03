import SwiftUI
import Observation

@Observable
@MainActor
class AuthService {
    var isAuthenticated = false
    var isLoading = false
    var errorMessage: String?
    var accountEmail: String?
    var accountName: String?

    private let api = APIClient.shared
    private let emailKey = "account_email"
    private let nameKey = "account_name"
    private var unauthorizedObserver: NSObjectProtocol?

    init() {
        isAuthenticated = api.isAuthenticated
        accountEmail = UserDefaults.standard.string(forKey: emailKey)
        accountName = UserDefaults.standard.string(forKey: nameKey)
        unauthorizedObserver = NotificationCenter.default.addObserver(
            forName: .apiUnauthorized,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.clearSession()
            }
        }
    }

    func login(email: String, password: String) async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await api.login(email: email, password: password)
            saveAccount(response)
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
            let response = try await api.register(email: email, password: password, fullName: fullName)
            saveAccount(response)
            isAuthenticated = true
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func logout() {
        api.logout()
        clearSession()
    }

    private func clearSession() {
        accountEmail = nil
        accountName = nil
        errorMessage = nil
        UserDefaults.standard.removeObject(forKey: emailKey)
        UserDefaults.standard.removeObject(forKey: nameKey)
        isAuthenticated = false
    }

    func refreshAccount() async {
        guard isAuthenticated else { return }
        do {
            let account = try await api.getCurrentUser()
            accountEmail = account.email
            accountName = account.name
            UserDefaults.standard.set(account.email, forKey: emailKey)
            UserDefaults.standard.set(account.name, forKey: nameKey)
        } catch {
            if let apiError = error as? APIError, apiError.isUnauthorized {
                clearSession()
            } else {
                errorMessage = error.localizedDescription
            }
        }
    }

    private func saveAccount(_ response: AuthResponse) {
        accountEmail = response.email
        accountName = response.name
        UserDefaults.standard.set(response.email, forKey: emailKey)
        UserDefaults.standard.set(response.name, forKey: nameKey)
    }
}
