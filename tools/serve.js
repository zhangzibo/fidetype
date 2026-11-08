// Local static server for the wiki. Usage: node tools/serve.js  (PORT env var optional)
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const ROOT = path.resolve(__dirname, '..');
const PORT = parseInt(process.env.PORT, 10) || 8000;
const HOST = '127.0.0.1';

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.htm': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.ico': 'image/x-icon',
  '.md': 'text/plain; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
  '.drawio': 'application/xml',
  '.xml': 'application/xml',
};

function send(res, code, msg) {
  res.writeHead(code, { 'Content-Type': 'text/plain; charset=utf-8' });
  res.end(msg);
}

function serveFile(res, file) {
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) return send(res, 404, 'Not found');
    const type = TYPES[path.extname(file).toLowerCase()] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size });
    fs.createReadStream(file).pipe(res);
  });
}

const server = http.createServer((req, res) => {
  let pathname;
  try {
    pathname = decodeURIComponent(url.parse(req.url).pathname || '/');
  } catch (e) {
    return send(res, 400, 'Bad request');
  }
  if (pathname.includes('\0')) return send(res, 400, 'Bad request');

  const target = path.resolve(ROOT, '.' + path.sep + pathname);
  if (target !== ROOT && !target.startsWith(ROOT + path.sep)) {
    return send(res, 403, 'Forbidden');
  }

  fs.stat(target, (err, st) => {
    if (err) return send(res, 404, 'Not found');
    if (st.isDirectory()) return serveFile(res, path.join(target, 'index.html'));
    serveFile(res, target);
  });
});

server.listen(PORT, HOST, () => {
  console.log(`Serving ${ROOT} at http://localhost:${PORT}/`);
});
