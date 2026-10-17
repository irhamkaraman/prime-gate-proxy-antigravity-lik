import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import net from "node:net";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.join(__dirname, "public");

// Parse command line arguments
const args = process.argv.slice(2);
function getArg(name, defVal) {
  const idx = args.indexOf(name);
  return idx !== -1 && args[idx + 1] ? args[idx + 1] : defVal;
}

const UI_PORT = parseInt(getArg("--port", "52110"), 10);
const API_PORT = parseInt(getArg("--api-port", "52111"), 10);
const HOST = "127.0.0.1";

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon"
};

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);

  // Proxy API and V1 calls directly to Python Core Server
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/v1/") || url.pathname === "/health") {
    const proxyReq = http.request(
      {
        host: "127.0.0.1",
        port: API_PORT,
        path: url.pathname + url.search,
        method: req.method,
        headers: {
          ...req.headers,
          host: `127.0.0.1:${API_PORT}`
        }
      },
      proxyRes => {
        res.writeHead(proxyRes.statusCode, proxyRes.headers);
        proxyRes.pipe(res);
      }
    );

    proxyReq.on("error", err => {
      res.writeHead(502, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        error: {
          message: `Python Core API (port ${API_PORT}) is unreachable. Please ensure 'prime-gate start' or daemon is active.`,
          detail: err.message
        }
      }));
    });

    req.pipe(proxyReq);
    return;
  }

  // Serve static files from public/
  let filePath = path.join(PUBLIC_DIR, url.pathname === "/" ? "index.html" : url.pathname);
  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(PUBLIC_DIR, "index.html");
  }

  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME_TYPES[ext] || "application/octet-stream";

  fs.readFile(filePath, (err, content) => {
    if (err) {
      res.writeHead(404, { "Content-Type": "text/plain" });
      res.end("404 Not Found");
      return;
    }
    res.writeHead(200, { "Content-Type": contentType });
    res.end(content);
  });
});

// Forward WebSocket upgrade requests to the Python core server
server.on("upgrade", (req, socket, head) => {
  const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
  if (url.pathname.startsWith("/ws/")) {
    const proxySocket = net.connect(API_PORT, "127.0.0.1", () => {
      proxySocket.write(
        `${req.method} ${req.url} HTTP/${req.httpVersion}\r\n` +
        Object.entries(req.headers)
          .map(([k, v]) => `${k}: ${v}`)
          .join("\r\n") +
        "\r\n\r\n"
      );
      if (head && head.length) proxySocket.write(head);
      proxySocket.pipe(socket);
      socket.pipe(proxySocket);
    });

    proxySocket.on("error", () => socket.destroy());
    socket.on("error", () => proxySocket.destroy());
  } else {
    socket.destroy();
  }
});

server.listen(UI_PORT, HOST, () => {
  console.log(`\n======================================================`);
  console.log(`  PRIME GATE DASHBOARD (Web UI)`);
  console.log(`  URL: http://${HOST}:${UI_PORT}`);
  console.log(`  Connected to API at: http://${HOST}:${API_PORT}`);
  console.log(`======================================================\n`);
});
