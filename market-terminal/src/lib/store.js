/* ─────────────────────────────────────────────────────────────────────────
   store.js — IndexedDB persistence for 清单 + 日记
   ───────────────────────────────────────────────────────────────────────── */

const DB_NAME = 'market_terminal';
const DB_VERSION = 1;
const STORES = { journals: { keyPath: 'date' }, checklists: { keyPath: 'date' } };

let _db = null;

function open() {
  if (_db) return Promise.resolve(_db);
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      for (const [name, opts] of Object.entries(STORES)) {
        if (!db.objectStoreNames.contains(name)) db.createObjectStore(name, opts);
      }
    };
    req.onsuccess = (e) => {
      _db = e.target.result;
      resolve(_db);
    };
    req.onerror = (e) => reject(e.target.error);
  });
}

const tx = (store, mode = 'readonly') => _db.transaction(store, mode).objectStore(store);

async function save(store, data) {
  await open();
  return new Promise((res, rej) => {
    const req = tx(store, 'readwrite').put({ ...data, updatedAt: Date.now() });
    req.onsuccess = () => res(req.result);
    req.onerror = (e) => rej(e.target.error);
  });
}

async function get(store, key) {
  await open();
  return new Promise((res, rej) => {
    const req = tx(store).get(key);
    req.onsuccess = () => res(req.result || null);
    req.onerror = (e) => rej(e.target.error);
  });
}

async function getAll(store) {
  await open();
  return new Promise((res, rej) => {
    const req = tx(store).getAll();
    req.onsuccess = () => res(req.result || []);
    req.onerror = (e) => rej(e.target.error);
  });
}

async function del(store, key) {
  await open();
  return new Promise((res, rej) => {
    const req = tx(store, 'readwrite').delete(key);
    req.onsuccess = () => res();
    req.onerror = (e) => rej(e.target.error);
  });
}

export const MarketStore = {
  open,
  save,
  get,
  getAll,
  del,
  today: () => new Date().toISOString().slice(0, 10),
};
