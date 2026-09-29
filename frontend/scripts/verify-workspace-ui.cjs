const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fs = require('node:fs')
const path = require('node:path')

async function main() {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' })
  const output = path.resolve(process.env.UI_OUTPUT || 'test-results/workspace-audit')
  fs.mkdirSync(output, { recursive: true })
  const failures = []
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } })
      page.on('pageerror', error => failures.push(error.message))
      await page.goto('http://127.0.0.1:12409/dev-preview.html?screen=workspace-copy')
      await page.getByLabel('采用标题 2').waitFor()
      await page.getByLabel('采用标题 2').check()
      const rows = await page.locator('.title-option').evaluateAll(elements => elements.map(row => {
        const radio = row.querySelector('input[type=radio]').getBoundingClientRect()
        const field = row.querySelector('.field').getBoundingClientRect()
        const copy = row.querySelector('button').getBoundingClientRect()
        return { radio: radio.y + radio.height / 2, field: field.y + field.height / 2,
          copy: copy.y + copy.height / 2, fieldWidth: field.width }
      }))
      if (rows.some(row => Math.abs(row.radio - row.field) > 2 || Math.abs(row.copy - row.field) > 2 || row.fieldWidth < 100)) {
        failures.push(`Title alignment at ${width}: ${JSON.stringify(rows)}`)
      }
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) failures.push(`Copy overflow ${width}`)
      await page.screenshot({ path: path.join(output, `copy-${width}.png`), fullPage: true })
      await page.goto('http://127.0.0.1:12409/dev-preview.html?screen=workspace-images')
      await page.getByRole('button', { name: '生成本页 · 1 张', exact: true }).waitFor()
      if (width === 390) {
        await page.getByRole('button', { name: '试用与设置', exact: true }).click()
        await page.locator('.mobile-settings-dialog[open] select').first().waitFor()
        if (!await page.locator('.mobile-settings-dialog').getByRole('button', { name: '生成本页 · 1 张', exact: true }).isVisible()) {
          failures.push('Mobile tools did not receive page controls')
        }
      }
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) failures.push(`Image overflow ${width}`)
      await page.screenshot({ path: path.join(output, `images-${width}.png`), fullPage: true })
      await page.close()
    }
    if (failures.length) throw new Error(failures.join('\n'))
    console.log(`PASS: desktop/mobile title alignment, no overflow, mobile page controls; screenshots: ${output}`)
  } finally {
    await browser.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
