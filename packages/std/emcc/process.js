// EzLang std/process Emscripten JS 封装层
// WebAssembly/浏览器不支持同步子进程；同步 ABI 下统一返回空可选值。
(function () {
  function writeProcess(ptr, handle, pid) {
    setValue(ptr, BigInt(handle || 0), 'i64');
    setValue(ptr + 8, BigInt(pid || 0), 'i64');
  }

  function writeOptProcess(ret, ok) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeProcess(ret + 8, 0, 0);
  }

  function writeOptProcessResult(ret, ok) {
    HEAPU8[ret] = ok ? 1 : 0;
    // 当前目标不支持子进程；只需保证可选值标志为 false。
    setValue(ret + 8, 0, 'i32');
  }

  function writeOptStr(ret, value) {
    HEAPU8[ret] = value === null ? 0 : 1;
    setValue(ret + 8, value === null ? 0 : stringToNewUTF8(value), '*');
  }

  mergeInto(LibraryManager.library, {
    processExec: function (ret, commandPtr) {
      void commandPtr;
      writeOptProcessResult(ret, false);
    },
    processSpawn: function (ret, commandPtr) {
      void commandPtr;
      writeOptProcess(ret, false);
    },
    processWait: function (ret, processPtr) {
      void processPtr;
      writeOptProcessResult(ret, false);
    },
    processTerminate: function (processPtr) {
      void processPtr;
      return 0;
    },
    processCurrentPath: function (ret) {
      writeOptStr(ret, null);
    },
  });
})();
