// ez-web-ui Emscripten DOM 绑定层
(function () {
  var nextId = 1;
  var nodes = Object.create(null);
  var listeners = Object.create(null);
  var activeEvents = Object.create(null);

  function text(ptr) { return UTF8ToString(ptr || 0); }
  function node(id) { return nodes[id | 0] || null; }
  function readNodeId(ptr) { return ptr ? getValue(ptr, 'i32') | 0 : 0; }
  function nodeFromPtr(ptr) { return node(readNodeId(ptr)); }
  function store(value) {
    if (!value) return { id: 0 };
    var id = nextId++;
    nodes[id] = value;
    try { value.__ezNodeId = id; } catch (e) {}
    return { id: id };
  }
  function writeNode(ret, n) { setValue(ret, (n && n.id) || 0, 'i32'); }
  function writeOptNode(ret, n) {
    HEAPU8[ret] = n && n.id ? 1 : 0;
    setValue(ret + 4, (n && n.id) || 0, 'i32');
  }
  function writeOptStr(ret, value) {
    HEAPU8[ret] = value == null ? 0 : 1;
    setValue(ret + 8, value == null ? 0 : stringToNewUTF8(String(value)), '*');
  }
  function writeOptBlob(ptr, bytes) {
    HEAPU8[ptr] = bytes && bytes.length ? 1 : 0;
    var dataPtr = 0;
    if (bytes && bytes.length) {
      dataPtr = _malloc(bytes.length);
      HEAPU8.set(bytes, dataPtr);
    }
    setValue(ptr + 8, dataPtr, '*');
    setValue(ptr + 16, bytes && bytes.length ? bytes.length : 0, 'i64');
  }
  function writeRect(ret, rect) {
    setValue(ret, rect.x || 0, 'float');
    setValue(ret + 4, rect.y || 0, 'float');
    setValue(ret + 8, rect.width || 0, 'float');
    setValue(ret + 12, rect.height || 0, 'float');
  }
  function writeNodeList(ret, items) {
    var ptrSize = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
    var pageCount = items.length === 0 ? 0 : Math.ceil(items.length / 8);
    var pagesPtr = pageCount === 0 ? 0 : _malloc(pageCount * ptrSize);
    for (var page = 0; page < pageCount; page++) {
      var pagePtr = _malloc(8 * 4);
      setValue(pagesPtr + page * ptrSize, pagePtr, '*');
      for (var offset = 0; offset < 8; offset++) {
        var idx = page * 8 + offset;
        setValue(pagePtr + offset * 4, idx < items.length ? (items[idx].id || 0) : 0, 'i32');
      }
    }
    setValue(ret, pagesPtr, '*');
    setValue(ret + 8, items.length, 'i64');
    setValue(ret + 16, pageCount * 8, 'i64');
    setValue(ret + 24, pageCount, 'i64');
  }
  function readDict(dictPtr) {
    var out = [];
    if (!dictPtr) return out;
    var keyPages = getValue(dictPtr, '*');
    var valuePages = getValue(dictPtr + 4, '*');
    var count = getValue(dictPtr + 8, 'i32') | 0;
    var pageCount = getValue(dictPtr + 16, 'i32') | 0;
    var ptrSize = typeof POINTER_SIZE !== 'undefined' ? POINTER_SIZE : 4;
    for (var i = 0; i < count; i++) {
      var page = (i / 8) | 0;
      var slot = i % 8;
      if (page >= pageCount) break;
      var keyPage = getValue(keyPages + page * ptrSize, '*');
      var valuePage = getValue(valuePages + page * ptrSize, '*');
      if (!keyPage || !valuePage) continue;
      var keyPtr = getValue(keyPage + slot * ptrSize, '*');
      var valuePtr = getValue(valuePage + slot * ptrSize, '*');
      out.push([text(keyPtr), text(valuePtr)]);
    }
    return out;
  }
  function callVoid(cb) {
    if (!cb) return;
    if (typeof dynCall_v === 'function') return dynCall_v(cb);
    if (typeof wasmTable !== 'undefined') return wasmTable.get(cb)();
  }
  function callEvent(cb, event) {
    if (!cb) return;
    var eventPtr = _malloc(32);
    var dataText = event && event.target && event.target.value != null ? String(event.target.value) : '';
    var bytes = typeof TextEncoder !== 'undefined' ? new TextEncoder().encode(dataText) : new Uint8Array(0);
    setValue(eventPtr, stringToNewUTF8(event.type || ''), '*');
    setValue(eventPtr + 4, event.target && event.target.__ezNodeId ? event.target.__ezNodeId : 0, 'i32');
    writeOptBlob(eventPtr + 8, bytes);
    activeEvents[eventPtr] = event;
    if (typeof dynCall_vi === 'function') dynCall_vi(cb, eventPtr);
    else if (typeof wasmTable !== 'undefined') wasmTable.get(cb)(eventPtr);
    delete activeEvents[eventPtr];
    _free(eventPtr);
  }
  function listenerKey(id, event, cb) { return id + ':' + event + ':' + cb; }
  function rememberListener(id, event, cb, fn) { listeners[listenerKey(id, event, cb)] = fn; }
  function takeListener(id, event, cb) {
    var key = listenerKey(id, event, cb);
    var fn = listeners[key];
    delete listeners[key];
    return fn;
  }

  mergeInto(LibraryManager.library, {
    createElement: function (ret, tag) {
      var created = typeof document !== 'undefined' ? document.createElement(text(tag) || 'div') : null;
      var stored = store(created);
      if (created) created.__ezNodeId = stored.id;
      writeNode(ret, stored);
    },
    createTextNode: function (ret, content) {
      var created = typeof document !== 'undefined' ? document.createTextNode(text(content)) : null;
      var stored = store(created);
      if (created) created.__ezNodeId = stored.id;
      writeNode(ret, stored);
    },
    destroyNode: function (nodeValue) { delete nodes[readNodeId(nodeValue)]; },
    appendChild: function (parent, child) { var p = nodeFromPtr(parent); var c = nodeFromPtr(child); if (p && c) p.appendChild(c); },
    insertBefore: function (parent, child, ref) { var p = nodeFromPtr(parent); var c = nodeFromPtr(child); var r = nodeFromPtr(ref); if (p && c) p.insertBefore(c, r || null); },
    removeChild: function (parent, child) { var p = nodeFromPtr(parent); var c = nodeFromPtr(child); if (p && c && c.parentNode === p) p.removeChild(c); },
    replaceChild: function (parent, newChild, oldChild) { var p = nodeFromPtr(parent); var n = nodeFromPtr(newChild); var o = nodeFromPtr(oldChild); if (p && n && o) p.replaceChild(n, o); },
    getParent: function (ret, nodeValue) { var n = nodeFromPtr(nodeValue); writeOptNode(ret, n && n.parentNode ? store(n.parentNode) : null); },
    getChildren: function (ret, nodeValue) {
      var n = nodeFromPtr(nodeValue);
      var items = n && n.childNodes ? Array.prototype.map.call(n.childNodes, function (child) { return store(child); }) : [];
      writeNodeList(ret, items);
    },
    getHostNode: function (ret, selector) { writeOptNode(ret, typeof document !== 'undefined' ? store(document.querySelector(text(selector))) : null); },
    getAttribute: function (ret, nodeValue, key) { var n = nodeFromPtr(nodeValue); writeOptStr(ret, n ? n.getAttribute(text(key)) : null); },
    setAttribute: function (nodeValue, key, value) { var n = nodeFromPtr(nodeValue); if (n) n.setAttribute(text(key), text(value)); },
    removeAttribute: function (nodeValue, key) { var n = nodeFromPtr(nodeValue); if (n) n.removeAttribute(text(key)); },
    setAttributes: function (nodeValue, attrs) { var n = nodeFromPtr(nodeValue); if (n) readDict(attrs).forEach(function (item) { n.setAttribute(item[0], item[1]); }); },
    getProperty: function (nodeValue, key) { var n = nodeFromPtr(nodeValue); var k = text(key); return stringToNewUTF8(n && n[k] != null ? String(n[k]) : ''); },
    setProperty: function (nodeValue, key, value) { var n = nodeFromPtr(nodeValue); if (n) n[text(key)] = text(value); },
    getStyle: function (nodeValue, prop) { var n = nodeFromPtr(nodeValue); return stringToNewUTF8(n && n.style ? String(n.style[text(prop)] || '') : ''); },
    setStyle: function (nodeValue, prop, value) { var n = nodeFromPtr(nodeValue); if (n && n.style) n.style[text(prop)] = text(value); },
    setStyles: function (nodeValue, styles) { var n = nodeFromPtr(nodeValue); if (n && n.style) readDict(styles).forEach(function (item) { n.style[item[0]] = item[1]; }); },
    addClass: function (nodeValue, name) { var n = nodeFromPtr(nodeValue); if (n && n.classList) n.classList.add(text(name)); },
    removeClass: function (nodeValue, name) { var n = nodeFromPtr(nodeValue); if (n && n.classList) n.classList.remove(text(name)); },
    hasClass: function (nodeValue, name) { var n = nodeFromPtr(nodeValue); return n && n.classList && n.classList.contains(text(name)) ? 1 : 0; },
    setClassName: function (nodeValue, name) { var n = nodeFromPtr(nodeValue); if (n) n.className = text(name); },
    getComputedStyle: function (nodeValue, prop) { var n = nodeFromPtr(nodeValue); var value = n && typeof getComputedStyle === 'function' ? getComputedStyle(n).getPropertyValue(text(prop)) : ''; return stringToNewUTF8(value || ''); },
    getTextContent: function (nodeValue) { var n = nodeFromPtr(nodeValue); return stringToNewUTF8(n ? n.textContent || '' : ''); },
    setTextContent: function (nodeValue, value) { var n = nodeFromPtr(nodeValue); if (n) n.textContent = text(value); },
    getInnerHTML: function (nodeValue) { var n = nodeFromPtr(nodeValue); return stringToNewUTF8(n ? n.innerHTML || '' : ''); },
    setInnerHTML: function (nodeValue, value) { var n = nodeFromPtr(nodeValue); if (n) n.innerHTML = text(value); },
    addEventListener: function (nodeValue, event, handler, capture) {
      var n = nodeFromPtr(nodeValue);
      var e = text(event);
      var id = readNodeId(nodeValue);
      if (!n) return;
      var fn = function (ev) { callEvent(handler, ev); };
      rememberListener(id, e, handler, fn);
      n.addEventListener(e, fn, !!capture);
    },
    removeEventListener: function (nodeValue, event, handler) {
      var n = nodeFromPtr(nodeValue);
      var e = text(event);
      var fn = takeListener(readNodeId(nodeValue), e, handler);
      if (n && fn) n.removeEventListener(e, fn);
    },
    delegateEvent: function (parent, event, selector, handler) {
      var p = nodeFromPtr(parent);
      var e = text(event);
      var sel = text(selector);
      if (!p) return;
      p.addEventListener(e, function (ev) {
        var target = ev.target && ev.target.closest ? ev.target.closest(sel) : null;
        if (target && p.contains(target)) callEvent(handler, ev);
      });
    },
    getEventValue: function (eventPtr) {
      if (!eventPtr || !HEAPU8[eventPtr + 8]) return stringToNewUTF8('');
      var dataPtr = getValue(eventPtr + 16, '*');
      var size = Number(getValue(eventPtr + 24, 'i64'));
      if (!dataPtr || size <= 0) return stringToNewUTF8('');
      var bytes = HEAPU8.slice(dataPtr, dataPtr + size);
      if (typeof TextDecoder !== 'undefined') return stringToNewUTF8(new TextDecoder('utf-8').decode(bytes));
      var out = '';
      for (var i = 0; i < bytes.length; i++) out += String.fromCharCode(bytes[i]);
      return stringToNewUTF8(out);
    },
    getEventKey: function (eventPtr) { var ev = activeEvents[eventPtr]; return stringToNewUTF8(ev && ev.key ? ev.key : ''); },
    getEventClientX: function (eventPtr) { var ev = activeEvents[eventPtr]; return ev && ev.clientX != null ? +ev.clientX || 0 : 0; },
    getEventClientY: function (eventPtr) { var ev = activeEvents[eventPtr]; return ev && ev.clientY != null ? +ev.clientY || 0 : 0; },
    preventDefault: function (eventPtr) { var ev = activeEvents[eventPtr]; if (ev && ev.preventDefault) ev.preventDefault(); },
    stopPropagation: function (eventPtr) { var ev = activeEvents[eventPtr]; if (ev && ev.stopPropagation) ev.stopPropagation(); },
    getBoundingRect: function (ret, nodeValue) { var n = nodeFromPtr(nodeValue); writeRect(ret, n && n.getBoundingClientRect ? n.getBoundingClientRect() : {}); },
    getScrollTop: function (nodeValue) { var n = nodeFromPtr(nodeValue); return n ? +n.scrollTop || 0 : 0; },
    getScrollLeft: function (nodeValue) { var n = nodeFromPtr(nodeValue); return n ? +n.scrollLeft || 0 : 0; },
    setScrollTop: function (nodeValue, value) { var n = nodeFromPtr(nodeValue); if (n) n.scrollTop = +value || 0; },
    focus_: function (nodeValue) { var n = nodeFromPtr(nodeValue); if (n && n.focus) n.focus(); },
    blur_: function (nodeValue) { var n = nodeFromPtr(nodeValue); if (n && n.blur) n.blur(); },
    scheduleFrame: function (cb) { return typeof requestAnimationFrame === 'function' ? requestAnimationFrame(function () { callVoid(cb); }) : 0; },
    cancelFrame: function (id) { if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(id); },
    scheduleMicrotask: function (cb) { (typeof queueMicrotask === 'function' ? queueMicrotask : function (f) { Promise.resolve().then(f); })(function () { callVoid(cb); }); },
    scheduleIdle: function (cb) { return typeof requestIdleCallback === 'function' ? requestIdleCallback(function (deadline) { if (cb) { if (typeof dynCall_vd === 'function') dynCall_vd(cb, deadline.timeRemaining()); else if (typeof wasmTable !== 'undefined') wasmTable.get(cb)(deadline.timeRemaining()); } }) : 0; },
    cancelIdle: function (id) { if (typeof cancelIdleCallback === 'function') cancelIdleCallback(id); },
    requestPermission: function (perm) { return typeof navigator !== 'undefined' && navigator.permissions && text(perm) ? 1 : 0; },
    queryPermission: function (perm) { return stringToNewUTF8(typeof navigator !== 'undefined' && navigator.permissions && text(perm) ? 'prompt' : 'unsupported'); },
    getWindowWidth: function () { return typeof window !== 'undefined' ? +window.innerWidth || 0 : 0; },
    getWindowHeight: function () { return typeof window !== 'undefined' ? +window.innerHeight || 0 : 0; },
    getDocumentNode: function (ret) { writeNode(ret, typeof document !== 'undefined' ? store(document.documentElement) : null); },
    getBodyNode: function (ret) { writeNode(ret, typeof document !== 'undefined' ? store(document.body) : null); },
    getLocation: function () { return stringToNewUTF8(typeof window !== 'undefined' ? window.location.href : ''); },
    setLocation: function (url) { if (typeof window !== 'undefined') window.location.href = text(url); },
    historyPush: function (url) { if (typeof history !== 'undefined') history.pushState(null, '', text(url)); },
    historyReplace: function (url) { if (typeof history !== 'undefined') history.replaceState(null, '', text(url)); }
  });
})();
