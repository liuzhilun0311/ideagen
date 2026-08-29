/**
 * DeAI 一键下载共享逻辑
 *
 * 供 ResultView 与 HistoryView 复用：选定目标文件夹后，
 * 自动执行去AI化 → 准备原图/处理图/文案/bat → 直接写入所选文件夹（不打包压缩）。
 */
import { getDeAIInfo, runDeAI } from '../api'
import { API_BASE_URL, authHeaders } from '../api/client'

export interface DownloadImageItem {
  index: number
  url: string
}

export type DeaiStrength = 'light' | 'medium' | 'heavy'

export interface DownloadContentData {
  titles?: string[]
  copywriting?: string
  tags?: string[]
}

export interface DeaiDownloadResult {
  ok: boolean
  message: string
}

/**
 * 构建文案 TXT 文本
 */
export function buildContentTxt(content: DownloadContentData): string {
  const { titles, copywriting, tags } = content
  let txtContent = '===== 标题 =====\n'
  if (titles && titles.length > 0) {
    titles.forEach((t, idx) => {
      txtContent += `${idx === 0 ? '[推荐]' : '[备选]'} ${t}\n`
    })
  } else {
    txtContent += '暂无标题\n'
  }
  txtContent += '\n===== 文案正文 =====\n'
  txtContent += copywriting || '暂无文案'
  txtContent += '\n\n===== 标签 =====\n'
  txtContent += (tags ?? []).map(t => `#${t}`).join(' ') || '暂无标签'
  return txtContent
}

/**
 * 构建 run_deai.bat 内容（纯 ASCII，无中文/BOM，兼容所有 Windows cmd）
 */
export function buildRunBat(pythonScript: string, deaiScript: string): string {
  const py = pythonScript && pythonScript.trim() ? pythonScript.trim() : 'python'
  const deai = deaiScript && deaiScript.trim() ? deaiScript.trim() : ''
  return `@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
cd /d "%~dp0"

:: Force local temp folder for session
set "LOCAL_TMP=%~dp0_tmp"
if not exist "%LOCAL_TMP%" md "%LOCAL_TMP%"
set "TEMP=%LOCAL_TMP%"
set "TMP=%LOCAL_TMP%"

:: ============ Config ============
set "PYTHON_SCRIPT=${py}"
set "DEAI_SCRIPT=${deai}"
set "STRENGTH=medium"
set "VERBOSE=0"
:: =================================

set "BASE_DIR=%~dp0"
set "INPUT_DIR=%BASE_DIR%picture"
set "OUTPUT_DIR=%BASE_DIR%deai"

echo ==============================================
echo  De-AI Batch Tool
echo  Python:    !PYTHON_SCRIPT!
echo  deai.py:   !DEAI_SCRIPT!
echo  Input:     !INPUT_DIR!
echo  Output:    !OUTPUT_DIR!
echo  Strength:  !STRENGTH!
echo  SessionTmp:!TEMP!
echo ==============================================

:: Check Python executable
"!PYTHON_SCRIPT!" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please check PYTHON_SCRIPT.
    echo         Current: !PYTHON_SCRIPT!
    pause
    exit /b 1
)

:: Check deai.py exists
if not exist "!DEAI_SCRIPT!" (
    echo [ERROR] deai.py not found. Please check DEAI_SCRIPT.
    echo         Current: !DEAI_SCRIPT!
    pause
    exit /b 1
)

:: Check input picture folder
if not exist "!INPUT_DIR!" (
    echo [ERROR] Input folder "picture" not found.
    echo         Current: !INPUT_DIR!
    pause
    exit /b 1
)

:: Auto create output folder
if not exist "!OUTPUT_DIR!" (
    md "!OUTPUT_DIR!"
    echo [INFO] Output folder "deai" created.
)

echo.
echo Start processing images ...
echo.

if !VERBOSE! equ 1 (
    "!PYTHON_SCRIPT!" "!DEAI_SCRIPT!" "!INPUT_DIR!" --strength !STRENGTH! -o "!OUTPUT_DIR!" --batch -v
) else (
    "!PYTHON_SCRIPT!" "!DEAI_SCRIPT!" "!INPUT_DIR!" --strength !STRENGTH! -o "!OUTPUT_DIR!" --batch
)
set EXIT_CODE=!errorlevel!

echo.
echo ==============================================
if !EXIT_CODE! equ 0 (
    echo [DONE] Finished successfully.
) else (
    echo [FAILED] Exit code: !EXIT_CODE!
)
echo ==============================================
pause
endlocal
`
}

/**
 * 时间戳命名（区分不同时间下载的同一作品）
 */
function buildTimestamp(): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  const now = new Date()
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
}

