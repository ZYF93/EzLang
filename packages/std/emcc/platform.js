// EzLang std/platform Emscripten JS 封装层
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
    if (typeof navigator !== 'undefined' && navigator.hardwareConcurrency) return navigator.hardwareConcurrency | 0;
    return 1;
  },
  platformMemoryLimit: function () {
    if (typeof performance !== 'undefined' && performance.memory && performance.memory.jsHeapSizeLimit) {
      return BigInt(performance.memory.jsHeapSizeLimit);
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
    return cryptoObj && typeof cryptoObj.getRandomValues === 'function' ? 1 : 0;
  },
  platformHasDom: function () {
    return typeof document !== 'undefined' ? 1 : 0;
  },
  platformHasSubprocess: function () {
    return 0;
  },
});
