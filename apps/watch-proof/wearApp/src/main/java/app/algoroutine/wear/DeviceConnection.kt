package app.algoroutine.wear

import android.util.Base64
import java.io.ByteArrayInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyStore
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.TrustManagerFactory

/** Debug-only local device bridge. Default hostname verification stays enabled. */
internal object DeviceConnection {
    var localPort: Int = 8791
        private set
    fun configureVerification(port:Int){localPort=if(BuildConfig.DEBUG&&port==8793)8793 else 8791}
    val pendingStore: String get()=if(localPort==8793)"remote-execution-verification-8793" else "remote-execution"

    val enabled: Boolean get() = localPort != 8793 && BuildConfig.DEBUG && BuildConfig.DEVICE_HOST.isNotEmpty()
    private val certificate by lazy {
        val bytes = Base64.decode(BuildConfig.DEVICE_CERTIFICATE, Base64.DEFAULT)
        CertificateFactory.getInstance("X.509").generateCertificate(ByteArrayInputStream(bytes)) as X509Certificate
    }
    private val socketFactory by lazy {
        val cert = certificate
        val anchors = KeyStore.getInstance(KeyStore.getDefaultType()).apply { load(null); setCertificateEntry("device", cert) }
        val managers = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()).apply { init(anchors) }
        SSLContext.getInstance("TLS").apply { init(null, managers.trustManagers, null) }.socketFactory
    }
    fun open(path: String): HttpURLConnection {
        require(path in setOf("context", "command", "search"))
        if (!enabled) return URL("http://10.0.2.2:$localPort/$path").openConnection() as HttpURLConnection
        require(BuildConfig.DEVICE_TOKEN.isNotEmpty())
        certificate.checkValidity()
        return (URL("https://${BuildConfig.DEVICE_HOST}:${BuildConfig.DEVICE_PORT}/$path").openConnection() as HttpsURLConnection).apply {
            sslSocketFactory = socketFactory
            instanceFollowRedirects = false
            setRequestProperty("Authorization", "Bearer ${BuildConfig.DEVICE_TOKEN}")
        }
    }
}
