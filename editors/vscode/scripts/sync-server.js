const fs = require('fs');
const path = require('path');
const cp = require('child_process');

const extensionRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(extensionRoot, '..', '..');
const targetRoot = path.join(extensionRoot, 'server');

const copies = [
  ['lsp', 'lsp'],
  ['cli', 'cli'],
  ['compiler/src/codegen', 'codegen'],
  ['compiler/src/parser', 'parser'],
  ['compiler/src/runtime', 'runtime'],
  ['compiler/src/semantic', 'semantic'],
  ['packages/std', 'packages/std'],
];

fs.rmSync(targetRoot, { recursive: true, force: true });

for (const [from, to] of copies) {
  copyRecursive(path.join(repoRoot, from), path.join(targetRoot, to));
}

copyRecursive(resolvePythonPackage('antlr4'), path.join(targetRoot, 'antlr4'));

function copyRecursive(source, destination) {
  const stat = fs.statSync(source);
  if (stat.isDirectory()) {
    fs.mkdirSync(destination, { recursive: true });
    for (const entry of fs.readdirSync(source)) {
      if (entry === '__pycache__') {
        continue;
      }
      copyRecursive(path.join(source, entry), path.join(destination, entry));
    }
    return;
  }

  if (!shouldCopyFile(source)) {
    return;
  }
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.copyFileSync(source, destination);
}

function shouldCopyFile(file) {
  return ['.py', '.interp', '.tokens', '.ez', '.c', '.inc', '.js'].includes(path.extname(file));
}

function resolvePythonPackage(name) {
  const script = `import ${name}, pathlib; print(pathlib.Path(${name}.__file__).resolve().parent)`;
  for (const command of pythonCommands()) {
    const result = cp.spawnSync(command, ['-c', script], { encoding: 'utf8' });
    if (result.status === 0) {
      return result.stdout.trim();
    }
  }
  throw new Error(`找不到 Python 包 ${name}。请先安装打包依赖：python3 -m pip install antlr4-python3-runtime`);
}

function pythonCommands() {
  const configured = process.env.PYTHON ? [process.env.PYTHON] : [];
  return [...configured, 'python3', 'python'].filter((command, index, commands) => commands.indexOf(command) === index);
}
