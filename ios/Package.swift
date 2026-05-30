// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "DachJob",
    platforms: [.iOS(.v17)],
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
