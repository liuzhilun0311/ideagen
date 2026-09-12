import { expect, it } from 'vitest'
import { readLayout, withLayout, imageParameters } from '../../src/features/generationOptions'

it('changes layout without changing printable facts', () => {
  const source = '[内容]\n单页布局：对比\n上图文字：\n标题：认识1K和3:4\n画面描述：并排放置'
  const result = withLayout(source, '步骤')
  expect(readLayout(result)).toBe('步骤')
  expect(result).toContain('标题：认识1K和3:4')
  expect(result.match(/单页布局/g)).toHaveLength(1)
})

it('supports legacy pages without layout', () => {
  expect(readLayout('Old page')).toBe('自动')
  expect(readLayout(withLayout('[内容]\n上图文字：示例', '清单'))).toBe('清单')
})

it('transmits every explicitly selected image parameter', () => {
  expect(imageParameters({ imageResolution: '2K', imageAspectRatio: '1:1',
    imageQuality: 'low', imageOutputFormat: 'webp' })).toEqual({
    resolution: '2K', aspect_ratio: '1:1', quality: 'low', output_format: 'webp',
  })
})
