import SwiftUI

struct JobDetailView: View {
    let jobId: String
    @State private var job: JobPosting?
    @State private var isLoading = true
    @State private var error: String?
    @State private var updatingStatus = false
    @State private var isParsing = false
    @State private var parseError: String?

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
                    if job.needsParsing || job.parsedJson == nil {
                        parseSection
                    }
                    if let parsed = job.parsedJson {
                        if !parsed.requiredQualifications.isEmpty || !parsed.preferredQualifications.isEmpty {
                            responsibilitiesSection(parsed: parsed)
                        }
                        qualificationsSection(job: job)
                        if !parsed.requiredQualifications.isEmpty {
                            requiredSection(parsed: parsed)
                        }
                    } else if let rawJd = job.rawJd, !rawJd.isEmpty {
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
                if let added = job.addedDateText {
                    Label("Added \(added)", systemImage: "calendar")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                ForEach(job.statusDateLabels, id: \.0) { label, date in
                    Label("\(label) \(date)", systemImage: "checkmark.circle")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }

            FlowLayout(spacing: 8) {
                savedButton(isActive: job.isSaved)
                statusButton(label: "Applied", targetStatus: "applied", currentStatus: job.displayApplicationStatus)
                statusButton(label: "Interview", targetStatus: "interview", currentStatus: job.displayApplicationStatus)
                statusButton(label: "Rejected", targetStatus: "rejected", currentStatus: job.displayApplicationStatus)
                statusButton(label: "Offer", targetStatus: "offer", currentStatus: job.displayApplicationStatus)
            }

            if let url = job.url, let link = URL(string: url) {
                Link(destination: link) {
                    Label("View Original", systemImage: "arrow.up.right.square")
                        .font(.subheadline)
                }
            }
        }
    }

    private var parseSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Job Details")
                        .font(.headline)
                    Text("Parse the job description when structured details are missing.")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                Spacer()
                Button {
                    Task { await runParse() }
                } label: {
                    if isParsing {
                        ProgressView()
                    } else {
                        Label("Parse Job", systemImage: "doc.text.magnifyingglass")
                    }
                }
                .buttonStyle(.bordered)
                .disabled(isParsing)
            }
            if let parseError {
                Text(parseError)
                    .font(.caption)
                    .foregroundColor(.red)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(.rect(cornerRadius: 12))
    }

    @ViewBuilder
    private func qualificationsSection(job: JobPosting) -> some View {
        if let parsed = job.parsedJson {
            VStack(alignment: .leading, spacing: 14) {
                Text("Qualifications")
                    .font(.headline)

                if !parsed.mustHaveSkills.isEmpty {
                    skillGroup(title: "Required Skills", skills: parsed.mustHaveSkills)
                }
                if !parsed.niceToHaveSkills.isEmpty {
                    skillGroup(title: "Preferred Skills", skills: parsed.niceToHaveSkills)
                }
                if let years = parsed.experienceYears {
                    Text("\(Int(years))+ years of experience required")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                if !parsed.requiredQualifications.isEmpty {
                    bulletGroup(title: "Required", items: parsed.requiredQualifications)
                }
                if !parsed.preferredQualifications.isEmpty {
                    bulletGroup(title: "Preferred", items: parsed.preferredQualifications)
                }
            }
            .padding()
            .background(Color(.systemBackground))
            .clipShape(.rect(cornerRadius: 12))
            .shadow(color: .black.opacity(0.05), radius: 4, y: 2)
        }
    }

    private func skillGroup(title: String, skills: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
                .textCase(.uppercase)
            FlowLayout(spacing: 6) {
                ForEach(skills, id: \.self) { skill in
                    SkillChip(skill: skill)
                }
            }
        }
    }

    private func bulletGroup(title: String, items: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
                .textCase(.uppercase)
            VStack(alignment: .leading, spacing: 6) {
                ForEach(items, id: \.self) { item in
                    Text("• \(item)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
        }
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

    private func responsibilitiesSection(parsed: ParsedJobDescription) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Responsibilities")
                .font(.headline)
            if !parsed.responsibilities.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(parsed.responsibilities, id: \.self) { item in
                        Text("• \(item)")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(.rect(cornerRadius: 12))
        .shadow(color: .black.opacity(0.05), radius: 4, y: 2)
    }

    private func requiredSection(parsed: ParsedJobDescription) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Requirements")
                .font(.headline)
            VStack(alignment: .leading, spacing: 6) {
                ForEach(parsed.requiredQualifications, id: \.self) { item in
                    Text("• \(item)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            if let years = parsed.experienceYears {
                Text("\(Int(years))+ years of experience required")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(.rect(cornerRadius: 12))
        .shadow(color: .black.opacity(0.05), radius: 4, y: 2)
    }

    private func loadJob() async {
        isLoading = true
        do {
            job = try await api.getJob(id: jobId)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func runParse() async {
        isParsing = true
        parseError = nil
        defer { isParsing = false }

        do {
            job = try await api.parseJob(id: jobId)
        } catch {
            parseError = error.localizedDescription
        }
    }

    @ViewBuilder
    private func statusButton(label: String, targetStatus: String, currentStatus: String?) -> some View {
        let isActive = currentStatus == targetStatus
        let activeColor = statusColor(targetStatus)
        let inactiveColor: Color = .blue
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
                .background(isActive ? activeColor : inactiveColor.opacity(0.12))
                .foregroundColor(isActive ? .white : inactiveColor)
                .clipShape(.rect(cornerRadius: 8))
        }
        .disabled(updatingStatus)
    }

    @ViewBuilder
    private func savedButton(isActive: Bool) -> some View {
        Button {
            Task {
                updatingStatus = true
                if let updated = try? await api.updateJobStatus(id: jobId, saved: !isActive) {
                    job = updated
                }
                updatingStatus = false
            }
        } label: {
            Text("Saved")
                .font(.subheadline)
                .fontWeight(.medium)
                .padding(.horizontal, 14)
                .padding(.vertical, 7)
                .background(isActive ? Color.orange : Color.orange.opacity(0.12))
                .foregroundColor(isActive ? .white : .orange)
                .clipShape(.rect(cornerRadius: 8))
        }
        .disabled(updatingStatus)
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

struct SkillChip: View {
    let skill: String

    var body: some View {
        Text(skill)
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(Color.blue.opacity(0.10))
            .foregroundColor(.blue)
            .clipShape(.rect(cornerRadius: 8))
    }
}
