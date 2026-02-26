import http.server
import socketserver
import urllib.parse

PORT = 9999 # Using a high port to avoid conflicts

class MyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        if 'code' in params:
            print(f"\n🚀 FOUND CODE: {params['code'][0]}\n")
            self.wfile.write(b"<h1>Success!</h1><p>Return to your terminal.</p>")
        else:
            self.wfile.write(b"No code found in URL.")

print(f"📡 Background Proxy listening on port {PORT}...")
socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("", PORT), MyHandler) as httpd:
    httpd.handle_request()
