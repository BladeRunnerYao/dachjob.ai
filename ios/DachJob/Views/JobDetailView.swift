import SwiftUI

struct JobDetailView: View {
    let jobId: String
    @State private var job: JobPosting?
    @State private var matchReport: MatchReport?
    @State private var isLoading = true
    @State private var error: String?
    @State private var updatingStatus = false

    private let api = APIClient.shared

    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .padding(.top, 60)
            } else if let error {
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text(error)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 60)
            } else if let job {
                VStack(alignment: .leading, spacing: 16) {
                    headerSection(job: job)
                    if let match = matchReport {
                        matchSection(match: match)
                    }
                    if let rawJd = job.rawJd, !rawJd.isEmpty {
                        descriptionSection(rawJd: rawJd)
                    }
                }
                .padding()
            }
        }
        .navigationTitle(job?.title ?? "Job Detail")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadJob() }
    }

    private func headerSection(job: JobPosting) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(job.title)
                .font(.title2)
                .fontWeight(.bold)

            HStack(spacing: 16) {
                if let company = job.company {
                    Label(company, systemImage: "building.2")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                if let location = job.location {
                    Label(location, systemImage: "mappin")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }

            HStack(spacing: 12) {
                if let percent = job.scorePercent {
                    HStack(spacing: 4) {
                        Image(systemName: "star.fill")
                            .foregroundColor(percent >= 84 ? .green : percent >= 72 ? .orange : .red)
                        Text("\(percent)% match")
                            .fontWeight(.semibold)
                    }
                    .font(.subheadline)
                }
                if let rec = job.recommendation {
                    RecommendationBadge(recommendation: rec)
                }
            }

            HStack(spacing: 10) {
                statusButton(label: "Applied", targetStatus: "applied", currentStatus: job.status)
                statusButton(label: "Saved", targetStatus: "saved", currentStatus: job.status)
            }

            if let url = job.url, let link = URL(string: url) {
                Link(destination: link) {
                    Label("View Original", systemImage: "arrow.up.right.square")
                        .font(.subheadline)
                }
            }
        }
    }

    private func matchSection(match: MatchReport) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Match Report")
                .font(.headline)
            HStack {
                Text("Score:")
                    .foregroundColor(.secondary)
                Text("\(Int(match.overallScore * 100))%")
                    .fontWeight(.bold)
                    .foregroundColor(match.overallScore >= 0.84 ? .green : match.overallScore >= 0.72 ? .orange : .red)
            }
            .font(.subheadline)
            if let explanation = match.explanation {
                Text(explanation)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(.rect(cornerRadius: 12))
    }

    private func descriptionSection(rawJd: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Job Description")
                .font(.headline)
            Text(rawJd)
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
    }

    private func loadJob() async {
        isLoading = true
        do {
            job = try await api.getJob(id: jobId)
            matchReport = try await api.getMatchReport(jobId: jobId)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    @ViewBuilder
    private func statusButton(label: String, targetStatus: String, currentStatus: String?) -> some View {
        let isActive = currentStatus == targetStatus
        let color: Color = targetStatus == "applied" ? .green : .orange
        Button {
            Task {
                updatingStatus = true
                let newStatus = isActive ? "new" : targetStatus
                if let updated = try? await api.updateJobStatus(id: jobId, status: newStatus) {
                    job = updated
                }
                updatingStatus = false
            }
        } label: {
            Text(label)
                .font(.subheadline)
                .fontWeight(.medium)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(isActive ? color : color.opacity(0.12))
                .foregroundColor(isActive ? .white : color)
                .clipShape(.rect(cornerRadius: 8))
        }
        .disabled(updatingStatus)
    }
}
