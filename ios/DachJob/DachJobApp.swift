import SwiftUI

@main
struct DachJobApp: App {
    @StateObject private var authService = AuthService()

    var body: some Scene {
        WindowGroup {
            if authService.isAuthenticated {
                MainTabView()
                    .environmentObject(authService)
            } else {
                LoginView()
                    .environmentObject(authService)
            }
        }
    }
}
