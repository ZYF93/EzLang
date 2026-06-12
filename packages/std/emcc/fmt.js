// EzLang std/fmt Emscripten JS 封装层
(function () {
  var I32_MIN = -2147483648n;
  var I32_MAX = 2147483647n;
  var I8_MIN = -128n;
  var I8_MAX = 127n;
  var U8_MAX = 255n;
  var U32_MAX = 4294967295n;
  var I64_MIN = -(1n << 63n);
  var I64_MAX = (1n << 63n) - 1n;
  var U64_MAX = (1n << 64n) - 1n;

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
    if (!Number.isFinite(size) || size <= 0 || Math.floor(size) !== size || !dataPtr) return new Uint8Array(0);
    if (dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function hasNulString(value) {
    return String(value || '').indexOf('\0') >= 0;
  }

  function hasNulBytes(bytes) {
    return bytes.indexOf(0) >= 0;
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

  function readU16(bytes, offset) {
    return (bytes[offset] << 8) | bytes[offset + 1];
  }

  function readU32(bytes, offset) {
    return ((bytes[offset] << 24) >>> 0) | (bytes[offset + 1] << 16) | (bytes[offset + 2] << 8) | bytes[offset + 3];
  }

  function readU64(bytes, offset) {
    var value = 0n;
    for (var i = 0; i < 8; i++) value = (value << 8n) | BigInt(bytes[offset + i]);
    return value;
  }

  function decodeInteger(bytes) {
    if (!bytes || bytes.length < 1) return null;
    var tag = bytes[0];
    if (tag <= 0x7f) return BigInt(tag);
    if (tag >= 0xe0) return BigInt(tag - 0x100);
    if (tag === 0xcc && bytes.length === 2) return BigInt(bytes[1]);
    if (tag === 0xcd && bytes.length === 3) return BigInt(readU16(bytes, 1));
    if (tag === 0xce && bytes.length === 5) return BigInt(readU32(bytes, 1));
    if (tag === 0xcf && bytes.length === 9) {
      var u64 = readU64(bytes, 1);
      return u64 <= 0x7fffffffffffffffn ? u64 : null;
    }
    if (tag === 0xd0 && bytes.length === 2) return BigInt((bytes[1] << 24) >> 24);
    if (tag === 0xd1 && bytes.length === 3) return BigInt((readU16(bytes, 1) << 16) >> 16);
    if (tag === 0xd2 && bytes.length === 5) return BigInt(readU32(bytes, 1) | 0);
    if (tag === 0xd3 && bytes.length === 9) return BigInt.asIntN(64, readU64(bytes, 1));
    return null;
  }

  function decodeUnsignedInteger(bytes) {
    if (!bytes || bytes.length < 1) return null;
    var tag = bytes[0];
    if (tag <= 0x7f) return BigInt(tag);
    if (tag === 0xcc && bytes.length === 2) return BigInt(bytes[1]);
    if (tag === 0xcd && bytes.length === 3) return BigInt(readU16(bytes, 1));
    if (tag === 0xce && bytes.length === 5) return BigInt(readU32(bytes, 1));
    if (tag === 0xcf && bytes.length === 9) return readU64(bytes, 1);
    return null;
  }

  function msgpackStrHeaderLen(len) {
    return len <= 31 ? 1 : len <= 0xff ? 2 : len <= 0xffff ? 3 : 5;
  }

  function writeMsgpackStrHeader(bytes, pos, len) {
    if (len <= 31) {
      bytes[pos++] = 0xa0 | len;
    } else if (len <= 0xff) {
      bytes[pos++] = 0xd9;
      bytes[pos++] = len;
    } else if (len <= 0xffff) {
      bytes[pos++] = 0xda;
      bytes[pos++] = (len >>> 8) & 0xff;
      bytes[pos++] = len & 0xff;
    } else {
      bytes[pos++] = 0xdb;
      bytes[pos++] = (len >>> 24) & 0xff;
      bytes[pos++] = (len >>> 16) & 0xff;
      bytes[pos++] = (len >>> 8) & 0xff;
      bytes[pos++] = len & 0xff;
    }
    return pos;
  }

  function msgpackStrSpanAt(bytes, index) {
    if (!bytes || index >= bytes.length) return null;
    var tag = bytes[index];
    var headerLen = 0;
    var len = 0;
    if ((tag & 0xe0) === 0xa0) {
      headerLen = 1;
      len = tag & 0x1f;
    } else if (tag === 0xd9 && index + 2 <= bytes.length) {
      headerLen = 2;
      len = bytes[index + 1];
    } else if (tag === 0xda && index + 3 <= bytes.length) {
      headerLen = 3;
      len = readU16(bytes, index + 1);
    } else if (tag === 0xdb && index + 5 <= bytes.length) {
      headerLen = 5;
      len = readU32(bytes, index + 1);
    } else {
      return null;
    }
    var start = index + headerLen;
    if (start + len > bytes.length) return null;
    return { start: start, len: len, next: start + len };
  }

  function skipMsgpackValue(bytes, index, depth) {
    if (!bytes || index >= bytes.length || depth > 64) return -1;
    var tag = bytes[index];
    if (tag <= 0x7f || tag >= 0xe0 || (tag >= 0xc0 && tag <= 0xc3)) return index + 1;
    if ((tag & 0xe0) === 0xa0) {
      var str = msgpackStrSpanAt(bytes, index);
      return str ? str.next : -1;
    }
    if ((tag & 0xf0) === 0x90) {
      var arrCount = tag & 0x0f;
      index++;
      for (var ai = 0; ai < arrCount; ai++) {
        index = skipMsgpackValue(bytes, index, depth + 1);
        if (index < 0) return -1;
      }
      return index;
    }
    if ((tag & 0xf0) === 0x80) {
      var fixCount = tag & 0x0f;
      index++;
      for (var fi = 0; fi < fixCount; fi++) {
        index = skipMsgpackValue(bytes, index, depth + 1);
        if (index < 0) return -1;
        index = skipMsgpackValue(bytes, index, depth + 1);
        if (index < 0) return -1;
      }
      return index;
    }

    var fixed = 0;
    if (tag === 0xcc || tag === 0xd0) fixed = 2;
    else if (tag === 0xcd || tag === 0xd1 || tag === 0xd4) fixed = tag === 0xd4 ? 3 : 3;
    else if (tag === 0xce || tag === 0xd2 || tag === 0xca || tag === 0xd5) fixed = tag === 0xd5 ? 4 : 5;
    else if (tag === 0xcf || tag === 0xd3 || tag === 0xcb || tag === 0xd6) fixed = tag === 0xd6 ? 6 : 9;
    else if (tag === 0xd7) fixed = 10;
    else if (tag === 0xd8) fixed = 18;
    if (fixed > 0) return index + fixed <= bytes.length ? index + fixed : -1;

    if (tag === 0xc4 || tag === 0xc7 || tag === 0xd9) {
      if (index + 2 > bytes.length) return -1;
      var len8 = bytes[index + 1];
      var extra8 = tag === 0xc7 ? 1 : 0;
      return index + 2 + extra8 + len8 <= bytes.length ? index + 2 + extra8 + len8 : -1;
    }
    if (tag === 0xc5 || tag === 0xc8 || tag === 0xda) {
      if (index + 3 > bytes.length) return -1;
      var len16 = readU16(bytes, index + 1);
      var extra16 = tag === 0xc8 ? 1 : 0;
      return index + 3 + extra16 + len16 <= bytes.length ? index + 3 + extra16 + len16 : -1;
    }
    if (tag === 0xc6 || tag === 0xc9 || tag === 0xdb) {
      if (index + 5 > bytes.length) return -1;
      var len32 = readU32(bytes, index + 1);
      var extra32 = tag === 0xc9 ? 1 : 0;
      return index + 5 + extra32 + len32 <= bytes.length ? index + 5 + extra32 + len32 : -1;
    }
    if (tag === 0xdc || tag === 0xdd) {
      var header = tag === 0xdc ? 3 : 5;
      if (index + header > bytes.length) return -1;
      var count = tag === 0xdc ? readU16(bytes, index + 1) : readU32(bytes, index + 1);
      index += header;
      for (var i = 0; i < count; i++) {
        index = skipMsgpackValue(bytes, index, depth + 1);
        if (index < 0) return -1;
      }
      return index;
    }
    if (tag === 0xde || tag === 0xdf) {
      var mapHeader = tag === 0xde ? 3 : 5;
      if (index + mapHeader > bytes.length) return -1;
      var mapCount = tag === 0xde ? readU16(bytes, index + 1) : readU32(bytes, index + 1);
      index += mapHeader;
      for (var m = 0; m < mapCount; m++) {
        index = skipMsgpackValue(bytes, index, depth + 1);
        if (index < 0) return -1;
        index = skipMsgpackValue(bytes, index, depth + 1);
        if (index < 0) return -1;
      }
      return index;
    }
    return -1;
  }

  function msgpackMapHeader(bytes) {
    if (!bytes || bytes.length < 1) return null;
    var tag = bytes[0];
    if ((tag & 0xf0) === 0x80) return { index: 1, count: tag & 0x0f };
    if (tag === 0xde && bytes.length >= 3) return { index: 3, count: readU16(bytes, 1) };
    if (tag === 0xdf && bytes.length >= 5) return { index: 5, count: readU32(bytes, 1) };
    return null;
  }

  function msgpackValidateTopMap(bytes) {
    var header = msgpackMapHeader(bytes);
    if (!header) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      var keySpan = msgpackStrSpanAt(bytes, index);
      if (!keySpan) return null;
      var keyBytes = bytes.slice(keySpan.start, keySpan.start + keySpan.len);
      if (hasNulBytes(keyBytes) || !validUtf8Bytes(keyBytes)) return null;
      index = keySpan.next;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
    }
    return index === bytes.length ? header.count : null;
  }

  function msgpackValidateTopMapAny(bytes) {
    var header = msgpackMapHeader(bytes);
    if (!header) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
    }
    return index === bytes.length ? header.count : null;
  }

  function msgpackMapField(bytes, key) {
    var header = msgpackMapHeader(bytes);
    if (!header) return null;
    var index = header.index;
    var found = null;
    for (var i = 0; i < header.count; i++) {
      var keySpan = msgpackStrSpanAt(bytes, index);
      if (!keySpan) return null;
      var keyBytes = bytes.slice(keySpan.start, keySpan.start + keySpan.len);
      if (hasNulBytes(keyBytes) || !validUtf8Bytes(keyBytes)) return null;
      var decodedKey = new TextDecoder('utf-8', { fatal: true }).decode(keyBytes);
      index = keySpan.next;
      var valueStart = index;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      if (decodedKey === key) found = bytes.slice(valueStart, index);
    }
    return index === bytes.length ? found : null;
  }

  function msgpackMapKeyAt(bytes, wanted) {
    var header = msgpackMapHeader(bytes);
    if (!header || wanted < 0 || wanted >= header.count) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      var keySpan = msgpackStrSpanAt(bytes, index);
      if (!keySpan) return null;
      var keyBytes = bytes.slice(keySpan.start, keySpan.start + keySpan.len);
      if (hasNulBytes(keyBytes) || !validUtf8Bytes(keyBytes)) return null;
      var decodedKey = new TextDecoder('utf-8', { fatal: true }).decode(keyBytes);
      index = keySpan.next;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      if (i === wanted) return decodedKey;
    }
    return null;
  }

  function msgpackMapValueAt(bytes, wanted) {
    var header = msgpackMapHeader(bytes);
    if (!header || wanted < 0 || wanted >= header.count) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      var valueStart = index;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      if (i === wanted) return bytes.slice(valueStart, index);
    }
    return null;
  }

  function msgpackMapKeyBlobAt(bytes, wanted) {
    var header = msgpackMapHeader(bytes);
    if (!header || wanted < 0 || wanted >= header.count) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      var keyStart = index;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      var keyEnd = index;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      if (i === wanted) return bytes.slice(keyStart, keyEnd);
    }
    return null;
  }

  function msgpackArrayHeader(bytes) {
    if (!bytes || bytes.length < 1) return null;
    var tag = bytes[0];
    if ((tag & 0xf0) === 0x90) return { index: 1, count: tag & 0x0f };
    if (tag === 0xdc && bytes.length >= 3) return { index: 3, count: readU16(bytes, 1) };
    if (tag === 0xdd && bytes.length >= 5) return { index: 5, count: readU32(bytes, 1) };
    return null;
  }

  function msgpackValidateTopArray(bytes) {
    var header = msgpackArrayHeader(bytes);
    if (!header) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
    }
    return index === bytes.length ? header.count : null;
  }

  function msgpackArrayItem(bytes, wanted) {
    var header = msgpackArrayHeader(bytes);
    if (!header || wanted < 0 || wanted >= header.count) return null;
    var index = header.index;
    for (var i = 0; i < header.count; i++) {
      var valueStart = index;
      index = skipMsgpackValue(bytes, index, 0);
      if (index < 0) return null;
      if (i === wanted) return bytes.slice(valueStart, index);
    }
    return null;
  }

  function trimJson(text) {
    return String(text || '').trim();
  }

  function jsonNumberSyntax(text) {
    return /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(text);
  }

  function parseUnicodeIsSpace(cp) {
    return cp === 0x0009 || cp === 0x000a || cp === 0x000b || cp === 0x000c || cp === 0x000d
      || cp === 0x0020 || cp === 0x0085 || cp === 0x00a0 || cp === 0x1680
      || (cp >= 0x2000 && cp <= 0x200a) || cp === 0x2028 || cp === 0x2029
      || cp === 0x202f || cp === 0x205f || cp === 0x3000;
  }

  function trimParseSpace(text) {
    var values = Array.from(String(text || ''));
    var start = 0;
    var end = values.length;
    while (start < end && parseUnicodeIsSpace(values[start].codePointAt(0))) start++;
    while (end > start && parseUnicodeIsSpace(values[end - 1].codePointAt(0))) end--;
    return values.slice(start, end).join('');
  }

  function parseDecimalInteger(text) {
    text = trimParseSpace(text);
    if (!/^[-+]?\d+$/.test(text)) return null;
    try {
      return BigInt(text);
    } catch (e) {
      return null;
    }
  }

  function parseJsonInteger(text) {
    text = trimJson(text);
    if (!jsonNumberSyntax(text)) return null;
    var i = 0;
    var negative = false;
    if (text.charAt(i) === '-') {
      negative = true;
      i++;
    }
    var digits = '';
    while (i < text.length && /\d/.test(text.charAt(i))) digits += text.charAt(i++);
    var fracLen = 0;
    if (text.charAt(i) === '.') {
      i++;
      while (i < text.length && /\d/.test(text.charAt(i))) {
        digits += text.charAt(i++);
        fracLen++;
      }
    }
    var exponent = 0;
    if (text.charAt(i) === 'e' || text.charAt(i) === 'E') {
      i++;
      var expNegative = false;
      if (text.charAt(i) === '+' || text.charAt(i) === '-') {
        expNegative = text.charAt(i) === '-';
        i++;
      }
      while (i < text.length && /\d/.test(text.charAt(i))) {
        if (exponent < 1000000) exponent = exponent * 10 + (text.charCodeAt(i) - 48);
        i++;
      }
      if (expNegative) exponent = -exponent;
    }
    var first = 0;
    while (first < digits.length && digits.charAt(first) === '0') first++;
    if (first === digits.length) return 0n;
    var scale = exponent - fracLen;
    if (scale < 0) {
      var trim = -scale;
      if (trim >= digits.length - first) return null;
      for (var n = 0; n < trim; n++) {
        if (digits.charAt(digits.length - 1 - n) !== '0') return null;
      }
      digits = digits.slice(0, digits.length - trim);
      scale = 0;
    }
    var body = digits.slice(first);
    if (scale > 0) body += '0'.repeat(scale);
    var value = BigInt(body);
    return negative ? -value : value;
  }

  function parseJsonUnsignedInteger(text) {
    var trimmed = trimJson(text);
    if (trimmed.charAt(0) === '-') return null;
    return parseJsonInteger(trimmed);
  }

  function parseJsonValue(text) {
    try {
      return { ok: true, value: JSON.parse(trimJson(text)) };
    } catch (e) {
      return { ok: false, value: null };
    }
  }

  function jsonHex4(text, offset) {
    var value = 0;
    for (var i = 0; i < 4; i++) {
      var code = text.charCodeAt(offset + i);
      var digit = code >= 48 && code <= 57 ? code - 48
        : code >= 65 && code <= 70 ? code - 55
        : code >= 97 && code <= 102 ? code - 87
        : -1;
      if (digit < 0) return -1;
      value = (value << 4) | digit;
    }
    return value;
  }

  function jsonStringSyntax(text) {
    text = trimJson(text);
    if (text.length < 2 || text.charAt(0) !== '"' || text.charAt(text.length - 1) !== '"') return false;
    for (var i = 1; i + 1 < text.length; i++) {
      if (text.charCodeAt(i) < 0x20) return false;
      if (text.charAt(i) !== '\\') continue;
      i++;
      if (i >= text.length - 1) return false;
      var esc = text.charAt(i);
      if (esc === '"' || esc === '\\' || esc === '/' || esc === 'b' || esc === 'f' || esc === 'n' || esc === 'r' || esc === 't') continue;
      if (esc !== 'u' || i + 4 >= text.length) return false;
      var cp = jsonHex4(text, i + 1);
      if (cp < 0) return false;
      i += 4;
      if (cp >= 0xd800 && cp <= 0xdbff) {
        if (i + 6 >= text.length || text.charAt(i + 1) !== '\\' || text.charAt(i + 2) !== 'u') return false;
        var low = jsonHex4(text, i + 3);
        if (low < 0xdc00 || low > 0xdfff) return false;
        i += 6;
      } else if (cp >= 0xdc00 && cp <= 0xdfff) {
        return false;
      }
    }
    return true;
  }

  function scanJsonWhitespace(text, state) {
    while (state.index < text.length && /[\t\n\r ]/.test(text.charAt(state.index))) state.index++;
    return true;
  }

  function scanJsonString(text, state) {
    if (text.charAt(state.index) !== '"') return false;
    state.index++;
    while (state.index < text.length) {
      var code = text.charCodeAt(state.index);
      if (code < 0x20) return false;
      var ch = text.charAt(state.index);
      if (ch === '"') {
        state.index++;
        return true;
      }
      if (ch !== '\\') {
        state.index++;
        continue;
      }
      state.index++;
      if (state.index >= text.length) return false;
      var esc = text.charAt(state.index);
      if (esc === '"' || esc === '\\' || esc === '/' || esc === 'b' || esc === 'f' || esc === 'n' || esc === 'r' || esc === 't') {
        state.index++;
        continue;
      }
      if (esc !== 'u' || state.index + 4 >= text.length) return false;
      var cp = jsonHex4(text, state.index + 1);
      if (cp < 0) return false;
      state.index += 5;
      if (cp >= 0xd800 && cp <= 0xdbff) {
        if (state.index + 5 >= text.length || text.charAt(state.index) !== '\\' || text.charAt(state.index + 1) !== 'u') return false;
        var low = jsonHex4(text, state.index + 2);
        if (low < 0xdc00 || low > 0xdfff) return false;
        state.index += 6;
      } else if (cp >= 0xdc00 && cp <= 0xdfff) {
        return false;
      }
    }
    return false;
  }

  function scanJsonLiteral(text, state, literal) {
    if (text.slice(state.index, state.index + literal.length) !== literal) return false;
    state.index += literal.length;
    return true;
  }

  function scanJsonNumber(text, state) {
    var rest = text.slice(state.index);
    var match = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(rest);
    if (!match) return false;
    state.index += match[0].length;
    return true;
  }

  function scanJsonArray(text, state) {
    if (text.charAt(state.index) !== '[') return false;
    state.index++;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === ']') {
      state.index++;
      return true;
    }
    while (state.index < text.length) {
      if (!scanJsonValue(text, state)) return false;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === ']') {
        state.index++;
        return true;
      }
      return false;
    }
    return false;
  }

  function scanJsonObject(text, state) {
    if (text.charAt(state.index) !== '{') return false;
    state.index++;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === '}') {
      state.index++;
      return true;
    }
    while (state.index < text.length) {
      if (!scanJsonString(text, state)) return false;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) !== ':') return false;
      state.index++;
      if (!scanJsonValue(text, state)) return false;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === '}') {
        state.index++;
        return true;
      }
      return false;
    }
    return false;
  }

  function scanJsonValue(text, state) {
    scanJsonWhitespace(text, state);
    var ch = text.charAt(state.index);
    if (ch === '"') return scanJsonString(text, state);
    if (ch === '{') return scanJsonObject(text, state);
    if (ch === '[') return scanJsonArray(text, state);
    if (ch === 't') return scanJsonLiteral(text, state, 'true');
    if (ch === 'f') return scanJsonLiteral(text, state, 'false');
    if (ch === 'n') return scanJsonLiteral(text, state, 'null');
    if (ch === '-' || /\d/.test(ch)) return scanJsonNumber(text, state);
    return false;
  }

  function validJsonObjectSyntax(text) {
    text = trimJson(text);
    var state = { index: 0 };
    return text.charAt(0) === '{' && scanJsonObject(text, state) && (scanJsonWhitespace(text, state), state.index === text.length);
  }

  function validJsonArraySyntax(text) {
    text = trimJson(text);
    var state = { index: 0 };
    return text.charAt(0) === '[' && scanJsonArray(text, state) && (scanJsonWhitespace(text, state), state.index === text.length);
  }

  function jsonArrayLength(text) {
    text = trimJson(text);
    if (text.charAt(0) !== '[') return -1;
    var state = { index: 1 };
    var count = 0;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === ']') {
      state.index++;
      scanJsonWhitespace(text, state);
      return state.index === text.length ? 0 : -1;
    }
    while (state.index < text.length) {
      if (!scanJsonValue(text, state)) return -1;
      count++;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === ']') {
        state.index++;
        scanJsonWhitespace(text, state);
        return state.index === text.length ? count : -1;
      }
      return -1;
    }
    return -1;
  }

  function jsonArrayItem(text, wanted) {
    text = trimJson(text);
    if (wanted < 0 || text.charAt(0) !== '[') return null;
    var state = { index: 1 };
    var count = 0;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === ']') return null;
    while (state.index < text.length) {
      var valueStart = state.index;
      if (!scanJsonValue(text, state)) return null;
      var valueText = text.slice(valueStart, state.index);
      if (count === wanted) return valueText;
      count++;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === ']') return null;
      return null;
    }
    return null;
  }

  function jsonObjectField(text, key) {
    text = trimJson(text);
    if (text.charAt(0) !== '{') return null;
    var state = { index: 1 };
    var found = null;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === '}') return null;
    while (state.index < text.length) {
      var keyStart = state.index;
      if (!scanJsonString(text, state)) return null;
      var keyText = text.slice(keyStart, state.index);
      var decodedKey = '';
      try { decodedKey = JSON.parse(keyText); } catch (e) { return null; }
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) !== ':') return null;
      state.index++;
      scanJsonWhitespace(text, state);
      var valueStart = state.index;
      if (!scanJsonValue(text, state)) return null;
      var valueText = text.slice(valueStart, state.index);
      if (decodedKey === key) found = valueText;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === '}') {
        state.index++;
        scanJsonWhitespace(text, state);
        return state.index === text.length ? found : null;
      }
      return null;
    }
    return null;
  }

  function jsonObjectKeyAt(text, wanted) {
    text = trimJson(text);
    if (wanted < 0 || text.charAt(0) !== '{') return null;
    var state = { index: 1 };
    var count = 0;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === '}') return null;
    while (state.index < text.length) {
      var keyStart = state.index;
      if (!scanJsonString(text, state)) return null;
      var keyText = text.slice(keyStart, state.index);
      var decodedKey = '';
      try { decodedKey = JSON.parse(keyText); } catch (e) { return null; }
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) !== ':') return null;
      state.index++;
      scanJsonWhitespace(text, state);
      if (!scanJsonValue(text, state)) return null;
      if (count === wanted) return decodedKey;
      count++;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === '}') return null;
      return null;
    }
    return null;
  }

  function jsonObjectValueAt(text, wanted) {
    text = trimJson(text);
    if (wanted < 0 || text.charAt(0) !== '{') return null;
    var state = { index: 1 };
    var count = 0;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === '}') return null;
    while (state.index < text.length) {
      if (!scanJsonString(text, state)) return null;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) !== ':') return null;
      state.index++;
      scanJsonWhitespace(text, state);
      var valueStart = state.index;
      if (!scanJsonValue(text, state)) return null;
      var valueText = text.slice(valueStart, state.index);
      if (count === wanted) return valueText;
      count++;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === '}') return null;
      return null;
    }
    return null;
  }

  function jsonObjectFieldCount(text) {
    text = trimJson(text);
    if (text.charAt(0) !== '{') return -1;
    var state = { index: 1 };
    var count = 0;
    scanJsonWhitespace(text, state);
    if (text.charAt(state.index) === '}') {
      state.index++;
      scanJsonWhitespace(text, state);
      return state.index === text.length ? 0 : -1;
    }
    while (state.index < text.length) {
      if (!scanJsonString(text, state)) return -1;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) !== ':') return -1;
      state.index++;
      if (!scanJsonValue(text, state)) return -1;
      count++;
      scanJsonWhitespace(text, state);
      if (text.charAt(state.index) === ',') {
        state.index++;
        scanJsonWhitespace(text, state);
        continue;
      }
      if (text.charAt(state.index) === '}') {
        state.index++;
        scanJsonWhitespace(text, state);
        return state.index === text.length ? count : -1;
      }
      return -1;
    }
    return -1;
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

  mergeInto(LibraryManager.library, {
    toString_I32: function (value) {
      return stringToNewUTF8(String(value | 0));
    },
    toString_I8: function (value) {
      return stringToNewUTF8(String((value << 24) >> 24));
    },
    toString_I64: function (value) {
      return stringToNewUTF8(String(value));
    },
    toString_U8: function (value) {
      return stringToNewUTF8(String(value & 0xff));
    },
    toString_U32: function (value) {
      return stringToNewUTF8(String(value >>> 0));
    },
    toString_U64: function (value) {
      return stringToNewUTF8(String(BigInt.asUintN(64, BigInt(value))));
    },
    toString_F32: function (value) {
      return stringToNewUTF8(String(Math.fround(value)));
    },
    toString_F64: function (value) {
      return stringToNewUTF8(String(value));
    },
    toString_I1: function (value) {
      return stringToNewUTF8(value ? 'true' : 'false');
    },
    toString_Str: function (value) {
      return stringToNewUTF8(UTF8ToString(value || 0));
    },
    parseInt: function (ret, s) {
      var value = parseDecimalInteger(UTF8ToString(s || 0));
      var ok = value !== null && value >= I32_MIN && value <= I32_MAX;
      writeOptI32(ret, ok, ok ? Number(value) : 0);
    },
    parseI64: function (ret, s) {
      var value = parseDecimalInteger(UTF8ToString(s || 0));
      var ok = value !== null && value >= I64_MIN && value <= I64_MAX;
      writeOptI64(ret, ok, ok ? value : 0n);
    },
    parseF64: function (ret, s) {
      var text = trimParseSpace(UTF8ToString(s || 0));
      var ok = /^[-+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][-+]?\d+)?$/.test(text);
      var value = ok ? Number(text) : 0;
      writeOptF64(ret, ok && Number.isFinite(value), value);
    },
    fmtFormat: function (templatePtr, argsPtr) {
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
    jsonStringify_I8: function (value) {
      return stringToNewUTF8(String((value << 24) >> 24));
    },
    jsonStringify_I64: function (value) {
      return stringToNewUTF8(String(value));
    },
    jsonStringify_U8: function (value) {
      return stringToNewUTF8(String(value & 0xff));
    },
    jsonStringify_U32: function (value) {
      return stringToNewUTF8(String(value >>> 0));
    },
    jsonStringify_U64: function (value) {
      return stringToNewUTF8(String(BigInt.asUintN(64, BigInt(value))));
    },
    jsonStringify_F32: function (value) {
      return stringToNewUTF8(Number.isFinite(value) ? JSON.stringify(Math.fround(value)) : 'null');
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
      var value = parseJsonInteger(UTF8ToString(s || 0));
      if (value === null || value < -2147483648n || value > 2147483647n) return 0;
      return Number(value) | 0;
    },
    jsonParse_I8: function (s) {
      var value = parseJsonInteger(UTF8ToString(s || 0));
      if (value === null || value < I8_MIN || value > I8_MAX) return 0;
      return (Number(value) << 24) >> 24;
    },
    jsonParse_I64: function (s) {
      var value = parseJsonInteger(UTF8ToString(s || 0));
      if (value === null || value < -9223372036854775808n || value > 9223372036854775807n) return BigInt(0);
      return value;
    },
    jsonParse_U32: function (s) {
      var value = parseJsonUnsignedInteger(UTF8ToString(s || 0));
      if (value === null || value > U32_MAX) return 0;
      return Number(value) >>> 0;
    },
    jsonParse_U8: function (s) {
      var value = parseJsonUnsignedInteger(UTF8ToString(s || 0));
      if (value === null || value > U8_MAX) return 0;
      return Number(value) & 0xff;
    },
    jsonParse_U64: function (s) {
      var value = parseJsonUnsignedInteger(UTF8ToString(s || 0));
      if (value === null || value > U64_MAX) return BigInt(0);
      return value;
    },
    jsonParse_F32: function (s) {
      try {
        var text = trimJson(UTF8ToString(s || 0));
        var value = jsonNumberSyntax(text) ? JSON.parse(text) : 0;
        return typeof value === 'number' && Number.isFinite(value) ? Math.fround(value) : 0;
      } catch (e) { return 0; }
    },
    jsonParse_F64: function (s) {
      try {
        var text = trimJson(UTF8ToString(s || 0));
        var value = jsonNumberSyntax(text) ? JSON.parse(text) : 0;
        return typeof value === 'number' && Number.isFinite(value) ? value : 0;
      } catch (e) { return 0; }
    },
    jsonParse_I1: function (s) {
      try {
        var value = JSON.parse(trimJson(UTF8ToString(s || 0)));
        return typeof value === 'boolean' && value ? 1 : 0;
      } catch (e) { return 0; }
    },
    jsonParse_Str: function (s) {
      try {
        var value = JSON.parse(trimJson(UTF8ToString(s || 0)));
        return stringToNewUTF8(typeof value === 'string' && !hasNulString(value) ? value : '');
      } catch (e) { return stringToNewUTF8(''); }
    },
    __ez_json_valid_I32: function (s) {
      var value = parseJsonInteger(UTF8ToString(s || 0));
      return value !== null && value >= -2147483648n && value <= 2147483647n ? 1 : 0;
    },
    __ez_json_valid_I8: function (s) {
      var value = parseJsonInteger(UTF8ToString(s || 0));
      return value !== null && value >= I8_MIN && value <= I8_MAX ? 1 : 0;
    },
    __ez_json_valid_I64: function (s) {
      var value = parseJsonInteger(UTF8ToString(s || 0));
      return value !== null && value >= -9223372036854775808n && value <= 9223372036854775807n ? 1 : 0;
    },
    __ez_json_valid_U32: function (s) {
      var value = parseJsonUnsignedInteger(UTF8ToString(s || 0));
      return value !== null && value <= U32_MAX ? 1 : 0;
    },
    __ez_json_valid_U8: function (s) {
      var value = parseJsonUnsignedInteger(UTF8ToString(s || 0));
      return value !== null && value <= U8_MAX ? 1 : 0;
    },
    __ez_json_valid_U64: function (s) {
      var value = parseJsonUnsignedInteger(UTF8ToString(s || 0));
      return value !== null && value <= U64_MAX ? 1 : 0;
    },
    __ez_json_valid_F32: function (s) {
      var text = trimJson(UTF8ToString(s || 0));
      if (!jsonNumberSyntax(text)) return 0;
      var parsed = parseJsonValue(text);
      return parsed.ok && typeof parsed.value === 'number' && Number.isFinite(parsed.value) && Number.isFinite(Math.fround(parsed.value)) ? 1 : 0;
    },
    __ez_json_valid_F64: function (s) {
      var text = trimJson(UTF8ToString(s || 0));
      if (!jsonNumberSyntax(text)) return 0;
      var parsed = parseJsonValue(text);
      return parsed.ok && typeof parsed.value === 'number' && Number.isFinite(parsed.value) ? 1 : 0;
    },
    __ez_json_valid_Bool: function (s) {
      var parsed = parseJsonValue(UTF8ToString(s || 0));
      return parsed.ok && typeof parsed.value === 'boolean' ? 1 : 0;
    },
    __ez_json_valid_Str: function (s) {
      var text = UTF8ToString(s || 0);
      if (!jsonStringSyntax(text)) return 0;
      var parsed = parseJsonValue(text);
      return parsed.ok && typeof parsed.value === 'string' && !hasNulString(parsed.value) ? 1 : 0;
    },
    __ez_json_valid_object: function (s) {
      return validJsonObjectSyntax(UTF8ToString(s || 0)) ? 1 : 0;
    },
    __ez_json_valid_array: function (s) {
      return validJsonArraySyntax(UTF8ToString(s || 0)) ? 1 : 0;
    },
    __ez_json_valid_value: function (s) {
      var text = trimAscii(UTF8ToString(s || 0));
      var state = { index: 0 };
      return scanJsonValue(text, state) && state.index === text.length ? 1 : 0;
    },
    __ez_json_valid_null: function (s) {
      return trimAscii(UTF8ToString(s || 0)) === 'null' ? 1 : 0;
    },
    __ez_json_array_length: function (s) {
      return BigInt(jsonArrayLength(UTF8ToString(s || 0)));
    },
    __ez_json_array_item: function (s, index) {
      var valueText = jsonArrayItem(UTF8ToString(s || 0), Number(index));
      return valueText === null ? 0 : stringToNewUTF8(valueText);
    },
    __ez_json_object_field_count: function (s) {
      return BigInt(jsonObjectFieldCount(UTF8ToString(s || 0)));
    },
    __ez_json_object_field: function (s, keyPtr) {
      var valueText = jsonObjectField(UTF8ToString(s || 0), UTF8ToString(keyPtr || 0));
      return valueText === null ? 0 : stringToNewUTF8(valueText);
    },
    __ez_json_object_key_at: function (s, index) {
      var keyText = jsonObjectKeyAt(UTF8ToString(s || 0), Number(index));
      return keyText === null ? 0 : stringToNewUTF8(keyText);
    },
    __ez_json_object_value_at: function (s, index) {
      var valueText = jsonObjectValueAt(UTF8ToString(s || 0), Number(index));
      return valueText === null ? 0 : stringToNewUTF8(valueText);
    },
    __ez_msgpack_encode_map: function (ret, count, keysPtr, valuesPtr) {
      var ptrSize = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
      var mapCount = Number(count);
      if (!Number.isFinite(mapCount) || mapCount < 0 || Math.floor(mapCount) !== mapCount) {
        writeBlob(ret, new Uint8Array(0));
        return;
      }
      var headerLen = mapCount <= 15 ? 1 : mapCount <= 0xffff ? 3 : 5;
      var keys = [];
      var values = [];
      var total = headerLen;
      for (var i = 0; i < mapCount; i++) {
        var keyPtr = getValue(keysPtr + i * ptrSize, '*');
        var keyText = UTF8ToString(keyPtr || 0);
        var keyLen = lengthBytesUTF8(keyText);
        var keyTmp = stringToNewUTF8(keyText);
        var keyBytes = HEAPU8.slice(keyTmp, keyTmp + keyLen);
        var valueBytes = blobBytes(valuesPtr + i * 16);
        keys.push(keyBytes);
        values.push(valueBytes);
        total += msgpackStrHeaderLen(keyLen) + keyLen + valueBytes.length;
      }
      var bytes = new Uint8Array(total);
      var pos = 0;
      if (mapCount <= 15) {
        bytes[pos++] = 0x80 | mapCount;
      } else if (mapCount <= 0xffff) {
        bytes[pos++] = 0xde;
        bytes[pos++] = (mapCount >>> 8) & 0xff;
        bytes[pos++] = mapCount & 0xff;
      } else {
        bytes[pos++] = 0xdf;
        bytes[pos++] = (mapCount >>> 24) & 0xff;
        bytes[pos++] = (mapCount >>> 16) & 0xff;
        bytes[pos++] = (mapCount >>> 8) & 0xff;
        bytes[pos++] = mapCount & 0xff;
      }
      for (var j = 0; j < mapCount; j++) {
        pos = writeMsgpackStrHeader(bytes, pos, keys[j].length);
        bytes.set(keys[j], pos);
        pos += keys[j].length;
        bytes.set(values[j], pos);
        pos += values[j].length;
      }
      writeBlob(ret, bytes);
    },
    __ez_msgpack_encode_map_raw: function (ret, count, keysPtr, valuesPtr) {
      var mapCount = Number(count);
      if (!Number.isFinite(mapCount) || mapCount < 0 || Math.floor(mapCount) !== mapCount) {
        writeBlob(ret, new Uint8Array(0));
        return;
      }
      var headerLen = mapCount <= 15 ? 1 : mapCount <= 0xffff ? 3 : 5;
      var keys = [];
      var values = [];
      var total = headerLen;
      for (var i = 0; i < mapCount; i++) {
        var keyBytes = blobBytes(keysPtr + i * 16);
        var valueBytes = blobBytes(valuesPtr + i * 16);
        keys.push(keyBytes);
        values.push(valueBytes);
        total += keyBytes.length + valueBytes.length;
      }
      var bytes = new Uint8Array(total);
      var pos = 0;
      if (mapCount <= 15) {
        bytes[pos++] = 0x80 | mapCount;
      } else if (mapCount <= 0xffff) {
        bytes[pos++] = 0xde;
        bytes[pos++] = (mapCount >>> 8) & 0xff;
        bytes[pos++] = mapCount & 0xff;
      } else {
        bytes[pos++] = 0xdf;
        bytes[pos++] = (mapCount >>> 24) & 0xff;
        bytes[pos++] = (mapCount >>> 16) & 0xff;
        bytes[pos++] = (mapCount >>> 8) & 0xff;
        bytes[pos++] = mapCount & 0xff;
      }
      for (var j = 0; j < mapCount; j++) {
        bytes.set(keys[j], pos);
        pos += keys[j].length;
        bytes.set(values[j], pos);
        pos += values[j].length;
      }
      writeBlob(ret, bytes);
    },
    __ez_msgpack_encode_array: function (ret, count, valuesPtr) {
      var arrayCount = Number(count);
      if (!Number.isFinite(arrayCount) || arrayCount < 0 || Math.floor(arrayCount) !== arrayCount) {
        writeBlob(ret, new Uint8Array(0));
        return;
      }
      var headerLen = arrayCount <= 15 ? 1 : arrayCount <= 0xffff ? 3 : 5;
      var values = [];
      var total = headerLen;
      for (var i = 0; i < arrayCount; i++) {
        var valueBytes = blobBytes(valuesPtr + i * 16);
        values.push(valueBytes);
        total += valueBytes.length;
      }
      var bytes = new Uint8Array(total);
      var pos = 0;
      if (arrayCount <= 15) {
        bytes[pos++] = 0x90 | arrayCount;
      } else if (arrayCount <= 0xffff) {
        bytes[pos++] = 0xdc;
        bytes[pos++] = (arrayCount >>> 8) & 0xff;
        bytes[pos++] = arrayCount & 0xff;
      } else {
        bytes[pos++] = 0xdd;
        bytes[pos++] = (arrayCount >>> 24) & 0xff;
        bytes[pos++] = (arrayCount >>> 16) & 0xff;
        bytes[pos++] = (arrayCount >>> 8) & 0xff;
        bytes[pos++] = arrayCount & 0xff;
      }
      for (var j = 0; j < arrayCount; j++) {
        bytes.set(values[j], pos);
        pos += values[j].length;
      }
      writeBlob(ret, bytes);
    },
    __ez_msgpack_valid_map: function (dataPtr) {
      return msgpackValidateTopMap(blobBytes(dataPtr)) === null ? 0 : 1;
    },
    __ez_msgpack_valid_map_any: function (dataPtr) {
      return msgpackValidateTopMapAny(blobBytes(dataPtr)) === null ? 0 : 1;
    },
    __ez_msgpack_valid_array: function (dataPtr) {
      return msgpackValidateTopArray(blobBytes(dataPtr)) === null ? 0 : 1;
    },
    __ez_msgpack_valid_value: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      return skipMsgpackValue(bytes, 0) === bytes.length ? 1 : 0;
    },
    __ez_msgpack_valid_nil: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      return bytes.length === 1 && bytes[0] === 0xc0 ? 1 : 0;
    },
    __ez_msgpack_array_length: function (dataPtr) {
      var count = msgpackValidateTopArray(blobBytes(dataPtr));
      return BigInt(count === null ? -1 : count);
    },
    __ez_msgpack_array_item: function (ret, dataPtr, index) {
      var value = msgpackArrayItem(blobBytes(dataPtr), Number(index));
      if (value === null) {
        setValue(ret, 0, '*');
        setValue(ret + 8, -1, 'i64');
        return;
      }
      writeBlob(ret, value);
    },
    __ez_msgpack_map_field_count: function (dataPtr) {
      var count = msgpackValidateTopMapAny(blobBytes(dataPtr));
      return BigInt(count === null ? -1 : count);
    },
    __ez_msgpack_map_field: function (ret, dataPtr, keyPtr) {
      var value = msgpackMapField(blobBytes(dataPtr), UTF8ToString(keyPtr || 0));
      if (value === null) {
        setValue(ret, 0, '*');
        setValue(ret + 8, -1, 'i64');
        return;
      }
      writeBlob(ret, value);
    },
    __ez_msgpack_map_key_at: function (dataPtr, index) {
      var key = msgpackMapKeyAt(blobBytes(dataPtr), Number(index));
      return key === null ? 0 : stringToNewUTF8(key);
    },
    __ez_msgpack_map_key_blob_at: function (ret, dataPtr, index) {
      var key = msgpackMapKeyBlobAt(blobBytes(dataPtr), Number(index));
      if (key === null) {
        setValue(ret, 0, '*');
        setValue(ret + 8, -1, 'i64');
        return;
      }
      writeBlob(ret, key);
    },
    __ez_msgpack_map_value_at: function (ret, dataPtr, index) {
      var value = msgpackMapValueAt(blobBytes(dataPtr), Number(index));
      if (value === null) {
        setValue(ret, 0, '*');
        setValue(ret + 8, -1, 'i64');
        return;
      }
      writeBlob(ret, value);
    },
    __ez_msgpack_valid_I32: function (dataPtr) {
      var value = decodeInteger(blobBytes(dataPtr));
      return value !== null && value >= I32_MIN && value <= I32_MAX ? 1 : 0;
    },
    __ez_msgpack_valid_I8: function (dataPtr) {
      var value = decodeInteger(blobBytes(dataPtr));
      return value !== null && value >= I8_MIN && value <= I8_MAX ? 1 : 0;
    },
    __ez_msgpack_valid_I64: function (dataPtr) {
      return decodeInteger(blobBytes(dataPtr)) !== null ? 1 : 0;
    },
    __ez_msgpack_valid_U32: function (dataPtr) {
      var value = decodeUnsignedInteger(blobBytes(dataPtr));
      return value !== null && value <= U32_MAX ? 1 : 0;
    },
    __ez_msgpack_valid_U8: function (dataPtr) {
      var value = decodeUnsignedInteger(blobBytes(dataPtr));
      return value !== null && value <= U8_MAX ? 1 : 0;
    },
    __ez_msgpack_valid_U64: function (dataPtr) {
      return decodeUnsignedInteger(blobBytes(dataPtr)) !== null ? 1 : 0;
    },
    __ez_msgpack_valid_F32: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length === 5 && bytes[0] === 0xca) {
        return Number.isFinite(new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat32(1, false)) ? 1 : 0;
      }
      if (bytes.length === 9 && bytes[0] === 0xcb) {
        var value = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat64(1, false);
        return Number.isFinite(value) && Number.isFinite(Math.fround(value)) ? 1 : 0;
      }
      return 0;
    },
    __ez_msgpack_valid_F64: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length === 5 && bytes[0] === 0xca) {
        return Number.isFinite(new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat32(1, false)) ? 1 : 0;
      }
      if (bytes.length === 9 && bytes[0] === 0xcb) {
        return Number.isFinite(new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat64(1, false)) ? 1 : 0;
      }
      return 0;
    },
    __ez_msgpack_valid_Bool: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      return bytes.length === 1 && (bytes[0] === 0xc2 || bytes[0] === 0xc3) ? 1 : 0;
    },
    __ez_msgpack_valid_Str: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var span = msgpackStrSpanAt(bytes, 0);
      if (!span || span.next !== bytes.length) return 0;
      var payload = bytes.slice(span.start, span.start + span.len);
      return !hasNulBytes(payload) && validUtf8Bytes(payload) ? 1 : 0;
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
    msgpackEncode_I8: function (ret, value) {
      writeBlob(ret, new Uint8Array([0xd0, value & 0xff]));
    },
    msgpackEncode_I64: function (ret, value) {
      var bytes = new Uint8Array(9);
      var n = BigInt(value);
      bytes[0] = 0xd3;
      for (var i = 0; i < 8; i++) bytes[i + 1] = Number((n >> BigInt(56 - i * 8)) & BigInt(0xff));
      writeBlob(ret, bytes);
    },
    msgpackEncode_U32: function (ret, value) {
      var bytes = new Uint8Array(5);
      var n = value >>> 0;
      bytes[0] = 0xce;
      bytes[1] = (n >>> 24) & 0xff;
      bytes[2] = (n >>> 16) & 0xff;
      bytes[3] = (n >>> 8) & 0xff;
      bytes[4] = n & 0xff;
      writeBlob(ret, bytes);
    },
    msgpackEncode_U8: function (ret, value) {
      writeBlob(ret, new Uint8Array([0xcc, value & 0xff]));
    },
    msgpackEncode_U64: function (ret, value) {
      var bytes = new Uint8Array(9);
      var n = BigInt.asUintN(64, BigInt(value));
      bytes[0] = 0xcf;
      for (var i = 0; i < 8; i++) bytes[i + 1] = Number((n >> BigInt(56 - i * 8)) & BigInt(0xff));
      writeBlob(ret, bytes);
    },
    msgpackEncode_F32: function (ret, value) {
      var bytes = new Uint8Array(5);
      var view = new DataView(bytes.buffer);
      bytes[0] = 0xca;
      view.setFloat32(1, value, false);
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
      var value = decodeInteger(bytes);
      if (value === null || value < -2147483648n || value > 2147483647n) return 0;
      return Number(value) | 0;
    },
    msgpackDecode_I8: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var value = decodeInteger(bytes);
      if (value === null || value < I8_MIN || value > I8_MAX) return 0;
      return (Number(value) << 24) >> 24;
    },
    msgpackDecode_I64: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var value = decodeInteger(bytes);
      return value === null ? BigInt(0) : value;
    },
    msgpackDecode_U32: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var value = decodeUnsignedInteger(bytes);
      if (value === null || value > U32_MAX) return 0;
      return Number(value) >>> 0;
    },
    msgpackDecode_U8: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var value = decodeUnsignedInteger(bytes);
      if (value === null || value > U8_MAX) return 0;
      return Number(value) & 0xff;
    },
    msgpackDecode_U64: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      var value = decodeUnsignedInteger(bytes);
      return value === null ? BigInt(0) : value;
    },
    msgpackDecode_F32: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length === 5 && bytes[0] === 0xca) {
        return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat32(1, false);
      }
      if (bytes.length === 9 && bytes[0] === 0xcb) {
        var value = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat64(1, false);
        return Number.isFinite(value) ? Math.fround(value) : 0;
      }
      return 0;
    },
    msgpackDecode_F64: function (dataPtr) {
      var bytes = blobBytes(dataPtr);
      if (bytes.length === 5 && bytes[0] === 0xca) {
        return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getFloat32(1, false);
      }
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
      if (headerLen + len !== bytes.length) return stringToNewUTF8('');
      var payload = bytes.slice(headerLen, headerLen + len);
      if (hasNulBytes(payload)) return stringToNewUTF8('');
      if (!validUtf8Bytes(payload)) return stringToNewUTF8('');
      return stringToNewUTF8(UTF8ArrayToString(payload, 0));
    },
    urlEncode: function (s) {
      return stringToNewUTF8(encodeURIComponent(UTF8ToString(s || 0)));
    },
    urlDecode: function (ret, s) {
      try {
        var decoded = decodeURIComponent(UTF8ToString(s || 0));
        if (hasNulString(decoded)) throw new Error('nul byte');
        HEAPU8[ret] = 1;
        setValue(ret + 8, stringToNewUTF8(decoded), '*');
      } catch (e) {
        HEAPU8[ret] = 0;
        setValue(ret + 8, 0, '*');
      }
    },
  });
})();
