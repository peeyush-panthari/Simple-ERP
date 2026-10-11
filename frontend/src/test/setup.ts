import "@testing-library/jest-dom/vitest";

// Recent Node ships an experimental global `localStorage` that shadows jsdom's
// (and throws without --localstorage-file); give tests a plain in-memory one.
class MemoryStorage implements Storage {
  private data = new Map<string, string>();
  get length() {
    return this.data.size;
  }
  clear() {
    this.data.clear();
  }
  getItem(key: string) {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }
  key(index: number) {
    return [...this.data.keys()][index] ?? null;
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
  setItem(key: string, value: string) {
    this.data.set(key, String(value));
  }
}

for (const target of [globalThis, window]) {
  Object.defineProperty(target, "localStorage", { value: new MemoryStorage(), configurable: true, writable: true });
}
