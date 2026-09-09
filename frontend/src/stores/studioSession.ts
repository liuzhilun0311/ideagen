import { defineStore } from 'pinia'

// Live ownership is deliberately not restored from localStorage.
export const useStudioSession = defineStore('studio-session', {
  state: () => ({
    homeBusy: false,
    workspaceBusy: false,
    dirty: false,
    revision: 0,
    notice: '',
  }),
  getters: {
    busy: state => state.homeBusy || state.workspaceBusy,
  },
  actions: {
    replaceDraft(): boolean {
      if (this.busy) return false
      this.revision += 1
      this.dirty = false
      this.notice = ''
      return true
    },
  },
})
