import { defineStore } from 'pinia'

// Live ownership is deliberately not restored from localStorage.
export const useStudioSession = defineStore('studio-session', {
  state: () => ({
    homeBusy: false,
    workspaceBusy: false,
    trialBusy: false,
    draftSaving: false,
    structureBusy: false,
    referenceLoading: false,
    referenceSaving: false,
    referenceStorageError: '',
    localStorageError: '',
    dirty: false,
    revision: 0,
    notice: '',
    workspacePath: '/workspace',
  }),
  getters: {
    busy: state => state.homeBusy || state.workspaceBusy || state.trialBusy || state.draftSaving || state.structureBusy || state.referenceLoading,
  },
  actions: {
    replaceDraft(): boolean {
      if (this.busy) return false
      this.revision += 1
      this.dirty = false
      this.notice = ''
      this.workspacePath = '/workspace'
      return true
    },
  },
})
