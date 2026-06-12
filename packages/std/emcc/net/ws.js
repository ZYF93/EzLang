// EzLang std/net/ws Emscripten JS 封装层
// 浏览器/Worker 使用 WebSocket + Asyncify 挂起客户端连接与接收；缺少 WebSocket 或 Asyncify 时显式失败。
(function () {
  var MAX_MESSAGE = 16 * 1024 * 1024;
  var nextHandle = 1;
  var conns = Object.create(null);

  function hasAsyncifyAsync() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleAsync === 'function';
  }

  function readStr(ptr) {
    return ptr ? UTF8ToString(ptr) : '';
  }

  function readConn(ptr) {
    if (!ptr) return null;
    var handle = Number(getValue(ptr, 'i64'));
    return conns[handle] || null;
  }

  function readBlob(blobPtr) {
    if (!blobPtr) return null;
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size < 0 || Math.floor(size) !== size || size > MAX_MESSAGE) return null;
    if (size === 0) return new Uint8Array(0);
    if (!dataPtr || dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function writeOptConn(ret, conn) {
    HEAPU8[ret] = conn ? 1 : 0;
    setValue(ret + 8, conn ? conn.handle : 0, 'i64');
  }

  function writeBlob(ptr, bytes) {
    bytes = bytes || new Uint8Array(0);
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

  function bytesFromString(value) {
    value = String(value || '');
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(value);
    var bytes = [];
    for (var i = 0; i < value.length; ++i) {
      var code = value.charCodeAt(i);
      if (code < 0x80) bytes.push(code);
      else if (code < 0x800) bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
      else bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    }
    return new Uint8Array(bytes);
  }

  function bytesFromMessage(data) {
    if (data == null) return Promise.resolve(new Uint8Array(0));
    if (data instanceof Uint8Array) return Promise.resolve(data);
    if (typeof ArrayBuffer !== 'undefined' && data instanceof ArrayBuffer) return Promise.resolve(new Uint8Array(data));
    if (typeof Blob !== 'undefined' && data instanceof Blob && typeof data.arrayBuffer === 'function') {
      return data.arrayBuffer().then(function (buffer) { return new Uint8Array(buffer); });
    }
    return Promise.resolve(bytesFromString(data));
  }

  function deliver(conn, item) {
    if (!conn) return;
    if (conn.waiters.length > 0) {
      var waiter = conn.waiters.shift();
      waiter(item);
      return;
    }
    conn.queue.push(item);
  }

  function failConn(conn) {
    if (!conn || conn.failed) return;
    conn.failed = true;
    while (conn.waiters.length > 0) conn.waiters.shift()(null);
  }

  function closeConn(conn) {
    if (!conn || conn.closed) return;
    conn.closed = true;
    while (conn.waiters.length > 0) conn.waiters.shift()({ closed: true, bytes: new Uint8Array(0) });
  }

  function connectAsync(url) {
    if (!hasAsyncifyAsync() || typeof WebSocket === 'undefined') return null;
    if (!url || !/^wss?:\/\//i.test(url)) return null;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var socket;
        try {
          socket = new WebSocket(url);
        } catch (e) {
          resolve(null);
          return;
        }
        try { socket.binaryType = 'arraybuffer'; } catch (e) {}
        var settled = false;
        function finish(value) {
          if (settled) return;
          settled = true;
          resolve(value);
        }
        socket.onopen = function () {
          var handle = nextHandle++;
          var conn = { handle: handle, socket: socket, queue: [], waiters: [], closed: false, failed: false };
          conns[handle] = conn;
          socket.onmessage = function (event) {
            bytesFromMessage(event.data).then(function (bytes) {
              deliver(conn, { bytes: bytes });
            }, function () {
              failConn(conn);
            });
          };
          socket.onerror = function () { failConn(conn); };
          socket.onclose = function () { closeConn(conn); };
          finish(conn);
        };
        socket.onerror = function () { finish(null); };
        socket.onclose = function () { finish(null); };
      });
    });
  }

  function recvAsync(conn) {
    if (!hasAsyncifyAsync()) return null;
    if (!conn || conn.failed) return null;
    if (conn.queue.length > 0) return conn.queue.shift();
    if (conn.closed) return { closed: true, bytes: new Uint8Array(0) };
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        conn.waiters.push(resolve);
      });
    });
  }

  mergeInto(LibraryManager.library, {
    wsConnect__async: 'auto',
    wsConnect: function (ret, url) {
      var conn = connectAsync(readStr(url));
      writeOptConn(ret, conn);
    },
    wsSend: function (connPtr, dataPtr) {
      var conn = readConn(connPtr);
      var bytes = readBlob(dataPtr);
      if (!conn || !conn.socket || conn.closed || conn.failed || bytes === null) return -1;
      if (bytes.length === 0) return 0;
      try {
        if (conn.socket.readyState !== 1) return -1;
        conn.socket.send(bytes);
        return bytes.length;
      } catch (e) {
        failConn(conn);
        return -1;
      }
    },
    wsRecv__async: 'auto',
    wsRecv: function (ret, connPtr, maxBytes) {
      var max = Number(maxBytes);
      if (!Number.isFinite(max) || max < 0) return writeOptBlob(ret, false, new Uint8Array(0));
      if (max > MAX_MESSAGE) max = MAX_MESSAGE;
      var item = recvAsync(readConn(connPtr));
      if (!item) return writeOptBlob(ret, false, new Uint8Array(0));
      if (item.closed) return writeOptBlob(ret, true, new Uint8Array(0));
      var bytes = item.bytes || new Uint8Array(0);
      if (bytes.length > max) return writeOptBlob(ret, false, new Uint8Array(0));
      writeOptBlob(ret, true, bytes);
    },
    wsClose: function (connPtr) {
      var conn = readConn(connPtr);
      if (!conn) return 0;
      var handle = conn.handle;
      try {
        if (conn.socket && conn.socket.readyState < 2) conn.socket.close();
      } catch (e) {}
      closeConn(conn);
      delete conns[handle];
      return 1;
    },
  });
})();
