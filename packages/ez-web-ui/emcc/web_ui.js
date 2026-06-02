// ez-web-ui Emscripten DOM 绑定层
(function () {
  var nextId = 1;
  var nodes = Object.create(null);

  function text(ptr) { return UTF8ToString(ptr || 0); }
  function node(id) { return nodes[id | 0] || null; }
  function store(value) {
    if (!value) return { id: 0 };
    var id = nextId++;
    nodes[id] = value;
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
  function writeRect(ret, rect) {
    setValue(ret, rect.x || 0, 'float');
    setValue(ret + 4, rect.y || 0, 'float');
    setValue(ret + 8, rect.width || 0, 'float');
    setValue(ret + 12, rect.height || 0, 'float');
  }

  mergeInto(LibraryManager.library, {
    createElement: function (ret, tag) { writeNode(ret, store(typeof document !== 'undefined' ? document.createElement(text(tag) || 'div') : null)); },
    createTextNode: function (ret, content) { writeNode(ret, store(typeof document !== 'undefined' ? document.createTextNode(text(content)) : null)); },
    destroyNode: function (nodeValue) { delete nodes[nodeValue && nodeValue.id || nodeValue | 0]; },
    appendChild: function (parent, child) { var p = node(parent.id || parent); var c = node(child.id || child); if (p && c) p.appendChild(c); },
    insertBefore: function (parent, child, ref) { var p = node(parent.id || parent); var c = node(child.id || child); var r = node(ref.id || ref); if (p && c) p.insertBefore(c, r || null); },
    removeChild: function (parent, child) { var p = node(parent.id || parent); var c = node(child.id || child); if (p && c && c.parentNode === p) p.removeChild(c); },
    replaceChild: function (parent, newChild, oldChild) { var p = node(parent.id || parent); var n = node(newChild.id || newChild); var o = node(oldChild.id || oldChild); if (p && n && o) p.replaceChild(n, o); },
    getParent: function (ret, nodeValue) { var n = node(nodeValue.id || nodeValue); writeOptNode(ret, n && n.parentNode ? store(n.parentNode) : null); },
    getHostNode: function (ret, selector) { writeOptNode(ret, typeof document !== 'undefined' ? store(document.querySelector(text(selector))) : null); },
    getAttribute: function (ret, nodeValue, key) { var n = node(nodeValue.id || nodeValue); writeOptStr(ret, n ? n.getAttribute(text(key)) : null); },
    setAttribute: function (nodeValue, key, value) { var n = node(nodeValue.id || nodeValue); if (n) n.setAttribute(text(key), text(value)); },
    removeAttribute: function (nodeValue, key) { var n = node(nodeValue.id || nodeValue); if (n) n.removeAttribute(text(key)); },
    getProperty: function (nodeValue, key) { var n = node(nodeValue.id || nodeValue); var k = text(key); return stringToNewUTF8(n && n[k] != null ? String(n[k]) : ''); },
    setProperty: function (nodeValue, key, value) { var n = node(nodeValue.id || nodeValue); if (n) n[text(key)] = text(value); },
    getStyle: function (nodeValue, prop) { var n = node(nodeValue.id || nodeValue); return stringToNewUTF8(n && n.style ? String(n.style[text(prop)] || '') : ''); },
    setStyle: function (nodeValue, prop, value) { var n = node(nodeValue.id || nodeValue); if (n && n.style) n.style[text(prop)] = text(value); },
    addClass: function (nodeValue, name) { var n = node(nodeValue.id || nodeValue); if (n && n.classList) n.classList.add(text(name)); },
    removeClass: function (nodeValue, name) { var n = node(nodeValue.id || nodeValue); if (n && n.classList) n.classList.remove(text(name)); },
    hasClass: function (nodeValue, name) { var n = node(nodeValue.id || nodeValue); return n && n.classList && n.classList.contains(text(name)) ? 1 : 0; },
    setClassName: function (nodeValue, name) { var n = node(nodeValue.id || nodeValue); if (n) n.className = text(name); },
    getComputedStyle: function (nodeValue, prop) { var n = node(nodeValue.id || nodeValue); var value = n && typeof getComputedStyle === 'function' ? getComputedStyle(n).getPropertyValue(text(prop)) : ''; return stringToNewUTF8(value || ''); },
    getTextContent: function (nodeValue) { var n = node(nodeValue.id || nodeValue); return stringToNewUTF8(n ? n.textContent || '' : ''); },
    setTextContent: function (nodeValue, value) { var n = node(nodeValue.id || nodeValue); if (n) n.textContent = text(value); },
    getInnerHTML: function (nodeValue) { var n = node(nodeValue.id || nodeValue); return stringToNewUTF8(n ? n.innerHTML || '' : ''); },
    setInnerHTML: function (nodeValue, value) { var n = node(nodeValue.id || nodeValue); if (n) n.innerHTML = text(value); },
    getBoundingRect: function (ret, nodeValue) { var n = node(nodeValue.id || nodeValue); writeRect(ret, n && n.getBoundingClientRect ? n.getBoundingClientRect() : {}); },
    getScrollTop: function (nodeValue) { var n = node(nodeValue.id || nodeValue); return n ? +n.scrollTop || 0 : 0; },
    getScrollLeft: function (nodeValue) { var n = node(nodeValue.id || nodeValue); return n ? +n.scrollLeft || 0 : 0; },
    setScrollTop: function (nodeValue, value) { var n = node(nodeValue.id || nodeValue); if (n) n.scrollTop = +value || 0; },
    focus_: function (nodeValue) { var n = node(nodeValue.id || nodeValue); if (n && n.focus) n.focus(); },
    blur_: function (nodeValue) { var n = node(nodeValue.id || nodeValue); if (n && n.blur) n.blur(); },
    scheduleFrame: function (cb) { return typeof requestAnimationFrame === 'function' ? requestAnimationFrame(function () { if (cb) dynCall_v(cb); }) : 0; },
    cancelFrame: function (id) { if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(id); },
    scheduleMicrotask: function (cb) { (typeof queueMicrotask === 'function' ? queueMicrotask : function (f) { Promise.resolve().then(f); })(function () { if (cb) dynCall_v(cb); }); },
    scheduleIdle: function () { return 0; },
    cancelIdle: function () {},
    requestPermission: function () { return 0; },
    queryPermission: function () { return stringToNewUTF8('unsupported'); },
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
