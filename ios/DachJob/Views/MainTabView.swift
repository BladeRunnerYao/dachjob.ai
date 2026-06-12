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

            ApplicationTrackerView()
                .tabItem {
                    Label("Tracker", systemImage: "checklist")
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

struct ApplicationTrackerView: View {
    @State private var applications: [Application] = []
    @State private var selectedStatus = "applied"
    @State private var isLoading = true
    @State private var error: String?
    private let api = APIClient.shared
    private let statuses = ["applied", "interview", "rejected", "offer"]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                statusFilterBar
                Group {
                    if isLoading {
                        ProgressView("Loading tracker...")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if let error {
                        VStack(spacing: 12) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.largeTitle)
                                .foregroundColor(.orange)
                            Text(error)
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                            Button("Retry") { Task { await loadApplications() } }
                        }
                        .padding()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if applications.isEmpty {
                        ContentUnavailableView(
                            "No \(selectedStatus.capitalized) jobs",
                            systemImage: "checklist",
                            description: Text("Jobs with this status will appear here.")
                        )
                    } else {
                        List {
                            ForEach(applications) { application in
                                ApplicationTrackerRow(
                                    application: application,
                                    statuses: statuses
                                ) { status in
                                    await update(application, status: status)
                                }
                            }
                        }
                        .listStyle(.insetGrouped)
                    }
                }
            }
            .navigationTitle("Tracker")
            .refreshable { await loadApplications() }
            .task(id: selectedStatus) { await loadApplications() }
        }
    }

    private var statusFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(statuses, id: \.self) { status in
                    Button {
                        selectedStatus = status
                    } label: {
                        Text(status.capitalized)
                            .font(.subheadline)
                            .fontWeight(.medium)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(selectedStatus == status ? statusColor(status) : .gray)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 10)
        }
        .background(.regularMaterial)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color(.separator))
                .frame(height: 0.5)
        }
        .frame(height: 58)
    }

    private func loadApplications() async {
        let status = selectedStatus
        isLoading = applications.isEmpty
        error = nil
        do {
            applications = try await api.getApplications(status: status)
                .filter { $0.status.lowercased() == status }
                .sorted(by: addedDateDescending)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func update(_ application: Application, status: String) async {
        do {
            let updated = try await api.updateApplication(id: application.id, status: status)
            applications = applications.map { $0.id == updated.id ? updated : $0 }
                .filter { $0.status.lowercased() == selectedStatus }
                .sorted(by: addedDateDescending)
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func addedDateDescending(_ lhs: Application, _ rhs: Application) -> Bool {
        let left = parseISODate(lhs.addedAt ?? lhs.createdAt) ?? .distantPast
        let right = parseISODate(rhs.addedAt ?? rhs.createdAt) ?? .distantPast
        return left > right
    }

    private func statusColor(_ status: String) -> Color {
        switch status {
        case "applied": return .green
        case "interview": return .blue
        case "rejected": return .red
        case "offer": return .purple
        default: return .gray
        }
    }
}

struct ApplicationTrackerRow: View {
    let application: Application
    let statuses: [String]
    let onStatusChange: (String) async -> Void
    @State private var isUpdating = false

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            NavigationLink(destination: JobDetailView(jobId: application.jobId)) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(application.jobTitle)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)
                        .lineLimit(2)
                    Text(application.company)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            HStack(spacing: 8) {
                Menu {
                    ForEach(statuses, id: \.self) { status in
                        Button(status.capitalized) {
                            Task { await changeStatus(status) }
                        }
                    }
                } label: {
                    StatusBadge(status: application.status.lowercased())
                }
                .disabled(isUpdating)

                if let score = application.scorePercent {
                    Text("\(score)% match")
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(score >= 84 ? .green : score >= 72 ? .orange : .red)
                }

                Spacer()

                if let added = application.addedDateText {
                    Label(added, systemImage: "calendar")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                ForEach(application.statusDateLabels, id: \.0) { label, date in
                    Label("\(label) \(date)", systemImage: "checkmark.circle")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            if let notes = application.notes, !notes.isEmpty {
                Text(notes)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 6)
    }

    private func changeStatus(_ status: String) async {
        guard status != application.status.lowercased() else { return }
        isUpdating = true
        await onStatusChange(status)
        isUpdating = false
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
