// EzLang std/net/ws Emscripten JS 封装层
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
