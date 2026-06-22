// EzLang flow/parallel Emscripten 运行时。
(function () {
  var nextTaskId = 1;
  var tasks = Object.create(null);

  function hasAsyncify() {
    return typeof Asyncify !== 'undefined' && Asyncify && typeof Asyncify.handleSleep === 'function';
  }

  function toI32(value) {
    if (typeof value === 'bigint') return Number(value) | 0;
    return Number(value || 0) | 0;
  }

  function tableFunction(ptr) {
    var index = Number(ptr || 0);
    if (!index) return null;
    if (typeof getWasmTableEntry === 'function') return getWasmTableEntry(index);
    if (typeof wasmTable !== 'undefined' && wasmTable && typeof wasmTable.get === 'function') return wasmTable.get(index);
    return null;
  }

  function callI32Branch(ptr) {
    if (!ptr) return 0;
    if (typeof dynCall_i === 'function') return toI32(dynCall_i(ptr));
    if (typeof Module !== 'undefined' && Module && typeof Module.dynCall_i === 'function') {
      return toI32(Module.dynCall_i(ptr));
    }
    var fn = tableFunction(ptr);
    return fn ? toI32(fn()) : 0;
  }

  function callI32EnvBranch(ptr, env) {
    if (!ptr) return 0;
    if (typeof dynCall_ii === 'function') return toI32(dynCall_ii(ptr, env));
    if (typeof Module !== 'undefined' && Module && typeof Module.dynCall_ii === 'function') {
      return toI32(Module.dynCall_ii(ptr, env));
    }
    var fn = tableFunction(ptr);
    return fn ? toI32(fn(env)) : 0;
  }

  function runTask(task) {
    if (!task || task.done || task.cancelled) return;
    try {
      task.result = task.hasEnv ? callI32EnvBranch(task.branch, task.env) : callI32Branch(task.branch);
    } catch (err) {
      task.error = err;
      task.result = 0;
    }
    task.done = true;
    var waiters = task.waiters.splice(0, task.waiters.length);
    for (var i = 0; i < waiters.length; i++) waiters[i](task.result | 0);
  }

  function createTask(branch, env, hasEnv) {
    var id = nextTaskId++;
    tasks[id] = { branch: branch, env: env || 0, hasEnv: !!hasEnv, result: 0, done: false, cancelled: false, waiters: [] };
    return id;
  }

  function startTask(branch) {
    var id = createTask(branch, 0, false);
    var task = tasks[id];
    if (hasAsyncify()) setTimeout(function () { runTask(task); }, 0);
    else runTask(task);
    return id;
  }

  function startEnvTask(branch, env) {
    var id = createTask(branch, env, true);
    var task = tasks[id];
    if (hasAsyncify()) setTimeout(function () { runTask(task); }, 0);
    else runTask(task);
    return id;
  }

  function joinTask(id) {
    var task = tasks[Number(id || 0)];
    if (!task) return 0;
    if (task.done || !hasAsyncify()) {
      if (!task.done) runTask(task);
      var immediate = task.result | 0;
      delete tasks[Number(id || 0)];
      return immediate;
    }
    return Asyncify.handleSleep(function (wakeUp) {
      task.waiters.push(function (result) {
        delete tasks[Number(id || 0)];
        wakeUp(result | 0);
      });
    });
  }

  function readBranchPtr(branches, index) {
    var ptrSize = typeof HEAPU32 !== 'undefined' && HEAPU32.BYTES_PER_ELEMENT ? HEAPU32.BYTES_PER_ELEMENT : 4;
    return HEAPU32[(Number(branches) + index * ptrSize) >> 2] || 0;
  }

  function setI32(ptr, value) {
    if (ptr) HEAP32[Number(ptr) >> 2] = value | 0;
  }

  function finishRace(state, result, timedOut) {
    if (state.finished) return;
    state.finished = true;
    state.result = result | 0;
    if (state.timer) clearTimeout(state.timer);
    setI32(state.timedOutPtr, timedOut ? 1 : 0);
    var waiters = state.waiters.splice(0, state.waiters.length);
    for (var i = 0; i < waiters.length; i++) waiters[i](result | 0);
  }

  function startRace(branches, count, timeoutMs, timedOutPtr) {
    var state = { finished: false, result: 0, timer: 0, waiters: [], timedOutPtr: timedOutPtr };
    setI32(timedOutPtr, 0);
    var total = Number(count || 0) | 0;
    if (!branches || total <= 0) {
      finishRace(state, 0, false);
      return state;
    }
    for (var i = 0; i < total; i++) {
      (function (branchPtr) {
        var run = function () {
          if (state.finished) return;
          var result = callI32Branch(branchPtr);
          finishRace(state, result, false);
        };
        if (hasAsyncify()) setTimeout(run, 0);
        else run();
      })(readBranchPtr(branches, i));
      if (state.finished && !hasAsyncify()) break;
    }
    var delay = Number(timeoutMs || 0);
    if (hasAsyncify() && delay > 0) {
      state.timer = setTimeout(function () { finishRace(state, 0, true); }, delay);
    }
    return state;
  }

  function waitRace(state) {
    if (state.finished || !hasAsyncify()) return state.result | 0;
    return Asyncify.handleSleep(function (wakeUp) {
      state.waiters.push(function (result) { wakeUp(result | 0); });
    });
  }

  mergeInto(LibraryManager.library, {
    __ezrt_task_join_i32__async: 'auto',
    __ezrt_task_start_i32: function (branch) {
      return startTask(branch) | 0;
    },
    __ezrt_task_start_env_i32: function (branch, env) {
      return startEnvTask(branch, env) | 0;
    },
    __ezrt_task_join_i32: function (handle) {
      return joinTask(handle) | 0;
    },
    __ezrt_race_i32__async: 'auto',
    __ezrt_race_i32: function (branches, count, timeoutMs, timedOutPtr) {
      var state = startRace(branches, count, timeoutMs, timedOutPtr);
      if (state.finished || !hasAsyncify()) return state.result | 0;
      return waitRace(state) | 0;
    },
  });
})();
