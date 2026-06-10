// EzLang std/io Emscripten JS 封装层
// Node 风格同步运行时读取 fd 0；浏览器/Worker 缺少同步 stdin 时返回空可选值。
(function () {
  var stdinLines = null;
  var stdinIndex = 0;
  var stdoutPending = '';

  function writeOptStr(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    setValue(ret + 8, ok ? stringToNewUTF8(value || '') : 0, '*');
  }

  function loadStdinLines() {
    if (stdinLines !== null) return stdinLines;
    stdinLines = [];
    if (typeof require !== 'function') return stdinLines;
    try {
      var fs = require('fs');
      var input = fs.readFileSync(0, 'utf8');
      if (!input) return stdinLines;
      stdinLines = input.split('\n');
      if (stdinLines.length && stdinLines[stdinLines.length - 1] === '') stdinLines.pop();
      for (var i = 0; i < stdinLines.length; ++i) {
        if (stdinLines[i].endsWith('\r')) stdinLines[i] = stdinLines[i].slice(0, -1);
      }
    } catch (e) {
      stdinLines = [];
    }
    return stdinLines;
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
