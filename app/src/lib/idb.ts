/**
 * IndexedDB bundle cache (DN-3 W8): once loaded, a world replays offline.
 *
 * One object store, keyed by run_id, holding the raw gzip bytes (small,
 * already under W2's 1 MB budget) — re-parsing on read keeps the cached
 * artifact byte-identical to what the server shipped, seal and all.
 */

const DB_NAME = "ah-bundles";
const STORE = "bundles";
const VERSION = 1;

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, VERSION);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function cachePut(runId: string, gzBytes: ArrayBuffer): Promise<void> {
  const db = await open();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put(gzBytes, runId);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function cacheGet(runId: string): Promise<ArrayBuffer | null> {
  const db = await open();
  const result = await new Promise<ArrayBuffer | null>((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).get(runId);
    req.onsuccess = () => resolve(req.result ?? null);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return result;
}

/** app-open-04 Item A: remove ONE cached bundle from this machine. A purely
 * LOCAL operation — it touches the IndexedDB store and nothing else; no
 * server call is made or implied (the server never held this entry's
 * staleness in the first place). Never called automatically: the front page
 * offers it as a control on dead entries and the player decides. */
export async function cacheDelete(runId: string): Promise<void> {
  const db = await open();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(runId);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function cacheList(): Promise<string[]> {
  const db = await open();
  const keys = await new Promise<string[]>((resolve, reject) => {
    const req = db.transaction(STORE, "readonly").objectStore(STORE).getAllKeys();
    req.onsuccess = () => resolve(req.result.map(String));
    req.onerror = () => reject(req.error);
  });
  db.close();
  return keys;
}
