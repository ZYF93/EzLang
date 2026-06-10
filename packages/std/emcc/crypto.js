// EzLang std/crypto Emscripten JS 封装层
// Node crypto 优先；不可用时使用同步 SHA-2/HMAC 回退。
(function () {
  var MASK_64 = (1n << 64n) - 1n;

  function blobBytes(blobPtr) {
    if (!blobPtr) return null;
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isFinite(size) || size < 0 || Math.floor(size) !== size) return null;
    if (size === 0) return new Uint8Array(0);
    if (!dataPtr) return null;
    if (dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function writeBlob(ptr, bytes) {
    var dataPtr = 0;
    if (bytes && bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ptr, dataPtr, '*');
    setValue(ptr + 8, bytes ? bytes.length : 0, 'i64');
  }

  function writeOptBlob(ret, ok, bytes) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeBlob(ret + 8, ok ? bytes : new Uint8Array(0));
  }

  function nodeCrypto() {
    if (typeof require !== 'function') return null;
    try { return require('crypto'); } catch (e) { return null; }
  }

  function nodeBytes(bytes) {
    return typeof Buffer !== 'undefined' ? Buffer.from(bytes) : bytes;
  }

  function rotr32(value, bits) {
    return (value >>> bits) | (value << (32 - bits));
  }

  function readBe32(bytes, offset) {
    return ((bytes[offset] << 24) |
      (bytes[offset + 1] << 16) |
      (bytes[offset + 2] << 8) |
      bytes[offset + 3]) >>> 0;
  }

  function writeBe32(out, offset, value) {
    out[offset] = (value >>> 24) & 0xff;
    out[offset + 1] = (value >>> 16) & 0xff;
    out[offset + 2] = (value >>> 8) & 0xff;
    out[offset + 3] = value & 0xff;
  }

  function paddedBytes(bytes, blockSize, lengthSize) {
    var bitLen = BigInt(bytes.length) * 8n;
    var size = bytes.length + 1 + lengthSize;
    var paddedSize = Math.ceil(size / blockSize) * blockSize;
    var out = new Uint8Array(paddedSize);
    out.set(bytes);
    out[bytes.length] = 0x80;
    for (var i = 0; i < lengthSize; ++i) {
      out[paddedSize - 1 - i] = Number((bitLen >> BigInt(i * 8)) & 0xffn);
    }
    return out;
  }

  var K256 = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];

  function sha256Bytes(bytes) {
    var state = [
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    var padded = paddedBytes(bytes, 64, 8);
    var words = new Array(64);
    for (var offset = 0; offset < padded.length; offset += 64) {
      for (var i = 0; i < 16; ++i) words[i] = readBe32(padded, offset + i * 4);
      for (i = 16; i < 64; ++i) {
        var s0 = (rotr32(words[i - 15], 7) ^ rotr32(words[i - 15], 18) ^ (words[i - 15] >>> 3)) >>> 0;
        var s1 = (rotr32(words[i - 2], 17) ^ rotr32(words[i - 2], 19) ^ (words[i - 2] >>> 10)) >>> 0;
        words[i] = (words[i - 16] + s0 + words[i - 7] + s1) >>> 0;
      }

      var a = state[0];
      var b = state[1];
      var c = state[2];
      var d = state[3];
      var e = state[4];
      var f = state[5];
      var g = state[6];
      var h = state[7];
      for (i = 0; i < 64; ++i) {
        var s1e = (rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25)) >>> 0;
        var ch = ((e & f) ^ (~e & g)) >>> 0;
        var temp1 = (h + s1e + ch + K256[i] + words[i]) >>> 0;
        var s0a = (rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22)) >>> 0;
        var maj = ((a & b) ^ (a & c) ^ (b & c)) >>> 0;
        var temp2 = (s0a + maj) >>> 0;
        h = g;
        g = f;
        f = e;
        e = (d + temp1) >>> 0;
        d = c;
        c = b;
        b = a;
        a = (temp1 + temp2) >>> 0;
      }
      state[0] = (state[0] + a) >>> 0;
      state[1] = (state[1] + b) >>> 0;
      state[2] = (state[2] + c) >>> 0;
      state[3] = (state[3] + d) >>> 0;
      state[4] = (state[4] + e) >>> 0;
      state[5] = (state[5] + f) >>> 0;
      state[6] = (state[6] + g) >>> 0;
      state[7] = (state[7] + h) >>> 0;
    }
    var out = new Uint8Array(32);
    for (i = 0; i < 8; ++i) writeBe32(out, i * 4, state[i]);
    return out;
  }

  function rotr64(value, bits) {
    return ((value >> BigInt(bits)) | (value << BigInt(64 - bits))) & MASK_64;
  }

  function readBe64(bytes, offset) {
    var value = 0n;
    for (var i = 0; i < 8; ++i) value = (value << 8n) | BigInt(bytes[offset + i]);
    return value;
  }

  function writeBe64(out, offset, value) {
    for (var i = 7; i >= 0; --i) {
      out[offset + i] = Number(value & 0xffn);
      value >>= 8n;
    }
  }

  var K512 = [
    0x428a2f98d728ae22n, 0x7137449123ef65cdn,
    0xb5c0fbcfec4d3b2fn, 0xe9b5dba58189dbbcn,
    0x3956c25bf348b538n, 0x59f111f1b605d019n,
    0x923f82a4af194f9bn, 0xab1c5ed5da6d8118n,
    0xd807aa98a3030242n, 0x12835b0145706fben,
    0x243185be4ee4b28cn, 0x550c7dc3d5ffb4e2n,
    0x72be5d74f27b896fn, 0x80deb1fe3b1696b1n,
    0x9bdc06a725c71235n, 0xc19bf174cf692694n,
    0xe49b69c19ef14ad2n, 0xefbe4786384f25e3n,
    0x0fc19dc68b8cd5b5n, 0x240ca1cc77ac9c65n,
    0x2de92c6f592b0275n, 0x4a7484aa6ea6e483n,
    0x5cb0a9dcbd41fbd4n, 0x76f988da831153b5n,
    0x983e5152ee66dfabn, 0xa831c66d2db43210n,
    0xb00327c898fb213fn, 0xbf597fc7beef0ee4n,
    0xc6e00bf33da88fc2n, 0xd5a79147930aa725n,
    0x06ca6351e003826fn, 0x142929670a0e6e70n,
    0x27b70a8546d22ffcn, 0x2e1b21385c26c926n,
    0x4d2c6dfc5ac42aedn, 0x53380d139d95b3dfn,
    0x650a73548baf63den, 0x766a0abb3c77b2a8n,
    0x81c2c92e47edaee6n, 0x92722c851482353bn,
    0xa2bfe8a14cf10364n, 0xa81a664bbc423001n,
    0xc24b8b70d0f89791n, 0xc76c51a30654be30n,
    0xd192e819d6ef5218n, 0xd69906245565a910n,
    0xf40e35855771202an, 0x106aa07032bbd1b8n,
    0x19a4c116b8d2d0c8n, 0x1e376c085141ab53n,
    0x2748774cdf8eeb99n, 0x34b0bcb5e19b48a8n,
    0x391c0cb3c5c95a63n, 0x4ed8aa4ae3418acbn,
    0x5b9cca4f7763e373n, 0x682e6ff3d6b2b8a3n,
    0x748f82ee5defb2fcn, 0x78a5636f43172f60n,
    0x84c87814a1f0ab72n, 0x8cc702081a6439ecn,
    0x90befffa23631e28n, 0xa4506cebde82bde9n,
    0xbef9a3f7b2c67915n, 0xc67178f2e372532bn,
    0xca273eceea26619cn, 0xd186b8c721c0c207n,
    0xeada7dd6cde0eb1en, 0xf57d4f7fee6ed178n,
    0x06f067aa72176fban, 0x0a637dc5a2c898a6n,
    0x113f9804bef90daen, 0x1b710b35131c471bn,
    0x28db77f523047d84n, 0x32caab7b40c72493n,
    0x3c9ebe0a15c9bebcn, 0x431d67c49c100d4cn,
    0x4cc5d4becb3e42b6n, 0x597f299cfc657e2an,
    0x5fcb6fab3ad6faecn, 0x6c44198c4a475817n,
  ];

  function sha512Bytes(bytes) {
    var state = [
      0x6a09e667f3bcc908n, 0xbb67ae8584caa73bn,
      0x3c6ef372fe94f82bn, 0xa54ff53a5f1d36f1n,
      0x510e527fade682d1n, 0x9b05688c2b3e6c1fn,
      0x1f83d9abfb41bd6bn, 0x5be0cd19137e2179n,
    ];
    var padded = paddedBytes(bytes, 128, 16);
    var words = new Array(80);
    for (var offset = 0; offset < padded.length; offset += 128) {
      for (var i = 0; i < 16; ++i) words[i] = readBe64(padded, offset + i * 8);
      for (i = 16; i < 80; ++i) {
        var s0 = (rotr64(words[i - 15], 1) ^ rotr64(words[i - 15], 8) ^ (words[i - 15] >> 7n)) & MASK_64;
        var s1 = (rotr64(words[i - 2], 19) ^ rotr64(words[i - 2], 61) ^ (words[i - 2] >> 6n)) & MASK_64;
        words[i] = (words[i - 16] + s0 + words[i - 7] + s1) & MASK_64;
      }

      var a = state[0];
      var b = state[1];
      var c = state[2];
      var d = state[3];
      var e = state[4];
      var f = state[5];
      var g = state[6];
      var h = state[7];
      for (i = 0; i < 80; ++i) {
        var s1e = (rotr64(e, 14) ^ rotr64(e, 18) ^ rotr64(e, 41)) & MASK_64;
        var ch = ((e & f) ^ (~e & g)) & MASK_64;
        var temp1 = (h + s1e + ch + K512[i] + words[i]) & MASK_64;
        var s0a = (rotr64(a, 28) ^ rotr64(a, 34) ^ rotr64(a, 39)) & MASK_64;
        var maj = ((a & b) ^ (a & c) ^ (b & c)) & MASK_64;
        var temp2 = (s0a + maj) & MASK_64;
        h = g;
        g = f;
        f = e;
        e = (d + temp1) & MASK_64;
        d = c;
        c = b;
        b = a;
        a = (temp1 + temp2) & MASK_64;
      }
      state[0] = (state[0] + a) & MASK_64;
      state[1] = (state[1] + b) & MASK_64;
      state[2] = (state[2] + c) & MASK_64;
      state[3] = (state[3] + d) & MASK_64;
      state[4] = (state[4] + e) & MASK_64;
      state[5] = (state[5] + f) & MASK_64;
      state[6] = (state[6] + g) & MASK_64;
      state[7] = (state[7] + h) & MASK_64;
    }
    var out = new Uint8Array(64);
    for (i = 0; i < 8; ++i) writeBe64(out, i * 8, state[i]);
    return out;
  }

  function concatBytes(a, b) {
    var out = new Uint8Array(a.length + b.length);
    out.set(a);
    out.set(b, a.length);
    return out;
  }

  function hmacBytes(hashFn, blockSize, key, data) {
    var normalizedKey = new Uint8Array(blockSize);
    normalizedKey.set(key.length > blockSize ? hashFn(key) : key);
    var innerPad = new Uint8Array(blockSize);
    var outerPad = new Uint8Array(blockSize);
    for (var i = 0; i < blockSize; ++i) {
      innerPad[i] = normalizedKey[i] ^ 0x36;
      outerPad[i] = normalizedKey[i] ^ 0x5c;
    }
    return hashFn(concatBytes(outerPad, hashFn(concatBytes(innerPad, data))));
  }

  function nodeDigest(algorithm, data) {
    var crypto = nodeCrypto();
    if (!crypto || typeof crypto.createHash !== 'function') return null;
    try {
      return new Uint8Array(crypto.createHash(algorithm).update(nodeBytes(data)).digest());
    } catch (e) {
      return null;
    }
  }

  function nodeHmac(algorithm, key, data) {
    var crypto = nodeCrypto();
    if (!crypto || typeof crypto.createHmac !== 'function') return null;
    try {
      return new Uint8Array(crypto.createHmac(algorithm, nodeBytes(key)).update(nodeBytes(data)).digest());
    } catch (e) {
      return null;
    }
  }

  function digest(algorithm, dataPtr) {
    var data = blobBytes(dataPtr);
    if (!data) return null;
    var out = nodeDigest(algorithm, data);
    if (out) return out;
    return algorithm === 'sha256' ? sha256Bytes(data) : sha512Bytes(data);
  }

  function hmac(algorithm, keyPtr, dataPtr) {
    var key = blobBytes(keyPtr);
    var data = blobBytes(dataPtr);
    if (!key || !data) return null;
    var out = nodeHmac(algorithm, key, data);
    if (out) return out;
    return algorithm === 'sha256' ? hmacBytes(sha256Bytes, 64, key, data) : hmacBytes(sha512Bytes, 128, key, data);
  }

  mergeInto(LibraryManager.library, {
    cryptoSha256: function (ret, data) {
      var out = digest('sha256', data);
      writeOptBlob(ret, !!out, out);
    },
    cryptoSha512: function (ret, data) {
      var out = digest('sha512', data);
      writeOptBlob(ret, !!out, out);
    },
    cryptoHmacSha256: function (ret, key, data) {
      var out = hmac('sha256', key, data);
      writeOptBlob(ret, !!out, out);
    },
    cryptoHmacSha512: function (ret, key, data) {
      var out = hmac('sha512', key, data);
      writeOptBlob(ret, !!out, out);
    },
  });
})();
