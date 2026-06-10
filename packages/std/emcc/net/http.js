// EzLang std/net/http Emscripten JS 封装层
// 浏览器/Worker 同步 XMLHttpRequest 支持 HTTP 客户端；服务端明确不支持。
(function () {
  var HTTP_SERVER_UNSUPPORTED_HANDLE = 0n;

  function ptrSize() {
    return typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
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

  function readRequest(reqPtr) {
    if (!reqPtr) return null;
    var method = readStr(getValue(reqPtr, '*')) || 'GET';
    var url = readStr(getValue(reqPtr + 8, '*'));
    if (!url) return null;
    var body = blobBytes(reqPtr + 40);
    if (body === null) return null;
    return {
      method: method,
      url: url,
      headers: dictEntries(reqPtr + 16),
      body: body,
    };
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

  mergeInto(LibraryManager.library, {
    fetch: function (ret, url) {
      var req = { method: 'GET', url: readStr(url), headers: [], body: new Uint8Array(0) };
      var response = req.url ? requestSync(req) : null;
      writeOptResponse(ret, !!response, response);
    },
    fetchEx: function (ret, req) {
      var request = readRequest(req);
      var response = request ? requestSync(request) : null;
      writeOptResponse(ret, !!response, response);
    },
    createServer: function (host, port) {
      void host;
      void port;
      return HTTP_SERVER_UNSUPPORTED_HANDLE;
    },
    HttpResponse_text: function (resp) {
      return stringToNewUTF8(responseBodyText(resp));
    },
  });
})();
