// EzLang std/crypto Emscripten JS 封装层
// 同步 ABI 下仅使用 Node crypto；浏览器 WebCrypto 为异步 API，当前返回空可选值。
(function () {
  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
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

  function digest(algorithm, dataPtr) {
    var crypto = nodeCrypto();
    if (!crypto || typeof crypto.createHash !== 'function') return null;
    return new Uint8Array(crypto.createHash(algorithm).update(Buffer.from(blobBytes(dataPtr))).digest());
  }

  function hmac(algorithm, keyPtr, dataPtr) {
    var crypto = nodeCrypto();
    if (!crypto || typeof crypto.createHmac !== 'function') return null;
    return new Uint8Array(crypto.createHmac(algorithm, Buffer.from(blobBytes(keyPtr))).update(Buffer.from(blobBytes(dataPtr))).digest());
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
