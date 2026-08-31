// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "LiNativePOC",
    platforms: [.iOS(.v16)],
    products: [.library(name: "LiNativePOC", targets: ["LiNativePOC"])],
    targets: [
        .target(name: "LiNativePOC"),
        .testTarget(name: "LiNativePOCTests", dependencies: ["LiNativePOC"]),
    ]
)
