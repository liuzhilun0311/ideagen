<script setup lang="ts">
import { onActivated, onMounted, ref } from 'vue'
import { Pencil, RefreshCw, Trash2 } from 'lucide-vue-next'
import { deleteReferenceAsset, listReferenceAssets, referenceAssetImageUrl, updateReferenceAsset, type ReferenceAsset } from '../api/referenceAssets'

const assets = ref<ReferenceAsset[]>([])
const loading = ref(false)
const error = ref('')
const editing = ref<string | null>(null)

async function load() {
  loading.value = true
  const result = await listReferenceAssets()
  loading.value = false
  if (!result.success) {
    error.value = result.error_message || '获取参考素材失败'
    return
  }
  error.value = ''
  assets.value = result.assets
}

async function save(asset: ReferenceAsset) {
  const result = await updateReferenceAsset(asset.id, {
    title: asset.title,
    rewritten_content: asset.rewritten_content,
    user_note: asset.user_note,
    content: asset.content,
  })
  if (!result.success) error.value = result.error_message || '保存参考素材失败'
  else editing.value = null
}

async function remove(asset: ReferenceAsset) {
  if (!window.confirm(`确定删除“${asset.title}”？`)) return
  const result = await deleteReferenceAsset(asset.id)
  if (!result.success) {
    error.value = result.error_message || '删除参考素材失败'
    return
  }
  assets.value = assets.value.filter(item => item.id !== asset.id)
}

onMounted(load)
onActivated(load)
</script>

<template>
  <main class="reference-assets-page">
    <header class="page-heading">
      <div><p class="eyebrow">参考资产</p><h1>参考素材库</h1><p>保存图片内容分析和可直接复用的改写内容。</p></div>
      <button class="icon-button" type="button" title="刷新" aria-label="刷新参考素材" :disabled="loading" @click="load"><RefreshCw :size="18" /></button>
    </header>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">正在加载参考素材...</p>
    <p v-else-if="!assets.length" class="empty">还没有保存的参考素材。</p>
    <section v-else class="asset-grid" aria-label="参考素材列表">
      <article v-for="asset in assets" :key="asset.id" class="asset-item">
        <img v-if="asset.image_url" :src="referenceAssetImageUrl(asset)" :alt="asset.title" />
        <div class="asset-body">
          <input v-if="editing === asset.id" v-model="asset.title" class="field" aria-label="素材名称" />
          <h2 v-else>{{ asset.title }}</h2>
          <p>{{ asset.content.summary || asset.rewritten_content || '暂无内容摘要' }}</p>
          <textarea v-if="editing === asset.id" v-model="asset.rewritten_content" rows="6" aria-label="改写内容"></textarea>
          <div class="asset-actions">
            <button v-if="editing !== asset.id" class="icon-button" type="button" title="编辑" aria-label="编辑参考素材" @click="editing = asset.id"><Pencil :size="16" /></button>
            <button v-else class="btn btn-secondary" type="button" @click="save(asset)">保存</button>
            <button class="icon-button danger" type="button" title="删除" aria-label="删除参考素材" @click="remove(asset)"><Trash2 :size="16" /></button>
          </div>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.reference-assets-page { max-width:1240px; margin:0 auto; padding:36px 28px 64px; }
.page-heading { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:24px; }
.eyebrow { margin:0 0 8px; color:var(--primary); font-size:12px; font-weight:700; letter-spacing:.08em; }
h1 { margin:0; font-size:30px; } .page-heading p:not(.eyebrow) { color:var(--text-sub); }
.asset-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:16px; }
.asset-item { min-width:0; border:1px solid var(--border-color); border-radius:8px; background:var(--bg-card); overflow:hidden; }
.asset-item img { display:block; width:100%; aspect-ratio:4/3; object-fit:cover; background:var(--bg-body); }
.asset-body { display:grid; gap:10px; padding:16px; } .asset-body h2 { margin:0; font-size:17px; overflow-wrap:anywhere; }
.asset-body p { margin:0; color:var(--text-sub); line-height:1.6; overflow-wrap:anywhere; } .asset-body textarea { width:100%; box-sizing:border-box; resize:vertical; }
.asset-actions { display:flex; justify-content:flex-end; gap:8px; } .danger { color:#a62b35; } .error { color:#a62b35; } .empty { color:var(--text-sub); }
@media(max-width:700px) { .reference-assets-page { padding:24px 16px 40px; } h1 { font-size:24px; } }
</style>
