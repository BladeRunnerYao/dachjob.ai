import SwiftUI

struct DashboardView: View {
    @State private var jobs: [JobPosting] = []
    @State private var totalJobs = 0
    @State private var appliedCount = 0
    @State private var savedCount = 0
    @State private var isLoading = true
    @State private var error: String?

    private let api = APIClient.shared

    var body: some View {
        NavigationStack {
            ScrollView {
                if isLoading {
                    ProgressView("Loading dashboard...")
                        .padding(.top, 60)
                } else if let error {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        Button("Retry") { Task { await loadData() } }
                    }
                    .padding(.top, 60)
                } else {
                    VStack(spacing: 20) {
                        statsGrid
                        recentJobsSection
                    }
                    .padding()
                }
            }
            .navigationTitle("Dashboard")
            .refreshable { await loadData() }
            .task { await loadData() }
        }
    }

    private var statsGrid: some View {
        LazyVGrid(columns: [
            GridItem(.flexible()),
            GridItem(.flexible()),
            GridItem(.flexible()),
        ], spacing: 12) {
            StatCard(title: "Jobs", value: "\(totalJobs)", color: .blue)
            StatCard(title: "Applied", value: "\(appliedCount)", color: .green)
            StatCard(title: "Saved", value: "\(savedCount)", color: .orange)
        }
    }

    private var recentJobsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Recent Jobs")
                .font(.headline)
            ForEach(jobs.prefix(5)) { job in
                NavigationLink(destination: JobDetailView(jobId: job.id)) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(job.title)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(.primary)
                                .lineLimit(1)
                            Text(job.company ?? "Unknown")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        if let percent = job.scorePercent {
                            Text("\(percent)%")
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundColor(percent >= 84 ? .green : percent >= 72 ? .orange : .red)
                        }
                        if let status = job.status, status != "new" {
                            StatusBadge(status: status)
                        } else if let rec = job.recommendation {
                            RecommendationBadge(recommendation: rec)
                        }
                    }
                    .padding(.vertical, 6)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(.rect(cornerRadius: 12))
        .shadow(color: .black.opacity(0.05), radius: 4, y: 2)
    }

    private func loadData() async {
        isLoading = jobs.isEmpty
        error = nil
        do {
            async let jobsResult = api.getJobs(limit: 5)
            async let appliedResult = api.getJobs(limit: 1, status: "applied")
            async let savedResult = api.getJobs(limit: 1, status: "saved")
            let recentJobs = try await jobsResult
            jobs = recentJobs.items
            totalJobs = recentJobs.total
            appliedCount = try await appliedResult.total
            savedCount = try await savedResult.total
        } catch let apiError as APIError where apiError.isCancelled {
            isLoading = false
            return
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
}

struct StatCard: View {
    let title: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title2)
                .fontWeight(.bold)
                .foregroundColor(color)
            Text(title)
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(Color(.systemBackground))
        .clipShape(.rect(cornerRadius: 10))
        .shadow(color: .black.opacity(0.05), radius: 3, y: 1)
    }
}

struct RecommendationBadge: View {
    let recommendation: String

    var color: Color {
        switch recommendation {
        case "apply": return .green
        case "maybe": return .orange
        default: return .red
        }
    }

    var body: some View {
        Text(recommendation.capitalized)
            .font(.caption2)
            .fontWeight(.semibold)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .clipShape(.rect(cornerRadius: 4))
    }
}
