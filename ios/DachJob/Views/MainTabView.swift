import SwiftUI

struct MainTabView: View {
    @Environment(AuthService.self) var authService

    var body: some View {
        TabView {
            DashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.bar")
                }

            JobsListView()
                .tabItem {
                    Label("Jobs", systemImage: "briefcase")
                }

            LLMRunsView()
                .tabItem {
                    Label("LLM Runs", systemImage: "cpu")
                }

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person")
                }
        }
    }
}
