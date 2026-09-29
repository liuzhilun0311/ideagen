const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fs = require('node:fs')
const path = require('node:path')
const samples = require('../src/features/styles/samples.json')

async function main() {
  const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' })
  const output = path.resolve('test-results/style-samples')
  fs.mkdirSync(output, { recursive: true })
  const errors = []
  try {
    const live = await browser.newPage()
    await live.goto('http://127.0.0.1:12399/')
    for (const sample of samples) {
      const dimensions = await live.evaluate(async sample => {
        const image = new Image()
        image.src = sample.url
        await image.decode()
        return [image.naturalWidth, image.naturalHeight]
      }, sample)
      if (dimensions[0] !== sample.width || dimensions[1] !== sample.height) {
        errors.push(`Production image dimensions: ${sample.id}`)
      }
    }
    await live.close()
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } })
      page.on('pageerror', error => errors.push(error.message))
      await page.goto('http://127.0.0.1:12409/dev-preview.html?screen=workspace-images')
      await page.getByRole('button', { name: '浏览图片风格', exact: true }).click()
      const dialog = page.locator('.style-dialog[open]')
      await dialog.locator('.style-item').first().waitFor()
      await dialog.locator('img').evaluateAll(images => images.forEach(image => { image.loading = 'eager' }))
      await page.waitForFunction(() => [...document.querySelectorAll('.style-dialog[open] img')]
        .every(image => image.complete && image.naturalWidth > 0))
      const count = await dialog.locator('.example-label').filter({ hasText: '模型实测 · 2K' }).count()
      if (count !== samples.length) errors.push(`Gallery sample count ${width}: ${count} vs ${samples.length}`)
      await page.screenshot({ path: path.join(output, `selector-${width}.png`) })
      await dialog.locator('.style-item').first().getByRole('button', { name: '放大预览', exact: true }).click()
      await page.waitForFunction(() => document.querySelector('.preview-dialog[open] img')?.naturalWidth === 1536)
      await page.screenshot({ path: path.join(output, `zoom-${width}.png`) })
      await page.goto('http://127.0.0.1:12409/dev-preview.html?screen=prompts')
      await page.getByRole('button', { name: '生成图片', exact: true }).click()
      await page.getByRole('button', { name: '图片风格', exact: true }).click()
      const entries = page.locator('article.entry')
      await entries.filter({ hasText: '水彩插画' }).waitFor()
      const approved = await entries.locator('.sample-caption').filter({ hasText: '模型实测 · 2K' }).count()
      if (approved !== samples.length) errors.push(`Manager sample count ${width}: ${approved}`)
      await page.screenshot({ path: path.join(output, `manager-${width}.png`) })
      await page.getByRole('button', { name: '放大查看水彩插画样图', exact: true }).click()
      await page.waitForFunction(() => document.querySelector('.preview-dialog[open] img')?.naturalWidth === 1536)
      await page.screenshot({ path: path.join(output, `manager-zoom-${width}.png`) })
      if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) errors.push(`Overflow at ${width}`)
      await page.close()
    }
    if (errors.length) throw new Error(errors.join('\n'))
    console.log(`PASS: ${samples.length} production images decode; both fixture entry points, 2K zoom, desktop/mobile, no page errors.`)
  } finally {
    await browser.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
