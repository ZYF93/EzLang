// EzLang std/os Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  args: function (ret) {
    setValue(ret, 0, '*');
    setValue(ret + 8, 0, 'i64');
    setValue(ret + 16, 0, 'i64');
    setValue(ret + 24, 0, 'i64');
  },
  env: function (ret, key) {
    HEAPU8[ret] = 0;
    setValue(ret + 8, 0, '*');
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
