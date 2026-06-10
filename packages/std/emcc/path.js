// EzLang std/path Emscripten JS 封装层
(function () {
  function ptrSize() {
    return typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
  }

  function listGet(listPtr, index) {
    if (!listPtr) return '';
    var size = ptrSize();
    var pages = getValue(listPtr, '*');
    var length = Number(getValue(listPtr + 8, 'i64'));
    if (!pages || index < 0 || index >= length) return '';
    var pagePtr = getValue(pages + Math.floor(index / 8) * size, '*');
    if (!pagePtr) return '';
    var itemPtr = getValue(pagePtr + (index % 8) * size, '*');
    return itemPtr ? UTF8ToString(itemPtr) : '';
  }

  function listLength(listPtr) {
    return listPtr ? Number(getValue(listPtr + 8, 'i64')) : 0;
  }

  function splitRoot(path) {
    if (!path) return '';
    if (/^[A-Za-z]:[\\/]/.test(path)) return path.slice(0, 3);
    if (/^[A-Za-z]:$/.test(path)) return path.slice(0, 2);
    if (/^[\\/]{2}/.test(path)) {
      var parts = path.slice(2).split(/[\\/]+/);
      if (parts.length >= 2 && parts[0] && parts[1]) {
        return path.slice(0, 2 + parts[0].length + 1 + parts[1].length);
      }
    }
    return /^[\\/]/.test(path) ? path.charAt(0) : '';
  }

  function isAbs(path) {
    return /^[\\/]/.test(path || '') || /^[A-Za-z]:[\\/]/.test(path || '');
  }

  function trimTrailingSeparators(path) {
    path = String(path || '');
    var root = splitRoot(path);
    var end = path.length;
    while (end > root.length && end > 1 && /[\\/]/.test(path.charAt(end - 1))) end--;
    return path.slice(0, end);
  }

  function isRootPath(path) {
    path = String(path || '');
    return path.length > 0 && path.length === splitRoot(path).length;
  }

  function styleSep(path) {
    return path && path.indexOf('\\') >= 0 ? '\\' : '/';
  }

  function normalize(path) {
    if (!path) return '.';
    var sep = styleSep(path);
    var root = splitRoot(path);
    var absolute = isAbs(path);
    var rest = path.slice(root.length);
    var out = [];
    rest.split(/[\\/]+/).forEach(function (part) {
      if (!part || part === '.') return;
      if (part === '..') {
        if (out.length && out[out.length - 1] !== '..') {
          out.pop();
        } else if (!absolute) {
          out.push('..');
        }
      } else {
        out.push(part);
      }
    });
    var result = root.replace(/[\\/]/g, sep);
    if (out.length) {
      if (result && !/[\\/]$/.test(result)) result += sep;
      result += out.join(sep);
    }
    if (!result) result = '.';
    return result;
  }

  function dirname(path) {
    if (!path) return '.';
    var clean = trimTrailingSeparators(path);
    var root = splitRoot(clean);
    if (clean.length <= root.length) return root || '.';
    var index = Math.max(clean.lastIndexOf('/'), clean.lastIndexOf('\\'));
    if (index < 0) return '.';
    if (index === 0) return clean.charAt(0);
    if (index < root.length) return root;
    return clean.slice(0, index);
  }

  function basename(path) {
    if (!path) return '';
    var clean = trimTrailingSeparators(path);
    var root = splitRoot(clean);
    if (clean.length <= root.length) return '';
    var index = Math.max(clean.lastIndexOf('/'), clean.lastIndexOf('\\'));
    return index < 0 ? clean : clean.slice(index + 1);
  }

  function extname(path) {
    var base = basename(path);
    var index = base.lastIndexOf('.');
    return index > 0 ? base.slice(index) : '';
  }

  function nameWithoutExt(path) {
    var base = basename(path);
    var ext = extname(path);
    return ext ? base.slice(0, base.length - ext.length) : base;
  }

  function relative(from, to) {
    var a = normalize(from || '.');
    var b = normalize(to || '.');
    if (isAbs(a) !== isAbs(b)) return b;
    var aRoot = splitRoot(a);
    var bRoot = splitRoot(b);
    if (aRoot.toLowerCase() !== bRoot.toLowerCase()) return b;
    var sep = styleSep(b);
    var aParts = a.slice(aRoot.length).split(/[\\/]+/).filter(Boolean);
    var bParts = b.slice(bRoot.length).split(/[\\/]+/).filter(Boolean);
    var i = 0;
    while (i < aParts.length && i < bParts.length && aParts[i] === bParts[i]) i++;
    var out = [];
    for (var j = i; j < aParts.length; j++) out.push('..');
    out = out.concat(bParts.slice(i));
    return out.length ? out.join(sep) : '.';
  }

  function encodeFilePath(path) {
    var clean = normalize(path || '').replace(/\\/g, '/');
    var driveAbs = /^[A-Za-z]:\//.test(clean);
    if (driveAbs || !isAbs(clean)) clean = '/' + clean;
    var out = 'file://';
    for (var i = 0; i < clean.length; i++) {
      var cp = clean.codePointAt(i);
      if (cp > 0xffff) i++;
      if (cp >= 0xd800 && cp <= 0xdfff) cp = 0xfffd;
      var bytes = [];
      appendCodePointUtf8(bytes, cp);
      for (var j = 0; j < bytes.length; j++) {
        out += driveAbs && i === 2 && bytes[j] === 58 ? ':' : fileUrlByte(bytes[j]);
      }
    }
    return out;
  }

  function fileUrlByte(byte) {
    if ((byte >= 65 && byte <= 90) || (byte >= 97 && byte <= 122) || (byte >= 48 && byte <= 57) ||
        byte === 45 || byte === 95 || byte === 46 || byte === 126 || byte === 47) {
      return String.fromCharCode(byte);
    }
    var hex = '0123456789ABCDEF';
    return '%' + hex.charAt(byte >> 4) + hex.charAt(byte & 15);
  }

  function decodeFileUrl(url) {
    if (String(url || '').slice(0, 7) !== 'file://') return null;
    var src = String(url).slice(7);
    var bytes = [];
    for (var i = 0; i < src.length; i++) {
      var ch = src.charAt(i);
      if (ch === '%') {
        if (i + 2 >= src.length) return null;
        var hi = hexValue(src.charAt(i + 1));
        var lo = hexValue(src.charAt(i + 2));
        if (hi < 0 || lo < 0) return null;
        bytes.push((hi << 4) | lo);
        i += 2;
      } else {
        var cp = src.charCodeAt(i);
        if (cp >= 0xd800 && cp <= 0xdbff && i + 1 < src.length) {
          var low = src.charCodeAt(i + 1);
          if (low >= 0xdc00 && low <= 0xdfff) {
            cp = 0x10000 + ((cp - 0xd800) << 10) + (low - 0xdc00);
            i++;
          }
        }
        appendCodePointUtf8(bytes, cp);
      }
    }
    if (bytes.length >= 3 && bytes[0] === 47 && ((bytes[1] >= 65 && bytes[1] <= 90) || (bytes[1] >= 97 && bytes[1] <= 122)) && bytes[2] === 58) {
      bytes.shift();
    }
    if (bytes.indexOf(0) >= 0) return null;
    return cStringFromBytes(bytes);
  }

  function hexValue(ch) {
    var code = ch.charCodeAt(0);
    if (code >= 48 && code <= 57) return code - 48;
    if (code >= 65 && code <= 70) return code - 55;
    if (code >= 97 && code <= 102) return code - 87;
    return -1;
  }

  function appendCodePointUtf8(bytes, cp) {
    if (cp <= 0x7f) {
      bytes.push(cp);
    } else if (cp <= 0x7ff) {
      bytes.push(0xc0 | (cp >> 6), 0x80 | (cp & 0x3f));
    } else if (cp <= 0xffff) {
      bytes.push(0xe0 | (cp >> 12), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    } else {
      bytes.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    }
  }

  function cStringFromBytes(bytes) {
    var ptr = _malloc(bytes.length + 1);
    if (bytes.length > 0) HEAPU8.set(bytes, ptr);
    HEAPU8[ptr + bytes.length] = 0;
    return ptr;
  }

  function writePathParts(ret, path) {
    var size = ptrSize();
    path = path || '';
    var root = splitRoot(path);
    var base = basename(path);
    var values = isRootPath(trimTrailingSeparators(path))
      ? [root, root, '', '', '']
      : [root, dirname(path), base, nameWithoutExt(path), extname(path)];
    for (var i = 0; i < values.length; i++) {
      setValue(ret + i * size, stringToNewUTF8(values[i]), '*');
    }
  }

  mergeInto(LibraryManager.library, {
    pathSeparator: function () {
      return stringToNewUTF8('/');
    },
    pathJoin: function (partsPtr) {
      var parts = [];
      var length = listLength(partsPtr);
      for (var i = 0; i < length; i++) parts.push(listGet(partsPtr, i));
      return stringToNewUTF8(normalize(parts.filter(Boolean).join('/')));
    },
    pathNormalize: function (path) {
      return stringToNewUTF8(normalize(UTF8ToString(path || 0)));
    },
    pathDir: function (path) {
      return stringToNewUTF8(dirname(UTF8ToString(path || 0)));
    },
    pathBase: function (path) {
      return stringToNewUTF8(basename(UTF8ToString(path || 0)));
    },
    pathExt: function (path) {
      return stringToNewUTF8(extname(UTF8ToString(path || 0)));
    },
    pathIsAbs: function (path) {
      return isAbs(UTF8ToString(path || 0)) ? 1 : 0;
    },
    pathRelative: function (from, to) {
      return stringToNewUTF8(relative(UTF8ToString(from || 0), UTF8ToString(to || 0)));
    },
    pathParse: function (ret, path) {
      writePathParts(ret, UTF8ToString(path || 0));
    },
    pathToFileUrl: function (path) {
      return stringToNewUTF8(encodeFilePath(UTF8ToString(path || 0)));
    },
    pathFromFileUrl: function (ret, url) {
      var value = decodeFileUrl(UTF8ToString(url || 0));
      HEAPU8[ret] = value === null ? 0 : 1;
      setValue(ret + 8, value === null ? 0 : value, '*');
    },
  });
})();
