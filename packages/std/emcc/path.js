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
    var clean = String(path).replace(/[\\/]+$/, '');
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
    var clean = String(path).replace(/[\\/]+$/, '');
    var root = splitRoot(clean);
    if (clean.length <= root.length) return root;
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
    if (!isAbs(clean)) clean = '/' + clean;
    return 'file://' + clean.split('').map(function (ch) {
      return /[A-Za-z0-9_.~\-/]/.test(ch) ? ch : encodeURIComponent(ch);
    }).join('');
  }

  function decodeFileUrl(url) {
    if (String(url || '').slice(0, 7) !== 'file://') return null;
    try {
      return decodeURIComponent(String(url).slice(7));
    } catch (e) {
      return null;
    }
  }

  function writePathParts(ret, path) {
    var size = ptrSize();
    var root = splitRoot(path || '');
    var values = [root, dirname(path || ''), basename(path || ''), nameWithoutExt(path || ''), extname(path || '')];
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
      setValue(ret + 8, value === null ? 0 : stringToNewUTF8(value), '*');
    },
  });
})();
