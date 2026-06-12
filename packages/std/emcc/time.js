// EzLang std/time Emscripten JS 封装层
(function () {
  function sleepMs(ms) {
    var delay = Number(ms);
    if (!Number.isFinite(delay) || delay <= 0) return;
    if (typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleSleep === 'function') {
      return Asyncify.handleSleep(function (wakeUp) { setTimeout(wakeUp, delay); });
    }
    if (typeof SharedArrayBuffer !== 'undefined' && typeof Atomics !== 'undefined') {
      var flag = new Int32Array(new SharedArrayBuffer(4));
      Atomics.wait(flag, 0, 0, delay);
      return;
    }
    // 浏览器主线程没有可移植同步 sleep 原语，短时忙等用于保持 ABI 语义。
    var end = Date.now() + delay;
    while (Date.now() < end) {}
  }

  mergeInto(LibraryManager.library, {
  __durationToString: function (ms) {
    return stringToNewUTF8(String(ms) + 'ms');
  },
  now: function (ret) {
    HEAP64[ret >> 3] = BigInt(Date.now());
  },
  timestamp: function () {
    return BigInt(Date.now());
  },
  sleep__async: 'auto',
  sleep: function (ms) {
    return sleepMs(ms);
  },
  __ezrt_emcc_sleep__async: 'auto',
  __ezrt_emcc_sleep: function (ms) {
    return sleepMs(ms);
  },
  dateGetYear: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCFullYear();
  },
  dateGetMonth: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCMonth() + 1;
  },
  dateGetDay: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCDate();
  },
  dateGetHour: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCHours();
  },
  dateGetMinute: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCMinutes();
  },
  dateGetSecond: function (datePtr) {
    return new Date(Number(HEAP64[datePtr >> 3])).getUTCSeconds();
  },
  dateAdd: function (datePtr, yearPtr, monthPtr, dayPtr, hourPtr, minutePtr, secondPtr) {
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
  dateSub: function (datePtr, yearPtr, monthPtr, dayPtr, hourPtr, minutePtr, secondPtr) {
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
  dateFormat: function (datePtr, fmtPtr) {
    var date = new Date(Number(HEAP64[datePtr >> 3]));
    var fmt = UTF8ToString(fmtPtr || 0) || '%Y-%m-%dT%H:%M:%SZ';
    function pad(v) { return String(v).padStart(2, '0'); }
    function namedToken(index) {
      if (fmt.slice(index, index + 4) === 'YYYY') return [String(date.getUTCFullYear()), 4];
      if (fmt.slice(index, index + 2) === 'MM') return [pad(date.getUTCMonth() + 1), 2];
      if (fmt.slice(index, index + 2) === 'mm') return [pad(date.getUTCMinutes()), 2];
      if (fmt.slice(index, index + 2) === 'DD') return [pad(date.getUTCDate()), 2];
      if (fmt.slice(index, index + 2) === 'HH') return [pad(date.getUTCHours()), 2];
      if (fmt.slice(index, index + 2) === 'SS') return [pad(date.getUTCSeconds()), 2];
      return null;
    }
    function percentToken(index) {
      if (index + 1 >= fmt.length) return ['%', 1];
      var ch = fmt.charAt(index + 1);
      if (ch === 'Y') return [String(date.getUTCFullYear()), 2];
      if (ch === 'm') return [pad(date.getUTCMonth() + 1), 2];
      if (ch === 'd') return [pad(date.getUTCDate()), 2];
      if (ch === 'H') return [pad(date.getUTCHours()), 2];
      if (ch === 'M') return [pad(date.getUTCMinutes()), 2];
      if (ch === 'S') return [pad(date.getUTCSeconds()), 2];
      if (ch === '%') return ['%', 2];
      return ['%' + ch, 2];
    }
    var out = '';
    for (var i = 0; i < fmt.length;) {
      var token = fmt.charAt(i) === '%' ? percentToken(i) : namedToken(i);
      if (token) {
        out += token[0];
        i += token[1];
      } else {
        out += fmt.charAt(i);
        i++;
      }
    }
    return stringToNewUTF8(out);
  },
  });
})();
