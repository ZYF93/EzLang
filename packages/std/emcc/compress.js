// EzLang std/compress Emscripten JS 封装层
// 同步 ABI 下使用 Node zlib；浏览器端暂无同步压缩 API，返回空可选值。
(function () {
  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function writeBlob(ptr, bytes) {
    var dataPtr = 0;
    if (bytes && bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ptr, dataPtr, '*');
    setValue(ptr + 8, bytes ? bytes.length : 0, 'i64');
  }

  function writeOptBlob(ret, ok, bytes) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeBlob(ret + 8, ok ? bytes : new Uint8Array(0));
  }

  function nodeZlib() {
    if (typeof require !== 'function') return null;
    try { return require('zlib'); } catch (e) { return null; }
  }

  function run(method, dataPtr) {
    var zlib = nodeZlib();
    if (!zlib || typeof zlib[method] !== 'function') return null;
    try {
      return new Uint8Array(zlib[method](Buffer.from(blobBytes(dataPtr))));
    } catch (e) {
      return null;
    }
  }

  mergeInto(LibraryManager.library, {
    compressGzip: function (ret, data) {
      var out = run('gzipSync', data);
      writeOptBlob(ret, !!out, out);
    },
    decompressGzip: function (ret, data) {
      var out = run('gunzipSync', data);
      writeOptBlob(ret, !!out, out);
    },
    compressZlib: function (ret, data) {
      var out = run('deflateSync', data);
      writeOptBlob(ret, !!out, out);
    },
    decompressZlib: function (ret, data) {
      var out = run('inflateSync', data);
      writeOptBlob(ret, !!out, out);
    },
    compressDeflate: function (ret, data) {
      var out = run('deflateRawSync', data);
      writeOptBlob(ret, !!out, out);
    },
    decompressDeflate: function (ret, data) {
      var out = run('inflateRawSync', data);
      writeOptBlob(ret, !!out, out);
    },
  });
})();