/**
 * 执行"一键下载全部"核心流程（调用方需先通过 showDirectoryPicker 获取 dirHandle，
 * 因为浏览器要求选择器必须紧跟用户点击手势）。
 */
export async function runDeaiDownload(opts: {
  dirHandle: any
  taskId: string
  strength?: DeaiStrength
  images: DownloadImageItem[]
  content: DownloadContentData
  setStage: (text: string) => void
}): Promise<DeaiDownloadResult> {
  const { dirHandle, taskId, strength = 'medium', images, content, setStage } = opts
  const folderName = taskId || 'rednote'

  // 时间戳命名（区分不同时间下载的同一作品）
  const stamp = buildTimestamp()
  const stampedFolder = `${folderName}-${stamp}`

  try {
    // 1. 自动执行 DeAI 去指纹处理（后端执行，无需手动运行 run_deai.bat）
    setStage('正在去AI化处理（约需 10~60 秒），请稍候...')
    let deaiOk = false
    let deaiNote = ''
    try {
      const deaiRes = await runDeAI(taskId, strength)
      deaiOk = deaiRes.success
      if (!deaiRes.success) {
        deaiNote = deaiRes.error_message || 'DeAI 执行失败'
      }
    } catch (e: any) {
      console.warn('调用 DeAI 自动执行接口失败:', e)
      deaiNote = e?.response?.data?.error_message || e?.message || 'DeAI 自动执行失败'
    }

    // 2. 准备文件数据：原图始终保存到 picture/；DeAI 成功时处理后的图保存到 deai/
    setStage('正在准备文件...')
    const originalImages: { name: string; blob: Blob }[] = []
    const processedImages: { name: string; blob: Blob }[] = []
    for (const image of images) {
      if (!image.url) continue
      const baseUrl = image.url.split('?')[0]
      const origRes = await fetch(baseUrl + '?thumbnail=false', { headers: authHeaders() })
      const blob = await origRes.blob()
      originalImages.push({ name: `page_${image.index + 1}.png`, blob })
      if (deaiOk) {
        try {
          const res = await fetch(`${API_BASE_URL}/deai/images/${taskId}/${image.index}_deai.png`, { headers: authHeaders() })
          if (res.ok) {
            processedImages.push({ name: `page_${image.index + 1}.png`, blob: await res.blob() })
          }
          // res 非 ok（如该页未生成）→ 跳过该张，避免把错误内容存成图片
        } catch {
          // 某张处理图拉取失败则跳过该张（不阻断下载）
        }
      }
    }
    const deaiNoteLine = deaiOk
      ? '已自动执行 DeAI 去指纹：picture/ 为原图，deai/ 为去 AI 处理后的图片。'
      : `DeAI 未执行成功（${deaiNote}），已保存原图到 picture/。\n如需去指纹，可在配置好 DeAI 后双击 run_deai.bat。`

    const contentTxtWithBom = '\uFEFF' + buildContentTxt(content)
    let runBat = buildRunBat('python', '')
    try {
      const deaiRes = await getDeAIInfo()
      const cfg = deaiRes.success && deaiRes.config ? deaiRes.config : { python_script: 'python', deai_script: '' }
      runBat = buildRunBat(cfg.python_script, cfg.deai_script)
    } catch (deaiErr) {
      console.warn('获取 DeAI 路径信息失败，使用默认值生成 run_deai.bat:', deaiErr)
    }

    // 3. 写入所选文件夹：创建 taskId 子文件夹 → 再建 taskId-时间 子文件夹
    setStage('正在保存文件...')
    const taskHandle = await dirHandle.getDirectoryHandle(folderName, { create: true })
    const targetHandle = await taskHandle.getDirectoryHandle(stampedFolder, { create: true })

    const pictureHandle = await targetHandle.getDirectoryHandle('picture', { create: true })
    for (const img of originalImages) {
      const fileHandle = await pictureHandle.getFileHandle(img.name, { create: true })
      const writable = await (fileHandle as any).createWritable()
      await writable.write(img.blob)
      await writable.close()
    }
    if (processedImages.length > 0) {
      const deaiHandle = await targetHandle.getDirectoryHandle('deai', { create: true })
      for (const img of processedImages) {
        const fileHandle = await deaiHandle.getFileHandle(img.name, { create: true })
        const writable = await (fileHandle as any).createWritable()
        await writable.write(img.blob)
        await writable.close()
      }
    }
    const contentHandle = await targetHandle.getFileHandle('content.txt', { create: true })
    const contentWritable = await (contentHandle as any).createWritable()
    await contentWritable.write(new Blob([contentTxtWithBom], { type: 'text/plain;charset=utf-8' }))
    await contentWritable.close()

    const batHandle = await targetHandle.getFileHandle('run_deai.bat', { create: true })
    const batWritable = await (batHandle as any).createWritable()
    await batWritable.write(new Blob([runBat], { type: 'text/plain;charset=utf-8' }))
    await batWritable.close()

    const tree = `├── picture/（原图）\n${processedImages.length > 0 ? '├── deai/（去AI处理）\n' : ''}└── content.txt  ·  run_deai.bat`
    return { ok: true, message: `文件已保存到：\n${folderName}/${stampedFolder}/\n${tree}\n\n${deaiNoteLine}` }
  } catch (e: any) {
    console.error('下载失败:', e)
    return { ok: false, message: `下载失败：${e?.message || '未知错误'}` }
  }
}

