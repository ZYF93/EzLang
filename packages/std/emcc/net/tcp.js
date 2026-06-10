// EzLang std/net/tcp Emscripten JS 封装层
// WebAssembly 目标不支持原生 TCP/UDP 套接字；所有接口明确返回不可用结果。
mergeInto(LibraryManager.library, {
  tcpConnect: function (ret, host, port) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, 'i64');
  },
  tcpListen: function (ret, host, port) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, 'i64');
  },
  tcpAccept: function (ret, listener) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, 'i64');
  },
  tcpRead: function (ret, conn, maxBytes) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
    setValue(ret + 16, 0, 'i64');
  },
  tcpWrite: function (conn, data) {
    return -1;
  },
  tcpClose: function (conn) {
    return 0;
  },
  tcpListenerClose: function (listener) {
    return 0;
  },
  udpBind: function (ret, host, port) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, 'i64');
  },
  udpSend: function (socket, host, port, data) {
    return -1;
  },
  udpRecvFrom: function (ret, socket, maxBytes) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
    setValue(ret + 16, 0, 'i64');
    setValue(ret + 24, 0, '*');
    setValue(ret + 32, 0, 'i32');
  },
  udpRecv: function (ret, socket, maxBytes) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
    setValue(ret + 16, 0, 'i64');
  },
  udpClose: function (socket) {
    return 0;
  },
});
