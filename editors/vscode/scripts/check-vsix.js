const cp = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const extensionRoot = path.resolve(__dirname, '..');
const manifest = require(path.join(extensionRoot, 'package.json'));
const vsixPath = path.join(extensionRoot, `${manifest.name}-${manifest.version}.vsix`);

if (!fs.existsSync(vsixPath)) {
  throw new Error(`找不到 VSIX: ${vsixPath}`);
}

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'ezlang-vsix-'));

try {
  cp.execFileSync('unzip', ['-q', vsixPath, '-d', tempRoot]);
  assertExists('extension/node_modules/vscode-languageclient/package.json');
  assertExists('extension/server/antlr4/__init__.py');
  assertExists('extension/server/lsp/server.py');
  assertExists('extension/server/parser/EzLangParser.py');
  assertExists('extension/server/semantic/analyzer.py');
  assertExists('extension/server/packages/std/io.ez');
  runLspSmokeTest(path.join(tempRoot, 'extension', 'server'));
  console.log('VSIX 发布前验证通过：依赖、内置 LSP、capabilities 和诊断均正常');
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true });
}

function assertExists(relativePath) {
  const fullPath = path.join(tempRoot, relativePath);
  if (!fs.existsSync(fullPath)) {
    throw new Error(`VSIX 缺少文件: ${relativePath}`);
  }
}

function runLspSmokeTest(serverRoot) {
  const script = String.raw`
import json
import subprocess
import sys
from pathlib import Path

server_root = Path(sys.argv[1])

def write_message(proc, message):
    payload = json.dumps(message, ensure_ascii=False).encode('utf-8')
    proc.stdin.write(b'Content-Length: ' + str(len(payload)).encode('ascii') + b'\r\n\r\n' + payload)
    proc.stdin.flush()

def read_message(proc):
    headers = {}
    while True:
        line = proc.stdout.readline()
        if not line:
            stderr = proc.stderr.read().decode('utf-8', errors='replace')
            raise RuntimeError('LSP 没有返回消息' + (': ' + stderr if stderr else ''))
        if line in (b'\r\n', b'\n'):
            break
        key, value = line.decode('ascii').split(':', 1)
        headers[key.lower()] = value.strip()
    body = proc.stdout.read(int(headers['content-length']))
    return json.loads(body.decode('utf-8'))

proc = subprocess.Popen(
    [sys.executable, '-S', '-m', 'lsp'],
    cwd=server_root,
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
try:
    write_message(proc, {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {'rootUri': server_root.as_uri()},
    })
    initialized = read_message(proc)
    capabilities = initialized['result']['capabilities']
    required = [
        'completionProvider',
        'hoverProvider',
        'definitionProvider',
        'documentSymbolProvider',
        'documentFormattingProvider',
        'inlayHintProvider',
        'semanticTokensProvider',
    ]
    missing = [capability for capability in required if not capabilities.get(capability)]
    if missing:
        raise RuntimeError(f'缺少 LSP capabilities: {missing}')
    write_message(proc, {'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
    write_message(proc, {
        'jsonrpc': '2.0',
        'method': 'textDocument/didOpen',
        'params': {
            'textDocument': {
                'uri': (server_root / 'market-check.ez').as_uri(),
                'languageId': 'ezlang',
                'version': 1,
                'text': 'let value: I32 = ;\n',
            }
        },
    })
    diagnostics = read_message(proc)
    items = diagnostics.get('params', {}).get('diagnostics', [])
    if diagnostics.get('method') != 'textDocument/publishDiagnostics' or not items or '语法错误' not in items[0].get('message', ''):
        raise RuntimeError(f'诊断不符合预期: {diagnostics}')
    write_message(proc, {'jsonrpc': '2.0', 'id': 2, 'method': 'shutdown', 'params': None})
    read_message(proc)
    write_message(proc, {'jsonrpc': '2.0', 'method': 'exit', 'params': None})
finally:
    proc.kill()
`;
  cp.execFileSync(pythonCommand(), ['-c', script, serverRoot], { stdio: 'inherit' });
}

function pythonCommand() {
  return process.platform === 'win32' ? 'python' : 'python3';
}
