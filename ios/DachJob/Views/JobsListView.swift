import SwiftUI

struct JobsListView: View {
    @State private var jobs: [JobPosting] = []
    @State private var total = 0
    @State private var isLoading = true
    @State private var showImport = false
    @State private var selectedCompany = ""
    @State private var selectedAddedDate = ""
    @State private var selectedCountry = ""
    @State private var selectedStatus = "all"
    @State private var filterOptions = JobFilterOptions(companies: [], statuses: [], addedDates: [], countries: [])
    @State private var page = 0
    @State private var pageSize = 15
    @State private var error: String?

    private let api = APIClient.shared
    private let statusFilters = ["saved", "applied", "interview", "rejected", "offer"]

    private var totalPages: Int {
        max(1, Int(ceil(Double(total) / Double(pageSize))))
    }

    private var loadTaskID: String {
        "\(selectedCompany):\(selectedAddedDate):\(selectedCountry):\(selectedStatus):\(page):\(pageSize)"
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
            .task(id: loadTaskID) { await loadJobs(debounced: !jobs.isEmpty) }
        }
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                Button {
                    clearFilters()
                } label: {
                    Label("All", systemImage: "tray.full")
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                .buttonStyle(.borderedProminent)
                .tint(filtersAreClear ? .blue : .gray)

                Menu {
                    Button("All companies") { selectCompany("") }
                    ForEach(filterOptions.companies) { company in
                        Button("\(company.value) (\(company.count))") { selectCompany(company.value) }
                    }
                } label: {
                    Label(selectedCompany.isEmpty ? "Company" : selectedCompany, systemImage: "building.2")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(1)
                }
                .buttonStyle(.borderedProminent)
                .tint(selectedCompany.isEmpty ? .gray : .blue)

                Menu {
                    Button("All added dates") { selectAddedDate("") }
                    ForEach(filterOptions.addedDates) { addedDate in
                        Button("\(formatShortDate(addedDate.value) ?? addedDate.value) (\(addedDate.count))") {
                            selectAddedDate(addedDate.value)
                        }
                    }
                } label: {
                    Label(selectedAddedDate.isEmpty ? "Added date" : (formatShortDate(selectedAddedDate) ?? selectedAddedDate), systemImage: "calendar")
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                .buttonStyle(.borderedProminent)
                .tint(selectedAddedDate.isEmpty ? .gray : .blue)

                Menu {
                    Button("All countries") { selectCountry("") }
                    ForEach(filterOptions.countries) { country in
                        Button("\(country.value) (\(country.count))") { selectCountry(country.value) }
                    }
                } label: {
                    Label(selectedCountry.isEmpty ? "Country" : selectedCountry, systemImage: "globe.europe.africa")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .lineLimit(1)
                }
                .buttonStyle(.borderedProminent)
                .tint(selectedCountry.isEmpty ? .gray : .blue)

                Menu {
                    Button("All statuses") { selectStatus("all") }
                    ForEach(statusFilters, id: \.self) { status in
                        let count = filterOptions.count(forStatus: status)
                        Button("\(status.capitalized) (\(count))") { selectStatus(status) }
                    }
                } label: {
                    Label(selectedStatus == "all" ? "Status" : selectedStatus.capitalized, systemImage: "line.3.horizontal.decrease.circle")
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                .buttonStyle(.borderedProminent)
                .tint(selectedStatus == "all" ? .gray : .blue)

                Menu {
                    ForEach([15, 30, 50, 100], id: \.self) { size in
                        Button("\(size)") { selectPageSize(size) }
                    }
                } label: {
                    Label("\(pageSize)", systemImage: "number")
                        .font(.subheadline)
                        .fontWeight(.medium)
                }
                .buttonStyle(.borderedProminent)
                .tint(.gray)
            }
            .padding(.horizontal)
            .padding(.vertical, 10)
        }
        .background(.regularMaterial)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(Color(.separator))
                .frame(height: 0.5)
        }
        .frame(height: 58)
    }

    private var paginationBar: some View {
        HStack(spacing: 16) {
            Button {
                page = max(0, page - 1)
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

    private func loadJobs(debounced: Bool = false) async {
        let company = selectedCompany
        let addedDate = selectedAddedDate
        let country = selectedCountry
        let status = selectedStatus
        let selectedPage = page
        let selectedPageSize = pageSize
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
            async let selectedResult = api.getJobs(
                limit: selectedPageSize,
                offset: selectedPage * selectedPageSize,
                status: status == "saved" ? status : nil,
                stage: status != "all" && status != "saved" ? status : nil,
                company: company.isEmpty ? nil : company,
                addedDate: addedDate.isEmpty ? nil : addedDate,
                country: country.isEmpty ? nil : country
            )
            async let filtersResult = api.getJobFilters()
            let result = try await selectedResult
            guard !Task.isCancelled,
                  company == selectedCompany,
                  addedDate == selectedAddedDate,
                  country == selectedCountry,
                  status == selectedStatus,
                  selectedPage == page,
                  selectedPageSize == pageSize else { return }
            jobs = result.items
            total = result.total
            filterOptions = try await filtersResult
        } catch let apiError as APIError where apiError.isCancelled {
            return
        } catch let apiError as APIError where apiError.isRateLimited && !jobs.isEmpty {
            return
        } catch {
            guard !Task.isCancelled,
                  company == selectedCompany,
                  addedDate == selectedAddedDate,
                  country == selectedCountry,
                  status == selectedStatus,
                  selectedPage == page else { return }
            self.error = error.localizedDescription
        }
        isLoading = false
    }

    private var filtersAreClear: Bool {
        selectedCompany.isEmpty && selectedAddedDate.isEmpty && selectedCountry.isEmpty && selectedStatus == "all"
    }

    private func clearFilters() {
        selectedCompany = ""
        selectedAddedDate = ""
        selectedCountry = ""
        selectedStatus = "all"
        page = 0
    }

    private func selectCompany(_ company: String) {
        selectedCompany = company
        page = 0
    }

    private func selectAddedDate(_ addedDate: String) {
        selectedAddedDate = addedDate
        page = 0
    }

    private func selectCountry(_ country: String) {
        selectedCountry = country
        page = 0
    }

    private func selectStatus(_ status: String) {
        selectedStatus = status
        page = 0
    }

    private func selectPageSize(_ size: Int) {
        pageSize = size
        page = 0
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
                if job.isSaved {
                    StatusBadge(status: "saved")
                }
                if let status = job.displayApplicationStatus {
                    StatusBadge(status: status)
                }
                if let added = job.addedDateText {
                    Text(added)
                        .font(.caption2)
                        .foregroundColor(.secondary)
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