/**
 * zip 兜底下载：当浏览器/地址不支持 showDirectoryPicker（非 localhost 的 http）时使用。
 * 流程与 runDeaiDownload 一致（自动去AI化 + 准备原图/处理图/文案/bat），最终打包成 zip 下载。
 */
export async function downloadAsZip(opts: {
  taskId: string
  strength?: DeaiStrength
  images: DownloadImageItem[]
  content: DownloadContentData
  setStage: (text: string) => void
}): Promise<DeaiDownloadResult> {
  const { taskId, strength = 'medium', images, content, setStage } = opts
  const folderName = taskId || 'rednote'
  const stampedFolder = `${folderName}-${buildTimestamp()}`

  try {
    // 1. 自动执行 DeAI 去指纹处理（后端执行）
    setStage('正在去AI化处理（约需 10~60 秒），请稍候...')
    let deaiOk = false
    let deaiNote = ''
    try {
      const deaiRes = await runDeAI(taskId, strength)
      deaiOk = deaiRes.success
      if (!deaiRes.success) {
        deaiNote = deaiRes.error_message || 'DeAI 执行失败'
      }
    } catch (e: any) {
      console.warn('调用 DeAI 自动执行接口失败:', e)
      deaiNote = e?.response?.data?.error_message || e?.message || 'DeAI 自动执行失败'
    }

    // 2. 准备文件数据（延迟加载 jszip，避免影响文件夹直写路径）
    setStage('正在准备文件...')
    const JSZip = (await import('jszip')).default
    const zip = new JSZip()
    const pictureFolder = zip.folder(`${stampedFolder}/picture`)
    const deaiFolder = deaiOk ? zip.folder(`${stampedFolder}/deai`) : null

    for (const image of images) {
      if (!image.url) continue
      const baseUrl = image.url.split('?')[0]
      const origRes = await fetch(baseUrl + '?thumbnail=false', { headers: authHeaders() })
      if (origRes.ok) {
        pictureFolder?.file(`page_${image.index + 1}.png`, await origRes.blob())
      }
      if (deaiOk) {
        try {
          const res = await fetch(`${API_BASE_URL}/deai/images/${taskId}/${image.index}_deai.png`, { headers: authHeaders() })
          if (res.ok) {
            deaiFolder?.file(`page_${image.index + 1}.png`, await res.blob())
          }
        } catch {
          // 某张处理图拉取失败则跳过该张（不阻断下载）
        }
      }
    }

    let runBat = buildRunBat('python', '')
    try {
      const deaiRes = await getDeAIInfo()
      const cfg = deaiRes.success && deaiRes.config ? deaiRes.config : { python_script: 'python', deai_script: '' }
      runBat = buildRunBat(cfg.python_script, cfg.deai_script)
    } catch {
      console.warn('获取 DeAI 路径信息失败，使用默认值生成 run_deai.bat')
    }
    zip.file(`${stampedFolder}/content.txt`, '\uFEFF' + buildContentTxt(content))
    zip.file(`${stampedFolder}/run_deai.bat`, runBat)

    // 3. 生成 zip 并触发浏览器下载
    setStage('正在生成 zip 压缩包...')
    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${folderName}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => URL.revokeObjectURL(url), 10000)

    const tree = `├── picture/（原图）\n${deaiOk ? '├── deai/（去AI处理）\n' : ''}└── content.txt  ·  run_deai.bat`
    const deaiNoteLine = deaiOk
      ? '已自动执行 DeAI 去指纹：picture/ 为原图，deai/ 为去 AI 处理后的图片。'
      : `DeAI 未执行成功（${deaiNote}），已保存原图到 picture/。\n如需去指纹，可在配置好 DeAI 后双击 run_deai.bat。`
    return {
      ok: true,
      message: `已下载 zip：${folderName}.zip\n（当前地址不支持直接选文件夹，已自动改用 zip 下载；使用 HTTPS 访问后可选择文件夹直存）\n${tree}\n\n${deaiNoteLine}`
    }
  } catch (e: any) {
    console.error('zip 下载失败:', e)
    return { ok: false, message: `下载失败：${e?.message || '未知错误'}` }
  }
}
