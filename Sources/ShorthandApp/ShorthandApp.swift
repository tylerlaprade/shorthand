import AppKit
import Security
import SwiftUI

@main
struct ShorthandApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 980, minHeight: 680)
        }
        Settings {
            SettingsView()
                .frame(width: 420)
        }
    }
}

struct ContentView: View {
    @AppStorage("anthropicModel") private var model = "claude-sonnet-4-6"
    @State private var request = "Ask me for a note, then copy it to the clipboard"
    @State private var recipeText = sampleRecipe
    @State private var status = "Ready"
    @State private var signedShortcutURL: URL?
    @State private var isWorking = false

    private var preview: RecipePreview? {
        try? JSONDecoder().decode(RecipePreview.self, from: Data(recipeText.utf8))
    }

    var body: some View {
        VStack(spacing: 0) {
            toolbar
            Divider()
            HSplitView {
                requestPane
                    .frame(minWidth: 280)
                recipePane
                    .frame(minWidth: 360)
                previewPane
                    .frame(minWidth: 260)
            }
            Divider()
            statusBar
        }
    }

    private var toolbar: some View {
        HStack(spacing: 8) {
            Button("Generate") {
                generateRecipe()
            }
            .disabled(isWorking)
            .keyboardShortcut("g", modifiers: [.command])

            Button("Validate") {
                validateResponse()
            }
            .disabled(isWorking)
            .keyboardShortcut("r", modifiers: [.command])

            Button("Compile") {
                compileShortcut()
            }
            .disabled(isWorking)
            .keyboardShortcut("b", modifiers: [.command])

            Button("Install") {
                installShortcut()
            }
            .disabled(signedShortcutURL == nil || isWorking)

            Spacer()

            Button("Sample") {
                recipeText = Self.sampleRecipe
                status = "Loaded sample recipe"
            }
        }
        .padding(12)
    }

