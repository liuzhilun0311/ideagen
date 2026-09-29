const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')

async function main() {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' })
  const output = path.resolve(process.env.UI_OUTPUT || 'test-results/toolbar')
  fs.mkdirSync(output, { recursive: true })
  try {
    for (const width of [1920, 1440, 1101, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } })
      const errors = []
      page.on('pageerror', error => errors.push(error.message))
      await page.goto(`${process.env.UI_BASE || 'http://127.0.0.1:12409'}/dev-preview.html?screen=workspace&candidate-delay=15000`)
      const toolbar = page.getByRole('region', { name: '整套生成工具栏' })
      const palette = toolbar.locator('.palette-control select')
      await palette.waitFor()
      await page.getByRole('button', { name: /生成剩余/ }).waitFor()
      await page.waitForFunction(() => !document.querySelector('.creation-actions .image-action')?.disabled)
      const fixedPalette = await palette.locator('option').evaluateAll(options =>
        options.map(option => option.value).find(value => !['auto', 'reference', 'custom'].includes(value)))
      await palette.selectOption(fixedPalette)
      async function verify(state) {
        const dimensions = await toolbar.evaluate(element => {
          const bounds = element.getBoundingClientRect()
          const control = element.querySelector('.palette-control')
          const label = control.querySelector('label')
          const palette = control.querySelector('select').getBoundingClientRect()
          const preview = control.querySelector('.swatches, .colors').getBoundingClientRect()
          const range = document.createRange()
          range.selectNodeContents(label.firstChild)
          const labelText = range.getBoundingClientRect()
          const buttons = [...element.querySelectorAll('.creation-actions>button')]
          return {
            rows: getComputedStyle(element).gridTemplateRows.split(' ').length,
            overflow: element.scrollWidth > element.clientWidth + 1,
            previewBottom: preview.bottom, selectTop: palette.top,
            labelRight: labelText.right, previewLeft: preview.left,
            controlsContained: buttons.every(button => {
              const rect = button.getBoundingClientRect()
              return rect.left >= bounds.left && rect.right <= bounds.right && rect.bottom <= bounds.bottom
                && button.scrollWidth <= button.clientWidth + 1
            }),
          }
        })
        assert.equal(dimensions.overflow, false, `${width}/${state}: toolbar overflow`)
        assert.equal(dimensions.controlsContained, true, `${width}/${state}: action overflow`)
        if (width > 1100) {
          assert.equal(dimensions.rows, 2, `${width}/${state}: expected two rows`)
          assert.ok(dimensions.previewBottom <= dimensions.selectTop, `${width}/${state}: swatches added a row`)
          assert.ok(dimensions.labelRight <= dimensions.previewLeft, `${width}/${state}: palette label overlap`)
        }
        await toolbar.screenshot({ path: path.join(output, `${width}-${state}.png`) })
      }
      await verify('palette')
      await palette.selectOption('custom')
      await verify('custom')
      await page.getByRole('button', { name: /生成剩余/ }).click()
      await page.getByRole('button', { name: '停止后续生成', exact: true }).waitFor()
      await verify('generating')
      await page.getByRole('button', { name: '停止后续生成', exact: true }).click()
      await page.getByRole('button', { name: '本张完成后停止', exact: true }).waitFor()
      await verify('stopping')
      assert.deepEqual(errors, [])
      await page.close()
    }
    console.log(`PASS: two desktop rows, palette alignment, stop controls and mobile overflow; screenshots: ${output}`)
  } finally {
    await browser.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
