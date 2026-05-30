import SwiftUI

struct ImportJobView: View {
    @Environment(\.dismiss) var dismiss
    @State private var urlText = ""
    @State private var isImporting = false
    @State private var error: String?
    @State private var successCount = 0

    private let api = APIClient.shared
    let onImported: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section("Job URLs") {
                    TextEditor(text: $urlText)
                        .frame(minHeight: 150)
                        .font(.subheadline)
                }

                Section {
                    Text("Paste one or more job URLs (one per line). Supported: LinkedIn, Indeed, StepStone, and others.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                if let error {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.caption)
                    }
                }

                if successCount > 0 {
                    Section {
                        Text("\(successCount) job(s) imported successfully!")
                            .foregroundColor(.green)
                            .font(.subheadline)
                    }
                }
            }
            .navigationTitle("Import Jobs")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button {
                        Task { await importJobs() }
                    } label: {
                        if isImporting {
                            ProgressView()
                        } else {
                            Text("Import")
                        }
                    }
                    .disabled(urlText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isImporting)
                }
            }
        }
    }

    private func importJobs() async {
        isImporting = true
        error = nil
        let urls = urlText
            .components(separatedBy: .whitespacesAndNewlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { $0.hasPrefix("http://") || $0.hasPrefix("https://") }

        guard !urls.isEmpty else {
            error = "No valid URLs found"
            isImporting = false
            return
        }

        do {
            let result = try await api.importJobs(urls: urls)
            successCount = result.imported.count
            if !result.errors.isEmpty {
                error = result.errors.map { "\($0.url): \($0.error)" }.joined(separator: "\n")
            }
            onImported()
            if result.errors.isEmpty {
                dismiss()
            }
        } catch {
            self.error = error.localizedDescription
        }
        isImporting = false
    }
}
