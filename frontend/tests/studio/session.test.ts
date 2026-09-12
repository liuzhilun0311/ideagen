import { beforeEach, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useStudioSession } from '../../src/stores/studioSession'

beforeEach(() => setActivePinia(createPinia()))

it('does not replace a draft while either creation owner is busy', () => {
  const session = useStudioSession()
  session.homeBusy = true
  expect(session.replaceDraft()).toBe(false)
  session.homeBusy = false
  session.workspaceBusy = true
  expect(session.replaceDraft()).toBe(false)
  expect(session.revision).toBe(0)
})

it('invalidates old draft ownership and notices on explicit replacement', () => {
  const session = useStudioSession()
  session.dirty = true
  session.notice = 'Completed'
  session.workspacePath = '/workspace/copy'
  expect(session.replaceDraft()).toBe(true)
  expect(session.revision).toBe(1)
  expect(session.dirty).toBe(false)
  expect(session.notice).toBe('')
  expect(session.workspacePath).toBe('/workspace')
})

it('does not inherit live operation state into a new app session', () => {
  useStudioSession().workspaceBusy = true
  setActivePinia(createPinia())
  expect(useStudioSession().busy).toBe(false)
})
