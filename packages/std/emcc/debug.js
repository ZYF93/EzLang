// EzLang std/debug Emscripten JS 封装层
(function () {
  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function writeOptStr(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    setValue(ret + 8, ok ? stringToNewUTF8(value || '') : 0, '*');
  }

  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size <= 0 || Math.floor(size) !== size || !dataPtr) return new Uint8Array(0);
    if (dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  mergeInto(LibraryManager.library, {
    debugPrint: function (msg) {
      if (typeof console !== 'undefined' && console.error) console.error(text(msg));
    },
    debugAssert: function (condition, msg) {
      if (!condition) {
        var message = text(msg) || 'assertion failed';
        if (typeof console !== 'undefined' && console.error) console.error(message);
        throw new Error(message);
      }
    },
    debugCrash: function (msg) {
      var message = text(msg) || 'debug crash';
      if (typeof console !== 'undefined' && console.error) console.error(message);
      throw new Error(message);
    },
    debugLocation: function (file, line, column) {
      return stringToNewUTF8(text(file) + ':' + (line | 0) + ':' + (column | 0));
    },
    debugRuntimeInfo: function () {
      return stringToNewUTF8('ezlang emcc/wasm32');
    },
    debugHex: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var out = '';
      for (var i = 0; i < bytes.length; i++) out += bytes[i].toString(16).padStart(2, '0');
      return stringToNewUTF8(out);
    },
    debugStack: function (ret) {
      try {
        var stack = new Error().stack || '';
        writeOptStr(ret, stack.length > 0, stack);
      } catch (e) {
        writeOptStr(ret, false, '');
      }
    },
  });
})();
