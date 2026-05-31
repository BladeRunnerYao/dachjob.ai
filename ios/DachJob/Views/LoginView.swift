import SwiftUI

struct LoginView: View {
    @Environment(AuthService.self) var authService
    @State private var email = ""
    @State private var password = ""
    @State private var showRegister = false
    @State private var showForgotPassword = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                Spacer()

                VStack(spacing: 8) {
                    Text("dachjob.ai")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    Text("AI-powered job matching for DACH")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }

                VStack(spacing: 16) {
                    TextField("Email", text: $email)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.emailAddress)
                        .autocapitalization(.none)
                        .keyboardType(.emailAddress)

                    SecureField("Password", text: $password)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.password)
                }
                .padding(.horizontal)

                if let error = authService.errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                Button {
                    Task {
                        await authService.login(email: email, password: password)
                    }
                } label: {
                    if authService.isLoading {
                        ProgressView()
                            .frame(maxWidth: .infinity)
                    } else {
                        Text("Sign In")
                            .frame(maxWidth: .infinity)
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(email.isEmpty || password.isEmpty || authService.isLoading)
                .padding(.horizontal)

                Button("Create Account") {
                    showRegister = true
                }
                .font(.subheadline)

                Button("Forgot password?") {
                    showForgotPassword = true
                }
                .font(.subheadline)

                Spacer()

                SettingsLink()
                    .padding(.bottom)
            }
            .sheet(isPresented: $showRegister) {
                RegisterView()
                    .environment(authService)
            }
            .sheet(isPresented: $showForgotPassword) {
                ForgotPasswordView(initialEmail: email)
            }
        }
    }
}

struct ForgotPasswordView: View {
    @Environment(\.dismiss) var dismiss
    @State private var email: String
    @State private var isSubmitting = false
    @State private var message: String?
    @State private var resetLink: String?
    @State private var error: String?

    private let api = APIClient.shared

    init(initialEmail: String) {
        _email = State(initialValue: initialEmail)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Account") {
                    TextField("Email", text: $email)
                        .textContentType(.emailAddress)
                        .autocapitalization(.none)
                        .keyboardType(.emailAddress)
                }

                if let error {
                    Section {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                }

                if let message {
                    Section("Reset Link") {
                        Text(message)
                            .font(.subheadline)
                        if let resetLink, let url = URL(string: resetLink) {
                            Link("Open password reset page", destination: url)
                        }
                    }
                }

                Section {
                    Button {
                        Task { await requestReset() }
                    } label: {
                        if isSubmitting {
                            ProgressView()
                                .frame(maxWidth: .infinity)
                        } else {
                            Text("Send Reset Link")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(email.isEmpty || isSubmitting)
                }
            }
            .navigationTitle("Reset Password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func requestReset() async {
        isSubmitting = true
        message = nil
        resetLink = nil
        error = nil
        defer { isSubmitting = false }

        do {
            let response = try await api.requestPasswordReset(email: email)
            message = response.message
            resetLink = response.resetLink
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct SettingsLink: View {
    @Environment(AuthService.self) var authService
    @State private var showSettings = false

    var body: some View {
        Button("Server Settings") {
            showSettings = true
        }
        .font(.caption)
        .foregroundColor(.secondary)
        .sheet(isPresented: $showSettings) {
            ServerSettingsView()
                .environment(authService)
        }
    }
}

struct ServerSettingsView: View {
    @Environment(AuthService.self) var authService
    @Environment(\.dismiss) var dismiss
    @State private var apiURL: String = UserDefaults.standard.string(forKey: "api_base_url") ?? "https://dachjob-dev-api-qxugiew36a-ew.a.run.app"

    var body: some View {
        NavigationStack {
            Form {
                Section("API Server") {
                    TextField("Base URL", text: $apiURL)
                        .autocapitalization(.none)
                        .keyboardType(.URL)
                }
                Section {
                    Text("Default: GCP Cloud Run endpoint")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text("Changing the server will require you to log in again.")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
            .navigationTitle("Server Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let oldURL = UserDefaults.standard.string(forKey: "api_base_url") ?? "https://dachjob-dev-api-qxugiew36a-ew.a.run.app"
                        UserDefaults.standard.set(apiURL, forKey: "api_base_url")
                        if apiURL != oldURL {
                            authService.logout()
                        }
                        dismiss()
                    }
                }
            }
        }
    }
}

struct RegisterView: View {
    @Environment(AuthService.self) var authService
    @Environment(\.dismiss) var dismiss
    @State private var fullName = ""
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Account") {
                    TextField("Full Name", text: $fullName)
                        .textContentType(.name)
                    TextField("Email", text: $email)
                        .textContentType(.emailAddress)
                        .autocapitalization(.none)
                        .keyboardType(.emailAddress)
                    SecureField("Password", text: $password)
                        .textContentType(.newPassword)
                }

                if let error = authService.errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.caption)
                    }
                }

                Section {
                    Button {
                        Task {
                            await authService.register(email: email, password: password, fullName: fullName)
                            if authService.isAuthenticated {
                                dismiss()
                            }
                        }
                    } label: {
                        if authService.isLoading {
                            ProgressView()
                                .frame(maxWidth: .infinity)
                        } else {
                            Text("Create Account")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(fullName.isEmpty || email.isEmpty || password.isEmpty || authService.isLoading)
                }
            }
            .navigationTitle("Register")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }
}
