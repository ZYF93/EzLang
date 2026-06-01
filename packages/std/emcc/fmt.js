// EzLang std/fmt Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  toString: function (value) {
    return stringToNewUTF8(String(value));
  },
  parseInt: function (s) {
    return Number.parseInt(UTF8ToString(s), 10) | 0;
  },
  parseI64: function (s) {
    return BigInt(Number.parseInt(UTF8ToString(s), 10));
  },
  parseF64: function (s) {
    return Number.parseFloat(UTF8ToString(s));
  },
  format: function (template, args) {
    return template;
  },
  b64Encode: function (data) {
    return stringToNewUTF8('');
  },
  b64Decode: function (s) {
    return 0;
  },
  jsonStringify: function (data) {
    return stringToNewUTF8('null');
  },
  jsonParse: function (s) {
    return 0;
  },
  msgpackEncode: function (data) {
    return 0;
  },
  msgpackDecode: function (data) {
    return 0;
  },
  urlEncode: function (s) {
    return stringToNewUTF8(encodeURIComponent(UTF8ToString(s)));
  },
  urlDecode: function (s) {
    return stringToNewUTF8(decodeURIComponent(UTF8ToString(s)));
  },
});
