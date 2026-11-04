import Foundation
import Security

/// Development profile only. Release builds cannot use embedded device credentials.
enum DeviceConnection {
    private static func value(_ key: String) -> String {
        #if DEBUG
        let result = Bundle.main.object(forInfoDictionaryKey: "RoutineServer" + key) as? String ?? ""
        return result.hasPrefix("$(") ? "" : result
        #else
        return ""
        #endif
    }
    static var localPort: Int {
        #if DEBUG && targetEnvironment(simulator)
        let args=ProcessInfo.processInfo.arguments
        if let i=args.firstIndex(of:"-verification-port"),args.indices.contains(i+1),args[i+1]=="8793" { return 8793 }
        #endif
        return 8791
    }
    static var pendingFile: String { localPort==8793 ? "remote-pending-verification-8793.json":"remote-pending.json" }
    static var enabled: Bool { localPort != 8793 && !value("Host").isEmpty }
    private static let trust = DeviceTrust(host: value("Host"), certificate: Data(base64Encoded: value("Certificate")))
    static let session = URLSession(configuration: .ephemeral, delegate: trust, delegateQueue: nil)
    static func request(_ path: String) throws -> URLRequest {
        guard ["context", "command", "search"].contains(path) else { throw URLError(.badURL) }
        if !enabled { return URLRequest(url: URL(string: "http://127.0.0.1:\(localPort)/" + path)!) }
        guard !value("Token").isEmpty, Data(base64Encoded: value("Certificate")) != nil,
              let port = Int(value("Port")), (1...65535).contains(port) else { throw URLError(.badURL) }
        var parts = URLComponents(); parts.scheme = "https"; parts.host = value("Host"); parts.port = port; parts.path = "/" + path
        guard let url = parts.url else { throw URLError(.badURL) }
        var request = URLRequest(url: url)
        request.setValue("Bearer " + value("Token"), forHTTPHeaderField: "Authorization")
        return request
    }
}
private final class DeviceTrust: NSObject, URLSessionDelegate, URLSessionTaskDelegate {
    let host: String
    let certificate: Data?
    init(host: String, certificate: Data?) { self.host = host; self.certificate = certificate }
    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              challenge.protectionSpace.host == host, let trust = challenge.protectionSpace.serverTrust,
              let data = certificate, let anchor = SecCertificateCreateWithData(nil, data as CFData),
              let chain = SecTrustCopyCertificateChain(trust) as? [SecCertificate], let leaf = chain.first,
              (SecCertificateCopyData(leaf) as Data) == data else {
            completionHandler(.cancelAuthenticationChallenge, nil); return
        }
        SecTrustSetPolicies(trust, SecPolicyCreateSSL(true, host as CFString))
        SecTrustSetAnchorCertificates(trust, [anchor] as CFArray)
        SecTrustSetAnchorCertificatesOnly(trust, true)
        guard SecTrustEvaluateWithError(trust, nil) else { completionHandler(.cancelAuthenticationChallenge, nil); return }
        completionHandler(.useCredential, URLCredential(trust: trust))
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) { completionHandler(nil) }
}
