// EzLang std/stream Emscripten JS 封装层
(function () {
  var STREAM_KIND_MEMORY = 1;
  var STREAM_KIND_FILE_READ = 2;
  var STREAM_KIND_FILE_WRITE = 3;
  var STREAM_KIND_TCP = 4;
  var STREAM_KIND_PROCESS_STDIN = 5;
  var STREAM_KIND_PROCESS_STDOUT = 6;
  var STREAM_KIND_PROCESS_STDERR = 7;
  var nextHandle = 1;
  var streams = Object.create(null);
  var root = typeof Module !== 'undefined' && Module ? Module : (typeof globalThis !== 'undefined' ? globalThis : this);
  var bridge = root.__ez_stream_bridge || (root.__ez_stream_bridge = {});

  function hasAsyncify() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleSleep === 'function';
  }

  function suspendStream(fn) {
    if (!hasAsyncify() || typeof setTimeout !== 'function') return fn();
    return Asyncify.handleSleep(function (wakeUp) {
      setTimeout(function () { wakeUp(fn()); }, 0);
    });
  }

  function pathText(path) {
    return UTF8ToString(path || 0);
  }

  function readBlob(blobPtr) {
    if (!blobPtr) return null;
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size < 0 || Math.floor(size) !== size) return null;
    if (size === 0) return new Uint8Array(0);
    if (!dataPtr || dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function writeBlob(ptr, bytes) {
    var dataPtr = 0;
    if (bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ptr, dataPtr, '*');
    setValue(ptr + 8, bytes.length, 'i64');
  }

  function writeOptBlob(ret, ok, bytes) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeBlob(ret + 8, ok ? bytes : new Uint8Array(0));
  }

  function writeStream(ptr, handle, kind) {
    setValue(ptr, handle, 'i64');
    setValue(ptr + 8, kind, 'i32');
  }

  function readStream(ptr, expectedKind) {
    if (!ptr) return null;
    var handle = Number(getValue(ptr, 'i64'));
    var kind = getValue(ptr + 8, 'i32') | 0;
    if (kind !== expectedKind || !streams[handle]) return null;
    return streams[handle];
  }

  function appendBytes(stream, bytes) {
    if (!bytes || bytes.length === 0) return 0;
    var next = new Uint8Array(stream.data.length + bytes.length);
    next.set(stream.data, 0);
    next.set(bytes, stream.data.length);
    stream.data = next;
    return bytes.length;
  }

  function createByteStream(bytes, kind) {
    if (!(bytes instanceof Uint8Array)) bytes = new Uint8Array(bytes || 0);
    var handle = nextHandle++;
    streams[handle] = { kind: kind, data: bytes.slice(0), cursor: 0, closed: false };
    return { handle: handle, kind: kind };
  }

  bridge.fromBytes = function (bytes, kind) {
    kind = kind | 0;
    if (kind !== STREAM_KIND_MEMORY && kind !== STREAM_KIND_PROCESS_STDOUT && kind !== STREAM_KIND_PROCESS_STDERR) return null;
    return createByteStream(bytes, kind);
  };

  function flushFileStream(stream) {
    if (!stream || stream.closed || !stream.file || typeof FS === 'undefined') return 0;
    try {
      if (typeof FS.fsync === 'function') FS.fsync(stream.file);
      if (typeof FS.syncfs === 'function') FS.syncfs(false, function () {});
      return 1;
    } catch (e) {
      return 0;
    }
  }

  function streamReadImpl(ret, streamPtr, maxBytes) {
    var max = Number(maxBytes);
    var stream = readStream(streamPtr, STREAM_KIND_MEMORY);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_FILE_READ);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_PROCESS_STDOUT);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_PROCESS_STDERR);
    if (!stream && streamPtr && (getValue(streamPtr + 8, 'i32') | 0) === STREAM_KIND_TCP) {
      return writeOptBlob(ret, false, new Uint8Array(0));
    }
    if (!stream || stream.closed || max < 0) return writeOptBlob(ret, false, new Uint8Array(0));
    if (max === 0) return writeOptBlob(ret, true, new Uint8Array(0));
    if (stream.kind === STREAM_KIND_MEMORY || stream.kind === STREAM_KIND_PROCESS_STDOUT || stream.kind === STREAM_KIND_PROCESS_STDERR) {
      var remaining = stream.data.length - stream.cursor;
      var count = Math.min(remaining, max);
      if (count <= 0) return writeOptBlob(ret, true, new Uint8Array(0));
      var out = stream.data.slice(stream.cursor, stream.cursor + count);
      stream.cursor += count;
      return writeOptBlob(ret, true, out);
    }
    try {
      var bytes = new Uint8Array(max);
      var read = FS.read(stream.file, bytes, 0, max, null);
      writeOptBlob(ret, true, read > 0 ? bytes.slice(0, read) : new Uint8Array(0));
    } catch (e) {
      writeOptBlob(ret, false, new Uint8Array(0));
    }
  }

  function streamWriteImpl(streamPtr, dataPtr) {
    var stream = readStream(streamPtr, STREAM_KIND_MEMORY);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_FILE_WRITE);
    if (!stream && streamPtr && (getValue(streamPtr + 8, 'i32') | 0) === STREAM_KIND_TCP) return -1;
    if (!stream || stream.closed) return -1;
    var bytes = readBlob(dataPtr);
    if (bytes === null) return -1;
    if (bytes.length === 0) return 0;
    if (stream.kind === STREAM_KIND_MEMORY) return appendBytes(stream, bytes);
    try {
      var written = FS.write(stream.file, bytes, 0, bytes.length, null);
      return written === bytes.length ? written : -1;
    } catch (e) {
      return -1;
    }
  }

  function streamCopyImpl(dstPtr, srcPtr, bufferSize) {
    var copied = 0;
    var chunk = Number(bufferSize) > 0 ? Number(bufferSize) : 4096;
    var tmpBlob = _malloc(16);
    var tmpOpt = _malloc(24);
    try {
      while (true) {
        streamReadImpl(tmpOpt, srcPtr, chunk);
        if (!HEAPU8[tmpOpt]) return -1;
        var dataPtr = getValue(tmpOpt + 8, '*');
        var size = Number(getValue(tmpOpt + 16, 'i64'));
        if (size === 0) {
          if (dataPtr) _free(dataPtr);
          return copied;
        }
        setValue(tmpBlob, dataPtr, '*');
        setValue(tmpBlob + 8, size, 'i64');
        var written = streamWriteImpl(dstPtr, tmpBlob);
        _free(dataPtr);
        if (written !== size) return -1;
        copied += written;
      }
    } finally {
      _free(tmpBlob);
      _free(tmpOpt);
    }
  }

  bridge.read = streamReadImpl;
  bridge.write = streamWriteImpl;
  bridge.flush = function (streamPtr) {
    var stream = readStream(streamPtr, STREAM_KIND_MEMORY);
    if (stream) return stream.closed ? 0 : 1;
    stream = readStream(streamPtr, STREAM_KIND_FILE_WRITE);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_PROCESS_STDIN);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_PROCESS_STDOUT);
    if (!stream) stream = readStream(streamPtr, STREAM_KIND_PROCESS_STDERR);
    if (stream && (stream.kind === STREAM_KIND_PROCESS_STDIN || stream.kind === STREAM_KIND_PROCESS_STDOUT || stream.kind === STREAM_KIND_PROCESS_STDERR)) return stream.closed ? 0 : 1;
    if (!stream && streamPtr && (getValue(streamPtr + 8, 'i32') | 0) === STREAM_KIND_TCP) return 0;
    return flushFileStream(stream);
  };

  mergeInto(LibraryManager.library, {
    streamFromBlob: function (ret, dataPtr) {
      var data = readBlob(dataPtr);
      if (data === null) {
        HEAPU8[ret] = 0;
        writeStream(ret + 8, 0, 0);
        return;
      }
      var handle = nextHandle++;
      streams[handle] = { kind: STREAM_KIND_MEMORY, data: data, cursor: 0, closed: false };
      HEAPU8[ret] = 1;
      writeStream(ret + 8, handle, STREAM_KIND_MEMORY);
    },
    streamFromTcpHandle: function (ret, handle) {
      writeStream(ret, Number(handle), STREAM_KIND_TCP);
    },
    streamOpenFileRead__async: 'auto',
    streamOpenFileRead: function (ret, pathPtr) {
      return suspendStream(function () {
        try {
          if (typeof FS === 'undefined') throw new Error('FS unavailable');
          var path = pathText(pathPtr);
          if (!path) throw new Error('empty path');
          var handle = nextHandle++;
          streams[handle] = { kind: STREAM_KIND_FILE_READ, file: FS.open(path, 'r'), closed: false };
          HEAPU8[ret] = 1;
          writeStream(ret + 8, handle, STREAM_KIND_FILE_READ);
        } catch (e) {
          HEAPU8[ret] = 0;
          writeStream(ret + 8, 0, 0);
        }
      });
    },
    streamOpenFileWrite__async: 'auto',
    streamOpenFileWrite: function (ret, pathPtr) {
      return suspendStream(function () {
        try {
          if (typeof FS === 'undefined') throw new Error('FS unavailable');
          var path = pathText(pathPtr);
          if (!path) throw new Error('empty path');
          var parts = path.split('/');
          parts.pop();
          var current = path.charAt(0) === '/' ? '/' : '';
          for (var i = 0; i < parts.length; i++) {
            var part = parts[i];
            if (!part) continue;
            current = current === '/' ? '/' + part : current + '/' + part;
            try { FS.mkdir(current); } catch (ignored) {}
          }
          var handle = nextHandle++;
          streams[handle] = { kind: STREAM_KIND_FILE_WRITE, file: FS.open(path, 'w'), closed: false };
          HEAPU8[ret] = 1;
          writeStream(ret + 8, handle, STREAM_KIND_FILE_WRITE);
        } catch (e) {
          HEAPU8[ret] = 0;
          writeStream(ret + 8, 0, 0);
        }
      });
    },
    streamRead__async: 'auto',
    streamRead: function (ret, streamPtr, maxBytes) {
      return suspendStream(function () { return streamReadImpl(ret, streamPtr, maxBytes); });
    },
    streamWrite__async: 'auto',
    streamWrite: function (streamPtr, dataPtr) {
      return suspendStream(function () { return streamWriteImpl(streamPtr, dataPtr); });
    },
    streamToBlob: function (ret, streamPtr) {
      var stream = readStream(streamPtr, STREAM_KIND_MEMORY);
      if (!stream || stream.closed) return writeOptBlob(ret, false, new Uint8Array(0));
      writeOptBlob(ret, true, stream.data.slice(0));
    },
    streamCopy__async: 'auto',
    streamCopy: function (dstPtr, srcPtr, bufferSize) {
      return suspendStream(function () { return streamCopyImpl(dstPtr, srcPtr, bufferSize); });
    },
    streamFlush__async: 'auto',
    streamFlush: function (streamPtr) {
      return suspendStream(function () { return bridge.flush(streamPtr); });
    },
    streamClose__async: 'auto',
    streamClose: function (streamPtr) {
      return suspendStream(function () {
        var handle = streamPtr ? Number(getValue(streamPtr, 'i64')) : 0;
        var stream = streams[handle];
        if (!stream && streamPtr && (getValue(streamPtr + 8, 'i32') | 0) === STREAM_KIND_TCP) return 0;
        if (!stream || stream.closed) return 0;
        if (stream.file) {
          try { FS.close(stream.file); } catch (e) { return 0; }
        }
        stream.closed = true;
        delete streams[handle];
        return 1;
      });
    },
  });
})();
