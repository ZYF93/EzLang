// EzLang std/random Emscripten JS 封装层
(function () {
  var MOD64 = 1n << 64n;

  function u64(value) {
    return BigInt.asUintN(64, typeof value === 'bigint' ? value : BigInt(value));
  }

  function i64(value) {
    return BigInt.asIntN(64, u64(value));
  }

  function readState(ptr) {
    return ptr ? u64(HEAP64[ptr >> 3]) : mixSeed(0n);
  }

  function writeState(ptr, value) {
    if (ptr) HEAP64[ptr >> 3] = i64(value);
  }

  function mixSeed(seed) {
    var z = u64(seed + 0x9E3779B97F4A7C15n);
    z = u64((z ^ (z >> 30n)) * 0xBF58476D1CE4E5B9n);
    z = u64((z ^ (z >> 27n)) * 0x94D049BB133111EBn);
    return u64(z ^ (z >> 31n));
  }

  function next(sourcePtr) {
    var x = readState(sourcePtr);
    if (x === 0n) x = mixSeed(0n);
    x = u64(x ^ (x >> 12n));
    x = u64(x ^ (x << 25n));
    x = u64(x ^ (x >> 27n));
    writeState(sourcePtr, x);
    return u64(x * 0x2545F4914F6CDD1Dn);
  }

  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function writeBlob(ret, bytes) {
    var dataPtr = 0;
    if (bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ret, dataPtr, '*');
    setValue(ret + 8, bytes.length, 'i64');
  }

  function writeOptBlob(ret, ok, bytes) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeBlob(ret + 8, bytes || new Uint8Array(0));
  }

  function writeOptU64(ret, ok, value) {
    HEAPU8[ret] = ok ? 1 : 0;
    HEAP64[(ret + 8) >> 3] = ok ? i64(value) : 0n;
  }

  function rangeI64(sourcePtr, minValue, maxValue) {
    minValue = BigInt(minValue);
    maxValue = BigInt(maxValue);
    if (minValue > maxValue) {
      var tmp = minValue;
      minValue = maxValue;
      maxValue = tmp;
    }
    var span = maxValue - minValue + 1n;
    if (span >= MOD64) return i64(next(sourcePtr));
    var limit = MOD64 - (MOD64 % span);
    var value = 0n;
    do {
      value = next(sourcePtr);
    } while (value >= limit);
    return i64(minValue + (value % span));
  }

  function secureBytes(size) {
    size = typeof size === 'bigint' ? Number(size) : Number(size);
    if (!Number.isSafeInteger(size) || size < 0) return null;
    var bytes = new Uint8Array(size);
    var cryptoObj = typeof crypto !== 'undefined' ? crypto : (typeof globalThis !== 'undefined' ? globalThis.crypto : null);
    if (cryptoObj && typeof cryptoObj.getRandomValues === 'function') {
      for (var offset = 0; offset < size; offset += 65536) {
        cryptoObj.getRandomValues(bytes.subarray(offset, Math.min(offset + 65536, size)));
      }
      return bytes;
    }
    if (typeof require === 'function') {
      try {
        var nodeCrypto = require('crypto');
        if (nodeCrypto && typeof nodeCrypto.randomBytes === 'function') return new Uint8Array(nodeCrypto.randomBytes(size));
      } catch (e) {}
    }
    return null;
  }

  mergeInto(LibraryManager.library, {
    randomSeed: function (ret, seed) {
      var state = mixSeed(u64(seed));
      if (state === 0n) state = 0x9E3779B97F4A7C15n;
      HEAP64[ret >> 3] = i64(state);
    },
    randomNextU32: function (sourcePtr) {
      return Number((next(sourcePtr) >> 32n) & 0xFFFFFFFFn) | 0;
    },
    randomNextU64: function (sourcePtr) {
      return i64(next(sourcePtr));
    },
    randomRangeI64: function (sourcePtr, minValue, maxValue) {
      return rangeI64(sourcePtr, minValue, maxValue);
    },
    randomRangeF64: function (sourcePtr, minValue, maxValue) {
      if (minValue > maxValue) {
        var tmp = minValue;
        minValue = maxValue;
        maxValue = tmp;
      }
      var raw = next(sourcePtr) >> 11n;
      var unit = Number(raw) / 9007199254740992;
      return minValue + (maxValue - minValue) * unit;
    },
    randomShuffleBytes: function (ret, sourcePtr, dataPtr) {
      var bytes = blobBytes(dataPtr);
      var out = new Uint8Array(bytes);
      for (var i = out.length - 1; i > 0; i--) {
        var j = Number(rangeI64(sourcePtr, 0n, BigInt(i)));
        var t = out[i];
        out[i] = out[j];
        out[j] = t;
      }
      writeBlob(ret, out);
    },
    randomEntropy: function (ret, size) {
      var bytes = secureBytes(size);
      writeOptBlob(ret, !!bytes, bytes || new Uint8Array(0));
    },
    randomSecureBytes: function (ret, size) {
      var bytes = secureBytes(size);
      writeOptBlob(ret, !!bytes, bytes || new Uint8Array(0));
    },
    randomSecureU64: function (ret) {
      var bytes = secureBytes(8);
      if (!bytes) {
        writeOptU64(ret, false, 0n);
        return;
      }
      var value = 0n;
      for (var i = 0; i < 8; i++) value |= BigInt(bytes[i]) << BigInt(i * 8);
      writeOptU64(ret, true, value);
    },
  });
})();
