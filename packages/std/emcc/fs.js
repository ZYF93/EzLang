// EzLang std/fs Emscripten JS 封装层
// 默认使用 Emscripten MEMFS；浏览器环境可按需把 /ezdata 挂到 IDBFS。
(function () {
  var EZFS_IDBFS_ROOT = '/ezdata';
  var EZFS_IDBFS_READY = false;

  function pathText(path) {
    return UTF8ToString(path || 0);
  }

  function ok(fn) {
    try {
      fn();
      return 1;
    } catch (e) {
      return 0;
    }
  }

  function ensureParent(path) {
    var parts = path.split('/');
    parts.pop();
    var current = path.charAt(0) === '/' ? '/' : '';
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      if (!part) continue;
      current = current === '/' ? '/' + part : current + '/' + part;
      try { FS.mkdir(current); } catch (e) {}
    }
  }

  function ensureIdbfs() {
    if (EZFS_IDBFS_READY || typeof IDBFS === 'undefined') return;
    try { FS.mkdir(EZFS_IDBFS_ROOT); } catch (e) {}
    try {
      FS.mount(IDBFS, {}, EZFS_IDBFS_ROOT);
      FS.syncfs(true, function () {});
      EZFS_IDBFS_READY = true;
    } catch (e) {}
  }

  function syncFs() {
    if (!EZFS_IDBFS_READY) return;
    try { FS.syncfs(false, function () {}); } catch (e) {}
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

  function blobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function writeStrList(ret, entries) {
    var ptrSize = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
    var pageCount = entries.length === 0 ? 0 : Math.ceil(entries.length / 8);
    var pagesPtr = pageCount === 0 ? 0 : _malloc(pageCount * ptrSize);
    for (var page = 0; page < pageCount; page++) {
      var pagePtr = _malloc(8 * ptrSize);
      setValue(pagesPtr + page * ptrSize, pagePtr, '*');
      for (var offset = 0; offset < 8; offset++) {
        var idx = page * 8 + offset;
        setValue(pagePtr + offset * ptrSize, idx < entries.length ? stringToNewUTF8(entries[idx]) : 0, '*');
      }
    }
    setValue(ret, pagesPtr, '*');
    setValue(ret + 8, entries.length, 'i64');
    setValue(ret + 16, pageCount * 8, 'i64');
    setValue(ret + 24, pageCount, 'i64');
  }

  function writeStat(ret, info) {
    HEAPU8[ret] = info ? 1 : 0;
    var base = ret + 8;
    setValue(base, info ? (info.size || 0) : 0, 'i64');
    setValue(base + 8, info && FS.isDir(info.mode) ? 1 : 0, 'i8');
    setValue(base + 16, info && info.mtime ? info.mtime.getTime() : 0, 'i64');
    setValue(base + 24, info && info.ctime ? info.ctime.getTime() : 0, 'i64');
  }

  function writeFileImpl(pathPtr, blobPtr, append) {
    return ok(function () {
      ensureIdbfs();
      var path = pathText(pathPtr);
      ensureParent(path);
      var data = blobBytes(blobPtr);
      if (append) {
        var oldData = new Uint8Array(0);
        try { oldData = FS.readFile(path, { encoding: 'binary' }); } catch (e) {}
        var merged = new Uint8Array(oldData.length + data.length);
        merged.set(oldData, 0);
        merged.set(data, oldData.length);
        data = merged;
      }
      FS.writeFile(path, data, { encoding: 'binary' });
      syncFs();
    });
  }

  function removeTree(path) {
    var entries = FS.readdir(path);
    for (var i = 0; i < entries.length; i++) {
      var name = entries[i];
      if (name === '.' || name === '..') continue;
      var child = path.replace(/\/$/, '') + '/' + name;
      if (FS.isDir(FS.stat(child).mode)) removeTree(child);
      else FS.unlink(child);
    }
    FS.rmdir(path);
  }

  mergeInto(LibraryManager.library, {
    readFile: function (ret, path) {
      try {
        ensureIdbfs();
        writeBlob(ret, FS.readFile(pathText(path), { encoding: 'binary' }));
      } catch (e) {
        writeBlob(ret, new Uint8Array(0));
      }
    },
    writeFile: function (path, content) {
      return writeFileImpl(path, content, false);
    },
    appendFile: function (path, content) {
      return writeFileImpl(path, content, true);
    },
    removeFile: function (path) {
      return ok(function () { ensureIdbfs(); FS.unlink(pathText(path)); syncFs(); });
    },
    mkdir: function (path) {
      return ok(function () { ensureIdbfs(); FS.mkdirTree(pathText(path)); syncFs(); });
    },
    removeDir: function (path, recursive) {
      return ok(function () {
        ensureIdbfs();
        var target = pathText(path);
        if (recursive) removeTree(target);
        else FS.rmdir(target);
        syncFs();
      });
    },
    listDir: function (ret, path) {
      try {
        ensureIdbfs();
        writeStrList(ret, FS.readdir(pathText(path)).filter(function (name) { return name !== '.' && name !== '..'; }));
      } catch (e) {
        writeStrList(ret, []);
      }
    },
    exists: function (path) {
      return ok(function () { ensureIdbfs(); FS.stat(pathText(path)); });
    },
    isDir: function (path) {
      try { ensureIdbfs(); return FS.isDir(FS.stat(pathText(path)).mode) ? 1 : 0; } catch (e) { return 0; }
    },
    stat: function (ret, path) {
      try { ensureIdbfs(); writeStat(ret, FS.stat(pathText(path))); } catch (e) { writeStat(ret, null); }
    },
    absPath: function (path) {
      var raw = pathText(path);
      return raw.charAt(0) === '/' ? path : stringToNewUTF8('/' + raw);
    },
    __ez_fs_sync: function () {
      ensureIdbfs();
      syncFs();
    },
  });
})();
