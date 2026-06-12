// EzLang std/net/tcp Emscripten JS 封装层
// Node 风格运行时使用 net/tls/dgram + Asyncify 挂起 TCP/TLS/UDP；浏览器/Worker 没有原生 TCP/UDP 能力时显式失败。
(function () {
  var MAX_PACKET = 16 * 1024 * 1024;
  var nextHandle = 1;
  var conns = Object.create(null);
  var listeners = Object.create(null);
  var udpSockets = Object.create(null);
  var root = typeof Module !== 'undefined' && Module ? Module : (typeof globalThis !== 'undefined' ? globalThis : this);

  function hasAsyncifyAsync() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleAsync === 'function';
  }

  function nodeRequire(name) {
    if (typeof require === 'function') {
      try { return require(name); } catch (e) {}
    }
    if (root && typeof root.require === 'function') {
      try { return root.require(name); } catch (e) {}
    }
    return null;
  }

  function readStr(ptr) {
    return ptr ? UTF8ToString(ptr) : '';
  }

  function validPort(port) {
    port = Number(port);
    return Number.isInteger(port) && port >= 0 && port <= 65535;
  }

  function validMax(maxBytes) {
    var max = Number(maxBytes);
    if (!Number.isFinite(max) || max < 0 || Math.floor(max) !== max) return -1;
    return Math.min(max, MAX_PACKET);
  }

  function validTimeout(timeoutMs) {
    if (timeoutMs === null || timeoutMs === undefined) return null;
    var timeout = Number(timeoutMs);
    if (!Number.isFinite(timeout) || timeout < 0 || Math.floor(timeout) !== timeout) return -1;
    return timeout;
  }

  function readHandle(ptr) {
    return ptr ? Number(getValue(ptr, 'i64')) : 0;
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

  function bytesValue(value) {
    if (!value) return new Uint8Array(0);
    if (value instanceof Uint8Array) return value;
    if (typeof Buffer !== 'undefined' && Buffer.isBuffer && Buffer.isBuffer(value)) return new Uint8Array(value);
    return new Uint8Array(value);
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

  function writeOptHandle(ret, handle) {
    HEAPU8[ret] = handle ? 1 : 0;
    setValue(ret + 8, handle || 0, 'i64');
  }

  function writeOptBlob(ret, ok, bytes) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeBlob(ret + 8, ok ? bytes : new Uint8Array(0));
  }

  function writeOptUdpPacket(ret, packet) {
    HEAPU8[ret] = packet ? 1 : 0;
    writeBlob(ret + 8, packet ? packet.bytes : new Uint8Array(0));
    setValue(ret + 24, packet ? stringToNewUTF8(packet.host || '') : 0, '*');
    setValue(ret + 32, packet ? packet.port | 0 : 0, 'i32');
  }

  function newConn(socket) {
    var handle = nextHandle++;
    var conn = { handle: handle, socket: socket, queue: [], waiters: [], closed: false, failed: false };
    conns[handle] = conn;
    socket.on('data', function (chunk) { deliverTcp(conn, bytesValue(chunk)); });
    socket.on('end', function () { closeTcp(conn); });
    socket.on('close', function () { closeTcp(conn); });
    socket.on('error', function () { failTcp(conn); });
    return conn;
  }

  function deliverTcp(conn, bytes) {
    if (!conn || conn.closed || conn.failed) return;
    if (conn.waiters.length > 0) conn.waiters.shift()({ bytes: bytes });
    else conn.queue.push(bytes);
  }

  function failTcp(conn) {
    if (!conn || conn.failed) return;
    conn.failed = true;
    while (conn.waiters.length > 0) conn.waiters.shift()(null);
  }

  function closeTcp(conn) {
    if (!conn || conn.closed) return;
    conn.closed = true;
    while (conn.waiters.length > 0) conn.waiters.shift()({ bytes: new Uint8Array(0), closed: true });
  }

  function readConn(connPtr) {
    return conns[readHandle(connPtr)] || null;
  }

  function readListener(listenerPtr) {
    return listeners[readHandle(listenerPtr)] || null;
  }

  function readUdp(socketPtr) {
    return udpSockets[readHandle(socketPtr)] || null;
  }

  function bufferFor(bytes) {
    if (typeof Buffer !== 'undefined') return Buffer.from(bytes);
    return bytes;
  }

  function connectAsync(host, port) {
    return connectTimeoutAsync(host, port, null);
  }

  function connectTimeoutAsync(host, port, timeoutMs) {
    timeoutMs = validTimeout(timeoutMs);
    if (!host || !validPort(port) || timeoutMs === -1 || !hasAsyncifyAsync()) return null;
    var net = nodeRequire('net');
    if (!net || typeof net.createConnection !== 'function') return null;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        var timer = null;
        function done(value) {
          if (settled) return;
          settled = true;
          if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
          resolve(value);
        }
        try {
          var socket = net.createConnection({ host: host, port: port | 0 });
          if (timeoutMs !== null && typeof setTimeout === 'function') {
            timer = setTimeout(function () {
              closeSocket(socket);
              done(null);
            }, timeoutMs);
          }
          socket.once('connect', function () { done(newConn(socket)); });
          socket.once('error', function () { done(null); });
        } catch (e) {
          done(null);
        }
      });
    });
  }

  function tlsConnectAsync(host, port) {
    if (!host || !validPort(port) || !hasAsyncifyAsync()) return null;
    var tls = nodeRequire('tls');
    if (!tls || typeof tls.connect !== 'function') return null;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        function done(value) {
          if (settled) return;
          settled = true;
          resolve(value);
        }
        try {
          var socket = tls.connect({ host: host, servername: host, port: port | 0 });
          socket.once('secureConnect', function () { done(newConn(socket)); });
          socket.once('error', function () { done(null); });
        } catch (e) {
          done(null);
        }
      });
    });
  }

  function listenAsync(host, port) {
    if (!validPort(port) || !hasAsyncifyAsync()) return null;
    var net = nodeRequire('net');
    if (!net || typeof net.createServer !== 'function') return null;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        function done(value) {
          if (settled) return;
          settled = true;
          resolve(value);
        }
        try {
          var listener = { handle: nextHandle++, server: null, queue: [], waiters: [], closed: false, failed: false };
          var server = net.createServer(function (socket) {
            var conn = newConn(socket);
            if (listener.waiters.length > 0) listener.waiters.shift()(conn);
            else listener.queue.push(conn);
          });
          listener.server = server;
          listeners[listener.handle] = listener;
          server.once('listening', function () { done(listener); });
          server.on('error', function () {
            listener.failed = true;
            delete listeners[listener.handle];
            while (listener.waiters.length > 0) listener.waiters.shift()(null);
            done(null);
          });
          server.on('close', function () {
            listener.closed = true;
            while (listener.waiters.length > 0) listener.waiters.shift()(null);
          });
          server.listen({ host: host || undefined, port: port | 0 });
        } catch (e) {
          done(null);
        }
      });
    });
  }

  function acceptAsync(listener) {
    return acceptTimeoutAsync(listener, null);
  }

  function acceptTimeoutAsync(listener, timeoutMs) {
    timeoutMs = validTimeout(timeoutMs);
    if (timeoutMs === -1) return null;
    if (!listener || listener.closed || listener.failed || !hasAsyncifyAsync()) return null;
    if (listener.queue.length > 0) return listener.queue.shift();
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        var timer = null;
        function done(value) {
          if (settled) return;
          settled = true;
          if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
          listener.waiters = listener.waiters.filter(function (item) { return item !== done; });
          resolve(value);
        }
        listener.waiters.push(done);
        if (timeoutMs !== null && typeof setTimeout === 'function') timer = setTimeout(function () { done(null); }, timeoutMs);
      });
    });
  }

  function readTcpAsync(conn, max) {
    return readTcpTimeoutAsync(conn, max, null);
  }

  function readTcpTimeoutAsync(conn, max, timeoutMs) {
    timeoutMs = validTimeout(timeoutMs);
    if (timeoutMs === -1) return null;
    if (!conn || conn.failed || max < 0 || !hasAsyncifyAsync()) return null;
    if (max === 0) return new Uint8Array(0);
    if (conn.queue.length > 0) {
      var chunk = conn.queue.shift();
      if (chunk.length > max) {
        conn.queue.unshift(chunk.slice(max));
        return chunk.slice(0, max);
      }
      return chunk;
    }
    if (conn.closed) return new Uint8Array(0);
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        var timer = null;
        function done(item) {
          if (settled) return;
          settled = true;
          if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
          conn.waiters = conn.waiters.filter(function (waiter) { return waiter !== done; });
          if (!item) return resolve(null);
          var bytes = item.bytes || new Uint8Array(0);
          if (bytes.length > max) {
            conn.queue.unshift(bytes.slice(max));
            resolve(bytes.slice(0, max));
            return;
          }
          resolve(bytes);
        }
        conn.waiters.push(done);
        if (timeoutMs !== null && typeof setTimeout === 'function') timer = setTimeout(function () { done(null); }, timeoutMs);
      });
    });
  }

  function writeTcpAsync(conn, bytes) {
    return writeTcpTimeoutAsync(conn, bytes, null);
  }

  function writeTcpTimeoutAsync(conn, bytes, timeoutMs) {
    timeoutMs = validTimeout(timeoutMs);
    if (!conn || conn.closed || conn.failed || bytes === null) return -1;
    if (bytes.length === 0) return 0;
    if (timeoutMs === -1) return -1;
    if (!hasAsyncifyAsync()) return -1;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        var timer = null;
        function done(value) {
          if (settled) return;
          settled = true;
          if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
          if (typeof conn.socket.removeListener === 'function') conn.socket.removeListener('error', onError);
          resolve(value);
        }
        function onError() {
          failTcp(conn);
          done(-1);
        }
        try {
          if (typeof conn.socket.once === 'function') conn.socket.once('error', onError);
          if (timeoutMs !== null && typeof setTimeout === 'function') timer = setTimeout(function () { done(-1); }, timeoutMs);
          conn.socket.write(bufferFor(bytes), function (err) {
            if (err) onError();
            else done(bytes.length);
          });
        } catch (e) {
          onError();
        }
      });
    });
  }

  function bindUdpAsync(host, port) {
    if (!validPort(port) || !hasAsyncifyAsync()) return null;
    var dgram = nodeRequire('dgram');
    if (!dgram || typeof dgram.createSocket !== 'function') return null;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        function done(value) {
          if (settled) return;
          settled = true;
          resolve(value);
        }
        try {
          var socket = dgram.createSocket(host && host.indexOf(':') >= 0 ? 'udp6' : 'udp4');
          var value = { handle: nextHandle++, socket: socket, queue: [], waiters: [], closed: false, failed: false };
          socket.on('message', function (msg, rinfo) {
            var packet = { bytes: bytesValue(msg), host: rinfo && rinfo.address ? rinfo.address : '', port: rinfo ? rinfo.port | 0 : 0 };
            if (value.waiters.length > 0) value.waiters.shift()(packet);
            else value.queue.push(packet);
          });
          socket.once('listening', function () {
            udpSockets[value.handle] = value;
            done(value);
          });
          socket.on('error', function () {
            value.failed = true;
            delete udpSockets[value.handle];
            while (value.waiters.length > 0) value.waiters.shift()(null);
            done(null);
          });
          socket.on('close', function () {
            value.closed = true;
            while (value.waiters.length > 0) value.waiters.shift()(null);
          });
          socket.bind(port | 0, host || undefined);
        } catch (e) {
          done(null);
        }
      });
    });
  }

  function recvUdpAsync(socketValue, max) {
    return recvUdpTimeoutAsync(socketValue, max, null);
  }

  function recvUdpTimeoutAsync(socketValue, max, timeoutMs) {
    timeoutMs = validTimeout(timeoutMs);
    if (timeoutMs === -1) return null;
    if (!socketValue || socketValue.closed || socketValue.failed || max < 0 || !hasAsyncifyAsync()) return null;
    if (socketValue.queue.length > 0) return clampUdpPacket(socketValue.queue.shift(), max);
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        var timer = null;
        function done(packet) {
          if (settled) return;
          settled = true;
          if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
          socketValue.waiters = socketValue.waiters.filter(function (waiter) { return waiter !== done; });
          resolve(clampUdpPacket(packet, max));
        }
        socketValue.waiters.push(done);
        if (timeoutMs !== null && typeof setTimeout === 'function') timer = setTimeout(function () { done(null); }, timeoutMs);
      });
    });
  }

  function sendUdpAsync(socketValue, host, port, bytes) {
    return sendUdpTimeoutAsync(socketValue, host, port, bytes, null);
  }

  function sendUdpTimeoutAsync(socketValue, host, port, bytes, timeoutMs) {
    timeoutMs = validTimeout(timeoutMs);
    if (!socketValue || socketValue.closed || socketValue.failed || !host || !validPort(port) || bytes === null) return -1;
    if (timeoutMs === -1) return -1;
    if (!hasAsyncifyAsync()) return -1;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        var timer = null;
        function done(value) {
          if (settled) return;
          settled = true;
          if (timer !== null && typeof clearTimeout === 'function') clearTimeout(timer);
          resolve(value);
        }
        try {
          if (timeoutMs !== null && typeof setTimeout === 'function') timer = setTimeout(function () { done(-1); }, timeoutMs);
          socketValue.socket.send(bufferFor(bytes), port | 0, host, function (err) {
            if (err) {
              socketValue.failed = true;
              done(-1);
              return;
            }
            done(bytes.length);
          });
        } catch (e) {
          socketValue.failed = true;
          done(-1);
        }
      });
    });
  }

  function clampUdpPacket(packet, max) {
    if (!packet) return null;
    var bytes = packet.bytes || new Uint8Array(0);
    if (bytes.length > max) bytes = bytes.slice(0, max);
    return { bytes: bytes, host: packet.host || '', port: packet.port | 0 };
  }

  function closeSocket(socket) {
    if (!socket) return false;
    try {
      if (typeof socket.end === 'function') socket.end();
      if (typeof socket.destroy === 'function') socket.destroy();
      else if (typeof socket.close === 'function') socket.close();
      return true;
    } catch (e) {
      return false;
    }
  }

  var streamBridge = root.__ez_stream_bridge || (root.__ez_stream_bridge = {});
  streamBridge.readTcp = function (ret, streamPtr, maxBytes) {
    var max = validMax(maxBytes);
    var bytes = readTcpAsync(conns[readHandle(streamPtr)], max);
    writeOptBlob(ret, bytes !== null, bytes || new Uint8Array(0));
  };
  streamBridge.writeTcp = function (streamPtr, dataPtr) {
    var conn = conns[readHandle(streamPtr)];
    var bytes = readBlob(dataPtr);
    return writeTcpAsync(conn, bytes);
  };
  streamBridge.flushTcp = function (streamPtr) {
    var conn = conns[readHandle(streamPtr)];
    return conn && !conn.closed && !conn.failed ? 1 : 0;
  };
  streamBridge.closeTcp = function (streamPtr) {
    var conn = conns[readHandle(streamPtr)];
    if (!conn) return 0;
    var handle = conn.handle;
    var ok = closeSocket(conn.socket);
    closeTcp(conn);
    delete conns[handle];
    return ok ? 1 : 0;
  };

  mergeInto(LibraryManager.library, {
    tcpConnect__async: 'auto',
    tcpConnect: function (ret, host, port) {
      var conn = connectAsync(readStr(host), port);
      writeOptHandle(ret, conn ? conn.handle : 0);
    },
    tcpConnectTimeout__async: 'auto',
    tcpConnectTimeout: function (ret, host, port, timeoutMs) {
      var conn = connectTimeoutAsync(readStr(host), port, timeoutMs);
      writeOptHandle(ret, conn ? conn.handle : 0);
    },
    tcpTlsConnect__async: 'auto',
    tcpTlsConnect: function (ret, host, port) {
      var conn = tlsConnectAsync(readStr(host), port);
      writeOptHandle(ret, conn ? conn.handle : 0);
    },
    tcpTlsRead__async: 'auto',
    tcpTlsRead: function (ret, connPtr, maxBytes) {
      var max = validMax(maxBytes);
      var bytes = readTcpAsync(readConn(connPtr), max);
      writeOptBlob(ret, bytes !== null, bytes || new Uint8Array(0));
    },
    tcpTlsWrite__async: 'auto',
    tcpTlsWrite: function (connPtr, dataPtr) {
      return streamBridge.writeTcp(connPtr, dataPtr);
    },
    tcpTlsClose: function (connPtr) {
      return streamBridge.closeTcp(connPtr);
    },
    tcpListen__async: 'auto',
    tcpListen: function (ret, host, port) {
      var listener = listenAsync(readStr(host), port);
      writeOptHandle(ret, listener ? listener.handle : 0);
    },
    tcpAccept__async: 'auto',
    tcpAccept: function (ret, listenerPtr) {
      var conn = acceptAsync(readListener(listenerPtr));
      writeOptHandle(ret, conn ? conn.handle : 0);
    },
    tcpAcceptTimeout__async: 'auto',
    tcpAcceptTimeout: function (ret, listenerPtr, timeoutMs) {
      var conn = acceptTimeoutAsync(readListener(listenerPtr), timeoutMs);
      writeOptHandle(ret, conn ? conn.handle : 0);
    },
    tcpRead__async: 'auto',
    tcpRead: function (ret, connPtr, maxBytes) {
      var max = validMax(maxBytes);
      var bytes = readTcpAsync(readConn(connPtr), max);
      writeOptBlob(ret, bytes !== null, bytes || new Uint8Array(0));
    },
    tcpReadTimeout__async: 'auto',
    tcpReadTimeout: function (ret, connPtr, maxBytes, timeoutMs) {
      var max = validMax(maxBytes);
      var bytes = readTcpTimeoutAsync(readConn(connPtr), max, timeoutMs);
      writeOptBlob(ret, bytes !== null, bytes || new Uint8Array(0));
    },
    tcpWrite__async: 'auto',
    tcpWrite: function (connPtr, dataPtr) {
      return streamBridge.writeTcp(connPtr, dataPtr);
    },
    tcpWriteTimeout__async: 'auto',
    tcpWriteTimeout: function (connPtr, dataPtr, timeoutMs) {
      return writeTcpTimeoutAsync(readConn(connPtr), readBlob(dataPtr), timeoutMs);
    },
    tcpClose: function (connPtr) {
      return streamBridge.closeTcp(connPtr);
    },
    tcpListenerClose: function (listenerPtr) {
      var listener = readListener(listenerPtr);
      if (!listener) return 0;
      delete listeners[listener.handle];
      listener.closed = true;
      while (listener.waiters.length > 0) listener.waiters.shift()(null);
      try { listener.server.close(); } catch (e) { return 0; }
      return 1;
    },
    udpBind__async: 'auto',
    udpBind: function (ret, host, port) {
      var socket = bindUdpAsync(readStr(host), port);
      writeOptHandle(ret, socket ? socket.handle : 0);
    },
    udpSend__async: 'auto',
    udpSend: function (socketPtr, host, port, dataPtr) {
      var socketValue = readUdp(socketPtr);
      var bytes = readBlob(dataPtr);
      var target = readStr(host);
      return sendUdpAsync(socketValue, target, port, bytes);
    },
    udpSendTimeout__async: 'auto',
    udpSendTimeout: function (socketPtr, host, port, dataPtr, timeoutMs) {
      var socketValue = readUdp(socketPtr);
      var bytes = readBlob(dataPtr);
      var target = readStr(host);
      return sendUdpTimeoutAsync(socketValue, target, port, bytes, timeoutMs);
    },
    udpRecvFrom__async: 'auto',
    udpRecvFrom: function (ret, socketPtr, maxBytes) {
      var max = validMax(maxBytes);
      var socketValue = readUdp(socketPtr);
      if (max === 0 && socketValue && !socketValue.closed && !socketValue.failed) return writeOptUdpPacket(ret, { bytes: new Uint8Array(0), host: '', port: 0 });
      writeOptUdpPacket(ret, recvUdpAsync(socketValue, max));
    },
    udpRecvFromTimeout__async: 'auto',
    udpRecvFromTimeout: function (ret, socketPtr, maxBytes, timeoutMs) {
      var max = validMax(maxBytes);
      var socketValue = readUdp(socketPtr);
      if (max === 0 && socketValue && !socketValue.closed && !socketValue.failed) return writeOptUdpPacket(ret, { bytes: new Uint8Array(0), host: '', port: 0 });
      writeOptUdpPacket(ret, recvUdpTimeoutAsync(socketValue, max, timeoutMs));
    },
    udpRecv__async: 'auto',
    udpRecv: function (ret, socketPtr, maxBytes) {
      var max = validMax(maxBytes);
      var socketValue = readUdp(socketPtr);
      if (max === 0 && socketValue && !socketValue.closed && !socketValue.failed) return writeOptBlob(ret, true, new Uint8Array(0));
      var packet = recvUdpAsync(socketValue, max);
      writeOptBlob(ret, !!packet, packet ? packet.bytes : new Uint8Array(0));
    },
    udpRecvTimeout__async: 'auto',
    udpRecvTimeout: function (ret, socketPtr, maxBytes, timeoutMs) {
      var max = validMax(maxBytes);
      var socketValue = readUdp(socketPtr);
      if (max === 0 && socketValue && !socketValue.closed && !socketValue.failed) return writeOptBlob(ret, true, new Uint8Array(0));
      var packet = recvUdpTimeoutAsync(socketValue, max, timeoutMs);
      writeOptBlob(ret, !!packet, packet ? packet.bytes : new Uint8Array(0));
    },
    udpClose: function (socketPtr) {
      var socketValue = readUdp(socketPtr);
      if (!socketValue) return 0;
      delete udpSockets[socketValue.handle];
      socketValue.closed = true;
      while (socketValue.waiters.length > 0) socketValue.waiters.shift()(null);
      try { socketValue.socket.close(); } catch (e) { return 0; }
      return 1;
    },
  });
})();
