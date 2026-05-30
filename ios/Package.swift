// swift-tools-version:6.2
import PackageDescription

let package = Package(
    name: "DachJob",
    platforms: [.iOS(.v26)],
    products: [
        .library(name: "DachJob", targets: ["DachJob"]),
    ],
    targets: [
        .target(
            name: "DachJob",
            path: "DachJob"
        ),
    ]
)
