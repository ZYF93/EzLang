// EzLang std/net/http Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  fetch: function (ret, url) {
    HEAPU8[ret] = 0;
  },
  fetchEx: function (ret, req) {
    HEAPU8[ret] = 0;
  },
  createServer: function (host, port) {
    return 0n;
  },
});
