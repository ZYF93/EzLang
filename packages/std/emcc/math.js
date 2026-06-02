// EzLang std/math Emscripten JS 封装层
(function () {
  var I64_MIN = -(1n << 63n);
  var I64_MAX = (1n << 63n) - 1n;
  var I32_MIN = -2147483648;
  var I32_MAX = 2147483647;

  function asBigInt(value) {
    return typeof value === 'bigint' ? value : BigInt(value);
  }

  function writeOptI32(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    HEAP32[(ret + 4) >> 2] = value | 0;
  }

  function writeOptI64(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    HEAP64[(ret + 8) >> 3] = BigInt(value || 0);
  }

  function checkedI64(ret, value) {
    var ok = value >= I64_MIN && value <= I64_MAX;
    writeOptI64(ret, ok, ok ? value : 0n);
  }

  function absI64(value) {
    value = asBigInt(value);
    if (value === I64_MIN) return I64_MAX;
    return value < 0n ? -value : value;
  }

  function gcdI64(a, b) {
    var x = absI64(a);
    var y = absI64(b);
    while (y !== 0n) {
      var r = x % y;
      x = y;
      y = r;
    }
    return x > I64_MAX ? I64_MAX : x;
  }

  mergeInto(LibraryManager.library, {
    mathAbsI32: function (value) {
      return value === I32_MIN ? I32_MAX : Math.abs(value | 0);
    },
    mathAbsI64: function (value) {
      return absI64(value);
    },
    mathMinI32: function (a, b) {
      return Math.min(a | 0, b | 0) | 0;
    },
    mathMaxI32: function (a, b) {
      return Math.max(a | 0, b | 0) | 0;
    },
    mathClampI32: function (value, minValue, maxValue) {
      value = value | 0;
      minValue = minValue | 0;
      maxValue = maxValue | 0;
      if (minValue > maxValue) {
        var tmp = minValue;
        minValue = maxValue;
        maxValue = tmp;
      }
      return Math.min(Math.max(value, minValue), maxValue) | 0;
    },
    mathGcdI64: function (a, b) {
      return gcdI64(a, b);
    },
    mathLcmI64: function (a, b) {
      a = asBigInt(a);
      b = asBigInt(b);
      if (a === 0n || b === 0n) return 0n;
      var gcd = gcdI64(a, b);
      var value = absI64((a / gcd) * b);
      return value > I64_MAX ? I64_MAX : value;
    },
    mathSqrt: function (value) { return Math.sqrt(value); },
    mathPow: function (base, exp) { return Math.pow(base, exp); },
    mathSin: function (value) { return Math.sin(value); },
    mathCos: function (value) { return Math.cos(value); },
    mathTan: function (value) { return Math.tan(value); },
    mathLog: function (value) { return Math.log(value); },
    mathExp: function (value) { return Math.exp(value); },
    mathFloor: function (value) { return Math.floor(value); },
    mathCeil: function (value) { return Math.ceil(value); },
    mathRound: function (value) { return Math.round(value); },
    mathIsNaN: function (value) { return Number.isNaN(value) ? 1 : 0; },
    mathIsInf: function (value) { return !Number.isNaN(value) && !Number.isFinite(value) ? 1 : 0; },
    mathAddI64Checked: function (ret, a, b) {
      checkedI64(ret, asBigInt(a) + asBigInt(b));
    },
    mathSubI64Checked: function (ret, a, b) {
      checkedI64(ret, asBigInt(a) - asBigInt(b));
    },
    mathMulI64Checked: function (ret, a, b) {
      checkedI64(ret, asBigInt(a) * asBigInt(b));
    },
    mathDivI64Checked: function (ret, a, b) {
      a = asBigInt(a);
      b = asBigInt(b);
      if (b === 0n || (a === I64_MIN && b === -1n)) {
        writeOptI64(ret, false, 0n);
      } else {
        writeOptI64(ret, true, a / b);
      }
    },
    mathF64ToI32: function (ret, value) {
      writeOptI32(ret, Number.isFinite(value) && value >= I32_MIN && value <= I32_MAX, value | 0);
    },
    mathF64ToI64: function (ret, value) {
      var ok = Number.isFinite(value) && value >= Number(I64_MIN) && value <= Number(I64_MAX);
      writeOptI64(ret, ok, ok ? BigInt(Math.trunc(value)) : 0n);
    },
    mathI64ToF64: function (value) {
      return Number(value);
    },
  });
})();
