// EzLang std/hash Emscripten JS 封装层
(function () {
  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size <= 0 || Math.floor(size) !== size) return new Uint8Array(0);
    if (!dataPtr || dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function cStringBytes(ptr) {
    if (!ptr) return new Uint8Array(0);
    var end = ptr;
    while (HEAPU8[end] !== 0) end++;
    return HEAPU8.slice(ptr, end);
  }

  function fnv1a32(bytes) {
    var hash = 2166136261 >>> 0;
    for (var i = 0; i < bytes.length; i++) {
      hash ^= bytes[i];
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return hash | 0;
  }

  function fnv1a64(bytes) {
    var hash = 14695981039346656037n;
    for (var i = 0; i < bytes.length; i++) {
      hash ^= BigInt(bytes[i]);
      hash = BigInt.asUintN(64, hash * 1099511628211n);
    }
    return BigInt.asIntN(64, hash);
  }

  function crc32Bytes(bytes) {
    var crc = 0xFFFFFFFF >>> 0;
    for (var i = 0; i < bytes.length; i++) {
      crc = (crc ^ bytes[i]) >>> 0;
      for (var bit = 0; bit < 8; bit++) {
        var mask = -(crc & 1);
        crc = ((crc >>> 1) ^ (0xEDB88320 & mask)) >>> 0;
      }
    }
    return (~crc) | 0;
  }

  mergeInto(LibraryManager.library, {
    hashFnv1a32: function (dataPtr) {
      return fnv1a32(blobBytes(dataPtr));
    },
    hashFnv1a64: function (dataPtr) {
      return fnv1a64(blobBytes(dataPtr));
    },
    hashStrFnv1a32: function (s) {
      return fnv1a32(cStringBytes(s));
    },
    hashStrFnv1a64: function (s) {
      return fnv1a64(cStringBytes(s));
    },
    hashCombineU64: function (seed, value) {
      seed = BigInt.asUintN(64, BigInt(seed));
      value = BigInt.asUintN(64, BigInt(value));
      var out = seed ^ (value + 0x9E3779B97F4A7C15n + (seed << 6n) + (seed >> 2n));
      return BigInt.asIntN(64, BigInt.asUintN(64, out));
    },
    crc32: function (dataPtr) {
      return crc32Bytes(blobBytes(dataPtr));
    },
    crc32Str: function (s) {
      return crc32Bytes(cStringBytes(s));
    },
  });
})();
