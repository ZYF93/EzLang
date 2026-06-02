// EzLang std/time Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  now: function (ret) {
    HEAP64[ret >> 3] = BigInt(Date.now());
  },
  timestamp: function () {
    return BigInt(Date.now());
  },
  sleep: function (ms) {
    // WebAssembly 主线程无法同步 sleep；语言层 flow 负责挂起调度。
  },
  getYear: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCFullYear();
  },
  getMonth: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCMonth() + 1;
  },
  getDay: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCDate();
  },
  getHour: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCHours();
  },
  getMinute: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCMinutes();
  },
  getSecond: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCSeconds();
  },
  add: function (datePtr, yearPtr, monthPtr, dayPtr, hourPtr, minutePtr, secondPtr) {
    var d = new Date(Number(HEAP64[datePtr >> 3]));
    function opt(ptr) { return ptr && HEAPU8[ptr] ? HEAP32[(ptr + 4) >> 2] : 0; }
    d.setUTCFullYear(d.getUTCFullYear() + opt(yearPtr));
    d.setUTCMonth(d.getUTCMonth() + opt(monthPtr));
    d.setUTCDate(d.getUTCDate() + opt(dayPtr));
    d.setUTCHours(d.getUTCHours() + opt(hourPtr));
    d.setUTCMinutes(d.getUTCMinutes() + opt(minutePtr));
    d.setUTCSeconds(d.getUTCSeconds() + opt(secondPtr));
    HEAP64[datePtr >> 3] = BigInt(d.getTime());
  },
  sub: function (datePtr, yearPtr, monthPtr, dayPtr, hourPtr, minutePtr, secondPtr) {
    var d = new Date(Number(HEAP64[datePtr >> 3]));
    function opt(ptr) { return ptr && HEAPU8[ptr] ? HEAP32[(ptr + 4) >> 2] : 0; }
    d.setUTCFullYear(d.getUTCFullYear() - opt(yearPtr));
    d.setUTCMonth(d.getUTCMonth() - opt(monthPtr));
    d.setUTCDate(d.getUTCDate() - opt(dayPtr));
    d.setUTCHours(d.getUTCHours() - opt(hourPtr));
    d.setUTCMinutes(d.getUTCMinutes() - opt(minutePtr));
    d.setUTCSeconds(d.getUTCSeconds() - opt(secondPtr));
    HEAP64[datePtr >> 3] = BigInt(d.getTime());
  },
  format: function (datePtr, fmtPtr) {
    var date = new Date(Number(HEAP64[datePtr >> 3]));
    var fmt = UTF8ToString(fmtPtr || 0) || '%Y-%m-%dT%H:%M:%SZ';
    function pad(v) { return String(v).padStart(2, '0'); }
    var text = fmt
      .replace(/%Y|YYYY/g, String(date.getUTCFullYear()))
      .replace(/%m|MM/g, pad(date.getUTCMonth() + 1))
      .replace(/%d|DD/g, pad(date.getUTCDate()))
      .replace(/%H|HH/g, pad(date.getUTCHours()))
      .replace(/%M/g, pad(date.getUTCMinutes()))
      .replace(/%S|SS/g, pad(date.getUTCSeconds()));
    return stringToNewUTF8(text);
  },
});
