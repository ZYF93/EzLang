// EzLang std/regex Emscripten JS 封装层
(function () {
  var PTR = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
  var MAX_PATTERN_BYTES = 4096;
  var MAX_GROUPS = 64;
  var MAX_BOUNDED_REPEAT = 1024;

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
    if (!regex.ok || !safePattern(regex.pattern)) return null;
    try {
      return new RegExp(regex.pattern, jsFlags(regex.flags, forceGlobal));
    } catch (e) {
      return null;
    }
  }

  function pushPending(stack, pending) {
    if (!pending.exists || stack.length === 0) return;
    var frame = stack[stack.length - 1];
    frame.hasVariableRepeat = frame.hasVariableRepeat || pending.hasVariableRepeat;
    frame.hasAlternation = frame.hasAlternation || pending.hasAlternation;
    pending.exists = false;
    pending.hasVariableRepeat = false;
    pending.hasAlternation = false;
  }

  function parseInterval(pattern, start) {
    var i = start + 1;
    if (i >= pattern.length || !/[0-9]/.test(pattern.charAt(i))) return null;
    var min = 0;
    while (i < pattern.length && /[0-9]/.test(pattern.charAt(i))) {
      min = min * 10 + (pattern.charCodeAt(i) - 48);
      if (min > MAX_BOUNDED_REPEAT) return { invalid: true };
      i++;
    }
    var max = min;
    var hasMax = true;
    if (pattern.charAt(i) === ',') {
      i++;
      if (pattern.charAt(i) === '}') {
        hasMax = false;
      } else {
        if (i >= pattern.length || !/[0-9]/.test(pattern.charAt(i))) return null;
        max = 0;
        while (i < pattern.length && /[0-9]/.test(pattern.charAt(i))) {
          max = max * 10 + (pattern.charCodeAt(i) - 48);
          if (max > MAX_BOUNDED_REPEAT) return { invalid: true };
          i++;
        }
      }
    }
    if (pattern.charAt(i) !== '}') return null;
    if (hasMax && max < min) return null;
    return { end: i + 1, variable: !hasMax || max !== min };
  }

  function skipClass(pattern, start) {
    var i = start + 1;
    if (pattern.charAt(i) === '^') i++;
    if (pattern.charAt(i) === ']') i++;
    while (i < pattern.length) {
      if (pattern.charAt(i) === '\\' && i + 1 < pattern.length) {
        i += 2;
        continue;
      }
      if (pattern.charAt(i) === ']') return i + 1;
      i++;
    }
    return pattern.length;
  }

  function safePattern(pattern) {
    pattern = pattern || '';
    if (lengthBytesUTF8(pattern) > MAX_PATTERN_BYTES) return false;
    var stack = [{ hasVariableRepeat: false, hasAlternation: false }];
    var pending = { exists: false, hasVariableRepeat: false, hasAlternation: false };
    for (var i = 0; i < pattern.length;) {
      var ch = pattern.charAt(i);
      if (ch === '\\') {
        pushPending(stack, pending);
        pending = { exists: true, hasVariableRepeat: false, hasAlternation: false };
        i += i + 1 < pattern.length ? 2 : 1;
        continue;
      }
      if (ch === '[') {
        pushPending(stack, pending);
        pending = { exists: true, hasVariableRepeat: false, hasAlternation: false };
        i = skipClass(pattern, i);
        continue;
      }
      if (ch === '(') {
        pushPending(stack, pending);
        if (stack.length >= MAX_GROUPS + 1) return false;
        stack.push({ hasVariableRepeat: false, hasAlternation: false });
        i++;
        continue;
      }
      if (ch === ')') {
        pushPending(stack, pending);
        if (stack.length <= 1) {
          i++;
          continue;
        }
        var group = stack.pop();
        pending = { exists: true, hasVariableRepeat: group.hasVariableRepeat, hasAlternation: group.hasAlternation };
        i++;
        continue;
      }
      if (ch === '|') {
        pushPending(stack, pending);
        stack[stack.length - 1].hasAlternation = true;
        i++;
        continue;
      }
      if (ch === '?' || ch === '*' || ch === '+') {
        if (!pending.exists) {
          i++;
          continue;
        }
        if (pending.hasVariableRepeat || pending.hasAlternation) return false;
        pending.hasVariableRepeat = true;
        pushPending(stack, pending);
        i++;
        continue;
      }
      if (ch === '{' && pending.exists) {
        var interval = parseInterval(pattern, i);
        if (interval && interval.invalid) return false;
        if (interval) {
          if (interval.variable && (pending.hasVariableRepeat || pending.hasAlternation)) return false;
          if (interval.variable) pending.hasVariableRepeat = true;
          pushPending(stack, pending);
          i = interval.end;
          continue;
        }
      }
      pushPending(stack, pending);
      pending = { exists: true, hasVariableRepeat: false, hasAlternation: false };
      i++;
    }
    pushPending(stack, pending);
    return true;
  }

  function byteLengthPrefix(value, end) {
    return lengthBytesUTF8(value.slice(0, end));
  }

  function advanceOne(value, index) {
    if (index >= value.length) return index;
    var code = value.codePointAt(index);
    return index + (code > 0xffff ? 2 : 1);
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
      start: byteLengthPrefix(input, m.index),
      end: byteLengthPrefix(input, m.index + m[0].length),
      text: m[0],
      groups: m.slice(1).map(function (value) { return value || ''; }),
    };
  }

  function replaceLiteral(input, re, replacement, replaceAll) {
    if (!replaceAll) {
      var first = re.exec(input);
      if (!first) return input;
      return input.slice(0, first.index) + replacement + input.slice(first.index + first[0].length);
    }
    var out = '';
    var last = 0;
    var m;
    while ((m = re.exec(input)) !== null) {
      out += input.slice(last, m.index) + replacement;
      last = m.index + m[0].length;
      if (m[0].length === 0) {
        if (last >= input.length) break;
        var next = advanceOne(input, last);
        out += input.slice(last, next);
        last = next;
        re.lastIndex = last;
      }
    }
    return out + input.slice(last);
  }

  function splitNoCaptures(input, re) {
    var items = [];
    var last = 0;
    var m;
    while ((m = re.exec(input)) !== null) {
      items.push(input.slice(last, m.index));
      last = m.index + m[0].length;
      if (m[0].length === 0) {
        if (last >= input.length) break;
        last = advanceOne(input, last);
        re.lastIndex = last;
      }
    }
    items.push(input.slice(last));
    return items;
  }

  mergeInto(LibraryManager.library, {
    regexCompile: function (ret, pattern, flags) {
      var textPattern = text(pattern);
      var ok = safePattern(textPattern);
      try { if (ok) new RegExp(textPattern, jsFlags(flags | 0, false)); } catch (e) { ok = false; }
      writeRegex(ret, { pattern: textPattern, flags: flags | 0, ok: ok });
    },
    regexIsValid: function (regexPtr) {
      var regex = readRegex(regexPtr);
      return regex.ok && safePattern(regex.pattern) ? 1 : 0;
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
          if (m[0].length === 0) {
            if (re.lastIndex >= input.length) break;
            re.lastIndex = advanceOne(input, re.lastIndex);
          }
        }
      }
      writeStrList(ret, items);
    },
    regexReplace: function (regexPtr, inputPtr, replacementPtr) {
      var regex = readRegex(regexPtr);
      var replaceAll = (regex.flags & 4) !== 0;
      var re = compile(regex, replaceAll);
      var input = text(inputPtr);
      return stringToNewUTF8(re ? replaceLiteral(input, re, text(replacementPtr), replaceAll) : input);
    },
    regexSplit: function (ret, regexPtr, inputPtr) {
      var re = compile(readRegex(regexPtr), true);
      var input = text(inputPtr);
      writeStrList(ret, re ? splitNoCaptures(input, re) : [input]);
    },
  });
})();
