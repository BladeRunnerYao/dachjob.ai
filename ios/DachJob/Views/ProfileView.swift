import SwiftUI
import UniformTypeIdentifiers

private enum CVDisplayMode: String, CaseIterable, Identifiable {
    case preview = "Preview"
    case markdown = "Markdown"

    var id: String { rawValue }
}

struct ProfileView: View {
    @Environment(AuthService.self) var authService
    @State private var profile: CandidateProfile?
    @State private var isLoading = true
    @State private var isLoadingProfile = false
    @State private var isSavingCv = false
    @State private var showMarkdownEditor = false
    @State private var showPdfImporter = false
    @State private var showUrlImporter = false
    @State private var urlDraft = ""
    @State private var markdownDraft = ""
    @State private var cvDisplayMode: CVDisplayMode = .preview
    @State private var lastLoadedAt: Date?
    @State private var uploadMessage: String?
    @State private var error: String?

    private let api = APIClient.shared
    private let profileReloadInterval: TimeInterval = 30

    var body: some View {
        NavigationStack {
            ScrollView {
                if isLoading {
                    ProgressView("Loading profile...")
                        .padding(.top, 60)
                } else if let error {
                    VStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.badge.exclamationmark")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        Button("Retry") { Task { await loadProfile(force: true) } }
                    }
                    .padding(.top, 60)
                } else if let profile {
                    VStack(alignment: .leading, spacing: 16) {
                        uploadBanner
                        profileActions
                        profileContent(profile)
                    }
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.badge.plus")
                            .font(.largeTitle)
                            .foregroundColor(.blue)
                        Text("No profile yet")
                            .font(.headline)
                        Text("Upload your CV as Markdown or PDF to create your profile.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        profileActions
                    }
                    .padding(.top, 60)
                    .padding(.horizontal)
                }
            }
            .navigationTitle("Profile")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button {
                            openMarkdownEditor()
                        } label: {
                            Label("Edit Markdown CV", systemImage: "doc.text")
                        }
                        Button {
                            showPdfImporter = true
                        } label: {
                            Label("Upload PDF CV", systemImage: "doc.badge.plus")
                        }
                        Button {
                            showUrlImporter = true
                        } label: {
                            Label("Import from URL", systemImage: "link")
                        }
                        Divider()
                        Button(role: .destructive) {
                            authService.logout()
                        } label: {
                            Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .sheet(isPresented: $showMarkdownEditor) {
                MarkdownCVEditor(
                    markdown: $markdownDraft,
                    isSaving: isSavingCv,
                    onCancel: { showMarkdownEditor = false },
                    onSave: { Task { await uploadMarkdownCv() } }
                )
            }
            .fileImporter(
                isPresented: $showPdfImporter,
                allowedContentTypes: [.pdf],
                allowsMultipleSelection: false
            ) { result in
                switch result {
                case .success(let urls):
                    guard let url = urls.first else { return }
                    Task { await uploadPdfCv(url) }
                case .failure(let error):
                    self.error = error.localizedDescription
                }
            }
            .alert("Import from URL", isPresented: $showUrlImporter) {
                TextField("LinkedIn or personal website URL", text: $urlDraft)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("Import") { Task { await importFromUrl() } }
                Button("Cancel", role: .cancel) { urlDraft = "" }
            } message: {
                Text("Enter your LinkedIn profile or personal website URL to create your CV.")
            }
            .refreshable { await loadProfile(force: true) }
            .task { await loadProfile() }
        }
    }

    @ViewBuilder
    private var uploadBanner: some View {
        if let uploadMessage {
            Text(uploadMessage)
                .font(.caption)
                .foregroundColor(.green)
                .padding(.horizontal)
        }
    }

    private var profileActions: some View {
        HStack(spacing: 10) {
            Button {
                openMarkdownEditor()
            } label: {
                Label("Markdown CV", systemImage: "doc.text")
            }
            .buttonStyle(.borderedProminent)

            Button {
                showPdfImporter = true
            } label: {
                Label("Upload PDF", systemImage: "doc.badge.plus")
            }
            .buttonStyle(.bordered)

            Button {
                showUrlImporter = true
            } label: {
                Label("From URL", systemImage: "link")
            }
            .buttonStyle(.bordered)
        }
        .disabled(isSavingCv)
        .padding(.horizontal)
    }

