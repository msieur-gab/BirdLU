"""Serve the repo over HTTPS on the local network, so a phone can open the Listen page (browsers allow the
microphone only on HTTPS or localhost).

A self-signed certificate is made once into lab/out/https/ (not in git); the phone will warn about it once:
accept it ("Advanced" → proceed). Then open  https://<laptop IP>:8443/listen-bird.html?voice=<name>.
Run:  python3 lab/serve_https.py      (Ctrl+C to stop)
"""
import http.server, os, socket, ssl, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CERT = os.path.join(ROOT, "lab", "out", "https")
PORT = 8443


def main():
    os.makedirs(CERT, exist_ok=True)
    crt, key = os.path.join(CERT, "cert.pem"), os.path.join(CERT, "key.pem")
    if not os.path.exists(crt):
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365", "-subj", "/CN=birdlu-local",
                        "-keyout", key, "-out", crt], check=True, capture_output=True)
    os.chdir(ROOT)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), http.server.SimpleHTTPRequestHandler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9)); ip = s.getsockname()[0]   # no packet is sent: finds the LAN address
    except OSError:
        ip = "<laptop IP>"
    print(f"https://{ip}:{PORT}/listen-bird.html", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
