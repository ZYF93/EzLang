// EzLang std/io Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  print: function (msg) {
    console.log(UTF8ToString(msg));
  },
  println: function (msg) {
    console.log(UTF8ToString(msg));
  },
  error: function (msg) {
    console.error(UTF8ToString(msg));
  },
  readLine: function () {
    return 0;
  },
});
