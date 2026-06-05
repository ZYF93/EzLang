// EzLang std/io Emscripten JS 封装层
// WebAssembly 同步 ABI 当前不支持标准输入；readLine 明确返回空可选值。
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
  readLine: function (ret) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
  },
});
