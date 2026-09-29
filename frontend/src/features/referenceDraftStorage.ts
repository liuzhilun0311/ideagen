export interface ReferenceDraft {
  key: string
  files: { name: string; type: string; lastModified: number; blob: Blob }[]
}

export interface ReferenceDraftStorage {
  read(owner: string): Promise<ReferenceDraft | undefined>
  write(owner: string, value: ReferenceDraft): Promise<void>
}

function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') { reject(new Error('浏览器不支持图片草稿存储。')); return }
    let failed = false
    const fail = (error: unknown) => { failed = true; clearTimeout(timer); reject(error) }
    const timer = setTimeout(() => fail(new Error('打开图片草稿数据库超时，请重试。')), 10000)
    const request = indexedDB.open('ideagen-reference-drafts', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('references')
    request.onerror = () => fail(request.error)
    request.onblocked = () => fail(new Error('图片草稿数据库被其他页面占用，请关闭旧页面后重试。'))
    request.onsuccess = () => {
      clearTimeout(timer)
      if (failed) { request.result.close(); return }
      request.result.onversionchange = () => request.result.close()
      resolve(request.result)
    }
  })
}

export const referenceDraftStorage: ReferenceDraftStorage = {
  async read(owner) {
    const db = await database()
    return new Promise((resolve, reject) => {
      const tx = db.transaction('references', 'readonly')
      const request = tx.objectStore('references').get(owner)
      tx.oncomplete = () => { db.close(); resolve(request.result) }
      tx.onabort = () => { db.close(); reject(tx.error || new Error('读取图片草稿失败。')) }
    })
  },
  async write(owner, value) {
    const db = await database()
    return new Promise((resolve, reject) => {
      const tx = db.transaction('references', 'readwrite')
      tx.objectStore('references').put(value, owner)
      tx.oncomplete = () => { db.close(); resolve() }
      tx.onabort = () => { db.close(); reject(tx.error || new Error('保存图片草稿失败。')) }
    })
  },
}
