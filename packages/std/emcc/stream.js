// EzLang std/stream Emscripten JS 封装层
(function () {
  var nextHandle = 1;
  var streams = Object.create(null);

  function readBlob(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
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

  function writeStream(ptr, handle) {
    setValue(ptr, handle, 'i64');
    setValue(ptr + 8, 1, 'i32');
  }

  function readStream(ptr) {
    if (!ptr) return null;
    var handle = Number(getValue(ptr, 'i64'));
    var kind = getValue(ptr + 8, 'i32') | 0;
    if (kind !== 1 || !streams[handle]) return null;
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

  mergeInto(LibraryManager.library, {
    streamFromBlob: function (ret, dataPtr) {
      var handle = nextHandle++;
      streams[handle] = { data: readBlob(dataPtr), cursor: 0, closed: false };
      HEAPU8[ret] = 1;
      writeStream(ret + 8, handle);
    },
    streamRead: function (ret, streamPtr, maxBytes) {
      var stream = readStream(streamPtr);
      var max = Number(maxBytes);
      if (!stream || stream.closed || max < 0) return writeOptBlob(ret, false, new Uint8Array(0));
      var remaining = stream.data.length - stream.cursor;
      var count = Math.min(remaining, max);
      if (count <= 0) return writeOptBlob(ret, true, new Uint8Array(0));
      var out = stream.data.slice(stream.cursor, stream.cursor + count);
      stream.cursor += count;
      writeOptBlob(ret, true, out);
    },
    streamWrite: function (streamPtr, dataPtr) {
      var stream = readStream(streamPtr);
      if (!stream || stream.closed) return -1;
      return appendBytes(stream, readBlob(dataPtr));
    },
    streamToBlob: function (ret, streamPtr) {
      var stream = readStream(streamPtr);
      if (!stream || stream.closed) return writeOptBlob(ret, false, new Uint8Array(0));
      writeOptBlob(ret, true, stream.data.slice(0));
    },
    streamCopy: function (dstPtr, srcPtr, bufferSize) {
      var dst = readStream(dstPtr);
      var src = readStream(srcPtr);
      if (!dst || !src || dst.closed || src.closed) return -1;
      var copied = 0;
      var chunk = Number(bufferSize) > 0 ? Number(bufferSize) : 4096;
      while (src.cursor < src.data.length) {
        var count = Math.min(chunk, src.data.length - src.cursor);
        copied += appendBytes(dst, src.data.slice(src.cursor, src.cursor + count));
        src.cursor += count;
      }
      return copied;
    },
    streamFlush: function (streamPtr) {
      var stream = readStream(streamPtr);
      return stream && !stream.closed ? 1 : 0;
    },
    streamClose: function (streamPtr) {
      var handle = streamPtr ? Number(getValue(streamPtr, 'i64')) : 0;
      var stream = streams[handle];
      if (!stream || stream.closed) return 0;
      stream.closed = true;
      delete streams[handle];
      return 1;
    },
  });
})();
