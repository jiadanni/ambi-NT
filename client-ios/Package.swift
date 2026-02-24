// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AmbientClient",
    platforms: [
        .iOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "AmbientClient",
            targets: ["AmbientClient"]
        )
    ],
    dependencies: [
        // Sodium (libsodium) for NaCl encryption
        .package(url: "https://github.com/jedisct1/swift-sodium.git", from: "0.9.1")
    ],
    targets: [
        .target(
            name: "AmbientClient",
            dependencies: [
                .product(name: "Sodium", package: "swift-sodium")
            ]
        ),
        .testTarget(
            name: "AmbientClientTests",
            dependencies: ["AmbientClient"]
        )
    ]
)
