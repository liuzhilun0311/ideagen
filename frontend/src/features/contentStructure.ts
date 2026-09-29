const structureLabels: Record<string, string> = {
  hook_value_list_save: '吸引注意 → 提供价值 → 要点清单 → 引导收藏',
  hook_scene_benefit_proof: '吸引注意 → 使用场景 → 产品益处 → 证据',
  pain_solution_proof_cta: '痛点 → 解决方案 → 证据 → 行动建议',
  hook_problem_value_follow: '吸引注意 → 提出问题 → 提供价值 → 引导关注',
  hook_problem_solution_dm: '吸引注意 → 提出问题 → 解决方案 → 私信咨询',
  hook_demo_benefit_cta: '吸引注意 → 演示 → 益处 → 行动建议',
  hook_value_cta: '吸引注意 → 提供价值 → 行动建议',
  hook_solution_cta: '吸引注意 → 解决方案 → 行动建议',
  观点背景案例总结: '观点 → 背景 → 案例 → 总结',
  问题分析方案案例行动: '问题 → 分析 → 方案 → 案例 → 行动',
}
export function contentStructureLabel(value?: string): string {
  if (!value) return '根据主题与页面内容安排'
  return structureLabels[value] || value
}
