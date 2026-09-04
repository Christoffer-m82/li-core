(function (root) {
  const TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);
  const MAX_INPUT = 5 * 1024 * 1024;
  const MAX_SAVED = 512 * 1024;
  function initials() { return 'CM'; }
  function create({ document, fetch, URL, FormData, controls }) {
    const targets = new Set();
    let revision = 'absent', state = 'unknown', savedUrl = null, previewUrl = null;
    let selected = null, request = 0, busy = false;
    const status = message => { controls.status.textContent = message; };
    function fallback(target) { target.replaceChildren(document.createTextNode(initials())); }
    function render(target) {
      if (!savedUrl) { fallback(target); return; }
      const image = document.createElement('img'); image.alt = ''; image.src = savedUrl;
      image.addEventListener('error', () => fallback(target), {once:true}); target.replaceChildren(image);
    }
    function renderAll() { targets.forEach(target => { if (target.isConnected === false) targets.delete(target); else render(target); }); }
    function register(target) { targets.add(target); render(target); return target; }
    function avatar(className = 'workspace-avatar') {
      const target = document.createElement('span'); target.className = className;
      target.setAttribute('aria-hidden', 'true'); return register(target);
    }
    function setName() { renderAll(); controls.previewFallback.textContent = initials(); }
    function buttons(enabled) {
      controls.choose.disabled = !enabled || busy;
      controls.save.disabled = !enabled || busy || !selected;
      controls.cancel.disabled = busy || !selected;
      controls.remove.disabled = !enabled || busy || state !== 'available';
    }
    function refreshPreview() {
      const url = previewUrl || savedUrl;
      controls.previewImage.src = url || '';
      controls.previewImage.hidden = !url;
      controls.previewFallback.hidden = Boolean(url);
    }
    function setPreview(url) {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = url;
      refreshPreview();
    }
    async function load() {
      const current = ++request; status('Checking your private profile photo…'); buttons(false);
      try {
        const metadataResponse = await fetch('/api/profile/photo', {cache:'no-store'});
        if (!metadataResponse.ok) throw new Error('unavailable');
        const metadata = await metadataResponse.json();
        if (!metadata || !['available','empty'].includes(metadata.state) || typeof metadata.revision !== 'string') throw new Error('invalid');
        let nextUrl = null;
        if (metadata.state === 'available') {
          const imageResponse = await fetch('/api/profile/photo/image', {cache:'no-store'});
          if (!imageResponse.ok) throw new Error('unavailable');
          const blob = await imageResponse.blob();
          if (blob.type !== 'image/jpeg' || blob.size < 4 || blob.size > MAX_SAVED) throw new Error('invalid');
          nextUrl = URL.createObjectURL(blob);
        }
        if (current !== request) { if (nextUrl) URL.revokeObjectURL(nextUrl); return; }
        if (savedUrl) URL.revokeObjectURL(savedUrl);
        savedUrl = nextUrl; revision = metadata.revision; state = metadata.state; renderAll(); refreshPreview(); buttons(true);
        status(state === 'available' ? 'Your private profile photo is active.' : 'CM is shown until you add a profile photo.');
      } catch {
        if (current !== request) return;
        state = 'unavailable'; buttons(false);
        status(savedUrl ? 'Profile refresh is unavailable. Your current in-memory avatar is unchanged.' : 'Profile photos are not available yet. CM remains in use.');
      }
    }
    function select(file) {
      selected = null; setPreview(null);
      if (!file || !TYPES.has(file.type) || file.size < 1 || file.size > MAX_INPUT) {
        status('Choose one JPEG, PNG or WebP image up to 5 MB.'); buttons(state !== 'unavailable'); return false;
      }
      selected = file; setPreview(URL.createObjectURL(file));
      status('Preview only. The original stays on this device until you press Save photo.');
      buttons(state !== 'unavailable'); return true;
    }
    function cancel() { selected = null; controls.input.value = ''; setPreview(null); buttons(state !== 'unavailable'); status('Photo selection cancelled.'); }
    async function save() {
      if (!selected || busy || state === 'unavailable') return;
      busy = true; buttons(true); status('Saving a private profile-sized copy…');
      const data = new FormData(); data.append('photo', selected);
      try {
        const response = await fetch('/api/profile/photo', {method:'PUT', headers:{'If-Match':revision,'X-Li-Profile-Mutation':'1'}, body:data});
        if (!response.ok) throw new Error('save');
        cancel(); await load();
      } catch { status('Photo was not saved. Your current avatar is unchanged.'); }
      finally { busy = false; buttons(state !== 'unavailable'); }
    }
    async function remove(confirmed) {
      if (!confirmed || busy || state !== 'available') return;
      busy = true; buttons(true); status('Removing your profile photo…');
      try {
        const response = await fetch('/api/profile/photo', {method:'DELETE', headers:{'If-Match':revision,'X-Li-Profile-Mutation':'1'}});
        if (!response.ok) throw new Error('remove');
        cancel(); await load();
      } catch { status('Photo was not removed. Your current avatar is unchanged.'); }
      finally { busy = false; buttons(state !== 'unavailable'); }
    }
    function clear() {
      request++; state = 'unknown'; revision = 'absent'; selected = null;
      if (savedUrl) URL.revokeObjectURL(savedUrl); savedUrl = null; setPreview(null); renderAll(); buttons(false);
    }
    controls.choose.addEventListener('click', () => controls.input.click());
    controls.input.addEventListener('change', () => { select(controls.input.files[0]); });
    controls.previewImage.addEventListener('error', () => { controls.previewImage.hidden = true; controls.previewFallback.hidden = false; });
    controls.save.addEventListener('click', save); controls.cancel.addEventListener('click', cancel);
    return { register, avatar, setName, load, select, save, remove, clear, state:()=>state };
  }
  root.LiProfilePhoto = { create, initials, MAX_INPUT, MAX_SAVED };
})(typeof window === 'undefined' ? globalThis : window);
