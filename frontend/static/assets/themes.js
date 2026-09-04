/* Appearance data only: no imported HTML, scripts, URLs, or arbitrary CSS. */
(function (global) {
  'use strict';
  const fonts = Object.freeze({
    modern: 'Inter, ui-sans-serif, system-ui, "Segoe UI", sans-serif',
    humanist: 'Archivo, "Segoe UI", system-ui, sans-serif',
    editorial: 'Georgia, "Times New Roman", serif',
  });
  const colors = ['bg', 'surface', 'tile', 'text', 'muted', 'accent', 'onAccent'];
  const builtins = [
    { id: 'dark', name: 'Dark', mode: 'dark', bg: '#070812', surface: '#0e1120', tile: '#131729', text: '#f7f5ff', muted: '#a6a5bb', accent: '#a883ff', onAccent: '#171025', font: 'modern', radius: '22' },
    { id: 'light', name: 'Light', mode: 'light', bg: '#f5f4fa', surface: '#ffffff', tile: '#f3f1f9', text: '#191525', muted: '#706b7b', accent: '#7151c8', onAccent: '#ffffff', font: 'modern', radius: '22' },
    { id: 'forest', name: 'Forest', mode: 'light', bg: '#F6F4EF', surface: '#FFFFFF', tile: '#F7F5EF', text: '#14231D', muted: '#56655C', accent: '#1E5B44', onAccent: '#FFFFFF', font: 'humanist', radius: '20' },
  ].map(Object.freeze);
  const key = 'li-custom-themes-v1';
  function luminance(hex) {
    const values = hex.slice(1).match(/../g).map(value => parseInt(value, 16) / 255)
      .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
    return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
  }
  function contrast(a, b) {
    const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (values[0] + 0.05) / (values[1] + 0.05);
  }
  function validate(input) {
    if (!input || typeof input !== 'object' || typeof input.name !== 'string' || !input.name.trim() || input.name.trim().length > 40) throw new Error('Choose a theme name of 1–40 characters.');
    if (!['light', 'dark'].includes(input.mode) || !Object.hasOwn(fonts, input.font) || !['12', '20', '22', '28'].includes(input.radius)) throw new Error('Choose the supplied mode, font, and corner options.');
    for (const color of colors) if (typeof input[color] !== 'string' || !/^#[0-9a-f]{6}$/i.test(input[color])) throw new Error('Use six-digit hex colours.');
    for (const surface of ['bg', 'surface', 'tile']) {
      for (const foreground of ['text', 'muted', 'accent']) {
        if (contrast(input[foreground], input[surface]) < 4.5) throw new Error('Text, secondary text, and accent need at least 4.5:1 contrast on every surface. Darken text or lighten surfaces (reverse for dark themes).');
      }
    }
    if (contrast(input.accent, input.onAccent) < 4.5) throw new Error('Button text needs at least 4.5:1 contrast against the accent.');
    return Object.fromEntries(['name', 'mode', ...colors, 'font', 'radius'].map(field => [field, field === 'name' ? input.name.trim() : input[field]]));
  }
  function library(storage) {
    let custom = [];
    try {
      const saved = JSON.parse(storage.getItem(key) || '[]');
      if (Array.isArray(saved)) for (const item of saved) {
        try {
          if (/^custom-[a-z0-9-]+$/.test(item.id) && !custom.some(theme => theme.id === item.id)) custom.push({ ...validate(item), id: item.id });
        } catch { /* An invalid saved theme cannot execute or break the app. */ }
      }
    } catch { /* Storage may be disabled or corrupted. Built-ins still work. */ }
    return {
      all: () => [...builtins, ...custom],
      find: id => [...builtins, ...custom].find(theme => theme.id === id) || builtins[0],
      save(input, id) {
        if (!/^custom-[a-z0-9-]+$/.test(id) || custom.some(theme => theme.id === id)) throw new Error('Please try saving again with a new theme identifier.');
        const theme = { ...validate(input), id };
        const next = [...custom, theme];
        try { storage.setItem(key, JSON.stringify(next)); } catch { throw new Error('This browser cannot save more themes. Check available browser storage.'); }
        custom = next;
        return theme;
      },
    };
  }
  function apply(theme, root, meta) {
    const style = root.style;
    const tokens = { bg: theme.bg, surface: theme.surface, 'surface-2': theme.tile, text: theme.text,
      muted: theme.muted, purple: theme.accent, 'purple-2': theme.accent, blue: theme.accent,
      green: theme.accent, 'on-accent': theme.onAccent, 'bg-glow': theme.tile,
      line: `color-mix(in srgb, ${theme.text} 24%, ${theme.surface})`,
      shadow: theme.mode === 'dark' ? 'rgba(0,0,0,.35)' : 'rgba(20,35,29,.08)',
      'font-body': fonts[theme.font], 'font-heading': theme.font === 'humanist' ? '"Archivo Expanded", Archivo, "Segoe UI", sans-serif' : fonts[theme.font],
      'card-radius': `${theme.radius}px`, 'sidebar-surface': theme.id === 'forest' ? '#E7EFE7' : theme.bg,
    };
    for (const [name, value] of Object.entries(tokens)) style.setProperty(`--${name}`, value);
    style.colorScheme = theme.mode;
    root.dataset.theme = theme.id;
    meta.content = theme.bg;
  }
  global.LiThemes = Object.freeze({ builtins, fonts, colors, contrast, validate, library, apply });
})(typeof window === 'undefined' ? globalThis : window);
