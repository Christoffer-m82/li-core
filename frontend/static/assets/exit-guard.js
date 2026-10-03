/* Best-effort browser warning only. Never save, send, retry, or trap navigation. */
(() => {
  function create({ window, hasPendingWork }) {
    let attached = false;
    function warn(event) {
      if (!hasPendingWork()) return;
      event.preventDefault();
      event.returnValue = true; // Legacy browsers use their own generic warning.
    }
    function refresh() {
      const pending = Boolean(hasPendingWork());
      if (pending === attached) return;
      if (pending) window.addEventListener('beforeunload', warn);
      else window.removeEventListener('beforeunload', warn);
      attached = pending;
    }
    return { refresh };
  }
  (typeof window === 'undefined' ? globalThis : window).LiExitGuard = { create };
})();
