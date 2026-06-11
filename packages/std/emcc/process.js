// EzLang std/process Emscripten JS 封装层
// Node 风格运行时使用 child_process.spawn + Asyncify 挂起；无 Asyncify 时回退 spawnSync。浏览器显式失败。
(function () {
  var STREAM_KIND_PROCESS_STDIN = 5;
  var STREAM_KIND_PROCESS_STDOUT = 6;
  var STREAM_KIND_PROCESS_STDERR = 7;
  var nextHandle = 1;
  var completed = Object.create(null);
  var root = typeof Module !== 'undefined' && Module ? Module : (typeof globalThis !== 'undefined' ? globalThis : this);

  function hasAsyncify() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleSleep === 'function';
  }

  function ptrSize() {
    return typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
  }

  function readStr(ptr) {
    return ptr ? UTF8ToString(ptr) : '';
  }

  function listGet(listPtr, index) {
    if (!listPtr) return '';
    var size = ptrSize();
    var pages = getValue(listPtr, '*');
    var length = Number(getValue(listPtr + 8, 'i64'));
    if (!pages || index < 0 || index >= length) return '';
    var pagePtr = getValue(pages + Math.floor(index / 8) * size, '*');
    if (!pagePtr) return '';
    var itemPtr = getValue(pagePtr + (index % 8) * size, '*');
    return itemPtr ? UTF8ToString(itemPtr) : '';
  }

  function listItems(listPtr) {
    var length = listPtr ? Number(getValue(listPtr + 8, 'i64')) : 0;
    var out = [];
    for (var i = 0; i < length; ++i) out.push(listGet(listPtr, i));
    return out;
  }

  function blobBytes(blobPtr) {
    if (!blobPtr) return null;
    var dataPtr = getValue(blobPtr, '*');
    var size = Number(getValue(blobPtr + 8, 'i64'));
    if (!Number.isSafeInteger(size) || size < 0 || (size > 0 && !dataPtr)) return null;
    if (size === 0) return new Uint8Array(0);
    if (dataPtr < 0 || dataPtr > HEAPU8.length || size > HEAPU8.length - dataPtr) return null;
    return HEAPU8.slice(dataPtr, dataPtr + size);
  }

  function bytesValue(value) {
    if (!value) return new Uint8Array(0);
    if (value instanceof Uint8Array) return value;
    if (typeof Buffer !== 'undefined' && Buffer.isBuffer && Buffer.isBuffer(value)) return new Uint8Array(value);
    return new Uint8Array(value);
  }

  function writeBlob(ptr, bytes) {
    bytes = bytes || new Uint8Array(0);
    var dataPtr = 0;
    if (bytes.length > 0) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ptr, dataPtr, '*');
    setValue(ptr + 8, bytes.length, 'i64');
  }

  function writeProcess(ptr, handle, pid) {
    setValue(ptr, BigInt(handle || 0), 'i64');
    setValue(ptr + 8, BigInt(pid || 0), 'i64');
  }

  function writeOptProcess(ret, ok, processValue) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeProcess(ret + 8, ok && processValue ? processValue.handle : 0, ok && processValue ? processValue.pid : 0);
  }

  function writeProcessResult(ptr, result) {
    setValue(ptr, result ? result.exitCode | 0 : 0, 'i32');
    writeBlob(ptr + 8, result ? result.stdout : new Uint8Array(0));
    writeBlob(ptr + 24, result ? result.stderr : new Uint8Array(0));
    HEAPU8[ptr + 40] = result && result.exitCode === 0 ? 1 : 0;
  }

  function writeOptProcessResult(ret, ok, result) {
    HEAPU8[ret] = ok ? 1 : 0;
    writeProcessResult(ret + 8, ok ? result : null);
  }

  function writeOptStr(ret, value) {
    HEAPU8[ret] = value === null ? 0 : 1;
    setValue(ret + 8, value === null ? 0 : stringToNewUTF8(value), '*');
  }

  function writeStream(ptr, streamValue) {
    setValue(ptr, streamValue ? streamValue.handle : 0, 'i64');
    setValue(ptr + 8, streamValue ? streamValue.kind : 0, 'i32');
  }

  function writeOptStream(ret, streamValue) {
    HEAPU8[ret] = streamValue ? 1 : 0;
    writeStream(ret + 8, streamValue);
  }

  function nodeRequire(name) {
    if (typeof require !== 'function') return null;
    try { return require(name); } catch (e) { return null; }
  }

  function baseEnv() {
    if (typeof process !== 'undefined' && process && process.env) {
      var out = Object.create(null);
      Object.keys(process.env).forEach(function (key) { out[key] = process.env[key]; });
      return out;
    }
    return undefined;
  }

  function applyEnv(envItems) {
    var env = baseEnv();
    if (!env && envItems.length === 0) return undefined;
    if (!env) env = Object.create(null);
    envItems.forEach(function (entry) {
      var eq = entry.indexOf('=');
      if (eq <= 0) return;
      env[entry.slice(0, eq)] = entry.slice(eq + 1);
    });
    return env;
  }

  function readCommand(commandPtr) {
    if (!commandPtr) return null;
    var program = readStr(getValue(commandPtr, '*'));
    if (!program) return null;
    var stdin = blobBytes(commandPtr + 80);
    if (stdin === null) return null;
    return {
      program: program,
      args: listItems(commandPtr + 8),
      cwd: readStr(getValue(commandPtr + 40, '*')),
      env: listItems(commandPtr + 48),
      stdin: stdin,
    };
  }

  function spawnSyncResult(command) {
    var childProcess = nodeRequire('child_process');
    if (!childProcess || typeof childProcess.spawnSync !== 'function') return null;
    try {
      var options = {
        input: typeof Buffer !== 'undefined' ? Buffer.from(command.stdin) : command.stdin,
        encoding: null,
        env: applyEnv(command.env),
      };
      if (command.cwd) options.cwd = command.cwd;
      var result = childProcess.spawnSync(command.program, command.args, options);
      if (result.error) return null;
      var status = typeof result.status === 'number' ? result.status : (result.signal ? 128 : 0);
      return {
        exitCode: status | 0,
        stdout: bytesValue(result.stdout),
        stderr: bytesValue(result.stderr),
      };
    } catch (e) {
      return null;
    }
  }

  function spawnAsyncResult(command) {
    var childProcess = nodeRequire('child_process');
    if (!childProcess || typeof childProcess.spawn !== 'function') return null;
    return Asyncify.handleSleep(function (wakeUp) {
      var settled = false;
      function done(result) {
        if (settled) return;
        settled = true;
        wakeUp(result);
      }
      try {
        var options = { env: applyEnv(command.env) };
        if (command.cwd) options.cwd = command.cwd;
        var child = childProcess.spawn(command.program, command.args, options);
        var stdout = [];
        var stderr = [];
        if (child.stdout) child.stdout.on('data', function (chunk) { stdout.push(chunk); });
        if (child.stderr) child.stderr.on('data', function (chunk) { stderr.push(chunk); });
        child.on('error', function () { done(null); });
        child.on('close', function (code, signal) {
          done({
            exitCode: typeof code === 'number' ? code | 0 : (signal ? 128 : 0),
            stdout: typeof Buffer !== 'undefined' ? Buffer.concat(stdout) : new Uint8Array(0),
            stderr: typeof Buffer !== 'undefined' ? Buffer.concat(stderr) : new Uint8Array(0),
          });
        });
        if (child.stdin) {
          if (command.stdin && command.stdin.length > 0) child.stdin.write(typeof Buffer !== 'undefined' ? Buffer.from(command.stdin) : command.stdin);
          child.stdin.end();
        }
      } catch (e) {
        done(null);
      }
    });
  }

  function spawnResult(command) {
    if (hasAsyncify()) return spawnAsyncResult(command);
    return spawnSyncResult(command);
  }

  function readProcess(processPtr) {
    if (!processPtr) return null;
    return {
      handle: Number(getValue(processPtr, 'i64')),
      pid: Number(getValue(processPtr + 8, 'i64')),
    };
  }

  function streamBridge() {
    var bridge = root && root.__ez_stream_bridge;
    return bridge && typeof bridge.fromBytes === 'function' ? bridge : null;
  }

  function takeCompletedStream(ret, processPtr, field, kind) {
    var processValue = readProcess(processPtr);
    var result = processValue ? completed[processValue.handle] : null;
    var bridge = streamBridge();
    if (!result || !bridge) return writeOptStream(ret, null);
    var stream = bridge.fromBytes(result[field], kind);
    if (!stream) return writeOptStream(ret, null);
    result[field] = new Uint8Array(0);
    writeOptStream(ret, stream);
  }

  mergeInto(LibraryManager.library, {
    processExec__async: 'auto',
    processExec: function (ret, commandPtr) {
      var command = readCommand(commandPtr);
      var result = command ? spawnResult(command) : null;
      writeOptProcessResult(ret, !!result, result);
    },
    processSpawn__async: 'auto',
    processSpawn: function (ret, commandPtr) {
      var command = readCommand(commandPtr);
      var result = command ? spawnResult(command) : null;
      if (!result) return writeOptProcess(ret, false, null);
      var handle = nextHandle++;
      completed[handle] = result;
      writeOptProcess(ret, true, { handle: handle, pid: 0 });
    },
    processWait: function (ret, processPtr) {
      var processValue = readProcess(processPtr);
      var result = processValue ? completed[processValue.handle] : null;
      if (!result) return writeOptProcessResult(ret, false, null);
      delete completed[processValue.handle];
      writeOptProcessResult(ret, true, result);
    },
    processTerminate: function (processPtr) {
      readProcess(processPtr);
      return 0;
    },
    processStdin: function (ret, processPtr) {
      readProcess(processPtr);
      writeOptStream(ret, null);
    },
    processStdout: function (ret, processPtr) {
      takeCompletedStream(ret, processPtr, 'stdout', STREAM_KIND_PROCESS_STDOUT);
    },
    processStderr: function (ret, processPtr) {
      takeCompletedStream(ret, processPtr, 'stderr', STREAM_KIND_PROCESS_STDERR);
    },
    processCurrentPath: function (ret) {
      if (typeof process !== 'undefined' && process && process.execPath) {
        return writeOptStr(ret, String(process.execPath));
      }
      writeOptStr(ret, null);
    },
  });
})();
