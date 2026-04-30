// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "Shorthand",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "ShorthandApp", targets: ["ShorthandApp"])
    ],
    targets: [
        .executableTarget(name: "ShorthandApp")
    ]
)
