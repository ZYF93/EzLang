// EzLang std/test Emscripten JS 封装层
(function () {
  var passed = 0;
  var failed = 0;
  var skipped = 0;
  var tests = [];
  var currentTest = '';

  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function failNow(message) {
    failed += 1;
    var msg = message || 'assertion failed';
    if (typeof console !== 'undefined' && console.error) console.error('test failed: ' + (currentTest ? currentTest + ': ' : '') + msg);
    throw new Error(msg);
  }

  function remember(name) {
    var value = name || '';
    tests.push(value);
    currentTest = value;
  }

  function i64Value(value) {
    return typeof value === 'bigint' ? value : BigInt(value);
  }

  mergeInto(LibraryManager.library, {
    testAssert: function (condition, msg) {
      if (!condition) failNow(text(msg));
      passed += 1;
    },
    testEqualI64: function (actual, expected, msg) {
      var left = i64Value(actual);
      var right = i64Value(expected);
      if (left !== right) failNow((text(msg) || 'not equal') + ': expected ' + right.toString() + ', got ' + left.toString());
      passed += 1;
    },
    testNotEqualI64: function (actual, expected, msg) {
      var left = i64Value(actual);
      var right = i64Value(expected);
      if (left === right) failNow((text(msg) || 'equal') + ': unexpected ' + left.toString());
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
    testRegister: function (name) { remember(text(name)); },
    testRegisterParam: function (name, param) { remember(text(name) + '[' + text(param) + ']'); },
    testCount: function () { return tests.length | 0; },
    testName: function (index) {
      var value = tests[index | 0] || '';
      return stringToNewUTF8(value);
    },
    testPassed: function () { return passed | 0; },
    testFailed: function () { return failed | 0; },
    testSkipped: function () { return skipped | 0; },
    testReset: function () { passed = 0; failed = 0; skipped = 0; tests = []; currentTest = ''; },
  });
})();
