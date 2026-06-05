// EzLang std/net/ws Emscripten JS 封装层
// WebAssembly 同步 ABI 当前不支持浏览器 WebSocket；所有接口明确返回不可用结果。
mergeInto(LibraryManager.library, {
  wsConnect: function (ret, url) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, 'i64');
  },
  wsSend: function (conn, data) {
    return -1;
  },
  wsRecv: function (ret, conn, maxBytes) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
    setValue(ret + 16, 0, 'i64');
  },
  wsClose: function (conn) {
    return 0;
  },
});
