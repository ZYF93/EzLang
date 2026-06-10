// EzLang std/os Emscripten JS 封装层
(function () {
  function writeStrList(ret, items) {
    var ptrSize = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
    var pageCount = items.length === 0 ? 0 : Math.ceil(items.length / 8);
    var pagesPtr = pageCount === 0 ? 0 : _malloc(pageCount * ptrSize);
    for (var page = 0; page < pageCount; page++) {
      var pagePtr = _malloc(8 * ptrSize);
      setValue(pagesPtr + page * ptrSize, pagePtr, '*');
      for (var offset = 0; offset < 8; offset++) {
        var idx = page * 8 + offset;
        setValue(pagePtr + offset * ptrSize, idx < items.length ? stringToNewUTF8(items[idx]) : 0, '*');
      }
    }
    setValue(ret, pagesPtr, '*');
    setValue(ret + 8, items.length, 'i64');
    setValue(ret + 16, pageCount * 8, 'i64');
    setValue(ret + 24, pageCount, 'i64');
  }

  function runtimeArgs() {
    if (typeof Module !== 'undefined' && Array.isArray(Module.arguments)) {
      return Module.arguments.map(String);
    }
    if (typeof arguments_ !== 'undefined' && Array.isArray(arguments_)) {
      return arguments_.map(String);
    }
    return [];
  }

  function nodeProcess() {
    if (typeof process !== 'undefined' && process) return process;
    if (typeof globalThis !== 'undefined' && globalThis.process) return globalThis.process;
    return null;
  }

  mergeInto(LibraryManager.library, {
    args: function (ret) {
      writeStrList(ret, runtimeArgs());
    },
    env: function (ret, key) {
      var proc = nodeProcess();
      var name = UTF8ToString(key || 0);
      if (!name) {
        HEAPU8[ret] = 0;
        setValue(ret + 8, 0, '*');
        return;
      }
      var value = proc && proc.env ? proc.env[name] : undefined;
      HEAPU8[ret] = value !== undefined ? 1 : 0;
      setValue(ret + 8, value !== undefined ? stringToNewUTF8(String(value)) : 0, '*');
    },
    setEnv: function (key, value) {
      var proc = nodeProcess();
      var name = UTF8ToString(key || 0);
      if (!name) return 0;
      if (proc && proc.env) {
        proc.env[name] = UTF8ToString(value || 0);
        return 1;
      }
      return 0;
    },
    cwd: function () {
      var proc = nodeProcess();
      if (proc && typeof proc.cwd === 'function') {
        try { return stringToNewUTF8(proc.cwd()); } catch (e) {}
      }
      return stringToNewUTF8('/');
    },
    exit: function (code) {
      quit_(code, new ExitStatus(code));
    },
    pid: function () {
      var proc = nodeProcess();
      // 浏览器没有稳定进程 ID，使用 -1 明确表示不可用，避免伪装成真实 PID 0。
      return proc && proc.pid ? proc.pid | 0 : -1;
    },
    platform: function () {
      return stringToNewUTF8('emcc');
    },
    arch: function () {
      return stringToNewUTF8('wasm32');
    },
  });
})();
