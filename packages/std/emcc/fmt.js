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

  function isStrictBase64(text) {
    if (text.length % 4 !== 0) return false;
    var firstPadding = text.indexOf('=');
    if (firstPadding < 0) return /^[A-Za-z0-9+/]*$/.test(text);
    var padding = text.length - firstPadding;
    if (padding < 1 || padding > 2) return false;
    return /^[A-Za-z0-9+/]*={1,2}$/.test(text);
  }

  mergeInto(LibraryManager.library, {
    toString_I32: function (value) {
      return stringToNewUTF8(String(value | 0));
    },
    toString_I64: function (value) {
      return stringToNewUTF8(String(value));
    },
    toString_F32: function (value) {
      return stringToNewUTF8(String(Math.fround(value)));
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
      var ok = /^[-+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][-+]?\d+)?$/.test(text);
      var value = ok ? Number(text) : 0;
      writeOptF64(ret, ok && Number.isFinite(value), value);
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
        var text = UTF8ToString(s || 0);
        if (!isStrictBase64(text)) throw new Error('invalid base64');
        var bytes = atobBytes(text);
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
    msgpackEncode_F64: function (ret, value) {
      var bytes = new Uint8Array(9);
      var view = new DataView(bytes.buffer);
      bytes[0] = 0xcb;
      view.setFloat64(1, value, false);
      writeBlob(ret, bytes);
    },
    msgpackEncode_I1: function (ret, value) {
      writeBlob(ret, new Uint8Array([value ? 0xc3 : 0xc2]));
    },
    msgpackEncode_Str: function (ret, value) {
      var text = UTF8ToString(value || 0);
      var len = lengthBytesUTF8(text);
      var headerLen = len <= 31 ? 1 : len <= 0xff ? 2 : len <= 0xffff ? 3 : 5;
      var bytes = new Uint8Array(headerLen + len);
      if (len <= 31) {
        bytes[0] = 0xa0 | len;
      } else if (len <= 0xff) {
        bytes[0] = 0xd9;
        bytes[1] = len;
      } else if (len <= 0xffff) {
        bytes[0] = 0xda;
        bytes[1] = (len >>> 8) & 0xff;
        bytes[2] = len & 0xff;
      } else {
        bytes[0] = 0xdb;
        bytes[1] = (len >>> 24) & 0xff;
        bytes[2] = (len >>> 16) & 0xff;
        bytes[3] = (len >>> 8) & 0xff;
        bytes[4] = len & 0xff;
      }
      var ptr = stringToNewUTF8(text);
      bytes.set(HEAPU8.slice(ptr, ptr + len), headerLen);
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
    msgpackDecode_F64: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length !== 9 || bytes[0] !== 0xcb) return 0;
      return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat64(1, false);
    },
    msgpackDecode_I1: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      return bytes.length === 1 && bytes[0] === 0xc3 ? 1 : 0;
    },
    msgpackDecode_Str: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length < 1) return stringToNewUTF8('');
      var headerLen = 0;
      var len = 0;
      if ((bytes[0] & 0xe0) === 0xa0) {
        headerLen = 1;
        len = bytes[0] & 0x1f;
      } else if (bytes[0] === 0xd9 && bytes.length >= 2) {
        headerLen = 2;
        len = bytes[1];
      } else if (bytes[0] === 0xda && bytes.length >= 3) {
        headerLen = 3;
        len = (bytes[1] << 8) | bytes[2];
      } else if (bytes[0] === 0xdb && bytes.length >= 5) {
        headerLen = 5;
        len = ((bytes[1] << 24) >>> 0) | (bytes[2] << 16) | (bytes[3] << 8) | bytes[4];
      } else {
        return stringToNewUTF8('');
      }
      if (headerLen + len > bytes.length) return stringToNewUTF8('');
      return stringToNewUTF8(UTF8ArrayToString(bytes.slice(headerLen, headerLen + len), 0));
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
