// EzLang std/net/http Emscripten JS 封装层
// WebAssembly 同步 ABI 当前不支持异步 fetch/服务端；相关接口明确返回不可用结果。
// HTTP 服务端明确不支持：createServer 返回 handle = 0。
(function () {
  var HTTP_SERVER_UNSUPPORTED_HANDLE = 0n;

  function responseBodyText(respPtr) {
    if (!respPtr) return '';
    var bodyOffset = 24;
    var dataPtr = getValue(respPtr + bodyOffset, '*');
    var size = Number(getValue(respPtr + bodyOffset + 8, 'i64'));
    if (!dataPtr || size <= 0) return '';
    var bytes = HEAPU8.slice(dataPtr, dataPtr + size);
    if (typeof TextDecoder !== 'undefined') {
      return new TextDecoder('utf-8').decode(bytes);
    }
    var out = '';
    for (var i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i]);
    return out;
  }

  mergeInto(LibraryManager.library, {
    fetch: function (ret, url) {
      HEAPU8[ret] = 0;
    },
    fetchEx: function (ret, req) {
      HEAPU8[ret] = 0;
    },
    createServer: function (host, port) {
      return HTTP_SERVER_UNSUPPORTED_HANDLE;
    },
    HttpResponse_text: function (resp) {
      return stringToNewUTF8(responseBodyText(resp));
    },
  });
})();
