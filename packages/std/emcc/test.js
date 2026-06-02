// EzLang std/test Emscripten JS 封装层
(function () {
  var passed = 0;
  var failed = 0;
  var skipped = 0;

  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function failNow(message) {
    failed += 1;
    var msg = message || 'assertion failed';
    if (typeof console !== 'undefined' && console.error) console.error('test failed: ' + msg);
    throw new Error(msg);
  }

  mergeInto(LibraryManager.library, {
    testAssert: function (condition, msg) {
      if (!condition) failNow(text(msg));
      passed += 1;
    },
    testEqualI64: function (actual, expected, msg) {
      if (Number(actual) !== Number(expected)) failNow((text(msg) || 'not equal') + ': expected ' + Number(expected) + ', got ' + Number(actual));
      passed += 1;
    },
    testNotEqualI64: function (actual, expected, msg) {
      if (Number(actual) === Number(expected)) failNow((text(msg) || 'equal') + ': unexpected ' + Number(actual));
      passed += 1;
    },
    testEqualStr: function (actual, expected, msg) {
      var a = text(actual);
      var e = text(expected);
      if (a !== e) failNow((text(msg) || 'not equal') + ": expected '" + e + "', got '" + a + "'");
      passed += 1;
    },
    testSkip: function (msg) {
      skipped += 1;
      if (typeof console !== 'undefined' && console.warn) console.warn('test skipped: ' + text(msg));
    },
    testRegister: function () {},
    testPassed: function () { return passed | 0; },
    testFailed: function () { return failed | 0; },
    testSkipped: function () { return skipped | 0; },
    testReset: function () { passed = 0; failed = 0; skipped = 0; },
  });
})();
