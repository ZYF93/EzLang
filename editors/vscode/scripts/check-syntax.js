const fs = require('fs');
const path = require('path');
const vscodeTextmate = require('vscode-textmate');
const vscodeOniguruma = require('vscode-oniguruma');

const extensionRoot = path.resolve(__dirname, '..');
const grammarPath = path.join(extensionRoot, 'syntaxes', 'ezlang.tmLanguage.json');
const wasmPath = require.resolve('vscode-oniguruma/release/onig.wasm');

async function main() {
  const wasm = fs.readFileSync(wasmPath).buffer;
  await vscodeOniguruma.loadWASM(wasm);
  const registry = new vscodeTextmate.Registry({
    onigLib: Promise.resolve({
      createOnigScanner: (sources) => new vscodeOniguruma.OnigScanner(sources),
      createOnigString: (source) => new vscodeOniguruma.OnigString(source),
    }),
    loadGrammar: async (scopeName) => {
      if (scopeName !== 'source.ezlang') {
        return null;
      }
      return vscodeTextmate.parseRawGrammar(fs.readFileSync(grammarPath, 'utf8'), grammarPath);
    },
  });

  const grammar = await registry.loadGrammar('source.ezlang');
  if (!grammar) {
    throw new Error('无法加载 EzLang TextMate grammar');
  }

  assertArrowToken(grammar, 'const create = (seed: I32): Data => {');
  assertArrowToken(grammar, 'const main = (): I32 => {');
  assertThinArrowToken(grammar, 'value -> map(item = value);');
  assertRelationalToken(grammar, '(total > 8) ? break;');
  assertRelationalToken(grammar, 'return (n <= 1) ? n : fib(n = n - 1);');
  assertAngleBracketsAreNotLanguageBrackets();
  console.log('语法高亮验证通过：=>、-> 和关系运算符 scope 均符合预期');
}

function assertArrowToken(grammar, line) {
  const result = grammar.tokenizeLine(line);
  const arrow = result.tokens.find((token) => line.slice(token.startIndex, token.endIndex) === '=>');
  if (!arrow) {
    throw new Error(`=> 没有被整体 token 化: ${JSON.stringify(describeTokens(line, result.tokens), null, 2)}`);
  }
  if (!arrow.scopes.includes('keyword.operator.arrow.fat.ezlang')) {
    throw new Error(`=> scope 不正确: ${JSON.stringify(describeTokens(line, result.tokens), null, 2)}`);
  }
}

function tokenAt(line, tokens, index) {
  return tokens.find((token) => token.startIndex <= index && token.endIndex > index);
}

function assertThinArrowToken(grammar, line) {
  const result = grammar.tokenizeLine(line);
  const arrow = result.tokens.find((token) => line.slice(token.startIndex, token.endIndex) === '->');
  if (!arrow) {
    throw new Error(`-> 没有被整体 token 化: ${JSON.stringify(describeTokens(line, result.tokens), null, 2)}`);
  }
  if (!arrow.scopes.includes('keyword.operator.arrow.thin.ezlang')) {
    throw new Error(`-> scope 不正确: ${JSON.stringify(describeTokens(line, result.tokens), null, 2)}`);
  }
}

function assertRelationalToken(grammar, line) {
  const result = grammar.tokenizeLine(line);
  const gt = line.indexOf('>');
  const index = gt >= 0 ? gt : line.indexOf('<');
  for (const offset of [0, 1]) {
    const token = tokenAt(line, result.tokens, index + offset);
    if (!token) {
      continue;
    }
    if (token.scopes.some((scope) => scope.startsWith('keyword.operator') || scope === 'punctuation.separator.relational.ezlang')) {
      throw new Error(`关系运算符不应再使用运算符高亮 scope: ${JSON.stringify(describeTokens(line, result.tokens), null, 2)}`);
    }
  }
}

function describeTokens(line, tokens) {
  return tokens.map((token) => ({
    text: line.slice(token.startIndex, token.endIndex),
    scopes: token.scopes,
  }));
}

function assertAngleBracketsAreNotLanguageBrackets() {
  const configPath = path.join(extensionRoot, 'language-configuration.json');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const brackets = config.brackets || [];
  if (brackets.some((pair) => pair[0] === '<' && pair[1] === '>')) {
    throw new Error('language-configuration.json 不应把 < > 注册为 brackets，否则比较运算符和箭头右侧会被括号配色覆盖');
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
