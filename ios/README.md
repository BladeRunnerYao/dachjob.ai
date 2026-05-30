# DachJob iOS App

A native iOS app for the dachjob.ai platform, built with SwiftUI. Connects to the same backend API used by the web frontend.

## Requirements

- **Xcode 26+** (Swift 6.2+)
- **XcodeGen** (`brew install xcodegen`)
- **iOS 26.0+** (iPhone)
- macOS 14+ (Sonoma) for development

## Project Setup

### Option 1: Generate Xcode Project (Recommended)

```bash
cd ios
xcodegen generate
open DachJob.xcodeproj
```

The generated app target uses:
- Product Name: `DachJob`
- Bundle Identifier: `ai.dachjob.app`
- Interface: **SwiftUI**
- Language: **Swift 6.2**
- Minimum Deployment: **iOS 26.0**

### Option 2: Open as Swift Package (Preview Only)

```bash
cd ios
open Package.swift
```

This allows browsing/editing code but won't produce a runnable app (use Option 1 for that).

## Build & Run

1. Open the generated Xcode project (from Option 1)
2. Select an iPhone simulator or connect a real device
3. Press **⌘R** to build and run

### Running on Physical Device

1. In Xcode → Signing & Capabilities, select your Apple Developer Team
2. Connect your iPhone via USB or Wi-Fi
3. Trust the developer certificate on the device (Settings → General → Device Management)
4. Press **⌘R**

## Configuration

### API Server

By default, the app connects to the **AWS CloudFront** endpoint:
```
https://d3ktpumdo7sly4.cloudfront.net
```

To change the API server:
1. On the login screen, tap **"Server Settings"** at the bottom
2. Enter the base URL of your deployment:
   - **AWS**: `https://d3ktpumdo7sly4.cloudfront.net`
   - **Azure**: (your Azure Container Apps URL)
   - **GCP**: (your Cloud Run URL)
   - **Local**: `http://localhost:8000`

### Authentication

The app uses the same JWT authentication as the web frontend. Log in with your existing dachjob.ai account credentials.

## Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Overview with stats (jobs, applications, LLM runs) |
| **Jobs** | Browse, filter (apply/maybe/skip), and view job details |
| **Import Jobs** | Paste job URLs to import (LinkedIn, Indeed, StepStone, etc.) |
| **Match Reports** | View AI match scores and recommendations per job |
| **LLM Runs** | Monitor AI processing history and status |
| **Profile** | View your candidate profile and skills |

## Architecture

```
DachJobApp.swift          → App entry point, auth routing
├── Services/
│   ├── APIClient.swift   → HTTP client (GET/POST, auth headers, error handling)
│   ├── AuthService.swift → Login/register/logout state management
│   └── KeychainHelper.swift → Secure token storage
├── Models/
│   └── Models.swift      → Codable data models matching the API schema
└── Views/
    ├── LoginView.swift   → Auth screens (login + register)
    ├── MainTabView.swift → Tab bar navigation
    ├── DashboardView.swift → Stats overview
    ├── JobsListView.swift  → Paginated job list with filters
    ├── JobDetailView.swift → Job details + match report
    ├── ImportJobView.swift → URL-based job import
    ├── LLMRunsView.swift   → LLM observability
    └── ProfileView.swift   → Candidate profile
```

## Notes

- **Smoke test jobs** are automatically filtered out (case-insensitive regex on job title)
- **Pull-to-refresh** is supported on all list views
- **Keychain** is used for secure token storage (not UserDefaults)
- Requires network access to the API — no offline mode
- The app targets iPhone (portrait + landscape); iPad is not explicitly supported
