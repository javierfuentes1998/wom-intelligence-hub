(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.WOMTheme = api;
  if (typeof document !== 'undefined') api.bootstrap();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const STORAGE_KEY = 'wom_theme_preference';
  const VALID_PREFERENCES = new Set(['auto', 'light', 'dark']);

  function normalizePreference(value) {
    return VALID_PREFERENCES.has(value) ? value : 'auto';
  }

  function themeForLocalTime(value) {
    const date = value instanceof Date ? value : new Date(value);
    const minutes = date.getHours() * 60 + date.getMinutes();
    return minutes >= 8 * 60 && minutes < 20 * 60 + 30 ? 'light' : 'dark';
  }

  function effectiveTheme(preference, now) {
    const normalized = normalizePreference(preference);
    return normalized === 'auto' ? themeForLocalTime(now) : normalized;
  }

  function nextBoundary(value) {
    const now = value instanceof Date ? new Date(value.getTime()) : new Date(value);
    const lightStart = new Date(now.getTime());
    lightStart.setHours(8, 0, 0, 0);
    const darkStart = new Date(now.getTime());
    darkStart.setHours(20, 30, 0, 0);
    if (now < lightStart) return lightStart;
    if (now < darkStart) return darkStart;
    lightStart.setDate(lightStart.getDate() + 1);
    return lightStart;
  }

  function millisecondsUntilNextBoundary(now) {
    return Math.max(1, nextBoundary(now).getTime() - now.getTime());
  }

  function createController(options) {
    const storage = options.storage;
    const now = options.now || (() => new Date());
    const schedule = options.schedule || ((fn, delay) => setTimeout(fn, delay));
    const cancel = options.cancel || (id => clearTimeout(id));
    const apply = options.apply || (() => {});
    let timer = null;

    function getPreference() {
      try { return normalizePreference(storage && storage.getItem(STORAGE_KEY)); }
      catch (_) { return 'auto'; }
    }

    function refresh() {
      if (timer !== null) { cancel(timer); timer = null; }
      const preference = getPreference();
      const date = now();
      const theme = effectiveTheme(preference, date);
      apply({ preference, theme, date });
      if (preference === 'auto') {
        timer = schedule(refresh, millisecondsUntilNextBoundary(date) + 25);
      }
      return { preference, theme };
    }

    function setPreference(value) {
      const preference = normalizePreference(value);
      try { if (storage) storage.setItem(STORAGE_KEY, preference); } catch (_) {}
      return refresh();
    }

    function destroy() {
      if (timer !== null) cancel(timer);
      timer = null;
    }

    return { getPreference, setPreference, refresh, destroy };
  }

  function applyToDocument(state) {
    const html = document.documentElement;
    html.dataset.theme = state.theme;
    html.dataset.themePreference = state.preference;
    html.style.colorScheme = state.theme;
    const control = document.getElementById('themeControl');
    if (control) {
      control.querySelectorAll('[data-theme-choice]').forEach(button => {
        const selected = button.dataset.themeChoice === state.preference;
        button.classList.toggle('active', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
      const status = control.querySelector('[data-theme-status]');
      if (status) status.textContent = state.preference === 'auto'
        ? `Automático · ${state.theme === 'light' ? 'Día' : 'Noche'}`
        : state.theme === 'light' ? 'Modo Día' : 'Modo Noche';
    }
    document.dispatchEvent(new CustomEvent('wom:themechange', { detail: state }));
  }

  let browserController = null;
  function bootstrap() {
    browserController = createController({
      storage: window.localStorage,
      now: () => new Date(),
      apply: applyToDocument
    });
    browserController.refresh();
    const bind = () => {
      document.getElementById('themeControl')?.addEventListener('click', event => {
        const button = event.target.closest('[data-theme-choice]');
        if (button) browserController.setPreference(button.dataset.themeChoice);
      });
      browserController.refresh();
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind, { once: true });
    else bind();
  }

  return {
    STORAGE_KEY,
    normalizePreference,
    themeForLocalTime,
    effectiveTheme,
    nextBoundary,
    millisecondsUntilNextBoundary,
    createController,
    bootstrap
  };
});
