import SwiftUI

struct JobsListView: View {
    @State private var jobs: [JobPosting] = []
    @State private var total = 0
    @State private var isLoading = true
    @State private var showImport = false
    @State private var filter: String = "all"
    @State private var counts: [String: Int] = ["all": 0, "applied": 0, "saved": 0]
    @State private var page = 0
    @State private var error: String?

    private let api = APIClient.shared
    private let pageSize = 7

    private var totalPages: Int {
        max(1, Int(ceil(Double(total) / Double(pageSize))))
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
                    VStack(spacing: 0) {
                        List(jobs) { job in
                            NavigationLink(destination: JobDetailView(jobId: job.id)) {
                                JobRow(job: job)
                            }
                        }
                        .listStyle(.plain)

                        paginationBar
                    }
                }
            }
            .navigationTitle("Jobs (\(counts["all"] ?? total))")
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
                FilterChip(label: "All", count: counts["all"] ?? 0, isSelected: filter == "all") { selectFilter("all") }
                FilterChip(label: "Applied", count: counts["applied"] ?? 0, isSelected: filter == "applied") { selectFilter("applied") }
                FilterChip(label: "Saved", count: counts["saved"] ?? 0, isSelected: filter == "saved") { selectFilter("saved") }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(Color(.systemGroupedBackground))
    }

    private var paginationBar: some View {
        HStack(spacing: 16) {
            Button {
                page = max(0, page - 1)
                Task { await loadJobs() }
            } label: {
                Image(systemName: "chevron.left")
                    .frame(width: 36, height: 36)
            }
            .buttonStyle(.bordered)
            .disabled(page == 0 || isLoading)

            Text("Page \(page + 1) of \(totalPages)")
                .font(.caption)
                .foregroundColor(.secondary)

            Button {
                page = min(totalPages - 1, page + 1)
                Task { await loadJobs() }
            } label: {
                Image(systemName: "chevron.right")
                    .frame(width: 36, height: 36)
            }
            .buttonStyle(.bordered)
            .disabled(page >= totalPages - 1 || isLoading)
        }
        .padding(.vertical, 10)
        .frame(maxWidth: .infinity)
        .background(Color(.systemBackground))
    }

    private func loadJobs() async {
        isLoading = jobs.isEmpty
        error = nil
        do {
            async let selectedResult = api.getJobs(limit: pageSize, offset: page * pageSize, status: filter == "all" ? nil : filter)
            async let allResult = api.getJobs(limit: 1)
            async let appliedResult = api.getJobs(limit: 1, status: "applied")
            async let savedResult = api.getJobs(limit: 1, status: "saved")
            let result = try await selectedResult
            jobs = result.items
            total = result.total
            counts = [
                "all": try await allResult.total,
                "applied": try await appliedResult.total,
                "saved": try await savedResult.total,
            ]
        } catch let apiError as APIError where apiError.isCancelled {
            isLoading = false
            return
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func selectFilter(_ nextFilter: String) {
        guard filter != nextFilter else { return }
        filter = nextFilter
        page = 0
        Task { await loadJobs() }
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
                if job.isSaved {
                    StatusBadge(status: "saved")
                }
                if let status = job.displayApplicationStatus {
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
    let count: Int
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text("\(label) (\(count))")
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
        case "interview": return .blue
        case "saved": return .orange
        case "rejected": return .red
        case "offer": return .purple
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
