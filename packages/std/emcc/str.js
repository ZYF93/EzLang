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
    if (!blobPtr) return null;
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size < 0 || (!dataPtr && size > 0)) return null;
    if (size === 0) return new Uint8Array(0);
    if (dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
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

  var latinExtACasePairs = [
    [0x0100, 0x0101], [0x0102, 0x0103], [0x0104, 0x0105], [0x0106, 0x0107],
    [0x0108, 0x0109], [0x010a, 0x010b], [0x010c, 0x010d], [0x010e, 0x010f],
    [0x0110, 0x0111], [0x0112, 0x0113], [0x0114, 0x0115], [0x0116, 0x0117],
    [0x0118, 0x0119], [0x011a, 0x011b], [0x011c, 0x011d], [0x011e, 0x011f],
    [0x0120, 0x0121], [0x0122, 0x0123], [0x0124, 0x0125], [0x0126, 0x0127],
    [0x0128, 0x0129], [0x012a, 0x012b], [0x012c, 0x012d], [0x012e, 0x012f],
    [0x0132, 0x0133], [0x0134, 0x0135], [0x0136, 0x0137], [0x0139, 0x013a],
    [0x013b, 0x013c], [0x013d, 0x013e], [0x013f, 0x0140], [0x0141, 0x0142],
    [0x0143, 0x0144], [0x0145, 0x0146], [0x0147, 0x0148], [0x014a, 0x014b],
    [0x014c, 0x014d], [0x014e, 0x014f], [0x0150, 0x0151], [0x0152, 0x0153],
    [0x0154, 0x0155], [0x0156, 0x0157], [0x0158, 0x0159], [0x015a, 0x015b],
    [0x015c, 0x015d], [0x015e, 0x015f], [0x0160, 0x0161], [0x0162, 0x0163],
    [0x0164, 0x0165], [0x0166, 0x0167], [0x0168, 0x0169], [0x016a, 0x016b],
    [0x016c, 0x016d], [0x016e, 0x016f], [0x0170, 0x0171], [0x0172, 0x0173],
    [0x0174, 0x0175], [0x0176, 0x0177], [0x0178, 0x00ff], [0x0179, 0x017a],
    [0x017b, 0x017c], [0x017d, 0x017e], [0x1e9e, 0x00df],
  ];

  function unicodeToLower(cp) {
    if (cp >= 0x41 && cp <= 0x5a) return cp + 0x20;
    if ((cp >= 0x00c0 && cp <= 0x00d6) || (cp >= 0x00d8 && cp <= 0x00de)) return cp + 0x20;
    if (cp >= 0x0391 && cp <= 0x03a1) return cp + 0x20;
    if (cp >= 0x03a3 && cp <= 0x03ab) return cp + 0x20;
    if (cp >= 0x0400 && cp <= 0x040f) return cp + 0x50;
    if (cp >= 0x0410 && cp <= 0x042f) return cp + 0x20;
    for (var i = 0; i < latinExtACasePairs.length; i++) {
      if (cp === latinExtACasePairs[i][0]) return latinExtACasePairs[i][1];
    }
    return cp;
  }

  function unicodeToUpper(cp) {
    if (cp >= 0x61 && cp <= 0x7a) return cp - 0x20;
    if ((cp >= 0x00e0 && cp <= 0x00f6) || (cp >= 0x00f8 && cp <= 0x00fe)) return cp - 0x20;
    if (cp === 0x00ff) return 0x0178;
    if (cp >= 0x03b1 && cp <= 0x03c1) return cp - 0x20;
    if (cp === 0x03c2) return 0x03a3;
    if (cp >= 0x03c3 && cp <= 0x03cb) return cp - 0x20;
    if (cp >= 0x0450 && cp <= 0x045f) return cp - 0x50;
    if (cp >= 0x0430 && cp <= 0x044f) return cp - 0x20;
    for (var i = 0; i < latinExtACasePairs.length; i++) {
      if (cp === latinExtACasePairs[i][1]) return latinExtACasePairs[i][0];
    }
    return cp;
  }

  function unicodeCase(value, upper) {
    var out = '';
    var values = Array.from(value || '');
    for (var i = 0; i < values.length; i++) {
      var cp = values[i].codePointAt(0);
      out += String.fromCodePoint(upper ? unicodeToUpper(cp) : unicodeToLower(cp));
    }
    return out;
  }

  function unicodeIsSpace(cp) {
    return cp === 0x0009 || cp === 0x000a || cp === 0x000b || cp === 0x000c || cp === 0x000d
      || cp === 0x0020 || cp === 0x0085 || cp === 0x00a0 || cp === 0x1680
      || (cp >= 0x2000 && cp <= 0x200a) || cp === 0x2028 || cp === 0x2029
      || cp === 0x202f || cp === 0x205f || cp === 0x3000;
  }

  function trimUnicodeSpace(value) {
    var values = Array.from(value || '');
    var start = 0;
    var end = values.length;
    while (start < end && unicodeIsSpace(values[start].codePointAt(0))) start++;
    while (end > start && unicodeIsSpace(values[end - 1].codePointAt(0))) end--;
    return values.slice(start, end).join('');
  }

  function byteLengthPrefix(value, end) {
    return lengthBytesUTF8(value.slice(0, end));
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
      var arr = chars(text(s));
      var begin = Math.max(0, Number(start));
      var finish = Number(end);
      if (finish < begin) finish = begin;
      if (finish > arr.length) finish = arr.length;
      return stringToNewUTF8(arr.slice(begin, finish).join(''));
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
      if (bytes === null || bytes.indexOf(0) >= 0 || !validUtf8Bytes(bytes)) {
        HEAPU8[ret] = 0;
        setValue(ret + 8, 0, '*');
        return;
      }
      HEAPU8[ret] = 1;
      setValue(ret + 8, stringToNewUTF8(UTF8ArrayToString(bytes, 0)), '*');
    },
    strEqual: function (a, b) {
      return text(a) === text(b) ? 1 : 0;
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
      var source = text(s);
      var index = source.indexOf(text(needle));
      return index < 0 ? -1 : byteLengthPrefix(source, index);
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
      return stringToNewUTF8(trimUnicodeSpace(text(s)));
    },
    strReplace: function (s, oldValue, newValue) {
      var oldText = text(oldValue);
      if (oldText === '') return stringToNewUTF8(text(s));
      return stringToNewUTF8(text(s).split(oldText).join(text(newValue)));
    },
    strToLower: function (s) {
      return stringToNewUTF8(unicodeCase(text(s), false));
    },
    strToUpper: function (s) {
      return stringToNewUTF8(unicodeCase(text(s), true));
    },
  });
})();
