// EzLang std/str Emscripten JS 封装层
(function () {
  function ptrSize() {
    return typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
  }

  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function utf8Bytes(value) {
    var len = lengthBytesUTF8(value);
    var ptr = _malloc(len + 1);
    stringToUTF8(value, ptr, len + 1);
    return HEAPU8.slice(ptr, ptr + len);
  }

  function writeBlob(ret, bytes) {
    var dataPtr = 0;
    if (bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ret, dataPtr, '*');
    setValue(ret + 8, bytes.length, 'i64');
  }

  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
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

  function writeStrList(ret, items) {
    var size = ptrSize();
    var pageCount = items.length === 0 ? 0 : Math.ceil(items.length / 8);
    var pagesPtr = pageCount === 0 ? 0 : _malloc(pageCount * size);
    for (var page = 0; page < pageCount; page++) {
      var pagePtr = _malloc(8 * size);
      setValue(pagesPtr + page * size, pagePtr, '*');
      for (var offset = 0; offset < 8; offset++) {
        var idx = page * 8 + offset;
        setValue(pagePtr + offset * size, idx < items.length ? stringToNewUTF8(items[idx]) : 0, '*');
      }
    }
    setValue(ret, pagesPtr, '*');
    setValue(ret + 8, items.length, 'i64');
    setValue(ret + 16, pageCount * 8, 'i64');
    setValue(ret + 24, pageCount, 'i64');
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

  function chars(value) {
    return Array.from(value || '');
  }

  mergeInto(LibraryManager.library, {
    strByteLen: function (s) {
      return lengthBytesUTF8(text(s));
    },
    strCharLen: function (s) {
      return chars(text(s)).length;
    },
    strIsEmpty: function (s) {
      return text(s).length === 0 ? 1 : 0;
    },
    strIsValidUtf8: function (s) {
      return validUtf8Bytes(utf8Bytes(text(s))) ? 1 : 0;
    },
    strSliceBytes: function (s, start, end) {
      var bytes = utf8Bytes(text(s));
      var begin = Math.max(0, Number(start));
      var finish = Math.max(begin, Math.min(bytes.length, Number(end)));
      return stringToNewUTF8(UTF8ArrayToString(bytes.slice(begin, finish), 0));
    },
    strSliceChars: function (s, start, end) {
      return stringToNewUTF8(chars(text(s)).slice(Number(start), Number(end)).join(''));
    },
    strCharAt: function (ret, s, index) {
      var arr = chars(text(s));
      var idx = Number(index);
      var ok = idx >= 0 && idx < arr.length;
      HEAPU8[ret] = ok ? 1 : 0;
      setValue(ret + 8, ok ? stringToNewUTF8(arr[idx]) : 0, '*');
    },
    strToBytes: function (ret, s) {
      writeBlob(ret, utf8Bytes(text(s)));
    },
    strFromBytes: function (ret, data) {
      var bytes = blobBytes(data);
      if (!validUtf8Bytes(bytes)) {
        HEAPU8[ret] = 0;
        setValue(ret + 8, 0, '*');
        return;
      }
      HEAPU8[ret] = 1;
      setValue(ret + 8, stringToNewUTF8(UTF8ArrayToString(bytes, 0)), '*');
    },
    strContains: function (s, needle) {
      return text(s).indexOf(text(needle)) >= 0 ? 1 : 0;
    },
    strStartsWith: function (s, prefix) {
      return text(s).indexOf(text(prefix)) === 0 ? 1 : 0;
    },
    strEndsWith: function (s, suffix) {
      var a = text(s);
      var b = text(suffix);
      return a.slice(a.length - b.length) === b ? 1 : 0;
    },
    strIndexOf: function (s, needle) {
      return text(s).indexOf(text(needle));
    },
    strSplit: function (ret, s, sep) {
      var separator = text(sep);
      writeStrList(ret, separator === '' ? chars(text(s)) : text(s).split(separator));
    },
    strJoin: function (parts, sep) {
      var length = listLength(parts);
      var values = [];
      for (var i = 0; i < length; i++) values.push(listGet(parts, i));
      return stringToNewUTF8(values.join(text(sep)));
    },
    strTrim: function (s) {
      return stringToNewUTF8(text(s).trim());
    },
    strReplace: function (s, oldValue, newValue) {
      return stringToNewUTF8(text(s).split(text(oldValue)).join(text(newValue)));
    },
    strToLower: function (s) {
      return stringToNewUTF8(text(s).toLowerCase());
    },
    strToUpper: function (s) {
      return stringToNewUTF8(text(s).toUpperCase());
    },
  });
})();
