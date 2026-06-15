// EzLang std/net/http Emscripten JS 封装层
// 浏览器/Worker 使用 fetch + Asyncify 挂起 HTTP 客户端；无 Asyncify 时保留同步 XHR fallback。Node 风格运行时支持基础 HTTP 服务端。
(function () {
  var nextServerHandle = 1;
  var servers = Object.create(null);
  var root = typeof Module !== 'undefined' && Module ? Module : (typeof globalThis !== 'undefined' ? globalThis : this);

  function hasAsyncifyAsync() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleAsync === 'function';
  }

  function ptrSize() {
    return typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
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
    bytes = bytes || new Uint8Array(0);
    var dataPtr = 0;
    if (bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ptr, dataPtr, '*');
    setValue(ptr + 8, bytes.length, 'i64');
  }

  function textBytes(value) {
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

  function decodeBytes(bytes) {
    if (!bytes || bytes.length === 0) return '';
    if (typeof TextDecoder !== 'undefined') return new TextDecoder('utf-8').decode(bytes);
    var out = '';
    for (var i = 0; i < bytes.length; ++i) out += String.fromCharCode(bytes[i]);
    return out;
  }

  function hasNulBytes(bytes) {
    return bytes && bytes.indexOf(0) >= 0;
  }

  function validUtf8Bytes(bytes) {
    var i = 0;
    while (i < bytes.length) {
      var ch = bytes[i];
      var width = 0;
      if (ch < 0x80) width = 1;
      else if (ch >= 0xc2 && ch <= 0xdf) width = 2;
      else if (ch >= 0xe0 && ch <= 0xef) width = 3;
      else if (ch >= 0xf0 && ch <= 0xf4) width = 4;
      else return false;
      if (i + width > bytes.length) return false;
      for (var j = 1; j < width; j++) {
        if ((bytes[i + j] & 0xc0) !== 0x80) return false;
      }
      if (width === 3 && ch === 0xe0 && bytes[i + 1] < 0xa0) return false;
      if (width === 3 && ch === 0xed && bytes[i + 1] >= 0xa0) return false;
      if (width === 4 && ch === 0xf0 && bytes[i + 1] < 0x90) return false;
      if (width === 4 && ch === 0xf4 && bytes[i + 1] > 0x8f) return false;
      i += width;
    }
    return true;
  }

  function arrayBufferBytes(buffer) {
    if (!buffer) return new Uint8Array(0);
    return new Uint8Array(buffer);
  }

  function dictCount(dictPtr) {
    return dictPtr ? (getValue(dictPtr + 16, 'i32') | 0) : 0;
  }

  function dictItem(dictPtr, pageFieldOffset, index) {
    var size = ptrSize();
    var pages = getValue(dictPtr + pageFieldOffset, '*');
    if (!pages) return '';
    var pagePtr = getValue(pages + Math.floor(index / 8) * size, '*');
    if (!pagePtr) return '';
    var itemPtr = getValue(pagePtr + (index % 8) * size, '*');
    return readStr(itemPtr);
  }

  function dictEntries(dictPtr) {
    var count = dictCount(dictPtr);
    var out = [];
    for (var i = 0; i < count; ++i) {
      var key = dictItem(dictPtr, 0, i);
      if (!key) continue;
      out.push([key, dictItem(dictPtr, 8, i)]);
    }
    return out;
  }

  function writeDict(ptr, entries) {
    entries = entries || [];
    var size = ptrSize();
    var pageCount = entries.length === 0 ? 0 : Math.ceil(entries.length / 8);
    var keyPages = pageCount === 0 ? 0 : _malloc(pageCount * size);
    var valuePages = pageCount === 0 ? 0 : _malloc(pageCount * size);
    for (var page = 0; page < pageCount; ++page) {
      var keyPage = _malloc(8 * size);
      var valuePage = _malloc(8 * size);
      setValue(keyPages + page * size, keyPage, '*');
      setValue(valuePages + page * size, valuePage, '*');
      for (var offset = 0; offset < 8; ++offset) {
        var index = page * 8 + offset;
        setValue(keyPage + offset * size, index < entries.length ? stringToNewUTF8(entries[index][0]) : 0, '*');
        setValue(valuePage + offset * size, index < entries.length ? stringToNewUTF8(entries[index][1]) : 0, '*');
      }
    }
    setValue(ptr, keyPages, '*');
    setValue(ptr + 8, valuePages, '*');
    setValue(ptr + 16, entries.length, 'i32');
    setValue(ptr + 20, pageCount * 8, 'i32');
    setValue(ptr + 24, pageCount, 'i32');
  }

  function responseBodyText(respPtr) {
    if (!respPtr) return '';
    var bytes = blobBytes(respPtr + 32);
    if (bytes === null || hasNulBytes(bytes) || !validUtf8Bytes(bytes)) return '';
    return decodeBytes(bytes);
  }

  function parseResponseHeaders(raw) {
    if (!raw) return [];
    return String(raw).split(/\r?\n/).map(function (line) {
      var colon = line.indexOf(':');
      if (colon <= 0) return null;
      return [line.slice(0, colon).trim(), line.slice(colon + 1).trim()];
    }).filter(function (entry) { return entry && entry[0]; });
  }

  function writeResponse(ptr, status, headers, body) {
    setValue(ptr, status | 0, 'i32');
    writeDict(ptr + 8, headers);
    writeBlob(ptr + 32, body);
  }

  function writeOptResponse(ret, ok, response) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeResponse(ret + 8, ok ? response.status : 0, ok ? response.headers : [], ok ? response.body : new Uint8Array(0));
  }

  function readHttpServer(serverPtr) {
    return serverPtr ? servers[Number(getValue(serverPtr, 'i64'))] || null : null;
  }

  function callHandler(handler, reqPtr, respPtr) {
    if (!handler) return false;
    if (typeof dynCall_vii === 'function') {
      dynCall_vii(handler, respPtr, reqPtr);
      return true;
    }
    if (typeof Module !== 'undefined' && Module && typeof Module.dynCall_vii === 'function') {
      Module.dynCall_vii(handler, respPtr, reqPtr);
      return true;
    }
    var table = null;
    if (typeof getWasmTableEntry === 'function') table = { get: getWasmTableEntry };
    else if (typeof wasmTable !== 'undefined' && wasmTable && typeof wasmTable.get === 'function') table = wasmTable;
    if (!table) return false;
    var fn = table.get(Number(handler));
    if (!fn) return false;
    fn(respPtr, reqPtr);
    return true;
  }

  function readRequest(reqPtr) {
    if (!reqPtr) return null;
    var method = readStr(getValue(reqPtr, '*')) || 'GET';
    var url = readStr(getValue(reqPtr + 8, '*'));
    if (!url) return null;
    var hasBody = !!HEAPU8[reqPtr + 40];
    var body = hasBody ? blobBytes(reqPtr + 48) : new Uint8Array(0);
    if (body === null) return null;
    return {
      method: method,
      url: url,
      headers: dictEntries(reqPtr + 16),
      body: body,
    };
  }

  function requestUrl(req) {
    var url = req && req.url ? String(req.url) : '/';
    return url || '/';
  }

  function requestHeaders(req) {
    var entries = [];
    if (!req || !req.headers) return entries;
    Object.keys(req.headers).forEach(function (key) {
      var value = req.headers[key];
      if (Array.isArray(value)) value = value.join(', ');
      entries.push([key, value == null ? '' : String(value)]);
    });
    return entries;
  }

  function allocRequest(req, body) {
    var ptr = _malloc(64);
    setValue(ptr, stringToNewUTF8((req && req.method) || 'GET'), '*');
    setValue(ptr + 8, stringToNewUTF8(requestUrl(req)), '*');
    writeDict(ptr + 16, requestHeaders(req));
    HEAPU8[ptr + 40] = 1;
    for (var i = 41; i < 48; i++) HEAPU8[ptr + i] = 0;
    writeBlob(ptr + 48, body || new Uint8Array(0));
    return ptr;
  }

  function responseFromPtr(respPtr) {
    if (!respPtr) return { status: 404, headers: [], body: textBytes('not found') };
    var body = blobBytes(respPtr + 32);
    if (body === null) body = new Uint8Array(0);
    return {
      status: Number(getValue(respPtr, 'i32')) || 200,
      headers: dictEntries(respPtr + 8),
      body: body,
    };
  }

  function skipServerHeader(key) {
    key = String(key || '').toLowerCase();
    return key === 'content-length' || key === 'connection';
  }

  function sendNodeResponse(res, response) {
    var status = response && response.status > 0 ? response.status | 0 : 200;
    var body = response && response.body ? response.body : new Uint8Array(0);
    var headers = { 'Connection': 'close', 'Content-Length': String(body.length) };
    (response && response.headers || []).forEach(function (entry) {
      if (!entry || !entry[0] || skipServerHeader(entry[0])) return;
      headers[entry[0]] = entry[1] || '';
    });
    if (res && typeof res.writeHead === 'function') res.writeHead(status, headers);
    if (res && typeof res.end === 'function') res.end(bufferFor(body));
  }

  function bufferFor(bytes) {
    if (typeof Buffer !== 'undefined') return Buffer.from(bytes || new Uint8Array(0));
    return bytes || new Uint8Array(0);
  }

  function notFoundResponse() {
    return { status: 404, headers: [], body: textBytes('not found') };
  }

  function handlerFor(server, url) {
    if (!server || !url) return 0;
    var pathLen = String(url).search(/[?#]/);
    var path = pathLen < 0 ? String(url) : String(url).slice(0, pathLen);
    return server.routes[path] || 0;
  }

  function collectBody(req, callback) {
    var chunks = [];
    var done = false;
    function finish(bytes) {
      if (done) return;
      done = true;
      callback(bytes || new Uint8Array(0));
    }
    if (!req || typeof req.on !== 'function') return finish(new Uint8Array(0));
    req.on('data', function (chunk) { chunks.push(bufferFor(bytesValue(chunk))); });
    req.on('end', function () {
      if (typeof Buffer !== 'undefined') return finish(new Uint8Array(Buffer.concat(chunks)));
      var total = chunks.reduce(function (sum, item) { return sum + item.length; }, 0);
      var out = new Uint8Array(total);
      var offset = 0;
      chunks.forEach(function (item) { out.set(item, offset); offset += item.length; });
      finish(out);
    });
    req.on('error', function () { finish(new Uint8Array(0)); });
  }

  function bytesValue(value) {
    if (!value) return new Uint8Array(0);
    if (value instanceof Uint8Array) return value;
    if (typeof Buffer !== 'undefined' && Buffer.isBuffer && Buffer.isBuffer(value)) return new Uint8Array(value);
    return new Uint8Array(value);
  }

  function handleNodeRequest(server, req, res) {
    collectBody(req, function (body) {
      var handler = handlerFor(server, requestUrl(req));
      if (!handler) return sendNodeResponse(res, notFoundResponse());
      var reqPtr = allocRequest(req, body);
      var respPtr = _malloc(48);
      writeResponse(respPtr, 404, [], textBytes('not found'));
      var ok = callHandler(handler, reqPtr, respPtr);
      sendNodeResponse(res, ok ? responseFromPtr(respPtr) : notFoundResponse());
    });
  }

  function startServerAsync(server) {
    if (!server || server.running || !server.nodeServer || !hasAsyncifyAsync()) return false;
    server.running = true;
    return Asyncify.handleAsync(function () {
      return new Promise(function (resolve) {
        var settled = false;
        function done(value) {
          if (settled) return;
          settled = true;
          resolve(!!value);
        }
        try {
          server.nodeServer.once('error', function () { server.running = false; done(false); });
          server.nodeServer.once('listening', function () { done(true); });
          server.nodeServer.listen({ host: server.host || undefined, port: server.port });
        } catch (e) {
          server.running = false;
          done(false);
        }
      });
    });
  }

  function requestSync(req) {
    if (typeof XMLHttpRequest === 'undefined') return null;
    try {
      var xhr = new XMLHttpRequest();
      xhr.open(req.method || 'GET', req.url, false);
      xhr.responseType = 'arraybuffer';
      req.headers.forEach(function (entry) { xhr.setRequestHeader(entry[0], entry[1]); });
      xhr.send(req.body && req.body.length > 0 ? req.body : null);
      return {
        status: xhr.status | 0,
        headers: parseResponseHeaders(xhr.getAllResponseHeaders()),
        body: arrayBufferBytes(xhr.response || textBytes(xhr.responseText || '')),
      };
    } catch (e) {
      return null;
    }
  }

  function requestAsync(req) {
    if (!hasAsyncifyAsync() || typeof fetch !== 'function') return requestSync(req);
    return Asyncify.handleAsync(async function () {
      try {
        var headers = {};
        req.headers.forEach(function (entry) { headers[entry[0]] = entry[1]; });
        var response = await fetch(req.url, {
          method: req.method || 'GET',
          headers: headers,
          body: req.body && req.body.length > 0 ? req.body : undefined,
        });
        var responseHeaders = [];
        if (response.headers && typeof response.headers.forEach === 'function') {
          response.headers.forEach(function (value, key) { responseHeaders.push([key, value]); });
        }
        return {
          status: response.status | 0,
          headers: responseHeaders,
          body: arrayBufferBytes(await response.arrayBuffer()),
        };
      } catch (e) {
        return null;
      }
    });
  }

  mergeInto(LibraryManager.library, {
    fetch__async: 'auto',
    fetch: function (ret, url) {
      var req = { method: 'GET', url: readStr(url), headers: [], body: new Uint8Array(0) };
      var response = req.url ? requestAsync(req) : null;
      writeOptResponse(ret, !!response, response);
    },
    fetchEx__async: 'auto',
    fetchEx: function (ret, req) {
      var request = readRequest(req);
      var response = request ? requestAsync(request) : null;
      writeOptResponse(ret, !!response, response);
    },
    createServer: function (host, port) {
      port = Number(port);
      if (!Number.isInteger(port) || port < 0 || port > 65535) return 0n;
      var http = nodeRequire('http');
      if (!http || typeof http.createServer !== 'function' || !hasAsyncifyAsync()) return 0n;
      var handle = nextServerHandle++;
      var server = {
        handle: handle,
        host: readStr(host) || '127.0.0.1',
        port: port,
        routes: Object.create(null),
        nodeServer: null,
        running: false,
      };
      server.nodeServer = http.createServer(function (req, res) { handleNodeRequest(server, req, res); });
      servers[handle] = server;
      return BigInt(handle);
    },
    HttpServer_on: function (serverPtr, path, handler) {
      var server = readHttpServer(serverPtr);
      var route = readStr(path);
      if (!server || !route || !handler) return;
      server.routes[route] = handler;
    },
    HttpServer_start__async: 'auto',
    HttpServer_start: function (serverPtr) {
      startServerAsync(readHttpServer(serverPtr));
    },
    HttpServer_stop: function (serverPtr) {
      var server = readHttpServer(serverPtr);
      if (!server) return;
      delete servers[server.handle];
      if (server.nodeServer && typeof server.nodeServer.close === 'function') {
        try { server.nodeServer.close(); } catch (e) {}
      }
      server.running = false;
      if (serverPtr) setValue(serverPtr, 0, 'i64');
    },
    HttpResponse_text: function (resp) {
      return stringToNewUTF8(responseBodyText(resp));
    },
  });
})();
