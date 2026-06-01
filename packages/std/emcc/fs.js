// EzLang std/fs Emscripten JS 封装层
// 使用 MEMFS 作为默认文件系统；浏览器环境可把 /ezdata 挂载到 IDBFS。
(function () {
  var EZFS_IDBFS_ROOT = '/ezdata';
  var EZFS_IDBFS_READY = false;

  function ezfsPath(path) {
    return UTF8ToString(path || 0);
  }

  function ezfsOk(fn) {
    try {
      fn();
      return 1;
    } catch (e) {
      return 0;
    }
  }

  function ezfsEnsureParent(path) {
    var parts = path.split('/');
    parts.pop();
    var current = path.charAt(0) === '/' ? '/' : '';
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      if (!part) continue;
      current = current === '/' ? '/' + part : current + '/' + part;
      try {
        FS.mkdir(current);
      } catch (e) {
        // 目录已存在时忽略；其它错误交给后续文件操作暴露。
      }
    }
  }

  function ezfsEnsureIdbfs() {
    if (EZFS_IDBFS_READY || typeof IDBFS === 'undefined') return;
    try {
      FS.mkdir(EZFS_IDBFS_ROOT);
    } catch (e) {
      // 已存在则忽略。
    }
    try {
      FS.mount(IDBFS, {}, EZFS_IDBFS_ROOT);
      FS.syncfs(true, function () {});
      EZFS_IDBFS_READY = true;
    } catch (e) {
      // 非浏览器或未启用 IDBFS 时继续使用 MEMFS。
    }
  }

  function ezfsSync() {
    if (!EZFS_IDBFS_READY) return;
    try {
      FS.syncfs(false, function () {});
    } catch (e) {
      // 同步失败不影响本次内存态文件操作结果。
    }
  }

  function ezfsAllocBlob(bytes) {
    var dataPtr = 0;
    if (bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    var blobPtr = _malloc(16);
    setValue(blobPtr, dataPtr, '*');
    setValue(blobPtr + 8, bytes.length, 'i64');
    return blobPtr;
  }

  function ezfsBlobBytes(blobPtr) {
    if (!blobPtr) return new Uint8Array(0);
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!dataPtr || size <= 0) return new Uint8Array(0);
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function ezfsWrite(pathPtr, blobPtr, append) {
    return ezfsOk(function () {
      ezfsEnsureIdbfs();
      var path = ezfsPath(pathPtr);
      ezfsEnsureParent(path);
      var data = ezfsBlobBytes(blobPtr);
      if (append) {
        var oldData = new Uint8Array(0);
        try {
          oldData = FS.readFile(path, { encoding: 'binary' });
        } catch (e) {
          oldData = new Uint8Array(0);
        }
        var merged = new Uint8Array(oldData.length + data.length);
        merged.set(oldData, 0);
        merged.set(data, oldData.length);
        data = merged;
      }
      FS.writeFile(path, data, { encoding: 'binary' });
      ezfsSync();
    });
  }

  mergeInto(LibraryManager.library, {
    readFile: function (path) {
      try {
        ezfsEnsureIdbfs();
        return ezfsAllocBlob(FS.readFile(ezfsPath(path), { encoding: 'binary' }));
      } catch (e) {
        return ezfsAllocBlob(new Uint8Array(0));
      }
    },
    writeFile: function (path, content) {
      return ezfsWrite(path, content, false);
    },
    appendFile: function (path, content) {
      return ezfsWrite(path, content, true);
    },
    removeFile: function (path) {
      return ezfsOk(function () {
        ezfsEnsureIdbfs();
        FS.unlink(ezfsPath(path));
        ezfsSync();
      });
    },
    mkdir: function (path) {
      return ezfsOk(function () {
        ezfsEnsureIdbfs();
        FS.mkdirTree(ezfsPath(path));
        ezfsSync();
      });
    },
    removeDir: function (path, recursive) {
      return ezfsOk(function () {
        ezfsEnsureIdbfs();
        var target = ezfsPath(path);
        if (recursive) {
          var entries = FS.readdir(target);
          for (var i = 0; i < entries.length; i++) {
            var name = entries[i];
            if (name === '.' || name === '..') continue;
            var child = target.replace(/\/$/, '') + '/' + name;
            var mode = FS.stat(child).mode;
            if (FS.isDir(mode)) {
              LibraryManager.library.removeDir(stringToNewUTF8(child), 1);
            } else {
              FS.unlink(child);
            }
          }
        }
        FS.rmdir(target);
        ezfsSync();
      });
    },
    listDir: function (path) {
      try {
        ezfsEnsureIdbfs();
        var entries = FS.readdir(ezfsPath(path)).filter(function (name) {
          return name !== '.' && name !== '..';
        });
        var joined = entries.join('\n');
        return stringToNewUTF8(joined);
      } catch (e) {
        return 0;
      }
    },
    exists: function (path) {
      try {
        ezfsEnsureIdbfs();
        FS.stat(ezfsPath(path));
        return 1;
      } catch (e) {
        return 0;
      }
    },
    isDir: function (path) {
      try {
        ezfsEnsureIdbfs();
        return FS.isDir(FS.stat(ezfsPath(path)).mode) ? 1 : 0;
      } catch (e) {
        return 0;
      }
    },
    stat: function (path) {
      try {
        ezfsEnsureIdbfs();
        var info = FS.stat(ezfsPath(path));
        var ptr = _malloc(32);
        setValue(ptr, info.size || 0, 'i64');
        setValue(ptr + 8, FS.isDir(info.mode) ? 1 : 0, 'i8');
        setValue(ptr + 16, Math.floor((info.mtime ? info.mtime.getTime() : 0) / 1000), 'i64');
        setValue(ptr + 24, Math.floor((info.ctime ? info.ctime.getTime() : 0) / 1000), 'i64');
        return ptr;
      } catch (e) {
        return 0;
      }
    },
    absPath: function (path) {
      var raw = ezfsPath(path);
      if (raw.charAt(0) === '/') return path;
      return stringToNewUTF8('/' + raw);
    },
    __ez_fs_sync: function () {
      ezfsEnsureIdbfs();
      ezfsSync();
    },
  });
})();
