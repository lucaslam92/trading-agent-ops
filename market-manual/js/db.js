const DB_NAME = 'market_manual';
const DB_VERSION = 1;

const STORES = {
  journals:   { keyPath: 'date' },
  checklists: { keyPath: 'date' },
  market_data:{ keyPath: 'date' },
};

class DB {
  constructor() { this._db = null; }

  async open() {
    if (this._db) return this;
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = e => {
        const db = e.target.result;
        for (const [name, opts] of Object.entries(STORES)) {
          if (!db.objectStoreNames.contains(name)) db.createObjectStore(name, opts);
        }
      };
      req.onsuccess  = e => { this._db = e.target.result; resolve(this); };
      req.onerror    = e => reject(e.target.error);
    });
  }

  _tx(store, mode = 'readonly') {
    return this._db.transaction(store, mode).objectStore(store);
  }

  save(store, data) {
    return new Promise((res, rej) => {
      const req = this._tx(store, 'readwrite').put({ ...data, updatedAt: Date.now() });
      req.onsuccess = () => res(req.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  get(store, key) {
    return new Promise((res, rej) => {
      const req = this._tx(store).get(key);
      req.onsuccess = () => res(req.result || null);
      req.onerror   = e => rej(e.target.error);
    });
  }

  getAll(store) {
    return new Promise((res, rej) => {
      const req = this._tx(store).getAll();
      req.onsuccess = () => res(req.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  // Returns records with date keys between start and end (inclusive, YYYY-MM-DD)
  getRange(store, start, end) {
    return new Promise((res, rej) => {
      const range = IDBKeyRange.bound(start, end);
      const req   = this._tx(store).getAll(range);
      req.onsuccess = () => res(req.result);
      req.onerror   = e => rej(e.target.error);
    });
  }

  delete(store, key) {
    return new Promise((res, rej) => {
      const req = this._tx(store, 'readwrite').delete(key);
      req.onsuccess = () => res();
      req.onerror   = e => rej(e.target.error);
    });
  }
}

export const db = new DB();
