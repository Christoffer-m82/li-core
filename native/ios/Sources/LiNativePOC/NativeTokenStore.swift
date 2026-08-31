import Foundation
import Security

public protocol NativeTokenStoring: Sendable {
    func save(refreshToken: String) throws
    func loadRefreshToken() throws -> String?
    func clear() throws
}

public struct KeychainNativeTokenStore: NativeTokenStoring {
    private let service: String
    private let account: String

    public init(service: String, account: String = "native-refresh-token") {
        self.service = service
        self.account = account
    }

    public func save(refreshToken: String) throws {
        try clear()
        let status = SecItemAdd([
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecAttrAccessible: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
            kSecValueData: Data(refreshToken.utf8),
        ] as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainTokenError(status: status) }
    }

    public func loadRefreshToken() throws -> String? {
        var result: CFTypeRef?
        let status = SecItemCopyMatching([
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
            kSecReturnData: true,
            kSecMatchLimit: kSecMatchLimitOne,
        ] as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            throw KeychainTokenError(status: status)
        }
        return token
    }

    public func clear() throws {
        let status = SecItemDelete([
            kSecClass: kSecClassGenericPassword,
            kSecAttrService: service,
            kSecAttrAccount: account,
        ] as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainTokenError(status: status)
        }
    }
}

public struct KeychainTokenError: Error, Equatable {
    public let status: OSStatus
}
