import SwiftUI

struct JobsListView: View {
    @State private var jobs: [JobPosting] = []
    @State private var total = 0
    @State private var isLoading = true
    @State private var showImport = false
    @State private var filter: String = "all"
    @State private var error: String?

    private let api = APIClient.shared
    private let pageSize = 30

    var filteredJobs: [JobPosting] {
        if filter == "all" { return jobs }
        return jobs.filter { $0.status == filter }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                filterBar
                if isLoading {
                    Spacer()
                    ProgressView("Loading jobs...")
                    Spacer()
                } else if let error {
                    Spacer()
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        Button("Retry") { Task { await loadJobs() } }
                    }
                    Spacer()
                } else {
                    List(filteredJobs) { job in
                        NavigationLink(destination: JobDetailView(jobId: job.id)) {
                            JobRow(job: job)
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Jobs (\(total))")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showImport = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showImport) {
                ImportJobView {
                    Task { await loadJobs() }
                }
            }
            .refreshable { await loadJobs() }
            .task { await loadJobs() }
        }
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                FilterChip(label: "All", isSelected: filter == "all") { filter = "all" }
                FilterChip(label: "Applied", isSelected: filter == "applied") { filter = "applied" }
                FilterChip(label: "Saved", isSelected: filter == "saved") { filter = "saved" }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(Color(.systemGroupedBackground))
    }

    private func loadJobs() async {
        isLoading = jobs.isEmpty
        error = nil
        do {
            let result = try await api.getJobs(limit: pageSize)
            jobs = result.items
            total = result.total
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
}

struct JobRow: View {
    let job: JobPosting

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(job.title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(2)
                HStack(spacing: 8) {
                    if let company = job.company {
                        Label(company, systemImage: "building.2")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    if let location = job.location {
                        Label(location, systemImage: "mappin")
                            .font(.caption)
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
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
        }
        .padding(.vertical, 4)
    }
}

struct FilterChip: View {
    let label: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(label)
                .font(.caption)
                .fontWeight(.medium)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(isSelected ? Color.blue : Color(.systemGray5))
                .foregroundColor(isSelected ? .white : .primary)
                .clipShape(.rect(cornerRadius: 16))
        }
    }
}

struct StatusBadge: View {
    let status: String

    var color: Color {
        switch status {
        case "applied": return .green
        case "saved": return .orange
        default: return .gray
        }
    }

    var body: some View {
        Text(status.capitalized)
            .font(.caption2)
            .fontWeight(.semibold)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .clipShape(.rect(cornerRadius: 4))
    }
}
