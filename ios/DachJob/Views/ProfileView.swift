import SwiftUI

struct ProfileView: View {
    @EnvironmentObject var authService: AuthService
    @State private var profile: CandidateProfile?
    @State private var isLoading = true
    @State private var error: String?

    private let api = APIClient.shared

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
                        Button("Retry") { Task { await loadProfile() } }
                    }
                    .padding(.top, 60)
                } else if let profile {
                    profileContent(profile)
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "person.crop.circle.badge.plus")
                            .font(.largeTitle)
                            .foregroundColor(.blue)
                        Text("No profile yet")
                            .font(.headline)
                        Text("Upload your CV in the web app to create your profile.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 60)
                    .padding(.horizontal)
                }
            }
            .navigationTitle("Profile")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
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
            .refreshable { await loadProfile() }
            .task { await loadProfile() }
        }
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
                                .cornerRadius(6)
                        }
                    }
                }
            }
        }
        .padding()
    }

    private func loadProfile() async {
        isLoading = true
        error = nil
        do {
            profile = try await api.getProfile()
        } catch let apiError as APIError {
            if case .serverError(404, _) = apiError {
                profile = nil
            } else {
                error = apiError.localizedDescription
            }
        } catch {
            self.error = error.localizedDescription
        }
        isLoading = false
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
