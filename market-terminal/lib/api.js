/* ─────────────────────────────────────────────────────────────────────────
   api.js — REST-backed drop-in replacement for store.js
   Exposes window.MarketStore with the same interface, backed by market-api.
   ───────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';
  const BASE = 'http://localhost:8000';
  const JSON_HEADERS = { 'Content-Type': 'application/json' };

  async function get(store, key) {
    if (store === 'journals') {
      const r = await fetch(`${BASE}/api/journal?date=${key}`);
      return r.ok ? r.json() : null;
    }
    if (store === 'checklists') {
      const r = await fetch(`${BASE}/api/checklist?date=${key}`);
      return r.ok ? r.json() : null;
    }
    return null;
  }

  async function save(store, data) {
    if (store === 'journals') {
      const r = await fetch(`${BASE}/api/journal`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(data) });
      return r.json();
    }
    if (store === 'checklists') {
      const r = await fetch(`${BASE}/api/checklist`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(data) });
      return r.json();
    }
  }

  async function getAll(store) {
    if (store === 'journals') {
      const r = await fetch(`${BASE}/api/journal/history?limit=30`);
      return r.ok ? r.json() : [];
    }
    return [];
  }

  async function del(store, key) {
    if (store === 'journals') {
      await fetch(`${BASE}/api/journal?date=${key}`, { method: 'DELETE' });
    }
  }

  window.MarketStore = {
    today: () => new Date().toISOString().slice(0, 10),
    get,
    save,
    getAll,
    del,
  };
})();
