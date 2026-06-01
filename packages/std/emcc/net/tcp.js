// EzLang std/net/tcp Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  tcpConnect: function (host, port) { return 0; },
  tcpListen: function (host, port) { return 0; },
  udpBind: function (host, port) { return 0; },
});