    private func profileContent(_ profile: CandidateProfile) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                if let name = profile.fullName {
                    Text(name)
                        .font(.title2)
                        .fontWeight(.bold)
                }
                if let headline = profile.headline {
                    Text(headline)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                if let location = profile.location {
                    Label(location, systemImage: "mappin")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }

            if let skills = profile.skills, !skills.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Skills")
                        .font(.headline)
                    FlowLayout(spacing: 6) {
                        ForEach(skills, id: \.self) { skill in
                            Text(skill)
                                .font(.caption)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.blue.opacity(0.1))
                                .foregroundColor(.blue)
                                .clipShape(.rect(cornerRadius: 6))
                        }
                    }
                }
            }

            if !profile.rawCvMd.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text("CV")
                            .font(.headline)
                        Spacer()
                        Button("Edit") { openMarkdownEditor() }
                            .font(.caption)
                    }
                    Picker("CV View", selection: $cvDisplayMode) {
                        ForEach(CVDisplayMode.allCases) { mode in
                            Text(mode.rawValue).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)

                    if cvDisplayMode == .preview {
                        MarkdownPreview(markdown: profile.rawCvMd)
                    } else {
                        Text(profile.rawCvMd)
                            .font(.footnote.monospaced())
                            .foregroundColor(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(10)
                            .background(Color(.systemGray6))
                            .clipShape(.rect(cornerRadius: 8))
                    }
                }
            }
        }
        .padding()
    }

    private func openMarkdownEditor() {
        markdownDraft = profile?.rawCvMd ?? "# Your Name\n\n## Profile\n\n"
        showMarkdownEditor = true
    }

    private func uploadMarkdownCv() async {
        let markdown = markdownDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !markdown.isEmpty else { return }
        isSavingCv = true
        uploadMessage = nil
        error = nil
        defer { isSavingCv = false }

        do {
            profile = try await api.uploadCvMarkdown(markdown)
            lastLoadedAt = Date()
            uploadMessage = "CV markdown saved."
            showMarkdownEditor = false
        } catch let apiError as APIError where apiError.isCancelled {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func uploadPdfCv(_ url: URL) async {
        isSavingCv = true
        uploadMessage = nil
        error = nil
        defer { isSavingCv = false }

        do {
            profile = try await api.importProfileFromPdf(fileURL: url)
            lastLoadedAt = Date()
            uploadMessage = "PDF CV imported."
        } catch let apiError as APIError where apiError.isCancelled {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func importFromUrl() async {
        let url = urlDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !url.isEmpty else { return }
        isSavingCv = true
        uploadMessage = nil
        error = nil
        defer {
            isSavingCv = false
            urlDraft = ""
        }

        do {
            profile = try await api.importProfileFromUrl(url)
            lastLoadedAt = Date()
            uploadMessage = "Profile imported from URL."
        } catch let apiError as APIError where apiError.isCancelled {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func loadProfile(force: Bool = false) async {
        if isLoadingProfile { return }
        if !force,
           profile != nil,
           let lastLoadedAt,
           Date().timeIntervalSince(lastLoadedAt) < profileReloadInterval {
            isLoading = false
            return
        }

        isLoadingProfile = true
        isLoading = profile == nil
        error = nil
        defer {
            isLoadingProfile = false
            isLoading = false
        }
        do {
            profile = try await api.getProfile()
            lastLoadedAt = Date()
        } catch let apiError as APIError where apiError.isCancelled {
            return
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct MarkdownPreview: View {
    let markdown: String

    private enum MarkdownBlock {
        case heading(level: Int, text: String)
        case paragraph(String)
        case bullets([MarkdownListItem])
    }

    private struct MarkdownListItem: Hashable {
        let marker: String
        let text: String
    }

    private var blocks: [MarkdownBlock] {
        var result: [MarkdownBlock] = []
        var paragraphLines: [String] = []
        var bulletLines: [MarkdownListItem] = []

        func flushParagraph() {
            let text = paragraphLines.joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                result.append(.paragraph(text))
            }
            paragraphLines.removeAll()
        }

        func flushBullets() {
            if !bulletLines.isEmpty {
                result.append(.bullets(bulletLines))
            }
            bulletLines.removeAll()
        }

        for rawLine in markdown.replacingOccurrences(of: "\r\n", with: "\n").split(separator: "\n", omittingEmptySubsequences: false) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            if line.isEmpty {
                flushParagraph()
                flushBullets()
                continue
            }
            if line.hasPrefix("#") {
                flushParagraph()
                flushBullets()
                let level = line.prefix(while: { $0 == "#" }).count
                let text = String(line.drop(while: { $0 == "#" }))
                    .trimmingCharacters(in: .whitespaces)
                result.append(.heading(level: level, text: text))
            } else if line.hasPrefix("- ") || line.hasPrefix("* ") || line.hasPrefix("• ") {
                flushParagraph()
                bulletLines.append(MarkdownListItem(marker: "•", text: String(line.dropFirst(2))))
            } else if let ordered = orderedListItem(from: line) {
                flushParagraph()
                bulletLines.append(ordered)
            } else {
                flushBullets()
                paragraphLines.append(String(line))
            }
        }
        flushParagraph()
        flushBullets()
        return result
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(Array(blocks.enumerated()), id: \.offset) { _, block in
                switch block {
                case .heading(let level, let text):
                    markdownText(text)
                        .font(level <= 1 ? .title3.bold() : level == 2 ? .headline : .subheadline.bold())
                        .foregroundColor(.primary)
                        .padding(.top, level <= 2 ? 6 : 2)
                case .paragraph(let text):
                    markdownText(text)
                        .font(.body)
                        .lineSpacing(4)
                        .foregroundColor(.secondary)
                case .bullets(let items):
                    VStack(alignment: .leading, spacing: 6) {
                        ForEach(items, id: \.self) { item in
                            HStack(alignment: .top, spacing: 8) {
                                Text(item.marker)
                                    .fontWeight(.semibold)
                                    .frame(minWidth: item.marker == "•" ? 8 : 22, alignment: .leading)
                                markdownText(item.text)
                                    .lineSpacing(3)
                            }
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color(.systemBackground))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color(.systemGray4), lineWidth: 1)
            )
    }

    private func orderedListItem(from line: String) -> MarkdownListItem? {
        guard let dotIndex = line.firstIndex(of: ".") else { return nil }
        let marker = line[..<dotIndex]
        guard !marker.isEmpty, marker.allSatisfy({ $0.isNumber }) else { return nil }
        let contentStart = line.index(after: dotIndex)
        guard contentStart < line.endIndex, line[contentStart].isWhitespace else { return nil }
        let text = line[contentStart...].trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return nil }
        return MarkdownListItem(marker: "\(marker).", text: text)
    }

    private func markdownText(_ text: String) -> Text {
        if let attributed = try? AttributedString(markdown: text, options: AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
            return Text(attributed)
        }
        return Text(text)
    }
}

struct MarkdownCVEditor: View {
    @Binding var markdown: String
    let isSaving: Bool
    let onCancel: () -> Void
    let onSave: () -> Void

    var body: some View {
        NavigationStack {
            TextEditor(text: $markdown)
                .font(.body.monospaced())
                .padding()
                .navigationTitle("Markdown CV")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel", action: onCancel)
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button(isSaving ? "Saving..." : "Save", action: onSave)
                            .disabled(isSaving || markdown.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
        }
    }
}

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrange(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrange(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
        }
    }

    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var x: CGFloat = 0
        var y: CGFloat = 0
        var rowHeight: CGFloat = 0
        var totalHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if x + size.width > maxWidth && x > 0 {
                x = 0
                y += rowHeight + spacing
                rowHeight = 0
            }
            positions.append(CGPoint(x: x, y: y))
            rowHeight = max(rowHeight, size.height)
            x += size.width + spacing
            totalHeight = y + rowHeight
        }

        return (CGSize(width: maxWidth, height: totalHeight), positions)
    }
}