    private var requestPane: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Request")
                .font(.headline)
            TextEditor(text: $request)
                .font(.system(.body, design: .rounded))
                .scrollContentBackground(.hidden)
                .padding(8)
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .padding(12)
    }

    private var recipePane: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Recipe JSON")
                .font(.headline)
            TextEditor(text: $recipeText)
                .font(.system(.body, design: .monospaced))
                .scrollContentBackground(.hidden)
                .padding(8)
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .padding(12)
    }

    private var previewPane: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Preview")
                .font(.headline)

            if let preview {
                VStack(alignment: .leading, spacing: 6) {
                    Text(preview.name)
                        .font(.title3)
                    if preview.unsupported == true {
                        Text(preview.reason ?? "Unsupported")
                            .foregroundStyle(.red)
                    }
                }

                List(preview.actions) { action in
                    VStack(alignment: .leading, spacing: 3) {
                        Text(action.kind)
                            .font(.system(.body, design: .monospaced))
                        if let detail = action.detail {
                            Text(detail)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 2)
                }
            } else {
                Text("Invalid JSON")
                    .foregroundStyle(.red)
                Spacer()
            }
        }
        .padding(12)
    }

    private var statusBar: some View {
        HStack {
            Text(status)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            if let signedShortcutURL {
                Text(signedShortcutURL.path)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
        .font(.caption)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    private func generateRecipe() {
        isWorking = true
        status = "Generating"

        Task {
            do {
                let prompt = try buildPrompt()
                let apiKey = KeychainStore.readAPIKey()

                guard !apiKey.isEmpty else {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(prompt, forType: .string)
                    status = "Prompt copied; add an API key in Settings to call Claude"
                    isWorking = false
                    return
                }

                let client = AnthropicClient(apiKey: apiKey, model: model)
                let generatedRecipe = try await client.createRecipe(prompt: prompt)
                let responseURL = try writeModelResponse(generatedRecipe)
                let output = try runShortcutgen(["validate-response", responseURL.path])
                recipeText = generatedRecipe
                status = output.trimmingCharacters(in: .whitespacesAndNewlines)
            } catch {
                status = error.localizedDescription
            }

            isWorking = false
        }
    }

    private func validateResponse() {
        do {
            let responseURL = try writeModelResponse()
            let output = try runShortcutgen(["validate-response", responseURL.path])
            status = output.trimmingCharacters(in: .whitespacesAndNewlines)
        } catch {
            status = error.localizedDescription
        }
    }

    private func compileShortcut() {
        do {
            let buildURL = try buildDirectory()
            let responseURL = try writeModelResponse()
            let outputURL = buildURL.appendingPathComponent("generated.shortcut")
            let output = try runShortcutgen(
                [
                    "compile-response",
                    responseURL.path,
                    "--output",
                    outputURL.path,
                    "--sign",
                ]
            )
            let signedURL = buildURL.appendingPathComponent("generated.signed.shortcut")
            signedShortcutURL = signedURL
            status = output.trimmingCharacters(in: .whitespacesAndNewlines)
        } catch {
            status = error.localizedDescription
        }
    }

    private func installShortcut() {
        guard let signedShortcutURL else {
            status = "No signed shortcut"
            return
        }
        NSWorkspace.shared.open(signedShortcutURL)
        status = "Opened \(signedShortcutURL.lastPathComponent)"
    }

    private func writeModelResponse(_ text: String? = nil) throws -> URL {
        let responseURL = try buildDirectory().appendingPathComponent("model_response.json")
        try (text ?? recipeText).write(to: responseURL, atomically: true, encoding: .utf8)
        return responseURL
    }

    private func buildPrompt() throws -> String {
        let outputURL = try buildDirectory().appendingPathComponent("prompt.txt")
        _ = try runShortcutgen(
            [
                "prompt",
                request,
                "--example",
                "recipes/show_text.json",
                "--example",
                "recipes/ask_and_notify.json",
                "--output",
                outputURL.path,
            ]
        )
        return try String(contentsOf: outputURL, encoding: .utf8)
    }

    private func buildDirectory() throws -> URL {
        let url = try AppPaths.applicationSupportDirectory()
            .appendingPathComponent("build")
            .appendingPathComponent("app")
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }

    private func runShortcutgen(_ arguments: [String]) throws -> String {
        let compilerRoot = try CompilerLocator.find()
        let process = Process()
        process.currentDirectoryURL = compilerRoot
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = ["-m", "shortcutgen"] + arguments

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        try process.run()
        process.waitUntilExit()

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""

        guard process.terminationStatus == 0 else {
            throw AppCommandError(output.trimmingCharacters(in: .whitespacesAndNewlines))
        }

        return output
    }

    private static let sampleRecipe = """
    {
      "name": "Copy Note",
      "actions": [
        {
          "id": "note",
          "kind": "ask_for_input",
          "prompt": "What should I copy?"
        },
        {
          "kind": "set_clipboard",
          "input": {
            "ref": "note"
          }
        }
      ]
    }
    """
}

struct SettingsView: View {
    @AppStorage("anthropicModel") private var model = "claude-sonnet-4-6"
    @State private var apiKey = ""
    @State private var status = ""

    var body: some View {
        Form {
            SecureField("Anthropic API Key", text: $apiKey)
            TextField("Model", text: $model)

            HStack {
                Button("Save") {
                    save()
                }
                Spacer()
                Text(status)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(20)
        .onAppear {
            apiKey = KeychainStore.readAPIKey()
        }
    }

    private func save() {
        do {
            try KeychainStore.saveAPIKey(apiKey)
            status = "Saved"
        } catch {
            status = error.localizedDescription
        }
    }
}

struct RecipePreview: Decodable {
    let name: String
    let unsupported: Bool?
    let reason: String?
    let actions: [RecipeAction]
}

struct RecipeAction: Decodable, Identifiable {
    private let uuid = UUID()
    let recipeID: String?
    let kind: String
    let title: String?
    let text: String?
    let prompt: String?
    let url: String?
    let key: String?

    var id: UUID {
        uuid
    }

    var detail: String? {
        title ?? prompt ?? text ?? url ?? key ?? recipeID
    }

    enum CodingKeys: String, CodingKey {
        case recipeID = "id"
        case kind
        case title
        case text
        case prompt
        case url
        case key
    }
}

enum AppCommandError: LocalizedError {
    case commandFailed(String)

    init(_ message: String) {
        self = .commandFailed(message.isEmpty ? "Command failed" : message)
    }

    var errorDescription: String? {
        switch self {
        case .commandFailed(let message):
            message
        }
    }
}

struct AnthropicClient {
    let apiKey: String
    let model: String

    func createRecipe(prompt: String) async throws -> String {
        var request = URLRequest(url: URL(string: "https://api.anthropic.com/v1/messages")!)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.setValue("application/json", forHTTPHeaderField: "content-type")
        request.httpBody = try JSONEncoder().encode(
            AnthropicRequest(
                model: model,
                maxTokens: 4096,
                messages: [
                    AnthropicMessage(role: "user", content: prompt)
                ]
            )
        )

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AnthropicError.requestFailed("No HTTP response")
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw AnthropicError.requestFailed("HTTP \(httpResponse.statusCode): \(body)")
        }

        let decoded = try JSONDecoder().decode(AnthropicResponse.self, from: data)
        let text = decoded.content
            .filter { $0.type == "text" }
            .compactMap(\.text)
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard !text.isEmpty else {
            throw AnthropicError.requestFailed("Claude response did not include text")
        }

        return text
    }
}

struct AnthropicRequest: Encodable {
    let model: String
    let maxTokens: Int
    let messages: [AnthropicMessage]

    enum CodingKeys: String, CodingKey {
        case model
        case maxTokens = "max_tokens"
        case messages
    }
}

struct AnthropicMessage: Encodable {
    let role: String
    let content: String
}

struct AnthropicResponse: Decodable {
    let content: [AnthropicContent]
}

struct AnthropicContent: Decodable {
    let type: String
    let text: String?
}

enum AnthropicError: LocalizedError {
    case requestFailed(String)

    var errorDescription: String? {
        switch self {
        case .requestFailed(let message):
            message
        }
    }
}

enum KeychainStore {
    private static let service = "com.tylerlaprade.shorthand"
    private static let account = "anthropic-api-key"

    static func readAPIKey() -> String {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]

        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        guard status == errSecSuccess, let data = item as? Data else {
            return ""
        }

        return String(data: data, encoding: .utf8) ?? ""
    }

    static func saveAPIKey(_ apiKey: String) throws {
        let trimmed = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]

        SecItemDelete(query as CFDictionary)
        guard !trimmed.isEmpty else {
            return
        }

        let attributes: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: Data(trimmed.utf8),
        ]
        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw KeychainError.saveFailed(status)
        }
    }
}

