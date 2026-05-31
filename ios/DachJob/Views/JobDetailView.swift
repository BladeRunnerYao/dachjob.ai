import SwiftUI

struct JobDetailView: View {
    let jobId: String
    @State private var job: JobPosting?
    @State private var matchReport: MatchReport?
    @State private var isLoading = true
    @State private var error: String?
    @State private var updatingStatus = false
    @State private var generatingResumeStyle: ResumeStyle?
    @State private var resumeMessage: String?
    @State private var resumeError: String?
    @State private var selectedSkills: Set<String> = []

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
                    resumeSection
                    if let percent = matchReport?.scorePercent ?? job.scorePercent {
                        matchSection(percent: percent)
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

    private func matchSection(percent: Int) -> some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(matchColor(percent).opacity(0.12))
                Text("\(percent)%")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(matchColor(percent))
            }
            .frame(width: 72, height: 72)

            VStack(alignment: .leading, spacing: 4) {
                Text("Match")
                    .font(.headline)
                Text("Latest database score")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            Spacer()
        }
        .padding()
        .background(Color(.systemGray6))
        .clipShape(.rect(cornerRadius: 12))
    }

    private var resumeSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Generate CV")
                .font(.headline)

            HStack(spacing: 10) {
                ForEach(ResumeStyle.allCases) { style in
                    Button {
                        Task { await generateResume(style: style) }
                    } label: {
                        if generatingResumeStyle == style {
                            ProgressView()
                                .frame(maxWidth: .infinity)
                        } else {
                            Text(style.title)
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(style == .american ? .blue : .orange)
                    .disabled(generatingResumeStyle != nil)
                }
            }

            if let resumeMessage {
                Text(resumeMessage)
                    .font(.caption)
                    .foregroundColor(.green)
            }
            if let resumeError {
                Text(resumeError)
                    .font(.caption)
                    .foregroundColor(.red)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(.rect(cornerRadius: 12))
        .shadow(color: .black.opacity(0.05), radius: 4, y: 2)
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
                    SkillChoiceChip(skill: skill, isSelected: selectedSkills.contains(skill)) {
                        toggleSkill(skill)
                    }
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
            matchReport = try await api.getMatchReport(jobId: jobId)
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private func toggleSkill(_ skill: String) {
        if selectedSkills.contains(skill) {
            selectedSkills.remove(skill)
        } else {
            selectedSkills.insert(skill)
        }
    }

    private func generateResume(style: ResumeStyle) async {
        generatingResumeStyle = style
        resumeMessage = nil
        resumeError = nil
        defer { generatingResumeStyle = nil }

        do {
            _ = try await api.createResumeArtifact(
                jobId: jobId,
                style: style,
                confirmedSkills: Array(selectedSkills)
            )
            resumeMessage = "\(style.title) generated."
        } catch {
            resumeError = error.localizedDescription
        }
    }

    private func matchColor(_ percent: Int) -> Color {
        if percent >= 84 { return .green }
        if percent >= 72 { return .orange }
        return .red
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

struct SkillChoiceChip: View {
    let skill: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "plus.circle")
                    .font(.caption2)
                Text(skill)
            }
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 5)
            .background(isSelected ? Color.green.opacity(0.18) : Color.blue.opacity(0.10))
            .foregroundColor(isSelected ? .green : .blue)
            .clipShape(.rect(cornerRadius: 8))
        }
    }
}
