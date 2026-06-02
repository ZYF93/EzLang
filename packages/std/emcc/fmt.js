// EzLang std/fmt Emscripten JS 封装层
(function () {
  function writeOptI32(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    HEAP32[(ret + 4) >> 2] = value | 0;
  }

  function writeOptI64(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    HEAP64[(ret + 8) >> 3] = BigInt(value || 0);
  }

  function writeOptF64(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    HEAPF64[(ret + 8) >> 3] = value || 0;
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

  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function listGet(listPtr, index) {
    if (!listPtr) return '';
    var ptrSize = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
    var pages = getValue(listPtr, '*');
    var length = Number(getValue(listPtr + 8, 'i64'));
    if (!pages || index < 0 || index >= length) return '';
    var pagePtr = getValue(pages + Math.floor(index / 8) * ptrSize, '*');
    if (!pagePtr) return '';
    var itemPtr = getValue(pagePtr + (index % 8) * ptrSize, '*');
    return itemPtr ? UTF8ToString(itemPtr) : '';
  }

  function btoaBytes(bytes) {
    var text = '';
    for (var i = 0; i < bytes.length; i++) text += String.fromCharCode(bytes[i]);
    return btoa(text);
  }

  function atobBytes(text) {
    var raw = atob(text);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes;
  }

  mergeInto(LibraryManager.library, {
    toString_I32: function (value) {
      return stringToNewUTF8(String(value | 0));
    },
    toString_I64: function (value) {
      return stringToNewUTF8(String(value));
    },
    toString_F64: function (value) {
      return stringToNewUTF8(String(value));
    },
    toString_Str: function (value) {
      return stringToNewUTF8(UTF8ToString(value || 0));
    },
    parseInt: function (ret, s) {
      var text = UTF8ToString(s || 0).trim();
      var ok = /^[-+]?\d+$/.test(text);
      var value = ok ? Number.parseInt(text, 10) : 0;
      writeOptI32(ret, ok && value >= -2147483648 && value <= 2147483647, value);
    },
    parseI64: function (ret, s) {
      var text = UTF8ToString(s || 0).trim();
      var ok = /^[-+]?\d+$/.test(text);
      writeOptI64(ret, ok, ok ? BigInt(text) : 0);
    },
    parseF64: function (ret, s) {
      var text = UTF8ToString(s || 0).trim();
      var value = Number.parseFloat(text);
      writeOptF64(ret, Number.isFinite(value) && String(value) !== 'NaN', value);
    },
    format: function (templatePtr, argsPtr) {
      var text = UTF8ToString(templatePtr || 0);
      var index = 0;
      var out = '';
      for (var i = 0; i < text.length; i++) {
        var ch = text.charAt(i);
        var next = i + 1 < text.length ? text.charAt(i + 1) : '';
        if (ch === '{' && next === '}') {
          out += listGet(argsPtr, index++);
          i++;
        } else if (ch === '{' && next === '{') {
          out += '{';
          i++;
        } else if (ch === '}' && next === '}') {
          out += '}';
          i++;
        } else if (ch === '%' && next) {
          if (next === '%') {
            out += '%';
          } else if (next === 's' || next === 'd' || next === 'f') {
            out += listGet(argsPtr, index++);
          } else {
            out += '%' + next;
          }
          i++;
        } else {
          out += ch;
        }
      }
      return stringToNewUTF8(out);
    },
    b64Encode: function (dataPtr) {
      return stringToNewUTF8(btoaBytes(blobBytes(dataPtr)));
    },
    b64Decode: function (ret, s) {
      try {
        var bytes = atobBytes(UTF8ToString(s || 0));
        HEAPU8[ret] = 1;
        writeBlob(ret + 8, bytes);
      } catch (e) {
        HEAPU8[ret] = 0;
        writeBlob(ret + 8, new Uint8Array(0));
      }
    },
    jsonStringify_I32: function (value) {
      return stringToNewUTF8(JSON.stringify(value | 0));
    },
    jsonStringify_I64: function (value) {
      return stringToNewUTF8(String(value));
    },
    jsonStringify_F64: function (value) {
      return stringToNewUTF8(JSON.stringify(value));
    },
    jsonStringify_I1: function (value) {
      return stringToNewUTF8(value ? 'true' : 'false');
    },
    jsonStringify_Str: function (value) {
      return stringToNewUTF8(JSON.stringify(UTF8ToString(value || 0)));
    },
    jsonParse_I32: function (s) {
      var value = Number.parseInt(JSON.parse(UTF8ToString(s || 0)), 10);
      return Number.isFinite(value) ? value | 0 : 0;
    },
    jsonParse_I64: function (s) {
      try { return BigInt(JSON.parse(UTF8ToString(s || 0))); } catch (e) { return BigInt(0); }
    },
    jsonParse_F64: function (s) {
      var value = Number(JSON.parse(UTF8ToString(s || 0)));
      return Number.isFinite(value) ? value : 0;
    },
    jsonParse_I1: function (s) {
      return JSON.parse(UTF8ToString(s || 0)) ? 1 : 0;
    },
    jsonParse_Str: function (s) {
      try { return stringToNewUTF8(String(JSON.parse(UTF8ToString(s || 0)))); } catch (e) { return stringToNewUTF8(''); }
    },
    msgpackEncode_I32: function (ret, value) {
      var bytes = new Uint8Array(5);
      bytes[0] = 0xd2;
      bytes[1] = (value >>> 24) & 0xff;
      bytes[2] = (value >>> 16) & 0xff;
      bytes[3] = (value >>> 8) & 0xff;
      bytes[4] = value & 0xff;
      writeBlob(ret, bytes);
    },
    msgpackEncode_I64: function (ret, value) {
      var bytes = new Uint8Array(9);
      var n = BigInt(value);
      bytes[0] = 0xd3;
      for (var i = 0; i < 8; i++) bytes[i + 1] = Number((n >> BigInt(56 - i * 8)) & BigInt(0xff));
      writeBlob(ret, bytes);
    },
    msgpackDecode_I32: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length !== 5 || bytes[0] !== 0xd2) return 0;
      return (bytes[1] << 24) | (bytes[2] << 16) | (bytes[3] << 8) | bytes[4];
    },
    msgpackDecode_I64: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length !== 9 || bytes[0] !== 0xd3) return BigInt(0);
      var value = BigInt(0);
      for (var i = 1; i < 9; i++) value = (value << BigInt(8)) | BigInt(bytes[i]);
      return value;
    },
    urlEncode: function (s) {
      return stringToNewUTF8(encodeURIComponent(UTF8ToString(s || 0)));
    },
    urlDecode: function (ret, s) {
      try {
        HEAPU8[ret] = 1;
        setValue(ret + 8, stringToNewUTF8(decodeURIComponent(UTF8ToString(s || 0))), '*');
      } catch (e) {
        HEAPU8[ret] = 0;
        setValue(ret + 8, 0, '*');
      }
    },
  });
})();
