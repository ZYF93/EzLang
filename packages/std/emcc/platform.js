// EzLang std/platform Emscripten JS 封装层
function requireNodeModule(name) {
  if (typeof require !== 'function') return null;
  try { return require(name); } catch (e) { return null; }
}

mergeInto(LibraryManager.library, {
  platformOS: function () {
    return stringToNewUTF8('emcc');
  },
  platformArch: function () {
    return stringToNewUTF8('wasm32');
  },
  platformIsLittleEndian: function () {
    return 1;
  },
  platformPointerBits: function () {
    return (typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4) * 8;
  },
  platformPageSize: function () {
    return 65536n;
  },
  platformCpuCount: function () {
    var os = requireNodeModule('os');
    if (os && typeof os.cpus === 'function') {
      try {
        var cpus = os.cpus();
        if (Array.isArray(cpus) && cpus.length > 0) return Math.min(cpus.length, 2147483647);
      } catch (e) {}
    }
    if (typeof navigator !== 'undefined') {
      var concurrency = Number(navigator.hardwareConcurrency);
      if (Number.isFinite(concurrency) && concurrency > 0) return Math.min(Math.floor(concurrency), 2147483647);
    }
    return 1;
  },
  platformMemoryLimit: function () {
    if (typeof performance !== 'undefined' && performance.memory && performance.memory.jsHeapSizeLimit) {
      return BigInt(performance.memory.jsHeapSizeLimit);
    }
    var os = requireNodeModule('os');
    if (os && typeof os.totalmem === 'function') {
      try { return BigInt(os.totalmem()); } catch (e) {}
    }
    return -1n;
  },
  platformHasThreads: function () {
    return (typeof SharedArrayBuffer !== 'undefined' && typeof Atomics !== 'undefined') ? 1 : 0;
  },
  platformHasFileSystem: function () {
    return typeof FS !== 'undefined' ? 1 : 0;
  },
  platformHasNetwork: function () {
    return (typeof fetch !== 'undefined' || typeof WebSocket !== 'undefined') ? 1 : 0;
  },
  platformHasCrypto: function () {
    var cryptoObj = typeof crypto !== 'undefined' ? crypto : (typeof globalThis !== 'undefined' ? globalThis.crypto : null);
    if (cryptoObj && typeof cryptoObj.getRandomValues === 'function') return 1;
    var nodeCrypto = requireNodeModule('crypto');
    return nodeCrypto && (typeof nodeCrypto.randomBytes === 'function' || typeof nodeCrypto.createHash === 'function') ? 1 : 0;
  },
  platformHasDom: function () {
    return typeof document !== 'undefined' ? 1 : 0;
  },
  platformHasSubprocess: function () {
    var childProcess = requireNodeModule('child_process');
    return childProcess && typeof childProcess.spawnSync === 'function' ? 1 : 0;
  },
});
