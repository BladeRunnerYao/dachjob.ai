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

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape")
                }
        }
        .task {
            await authService.refreshAccount()
        }
    }
}

struct SettingsView: View {
    @Environment(AuthService.self) var authService

    var body: some View {
        NavigationStack {
            Form {
                Section("Account") {
                    LabeledContent("Email", value: authService.accountEmail ?? "Loading...")
                    LabeledContent("Username", value: authService.accountName ?? "Loading...")
                }

                Section("Server") {
                    SettingsLink()
                }

                Section {
                    Button(role: .destructive) {
                        authService.logout()
                    } label: {
                        Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .navigationTitle("Settings")
            .task {
                await authService.refreshAccount()
            }
        }
    }
}
