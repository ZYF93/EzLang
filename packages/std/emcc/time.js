// EzLang std/time Emscripten JS 封装层
mergeInto(LibraryManager.library, {
  now: function (ret) {
    HEAP64[ret >> 3] = BigInt(Date.now());
  },
  timestamp: function () {
    return BigInt(Date.now());
  },
  sleep: function (ms) {
    var delay = Number(ms);
    if (!Number.isFinite(delay) || delay <= 0) return;
    if (typeof SharedArrayBuffer !== 'undefined' && typeof Atomics !== 'undefined') {
      var flag = new Int32Array(new SharedArrayBuffer(4));
      Atomics.wait(flag, 0, 0, delay);
      return;
    }
    // 浏览器主线程没有可移植同步 sleep 原语，短时忙等用于保持 ABI 语义。
    var end = Date.now() + delay;
    while (Date.now() < end) {}
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
