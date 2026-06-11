// EzLang std/compress Emscripten JS 封装层
// 同步 ABI 下使用 Node zlib；浏览器端暂无同步压缩 API，返回空可选值。
(function () {
  var root = typeof Module !== 'undefined' && Module ? Module : (typeof globalThis !== 'undefined' ? globalThis : this);

  function blobBytes(blobPtr) {
    if (!blobPtr) return null;
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size < 0 || Math.floor(size) !== size || (!dataPtr && size > 0)) return null;
    if (size === 0) return new Uint8Array(0);
    if (dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
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
      var input = blobBytes(dataPtr);
      if (input === null) return null;
      return new Uint8Array(zlib[method](Buffer.from(input)));
    } catch (e) {
      return null;
    }
  }

  function freePtr(ptr) {
    if (ptr && typeof _free === 'function') _free(ptr);
  }

  function streamChunkSize(bufferSize) {
    var size = Number(bufferSize);
    if (!Number.isFinite(size) || size <= 0) size = 8192;
    if (size > 1024 * 1024) size = 1024 * 1024;
    return Math.floor(size);
  }

  function streamBridge() {
    var bridge = root && root.__ez_stream_bridge;
    if (bridge && typeof bridge.read === 'function' && typeof bridge.write === 'function') return bridge;
    var api = LibraryManager.library || {};
    return { read: api.streamRead, write: api.streamWrite, flush: api.streamFlush };
  }

  function readAllStream(srcPtr, bufferSize) {
    var bridge = streamBridge();
    if (typeof bridge.read !== 'function') return null;
    var chunk = streamChunkSize(bufferSize);
    var tmpOpt = _malloc(24);
    var chunks = [];
    var total = 0;
    try {
      while (true) {
        bridge.read(tmpOpt, srcPtr, chunk);
        if (!HEAPU8[tmpOpt]) return null;
        var dataPtr = getValue(tmpOpt + 8, '*');
        var size = Number(getValue(tmpOpt + 16, 'i64'));
        if (!Number.isFinite(size) || size < 0 || Math.floor(size) !== size) return null;
        if (size === 0) {
          freePtr(dataPtr);
          break;
        }
        if (!dataPtr || dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
        chunks.push(HEAPU8.slice(dataPtr, dataPtr + size));
        total += size;
        freePtr(dataPtr);
      }
    } finally {
      freePtr(tmpOpt);
    }
    var out = new Uint8Array(total);
    var offset = 0;
    for (var i = 0; i < chunks.length; i++) {
      out.set(chunks[i], offset);
      offset += chunks[i].length;
    }
    return out;
  }

  function writeAllStream(dstPtr, bytes) {
    var bridge = streamBridge();
    if (typeof bridge.write !== 'function') return -1;
    var tmpBlob = _malloc(16);
    var dataPtr = 0;
    try {
      if (bytes.length > 0) {
        dataPtr = _malloc(bytes.length);
        HEAPU8.set(bytes, dataPtr);
      }
      setValue(tmpBlob, dataPtr, '*');
      setValue(tmpBlob + 8, bytes.length, 'i64');
      var written = Number(bridge.write(dstPtr, tmpBlob));
      if (written !== bytes.length) return -1;
      if (typeof bridge.flush === 'function' && !bridge.flush(dstPtr)) return -1;
      return written;
    } finally {
      freePtr(dataPtr);
      freePtr(tmpBlob);
    }
  }

  function runStream(method, dstPtr, srcPtr, bufferSize) {
    var zlib = nodeZlib();
    if (!zlib || typeof zlib[method] !== 'function') return -1;
    try {
      var input = readAllStream(srcPtr, bufferSize);
      if (input === null) return -1;
      var output = new Uint8Array(zlib[method](Buffer.from(input)));
      return writeAllStream(dstPtr, output);
    } catch (e) {
      return -1;
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
    compressGzipStream: function (dst, src, bufferSize) {
      return runStream('gzipSync', dst, src, bufferSize);
    },
    decompressGzipStream: function (dst, src, bufferSize) {
      return runStream('gunzipSync', dst, src, bufferSize);
    },
    compressZlibStream: function (dst, src, bufferSize) {
      return runStream('deflateSync', dst, src, bufferSize);
    },
    decompressZlibStream: function (dst, src, bufferSize) {
      return runStream('inflateSync', dst, src, bufferSize);
    },
    compressDeflateStream: function (dst, src, bufferSize) {
      return runStream('deflateRawSync', dst, src, bufferSize);
    },
    decompressDeflateStream: function (dst, src, bufferSize) {
      return runStream('inflateRawSync', dst, src, bufferSize);
    },
  });
})();
