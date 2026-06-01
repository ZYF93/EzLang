// EzLang std/time Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  now: function () {
    return BigInt(Math.floor(Date.now() / 1000));
  },
  timestamp: function () {
    return BigInt(Math.floor(Date.now() / 1000));
  },
  sleep: function (ms) {
  },
  getYear: function (date) {
    return new Date(Number(date) * 1000).getUTCFullYear();
  },
  getMonth: function (date) {
    return new Date(Number(date) * 1000).getUTCMonth() + 1;
  },
  getDay: function (date) {
    return new Date(Number(date) * 1000).getUTCDate();
  },
  add: function (date, year, month, day, hour, minute, second) {
  },
  sub: function (date, year, month, day, hour, minute, second) {
  },
  format: function (date, fmt) {
    return fmt;
  },
});
