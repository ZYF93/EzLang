// EzLang std/net/http Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  fetch: function (url) { return 0; },
  fetchEx: function (req) { return 0; },
  createServer: function (host, port) { return 0; },
});
