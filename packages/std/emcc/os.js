// EzLang std/os Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  args: function () {
    return 0;
  },
  env: function (key) {
    return 0;
  },
  setEnv: function (key, value) {
    return 0;
  },
  cwd: function () {
    return stringToNewUTF8('/');
  },
  exit: function (code) {
    quit_(code, new ExitStatus(code));
  },
  pid: function () {
    return 0;
  },
  platform: function () {
    return stringToNewUTF8('emcc');
  },
  arch: function () {
    return stringToNewUTF8('wasm32');
  },
});
