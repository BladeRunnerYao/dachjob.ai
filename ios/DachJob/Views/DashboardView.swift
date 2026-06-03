import SwiftUI

struct DashboardView: View {
    @State private var jobs: [JobPosting] = []
    @State private var totalJobs = 0
    @State private var appliedCount = 0
    @State private var savedCount = 0
    @State private var filter = "all"
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
                        filterBar
                        recentJobsSection
                    }
                    .padding()
                }
            }
            .navigationTitle("Dashboard")
            .refreshable { await loadData() }
            .task(id: filter) { await loadData(debounced: !jobs.isEmpty) }
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
            Text(sectionTitle)
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
                        if job.isSaved {
                            StatusBadge(status: "saved")
                        }
                        if let status = job.displayApplicationStatus {
                            StatusBadge(status: status)
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

    private var filterBar: some View {
        HStack(spacing: 8) {
            FilterChip(label: "All", count: totalJobs, isSelected: filter == "all") {
                selectFilter("all")
            }
            FilterChip(label: "Applied", count: appliedCount, isSelected: filter == "applied") {
                selectFilter("applied")
            }
            FilterChip(label: "Saved", count: savedCount, isSelected: filter == "saved") {
                selectFilter("saved")
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var sectionTitle: String {
        switch filter {
        case "applied": return "Recent Applied"
        case "saved": return "Recent Saved"
        default: return "Recent Jobs"
        }
    }

    private func loadData(debounced: Bool = false) async {
        let selectedFilter = filter
        if debounced {
            do {
                try await Task.sleep(nanoseconds: 250_000_000)
            } catch {
                return
            }
        }
        guard !Task.isCancelled else { return }

        isLoading = jobs.isEmpty
        error = nil
        do {
            let listStatus = selectedFilter == "saved" ? "saved" : nil
            let listStage = selectedFilter == "applied" ? "applied" : nil
            async let jobsResult = api.getJobs(
                limit: 5,
                status: listStatus,
                stage: listStage
            )
            async let appliedResult = api.getJobs(limit: 1, stage: "applied")
            async let savedResult = api.getJobs(limit: 1, status: "saved")
            let recentJobs = try await jobsResult
            guard !Task.isCancelled, selectedFilter == filter else { return }
            jobs = recentJobs.items
            totalJobs = recentJobs.total
            appliedCount = try await appliedResult.total
            savedCount = try await savedResult.total
        } catch let apiError as APIError where apiError.isCancelled {
            return
        } catch let apiError as APIError where apiError.isRateLimited && !jobs.isEmpty {
            return
        } catch {
            guard !Task.isCancelled, selectedFilter == filter else { return }
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func selectFilter(_ nextFilter: String) {
        guard filter != nextFilter else { return }
        filter = nextFilter
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
