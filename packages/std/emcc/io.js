// EzLang std/io Emscripten JS 封装层
// Node 风格运行时读取 fd 0；启用 Asyncify 时异步读取并恢复，浏览器/Worker 缺少 stdin 时返回空可选值。
(function () {
  var stdinLines = null;
  var stdinIndex = 0;
  var stdoutPending = '';

  function hasAsyncify() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleSleep === 'function';
  }

  function writeOptStr(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    setValue(ret + 8, ok ? stringToNewUTF8(value || '') : 0, '*');
  }

  function splitStdin(input) {
    var lines = [];
    if (!input) return lines;
    lines = String(input).split('\n');
    if (lines.length && lines[lines.length - 1] === '') lines.pop();
    for (var i = 0; i < lines.length; ++i) {
      if (lines[i].endsWith('\r')) lines[i] = lines[i].slice(0, -1);
    }
    return lines;
  }

  function loadStdinLinesSync() {
    if (stdinLines !== null) return stdinLines;
    stdinLines = [];
    if (typeof require !== 'function') return stdinLines;
    try {
      var fs = require('fs');
      var input = fs.readFileSync(0, 'utf8');
      stdinLines = splitStdin(input);
    } catch (e) {
      stdinLines = [];
    }
    return stdinLines;
  }

  function loadStdinLines() {
    if (stdinLines !== null) return stdinLines;
    if (!hasAsyncify() || typeof require !== 'function') return loadStdinLinesSync();
    try {
      var fs = require('fs');
      if (typeof fs.readFile !== 'function') return loadStdinLinesSync();
      return Asyncify.handleSleep(function (wakeUp) {
        fs.readFile(0, 'utf8', function (err, input) {
          stdinLines = err ? [] : splitStdin(input);
          wakeUp(stdinLines);
        });
      });
    } catch (e) {
      stdinLines = [];
      return stdinLines;
    }
  }

  function writeStdout(value, newline) {
    if (typeof process !== 'undefined' && process.stdout && typeof process.stdout.write === 'function') {
      process.stdout.write(value + (newline ? '\n' : ''));
      return;
    }
    if (!newline) {
      stdoutPending += value;
      return;
    }
    var line = stdoutPending + value;
    stdoutPending = '';
    if (typeof out === 'function') {
      out(line);
      return;
    }
    if (typeof Module !== 'undefined' && typeof Module.print === 'function') {
      Module.print(line);
      return;
    }
    if (typeof console !== 'undefined' && console.log) console.log(line);
  }

  mergeInto(LibraryManager.library, {
    print: function (msg) {
      writeStdout(UTF8ToString(msg), false);
    },
    println: function (msg) {
      writeStdout(UTF8ToString(msg), true);
    },
    error: function (msg) {
      console.error(UTF8ToString(msg));
    },
    readLine__async: 'auto',
    readLine: function (ret) {
      var lines = loadStdinLines();
      if (stdinIndex >= lines.length) {
        writeOptStr(ret, false, '');
        return;
      }
      writeOptStr(ret, true, lines[stdinIndex++]);
    },
  });
})();
