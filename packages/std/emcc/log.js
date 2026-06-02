// EzLang std/log Emscripten JS 封装层
(function () {
  var config = { minLevel: 2, target: 2, includeTimestamp: 1, includeLocation: 1 };
  var PTR = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;

  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function levelName(level) {
    return ['TRACE', 'DEBUG', 'INFO', 'WARN', 'ERROR'][level] || 'LOG';
  }

  function listGet(listPtr, index) {
    if (!listPtr) return '';
    var pages = getValue(listPtr, '*');
    var length = Number(getValue(listPtr + 8, 'i64'));
    if (!pages || index < 0 || index >= length) return '';
    var pagePtr = getValue(pages + Math.floor(index / 8) * PTR, '*');
    if (!pagePtr) return '';
    return text(getValue(pagePtr + (index % 8) * PTR, '*'));
  }

  function listLength(listPtr) {
    return listPtr ? Number(getValue(listPtr + 8, 'i64')) : 0;
  }

  function readConfig(ptr) {
    if (!ptr) return config;
    return {
      minLevel: getValue(ptr, 'i32') | 0,
      target: getValue(ptr + 4, 'i32') | 0,
      includeTimestamp: HEAPU8[ptr + 8] ? 1 : 0,
      includeLocation: HEAPU8[ptr + 9] ? 1 : 0,
    };
  }

  function writeConfig(ret, value) {
    setValue(ret, value.minLevel | 0, 'i32');
    setValue(ret + 4, value.target | 0, 'i32');
    HEAPU8[ret + 8] = value.includeTimestamp ? 1 : 0;
    HEAPU8[ret + 9] = value.includeLocation ? 1 : 0;
  }

  function write(level, msg, file, line, column, fieldsPtr) {
    if (level < config.minLevel) return;
    var parts = [];
    if (config.includeTimestamp) parts.push(String(Date.now()));
    parts.push(levelName(level));
    parts.push(text(msg));
    var fileText = text(file);
    if (config.includeLocation && fileText) parts.push('@ ' + fileText + ':' + (line | 0) + ':' + (column | 0));
    for (var i = 0; i + 1 < listLength(fieldsPtr); i += 2) parts.push(listGet(fieldsPtr, i) + '=' + listGet(fieldsPtr, i + 1));
    var lineText = parts.join(' ');
    if (level >= 4 && console.error) console.error(lineText);
    else if (level >= 3 && console.warn) console.warn(lineText);
    else if (console.log) console.log(lineText);
  }

  mergeInto(LibraryManager.library, {
    logDefaultConfig: function (ret) {
      writeConfig(ret, { minLevel: 2, target: 2, includeTimestamp: 1, includeLocation: 1 });
    },
    logConfigure: function (configPtr) {
      config = readConfig(configPtr);
    },
    logSetLevel: function (level) {
      config.minLevel = level | 0;
    },
    logWrite: function (level, msg) {
      write(level | 0, msg, 0, 0, 0, 0);
    },
    logWriteFields: function (level, msg, fields) {
      write(level | 0, msg, 0, 0, 0, fields);
    },
    logWriteAt: function (level, msg, file, line, column, fields) {
      write(level | 0, msg, file, line, column, fields);
    },
    logTraceMsg: function (msg) { write(0, msg, 0, 0, 0, 0); },
    logDebugMsg: function (msg) { write(1, msg, 0, 0, 0, 0); },
    logInfoMsg: function (msg) { write(2, msg, 0, 0, 0, 0); },
    logWarnMsg: function (msg) { write(3, msg, 0, 0, 0, 0); },
    logErrorMsg: function (msg) { write(4, msg, 0, 0, 0, 0); },
  });
})();
