import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // Node-based component hosts do not implement the DOM static-HTML insertion API.
  plugins: [vue({ template: { compilerOptions: { hoistStatic: false } } })],
  test: {
    environment: 'node',
    testTransformMode: { web: ['**/imagePromptInspector.test.ts', '**/suiteDiagnostics.test.ts', '**/outlineParameterSummary.test.ts', '**/workspace.test.ts', '**/generationGuide.test.ts', '**/newCreation.test.ts', '**/outlineDiagnostics.test.ts', '**/outlineRecommendation.test.ts', '**/outlinePromptInspector.test.ts', '**/homeDiagnostics.test.ts', '**/referenceRoles.test.ts', '**/downloadDialog.test.ts', '**/promptLibrary.test.ts', '**/tests/history/*.test.ts'] },
    include: ['tests/**/*.test.ts'],
    setupFiles: ['./tests/setup.ts'],
    clearMocks: true,
  },
})
