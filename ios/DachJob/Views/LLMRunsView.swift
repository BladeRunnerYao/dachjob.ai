import SwiftUI

struct LLMRunsView: View {
    @State private var runs: [LLMRun] = []
    @State private var total = 0
    @State private var isLoading = true
    @State private var error: String?

    private let api = APIClient.shared

    var successCount: Int { runs.filter { $0.status == "success" || $0.status == "completed" }.count }
    var errorCount: Int { runs.filter { $0.status == "error" || $0.status == "failed" }.count }
    var avgLatency: Int {
        guard !runs.isEmpty else { return 0 }
        return runs.reduce(0) { $0 + $1.latencyMs } / runs.count
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if isLoading {
                    Spacer()
                    ProgressView("Loading LLM runs...")
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
                        Button("Retry") { Task { await loadRuns() } }
                    }
                    Spacer()
                } else {
                    List {
                        Section {
                            HStack {
                                StatPill(label: "Total", value: "\(total)", color: .blue)
                                StatPill(label: "OK", value: "\(successCount)", color: .green)
                                StatPill(label: "Err", value: "\(errorCount)", color: .red)
                                StatPill(label: "Avg ms", value: "\(avgLatency)", color: .purple)
                            }
                        }

                        Section("Recent Runs") {
                            ForEach(runs) { run in
                                LLMRunRow(run: run)
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("LLM Runs")
            .refreshable { await loadRuns() }
            .task { await loadRuns() }
        }
    }

    private func loadRuns() async {
        isLoading = runs.isEmpty
        error = nil
        do {
            let result = try await api.getLLMRuns(limit: 100)
            runs = result.items
            total = result.total
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }
}

struct LLMRunRow: View {
    let run: LLMRun

    var statusColor: Color {
        switch run.status {
        case "success", "completed": return .green
        case "cache_hit": return .blue
        case "error", "failed": return .red
        default: return .gray
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(run.task)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Text(run.status)
                    .font(.caption2)
                    .fontWeight(.semibold)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(statusColor.opacity(0.15))
                    .foregroundColor(statusColor)
                    .cornerRadius(4)
            }
            HStack(spacing: 12) {
                Text(run.provider)
                    .font(.caption)
                    .foregroundColor(.secondary)
                Text(run.model)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                Spacer()
                Text("\(run.latencyMs)ms")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            if let errorMsg = run.errorMessage {
                Text(errorMsg)
                    .font(.caption)
                    .foregroundColor(.red)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 2)
    }
}

struct StatPill: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundColor(color)
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity)
    }
}
