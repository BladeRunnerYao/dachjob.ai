import SwiftUI

@main
struct DachJobApp: App {
    @State private var authService = AuthService()

    var body: some Scene {
        WindowGroup {
            if authService.isAuthenticated {
                MainTabView()
                    .environment(authService)
            } else {
                LoginView()
                    .environment(authService)
            }
        }
    }
}