enum KeychainError: LocalizedError {
    case saveFailed(OSStatus)

    var errorDescription: String? {
        switch self {
        case .saveFailed(let status):
            "Keychain save failed: \(status)"
        }
    }
}

enum AppPaths {
    static func applicationSupportDirectory() throws -> URL {
        let fileManager = FileManager.default
        let baseURL = try fileManager.url(
            for: .applicationSupportDirectory,
            in: .userDomainMask,
            appropriateFor: nil,
            create: true
        )
        let url = baseURL.appendingPathComponent("Shorthand")
        try fileManager.createDirectory(at: url, withIntermediateDirectories: true)
        return url
    }
}

enum CompilerLocator {
    static func find() throws -> URL {
        let fileManager = FileManager.default
        let environment = ProcessInfo.processInfo.environment

        if let configuredRoot = environment["SHORTHAND_REPO_ROOT"], !configuredRoot.isEmpty {
            let url = URL(fileURLWithPath: configuredRoot)
            if isCompilerRoot(url, fileManager: fileManager) {
                return url
            }
        }

        let currentDirectory = URL(fileURLWithPath: fileManager.currentDirectoryPath)
        let resourceDirectory = Bundle.main.resourceURL
        let homeFallback = fileManager.homeDirectoryForCurrentUser
            .appendingPathComponent("Code")
            .appendingPathComponent("shorthand")
        let candidates = [
            currentDirectory,
            resourceDirectory,
            Bundle.main.bundleURL,
            Bundle.main.bundleURL.deletingLastPathComponent(),
            homeFallback,
        ].compactMap { $0 }

        for candidate in candidates {
            if let root = walkUp(from: candidate, fileManager: fileManager) {
                return root
            }
        }

        throw AppCommandError("Could not locate repository; set SHORTHAND_REPO_ROOT")
    }

    private static func walkUp(from startURL: URL, fileManager: FileManager) -> URL? {
        var url = startURL.standardizedFileURL
        var isDirectory: ObjCBool = false
        if fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory), !isDirectory.boolValue {
            url.deleteLastPathComponent()
        }

        while true {
            if isCompilerRoot(url, fileManager: fileManager) {
                return url
            }

            let parent = url.deletingLastPathComponent()
            if parent.path == url.path {
                return nil
            }
            url = parent
        }
    }

    private static func isCompilerRoot(_ url: URL, fileManager: FileManager) -> Bool {
        fileManager.fileExists(
            atPath: url
                .appendingPathComponent("shortcutgen")
                .appendingPathComponent("__main__.py")
                .path
        )
    }
}
