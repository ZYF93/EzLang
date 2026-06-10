// EzLang std/uri Emscripten JS 封装层
(function () {
  var PTR = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;

  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function writeStr(ptr, value) {
    setValue(ptr, stringToNewUTF8(value || ''), '*');
  }

  function writeUriParts(ptr, parts) {
    writeStr(ptr, parts.scheme);
    writeStr(ptr + PTR, parts.userInfo);
    writeStr(ptr + PTR * 2, parts.host);
    setValue(ptr + PTR * 3, parts.port | 0, 'i32');
    writeStr(ptr + PTR * 4, parts.path);
    writeStr(ptr + PTR * 5, parts.query);
    writeStr(ptr + PTR * 6, parts.fragment);
  }

  function readUriParts(ptr) {
    if (!ptr) return null;
    return {
      scheme: text(getValue(ptr, '*')),
      userInfo: text(getValue(ptr + PTR, '*')),
      host: text(getValue(ptr + PTR * 2, '*')),
      port: getValue(ptr + PTR * 3, 'i32') | 0,
      path: text(getValue(ptr + PTR * 4, '*')),
      query: text(getValue(ptr + PTR * 5, '*')),
      fragment: text(getValue(ptr + PTR * 6, '*')),
    };
  }

  function writeOptStr(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeStr(ret + 8, ok ? value : '');
  }

  function writeOptI32(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    setValue(ret + 4, ok ? (value | 0) : 0, 'i32');
  }

  function writeOptUriParts(ret, parts) {
    HEAPU8[ret] = parts ? 1 : 0;
    writeUriParts(ret + 8, parts || emptyParts());
  }

  function emptyParts() {
    return { scheme: '', userInfo: '', host: '', port: -1, path: '', query: '', fragment: '' };
  }

  function validScheme(value) {
    return /^[A-Za-z][A-Za-z0-9+.-]*$/.test(value);
  }

  function lower(value) {
    return String(value || '').toLowerCase();
  }

  function parsePort(value) {
    if (!/^\d+$/.test(value || '')) return null;
    var port = Number(value);
    return port >= 0 && port <= 65535 ? port : null;
  }

  function parse(url) {
    url = text(url);
    var schemeMatch = /^([^:/?#]+):/.exec(url);
    if (!schemeMatch || !validScheme(schemeMatch[1])) return null;
    var parts = emptyParts();
    parts.scheme = lower(schemeMatch[1]);
    var index = schemeMatch[0].length;
    if (url.slice(index, index + 2) === '//') {
      index += 2;
      var authEnd = index;
      while (authEnd < url.length && !/[/?#]/.test(url.charAt(authEnd))) authEnd++;
      var authority = url.slice(index, authEnd);
      index = authEnd;
      var at = authority.lastIndexOf('@');
      var hostPort = authority;
      if (at >= 0) {
        parts.userInfo = authority.slice(0, at);
        hostPort = authority.slice(at + 1);
      }
      if (hostPort.charAt(0) === '[') {
        var close = hostPort.indexOf(']');
        if (close < 0) return null;
        parts.host = lower(hostPort.slice(0, close + 1));
        if (hostPort.charAt(close + 1) === ':') {
          parts.port = parsePort(hostPort.slice(close + 2));
          if (parts.port === null) return null;
        } else if (close + 1 !== hostPort.length) {
          return null;
        }
      } else {
        var colon = hostPort.lastIndexOf(':');
        if (colon >= 0) {
          parts.host = lower(hostPort.slice(0, colon));
          parts.port = parsePort(hostPort.slice(colon + 1));
          if (parts.port === null) return null;
        } else {
          parts.host = lower(hostPort);
        }
      }
    }
    var pathStart = index;
    while (index < url.length && url.charAt(index) !== '?' && url.charAt(index) !== '#') index++;
    parts.path = url.slice(pathStart, index);
    if (url.charAt(index) === '?') {
      index++;
      var queryStart = index;
      while (index < url.length && url.charAt(index) !== '#') index++;
      parts.query = url.slice(queryStart, index);
    }
    if (url.charAt(index) === '#') parts.fragment = url.slice(index + 1);
    return parts;
  }

  function hasAuthorityMarker(url) {
    url = String(url || '');
    var match = /^[A-Za-z][A-Za-z0-9+.-]*:/.exec(url);
    return !!(match && url.slice(match[0].length, match[0].length + 2) === '//');
  }

  function build(parts, forceAuthority) {
    if (!parts || !parts.scheme) return '';
    var out = parts.scheme + ':';
    var hasAuthority = !!(forceAuthority || parts.host || parts.userInfo);
    if (hasAuthority) {
      out += '//';
      if (parts.userInfo) out += parts.userInfo + '@';
      out += parts.host || '';
      if (parts.port >= 0) out += ':' + parts.port;
    }
    if (parts.path) {
      if (hasAuthority && parts.path.charAt(0) !== '/') out += '/';
      out += parts.path;
    } else if (hasAuthority) {
      out += '/';
    }
    if (parts.query) out += '?' + parts.query;
    if (parts.fragment) out += '#' + parts.fragment;
    return out;
  }

  function normalizePath(path) {
    if (!path) return '/';
    var absolute = path.charAt(0) === '/';
    var stack = [];
    path.split('/').forEach(function (part) {
      if (!part || part === '.') return;
      if (part === '..') {
        if (stack.length && stack[stack.length - 1] !== '..') stack.pop();
        else if (!absolute) stack.push(part);
      } else {
        stack.push(part);
      }
    });
    var out = (absolute ? '/' : '') + stack.join('/');
    return out || (absolute ? '/' : '.');
  }

  function percentEncodeString(value, queryMode) {
    value = String(value || '');
    var bytes = [];
    var len = lengthBytesUTF8(value);
    var ptr = _malloc(len + 1);
    stringToUTF8(value, ptr, len + 1);
    for (var i = 0; i < len; i++) bytes.push(HEAPU8[ptr + i]);
    var hex = '0123456789ABCDEF';
    var out = '';
    bytes.forEach(function (ch) {
      var keep = (ch >= 48 && ch <= 57) || (ch >= 65 && ch <= 90) || (ch >= 97 && ch <= 122) || ch === 45 || ch === 46 || ch === 95 || ch === 126;
      if (keep) out += String.fromCharCode(ch);
      else if (queryMode && ch === 32) out += '+';
      else out += '%' + hex[(ch >> 4) & 15] + hex[ch & 15];
    });
    return out;
  }

  function percentEncode(value, queryMode) {
    return percentEncodeString(text(value), queryMode);
  }

  function hexValue(ch) {
    if (ch >= '0' && ch <= '9') return ch.charCodeAt(0) - 48;
    if (ch >= 'A' && ch <= 'F') return ch.charCodeAt(0) - 55;
    if (ch >= 'a' && ch <= 'f') return ch.charCodeAt(0) - 87;
    return -1;
  }

  function appendCodePointUtf8(bytes, cp) {
    if (cp <= 0x7f) {
      bytes.push(cp);
    } else if (cp <= 0x7ff) {
      bytes.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    } else if (cp >= 0xd800 && cp <= 0xdfff) {
      return false;
    } else if (cp <= 0xffff) {
      bytes.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    } else if (cp <= 0x10ffff) {
      bytes.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    } else {
      return false;
    }
    return true;
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

  function percentDecodeString(value, queryMode) {
    value = String(value || '');
    var bytes = [];
    for (var i = 0; i < value.length; i++) {
      var ch = value.charAt(i);
      if (queryMode && ch === '+') {
        bytes.push(32);
      } else if (ch === '%') {
        if (i + 2 >= value.length) return null;
        var hi = hexValue(value.charAt(i + 1));
        var lo = hexValue(value.charAt(i + 2));
        if (hi < 0 || lo < 0) return null;
        bytes.push((hi << 4) | lo);
        i += 2;
      } else {
        var cp = value.codePointAt(i);
        if (cp > 0xffff) i++;
        if (!appendCodePointUtf8(bytes, cp)) return null;
      }
    }
    if (bytes.indexOf(0) >= 0) return null;
    if (!validUtf8Bytes(bytes)) return null;
    var ptr = _malloc(bytes.length + 1);
    HEAPU8.set(bytes, ptr);
    HEAPU8[ptr + bytes.length] = 0;
    try {
      return UTF8ToString(ptr);
    } catch (e) {
      return null;
    }
  }

  function percentDecode(value, queryMode) {
    return percentDecodeString(text(value), queryMode);
  }

  function queryKeyMatches(rawKey, key) {
    var decoded = percentDecodeString(rawKey, true);
    return decoded !== null && decoded === key;
  }

  function queryGet(queryPtr, keyPtr) {
    var query = text(queryPtr);
    var key = text(keyPtr);
    var entries = query ? query.split('&').filter(function (entry) { return entry.length > 0; }) : [];
    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      var eq = entry.indexOf('=');
      var rawKey = eq >= 0 ? entry.slice(0, eq) : entry;
      if (queryKeyMatches(rawKey, key)) return eq >= 0 ? percentDecodeString(entry.slice(eq + 1), true) : '';
    }
    return null;
  }

  function querySet(queryPtr, keyPtr, valuePtr) {
    var query = text(queryPtr);
    var key = text(keyPtr);
    var encodedKey = percentEncodeString(key, true);
    var encodedValue = percentEncode(valuePtr, true);
    var entries = query ? query.split('&').filter(function (entry) { return entry.length > 0; }) : [];
    var replaced = false;
    for (var i = 0; i < entries.length; i++) {
      var eq = entries[i].indexOf('=');
      var rawKey = eq >= 0 ? entries[i].slice(0, eq) : entries[i];
      if (!replaced && queryKeyMatches(rawKey, key)) {
        entries[i] = encodedKey + '=' + encodedValue;
        replaced = true;
      }
    }
    if (!replaced) entries.push(encodedKey + '=' + encodedValue);
    return entries.join('&');
  }

  mergeInto(LibraryManager.library, {
    uriParse: function (ret, url) {
      writeOptUriParts(ret, parse(url));
    },
    uriBuild: function (partsPtr) {
      return stringToNewUTF8(build(readUriParts(partsPtr)));
    },
    uriNormalize: function (url) {
      var parts = parse(url);
      if (!parts) return stringToNewUTF8('');
      var forceAuthority = hasAuthorityMarker(text(url));
      parts.path = !forceAuthority && !parts.path ? '' : normalizePath(parts.path);
      return stringToNewUTF8(build(parts, forceAuthority));
    },
    uriScheme: function (ret, url) {
      var parts = parse(url);
      writeOptStr(ret, !!(parts && parts.scheme), parts ? parts.scheme : '');
    },
    uriHost: function (ret, url) {
      var parts = parse(url);
      writeOptStr(ret, !!(parts && parts.host), parts ? parts.host : '');
    },
    uriPort: function (ret, url) {
      var parts = parse(url);
      writeOptI32(ret, !!(parts && parts.port >= 0), parts ? parts.port : 0);
    },
    uriPath: function (url) {
      var parts = parse(url);
      return stringToNewUTF8(parts ? parts.path : '');
    },
    uriQuery: function (ret, url) {
      var parts = parse(url);
      writeOptStr(ret, !!(parts && parts.query), parts ? parts.query : '');
    },
    uriFragment: function (ret, url) {
      var parts = parse(url);
      writeOptStr(ret, !!(parts && parts.fragment), parts ? parts.fragment : '');
    },
    uriEncodeQuery: function (s) {
      return stringToNewUTF8(percentEncode(s, true));
    },
    uriDecodeQuery: function (ret, s) {
      var decoded = percentDecode(s, true);
      writeOptStr(ret, decoded !== null, decoded || '');
    },
    uriEncodePathSegment: function (s) {
      return stringToNewUTF8(percentEncode(s, false));
    },
    uriDecodePathSegment: function (ret, s) {
      var decoded = percentDecode(s, false);
      writeOptStr(ret, decoded !== null, decoded || '');
    },
    uriQueryGet: function (ret, query, key) {
      var value = queryGet(query, key);
      writeOptStr(ret, value !== null, value || '');
    },
    uriQuerySet: function (query, key, value) {
      return stringToNewUTF8(querySet(query, key, value));
    },
  });
})();
