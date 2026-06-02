// EzLang std/regex Emscripten JS 封装层
(function () {
  var PTR = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;

  function text(ptr) {
    return UTF8ToString(ptr || 0);
  }

  function writeStrList(ret, items) {
    var pageCount = items.length === 0 ? 0 : Math.ceil(items.length / 8);
    var pagesPtr = pageCount === 0 ? 0 : _malloc(pageCount * PTR);
    for (var page = 0; page < pageCount; page++) {
      var pagePtr = _malloc(8 * PTR);
      setValue(pagesPtr + page * PTR, pagePtr, '*');
      for (var offset = 0; offset < 8; offset++) {
        var idx = page * 8 + offset;
        setValue(pagePtr + offset * PTR, idx < items.length ? stringToNewUTF8(items[idx]) : 0, '*');
      }
    }
    setValue(ret, pagesPtr, '*');
    setValue(ret + 8, items.length, 'i64');
    setValue(ret + 16, pageCount * 8, 'i64');
    setValue(ret + 24, pageCount, 'i64');
  }

  function readRegex(ptr) {
    if (!ptr) return { pattern: '', flags: 0, ok: false };
    return {
      pattern: text(getValue(ptr, '*')),
      flags: getValue(ptr + PTR, 'i32') | 0,
      ok: HEAPU8[ptr + PTR + 4] !== 0,
    };
  }

  function writeRegex(ptr, value) {
    setValue(ptr, stringToNewUTF8(value.pattern || ''), '*');
    setValue(ptr + PTR, value.flags | 0, 'i32');
    HEAPU8[ptr + PTR + 4] = value.ok ? 1 : 0;
  }

  function jsFlags(flags, forceGlobal) {
    var out = forceGlobal ? 'g' : '';
    if (flags & 1) out += 'i';
    if (flags & 2) out += 'm';
    return out;
  }

  function compile(regex, forceGlobal) {
    if (!regex.ok) return null;
    try {
      return new RegExp(regex.pattern, jsFlags(regex.flags, forceGlobal));
    } catch (e) {
      return null;
    }
  }

  function writeMatch(ptr, match) {
    setValue(ptr, BigInt(match.start), 'i64');
    setValue(ptr + 8, BigInt(match.end), 'i64');
    setValue(ptr + 16, stringToNewUTF8(match.text || ''), '*');
    writeStrList(ptr + 24, match.groups || []);
  }

  function matchOf(re, input) {
    var m = re.exec(input);
    if (!m) return null;
    return {
      start: m.index,
      end: m.index + m[0].length,
      text: m[0],
      groups: m.slice(1).map(function (value) { return value || ''; }),
    };
  }

  mergeInto(LibraryManager.library, {
    regexCompile: function (ret, pattern, flags) {
      var textPattern = text(pattern);
      var ok = true;
      try { new RegExp(textPattern, jsFlags(flags | 0, false)); } catch (e) { ok = false; }
      writeRegex(ret, { pattern: textPattern, flags: flags | 0, ok: ok });
    },
    regexIsValid: function (regexPtr) {
      return readRegex(regexPtr).ok ? 1 : 0;
    },
    regexTest: function (regexPtr, inputPtr) {
      var re = compile(readRegex(regexPtr), false);
      return re && re.test(text(inputPtr)) ? 1 : 0;
    },
    regexFind: function (ret, regexPtr, inputPtr) {
      var re = compile(readRegex(regexPtr), false);
      var input = text(inputPtr);
      var match = re ? matchOf(re, input) : null;
      HEAPU8[ret] = match ? 1 : 0;
      writeMatch(ret + 8, match || { start: 0, end: 0, text: '', groups: [] });
    },
    regexFindAll: function (ret, regexPtr, inputPtr) {
      var re = compile(readRegex(regexPtr), true);
      var input = text(inputPtr);
      var items = [];
      if (re) {
        var m;
        while ((m = re.exec(input)) !== null) {
          items.push(m[0]);
          if (m[0].length === 0) re.lastIndex++;
        }
      }
      writeStrList(ret, items);
    },
    regexReplace: function (regexPtr, inputPtr, replacementPtr) {
      var re = compile(readRegex(regexPtr), false);
      var input = text(inputPtr);
      return stringToNewUTF8(re ? input.replace(re, text(replacementPtr)) : input);
    },
    regexSplit: function (ret, regexPtr, inputPtr) {
      var re = compile(readRegex(regexPtr), true);
      var input = text(inputPtr);
      writeStrList(ret, re ? input.split(re) : [input]);
    },
  });
})();
