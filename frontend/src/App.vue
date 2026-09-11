<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import html2canvas from 'html2canvas'
import type { CalendarDay, ReportData, TaskState } from '@/types/report'

const api: string = 'http://localhost:2001/api'
const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const task = ref<TaskState | null>(null)
const error = ref<string>('')
const showCalendar = ref<boolean>(false)
const selectedDate = ref<string>('2026-09-08')
const completedDates = ref<Set<string>>(new Set())
const isExporting = ref<boolean>(false)
const isRegenerating = ref<boolean>(false)

async function regenerateReport(): Promise<void> {
  const targetId = task.value?.id || selectedDate.value
  if (!targetId) return
  if (!confirm(`确定要使用原上传文件重新生成 ${selectedDate.value} 的 AI 日报吗？`)) return

  isRegenerating.value = true
  error.value = ''
  try {
    const res = await fetch(`${api}/tasks/${targetId}/regenerate`, {
      method: 'POST',
    })
    if (!res.ok) {
      const errJson = await res.json()
      throw new Error(errJson.detail || errJson.message || '重新生成失败')
    }
    task.value = await res.json()
    poll()
  } catch (e: any) {
    error.value = e.message || '重新生成发生异常'
  } finally {
    isRegenerating.value = false
  }
}

// Refine / Feedback Panel State
const isRefining = ref<boolean>(false)
const refineError = ref<string>('')
const showSuccessToast = ref<boolean>(false)

const showHistory = ref<boolean>(true)

function restoreSectionVersion(item: any): void {
  if (!task.value || !task.value.report || !item) return
  if (confirm(`确定要将【${item.section_name}】恢复到该修改意见提交前的历史版本吗？`)) {
    task.value.report[item.section_key as keyof ReportData] = item.previous_content
  }
}

const selectedSectionKey = ref<string>('summary')
const selectedRating = ref<number>(5)
const refineInstruction = ref<string>('')

const sectionOptions = [
  { key: 'summary', name: '🔥 氛围总结' },
  { key: 'important_notices', name: '📌 重要提醒 / 规则' },
  { key: 'hot_topics', name: '🎯 今日热门话题' },
  { key: 'funny_quotes', name: '🎈 趣味互动' },
  { key: 'tools_table_markdown', name: '🛠️ 工具及观点' },
  { key: 'insights', name: '💡 核心观点 / 避坑指南' },
  { key: 'ending_quote', name: '🌙 结语' },
]

const quickTags = [
  { label: '更扩充详细', text: '请扩充丰富细节内容；' },
  { label: '调整为精简', text: '请进一步归纳精简；' },
  { label: '更轻松幽默', text: '请将语气调整得更加轻松幽默；' },
  { label: '补充原文细节', text: '请对照原文补充具体讨论例子；' },
  { label: '核对发言人归属', text: '请严谨核对并修正发言人与具体观点的对应关系，防止张冠李戴；' },
]

function applyQuickTag(text: string): void {
  if (!refineInstruction.value.includes(text)) {
    refineInstruction.value = refineInstruction.value ? `${refineInstruction.value} ${text}` : text
  }
}

async function submitRefinement(): Promise<void> {
  if (!task.value || !refineInstruction.value.trim()) return
  isRefining.value = true
  refineError.value = ''

  try {
    const res = await fetch(`${api}/tasks/${task.value.id}/refine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        section_feedback: {
          section_key: selectedSectionKey.value,
          rating: selectedRating.value,
          instruction: refineInstruction.value.trim(),
        },
      }),
    })

    if (!res.ok) {
      const errJson = await res.json()
      throw new Error(errJson.detail || errJson.message || '局部增量微调失败')
    }

    const updatedTask: TaskState = await res.json()
    task.value = updatedTask
    refineInstruction.value = ''
    showSuccessToast.value = true
    setTimeout(() => {
      showSuccessToast.value = false
    }, 3000)
  } catch (e: any) {
    refineError.value = e.message || '局部增量微调异常'
  } finally {
    isRefining.value = false
  }
}

const stages: string[] = ['上传记录', '解析内容', '生成日报', '导出图片']
const stageIndex = computed<number>(() => task.value?.stage_index ?? 0)
const progress = computed<number>(() => task.value?.progress ?? 0)
const reportData = computed<ReportData | null>(() => task.value?.report || null)

const formatSummaryText = computed<string>(() => {
  const s = reportData.value?.summary
  if (!s) return ''
  if (typeof s === 'string') {
    if (s.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(s)
        return parsed.summary || parsed.content || s
      } catch (e) {
        return s
      }
    }
    return s
  }
  if (typeof s === 'object' && s !== null) {
    return (s as any).summary || (s as any).content || JSON.stringify(s)
  }
  return String(s)
})

function cleanText(str: string | undefined | null): string {
  if (!str) return ''
  return String(str).replace(/<br\s*\/?>/gi, '\n')
}

const summaryLines = computed<string[]>(() => {
  const raw = cleanText(formatSummaryText.value)
  if (!raw) return []
  return raw
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
})

function formatTopicTitle(title: string, index: number): string {
  const clean = cleanText(title)
  if (!clean) return `话题${['一', '二', '三', '四', '五', '六'][index] || index + 1}`
  if (/^话题[一二三四五六七八九十0-9]+[:：]/i.test(clean)) {
    return clean
  }
  return `话题${['一', '二', '三', '四', '五', '六'][index] || index + 1}：${clean}`
}

function formatTopicSummaryLines(summary: string): string[] {
  if (!summary) return []
  return cleanText(summary)
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

function parseFunnyQuote(quote: string) {
  const clean = cleanText(quote).trim()
  const match = clean.match(/^([^\:：]+[:：])\s*(.*)$/s)
  if (match) {
    return { title: match[1], body: match[2] }
  }
  return { title: '', body: clean }
}



// Calendar calculations

const currentYear = ref<number>(2026)
const currentMonth = ref<number>(9)

const daysInMonth = computed<CalendarDay[]>(() => {
  const year = currentYear.value
  const month = currentMonth.value
  const firstDay = new Date(year, month - 1, 1).getDay()
  const totalDays = new Date(year, month, 0).getDate()

  const list: CalendarDay[] = []
  for (let i = 0; i < firstDay; i++) {
    list.push({ label: '', muted: true, date: '' })
  }
  for (let d = 1; d <= totalDays; d++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    list.push({
      label: d,
      muted: false,
      date: dateStr,
      isCompleted: completedDates.value.has(dateStr),
      isSelected: dateStr === selectedDate.value,
    })
  }
  return list
})

async function refreshCompletedDates(): Promise<void> {
  try {
    const res = await fetch(`${api}/reports/dates`)
    if (res.ok) {
      const data: { dates?: string[] } = await res.json()
      if (data.dates) {
        completedDates.value = new Set(data.dates)
      }
    }
  } catch (e) {
    console.warn('获取已生成日期列表失败', e)
  }
}

async function fetchReportByDate(dateStr: string): Promise<void> {
  error.value = ''
  try {
    const res = await fetch(`${api}/tasks/latest/${dateStr}`)
    if (res.ok) {
      const data: TaskState = await res.json()
      task.value = data
      if (data && !['completed', 'failed'].includes(data.status)) {
        poll()
      }
    } else {
      task.value = null
    }
  } catch (e) {
    task.value = null
  }
}

function toggleCalendar(): void {
  showCalendar.value = !showCalendar.value
}

function selectDate(day: CalendarDay): void {
  if (day.muted || !day.date) return
  selectedDate.value = day.date
  showCalendar.value = false
  fetchReportByDate(day.date)
}

function prevMonth(): void {
  if (currentMonth.value === 1) {
    currentMonth.value = 12
    currentYear.value -= 1
  } else {
    currentMonth.value -= 1
  }
}

function nextMonth(): void {
  if (currentMonth.value === 12) {
    currentMonth.value = 1
    currentYear.value += 1
  } else {
    currentMonth.value += 1
  }
}

const pastedText = ref<string>('')

function chooseFile(): void {
  fileInput.value?.click()
}

function resetUpload(): void {
  file.value = null
  task.value = null
  error.value = ''
  pastedText.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

const isDragging = ref<boolean>(false)

function onDropFile(event: DragEvent): void {
  isDragging.value = false
  const files = event.dataTransfer?.files
  if (files && files.length > 0) {
    upload(files[0])
  }
}

function submitPastedText(): void {
  if (!pastedText.value.trim()) return
  const pastedFile = new File([pastedText.value.trim()], 'pasted_chat.txt', { type: 'text/plain;charset=utf-8' })
  upload(pastedFile)
  pastedText.value = ''
}

function onFileChange(event: Event): void {
  const target = event.target as HTMLInputElement
  const picked = target.files?.[0]
  if (picked) upload(picked)
}

async function upload(picked: File): Promise<void> {
  error.value = ''
  file.value = picked
  const form = new FormData()
  form.append('file', picked)
  form.append('report_date', selectedDate.value)

  try {
    const response = await fetch(`${api}/tasks/upload`, { method: 'POST', body: form })
    if (!response.ok) {
      const errJson = await response.json()
      throw new Error(errJson.detail || '上传失败')
    }
    task.value = await response.json()
    poll()
  } catch (e: any) {
    error.value = e.message || '上传处理发生异常'
    task.value = null
  }
}

async function poll(): Promise<void> {
  if (!task.value || !task.value.id || ['completed', 'failed'].includes(task.value.status)) return
  const currentTaskId = task.value.id
  await new Promise((resolve) => setTimeout(resolve, 800))
  try {
    const response = await fetch(`${api}/tasks/${currentTaskId}`)
    if (!response.ok) {
      const errJson = await response.json().catch(() => ({}))
      error.value = errJson.detail || errJson.message || '获取任务状态异常'
      return
    }
    const resData: TaskState = await response.json()
    if (resData && resData.id) {
      task.value = resData
      if (resData.status === 'completed') {
        completedDates.value.add(selectedDate.value)
        refreshCompletedDates()
      } else if (resData.status !== 'failed') {
        poll()
      }
    }
  } catch (e) {
    error.value = '轮询任务状态异常'
  }
}

// Parse markdown table rows
const parsedToolsTable = computed<string[][]>(() => {
  const raw = reportData.value?.tools_table_markdown
  if (!raw) return []
  const lines = cleanText(raw)
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)

  const rows: string[][] = []
  for (const line of lines) {
    if (line.startsWith('|') && !line.includes('---')) {
      const cells = line
        .split('|')
        .map((c) => c.trim())
        .filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
      if (cells.length >= 3) {
        rows.push(cells)
      }
    }
  }
  return rows
})

const coreTopicsText = computed<string>(() => {
  if (reportData.value?.hot_topics && reportData.value.hot_topics.length > 0) {
    return reportData.value.hot_topics
      .map((t) => t.title)
      .filter(Boolean)
      .slice(0, 5)
      .join(' / ')
  }
  return 'AI / 追星 / 股市 / 面试 / 长图方案'
})

// Export Word-style HD image via html2canvas
async function exportImage(): Promise<void> {
  const element = document.getElementById('report-document')
  if (!element) return

  isExporting.value = true
  try {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready
    }

    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
    })

    const link = document.createElement('a')
    link.download = `群聊日报-${selectedDate.value}.png`
    link.href = canvas.toDataURL('image/png', 1.0)
    link.click()
  } catch (err) {
    console.error('导出长图失败:', err)
  } finally {
    isExporting.value = false
  }
}

onMounted(() => {
  refreshCompletedDates()
  fetchReportByDate(selectedDate.value)
})
</script>

<template>
  <div class="app-layout">
    <!-- Top Header Bar (浅色系 mini 风格 Header) -->
    <header class="app-header">
      <div class="brand">
        <span class="brand-icon">◈</span>
        <span class="brand-title">群聊日报 AI 工作台</span>

        <!-- 耗时统计徽章 (显示在顶部 Header 区域) -->
        <span v-if="task?.status === 'completed' && reportData" class="header-time-badge">
          ⏱️ {{ reportData.elapsed_seconds ? reportData.elapsed_seconds + ' 秒' : '离线极速' }}
          <small>({{ reportData.ai_provider === 'cloud' ? '火山云端 API' : '本地 GGUF' }})</small>
        </span>
      </div>

      <div class="header-actions">
        <!-- 日期选择 mini 按钮 -->
        <div class="date-selector-wrapper">
          <button class="mini-btn mini-btn-date" @click="toggleCalendar">
            <span class="cal-icon">📅</span>
            <span class="date-text">{{ selectedDate }}</span>
            <span class="arrow">▼</span>
          </button>

          <!-- Calendar Popover Modal -->
          <div v-if="showCalendar" class="calendar-popover">
            <div class="popover-head">
              <button class="nav-btn" @click="prevMonth">‹</button>
              <strong>{{ currentYear }} 年 {{ currentMonth }} 月</strong>
              <button class="nav-btn" @click="nextMonth">›</button>
            </div>

            <div class="week-row">
              <span v-for="w in ['日', '一', '二', '三', '四', '五', '六']" :key="w">{{ w }}</span>
            </div>

            <div class="dates-grid">
              <button
                v-for="(day, idx) in daysInMonth"
                :key="idx"
                class="date-cell"
                :class="{
                  muted: day.muted,
                  selected: day.isSelected,
                  completed: day.isCompleted,
                }"
                @click="selectDate(day)"
              >
                {{ day.label }}
                <i v-if="day.isCompleted" class="dot" title="有完成日报"></i>
              </button>
            </div>

            <div class="popover-footer">
              <span><i class="dot-legend"></i> 绿点表示已有日报</span>
              <button class="close-btn" @click="showCalendar = false">关闭</button>
            </div>
          </div>
        </div>

        <button class="mini-btn mini-btn-upload" @click="resetUpload">☁ 上传记录</button>

        <input ref="fileInput" type="file" accept=".txt,.pdf,.html,.doc,.docx" hidden @change="onFileChange" />

        <!-- 顶部 Mini 风格按钮: 导出图片 & 重新生成 -->
        <template v-if="task?.status === 'completed' && reportData">
          <button class="mini-btn mini-btn-export" :disabled="isExporting" @click="exportImage">
            {{ isExporting ? '导出中...' : '📷 导出图片 PNG' }}
          </button>

          <button class="mini-btn mini-btn-regenerate" :disabled="isRegenerating" @click="regenerateReport">
            {{ isRegenerating ? '生成中...' : '⚡ 重新生成' }}
          </button>
        </template>
      </div>
    </header>

    <!-- Main Page Container -->
    <main class="page-container">
      <!-- Processing Status Banner -->
      <section v-if="task && task.status !== 'completed'" class="status-banner">
        <div class="steps-row">
          <div v-for="(stage, idx) in stages" :key="stage" class="step-item" :class="{ done: idx < stageIndex, active: idx === stageIndex }">
            <span class="step-badge">{{ idx < stageIndex ? '✓' : idx + 1 }}</span>
            <span class="step-name">{{ stage }}</span>
          </div>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="banner-info">
          <span>{{ task.message }}</span>
          <strong>{{ progress }}%</strong>
        </div>
      </section>

      <!-- Error Toast -->
      <div v-if="error" class="error-toast">⚠️ {{ error }}</div>

      <!-- State 1: Dual Upload Section (文件上传区 + 文本粘贴区) -->
      <section v-if="!task || (task.status === 'failed' && !reportData)" class="upload-section">
        <!-- 上方区域：文件选择/拖拽上传卡片 -->
        <div
          class="upload-card upload-card-file"
          :class="{ dragging: isDragging }"
          @click="chooseFile"
          @dragover.prevent="isDragging = true"
          @dragenter.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="onDropFile"
        >
          <div class="cloud-icon">{{ isDragging ? '📂' : '☁' }}</div>
          <h2>{{ isDragging ? '松开鼠标立即上传文件' : `上传 ${selectedDate} 群聊记录文件` }}</h2>
          <p>支持 TXT、PDF、HTML、DOC、DOCX 导出文件，单文件上限 20MB</p>
          <button class="primary-upload-btn" type="button">点击或拖拽文件至此处启动 AI 分析</button>
          <span class="hint-tag">支持微信、QQ、飞书、钉钉等导出的各种聊天文本文件</span>
        </div>

        <!-- 中间分隔标识 -->
        <div class="upload-divider">
          <span>或</span>
        </div>

        <!-- 下方区域：文本框直接粘贴消息记录 -->
        <div class="upload-card upload-card-paste">
          <div class="paste-card-header">
            <span class="paste-icon">📝</span>
            <div>
              <h3>直接粘贴聊天记录文本</h3>
              <p>复制微信/QQ/钉钉群聊文字对话，直接粘贴在下方框中启动分析</p>
            </div>
          </div>

          <textarea
            v-model="pastedText"
            class="paste-textarea"
            placeholder="请在此粘贴聊天记录文本内容（例如：&#10;10:15 张三: 今天大模型部署成功了吗？&#10;10:16 李四: 已经成功在本地运行了...）"
          ></textarea>

          <button
            class="primary-paste-btn"
            type="button"
            :disabled="!pastedText.trim()"
            @click="submitPastedText"
          >
            🚀 提交粘贴文本并启动 AI 分析
          </button>
        </div>
      </section>

      <!-- State 2: 100% PARITY WORD DOCUMENT VIEW + PERMANENT INLINE REFINE SIDEBAR -->
      <div v-if="task?.status === 'completed' && reportData" class="document-workspace">
        <!-- Left Column: Word Document View -->
        <article id="report-document" class="word-document-view">
          <!-- Header Banner -->
          <header class="word-doc-header">
            <h1 class="word-doc-title">🌹 {{ cleanText(reportData.group_name) || '微信交流群' }}</h1>
            <div class="word-doc-meta-list">
              <div>🕒 <b class="meta-label">时间：</b>{{ selectedDate }}</div>
              <div>👥 <b class="meta-label">讨论人数：</b>{{ reportData.member_count || 1 }} 人</div>
              <div>💬 <b class="meta-label">核心讨论：</b>{{ coreTopicsText }}</div>
            </div>
          </header>

          <!-- 1. 🔥 氛围总结 -->
          <section v-if="reportData.summary" class="word-section">
            <h2 class="word-section-title">🔥 氛围总结</h2>
            <div class="word-text-block">
              <ul v-if="summaryLines.length > 1" class="word-bullet-list">
                <li v-for="(line, idx) in summaryLines" :key="idx">
                  {{ line.replace(/^[•\-\*\s]+/, '') }}
                </li>
              </ul>
              <p v-else>• {{ formatSummaryText.replace(/^[•\-\*\s]+/, '') }}</p>
            </div>
          </section>

          <!-- 2. 📌 重要提醒 / 规则规矩 -->
          <section v-if="reportData.important_notices && reportData.important_notices.length" class="word-section">
            <h2 class="word-section-title">📌 重要提醒 / 规则提炼</h2>
            <ul class="word-bullet-list">
              <li v-for="(notice, idx) in reportData.important_notices" :key="idx">
                {{ cleanText(notice) }}
              </li>
            </ul>
          </section>

          <!-- 3. 🎯 今日热门话题 -->
          <section v-if="reportData.hot_topics && reportData.hot_topics.length" class="word-section">
            <h2 class="word-section-title">🎯 今日热门话题</h2>

            <div class="word-topics-list">
              <div v-for="(t, i) in reportData.hot_topics" :key="i" class="word-topic-item">
                <div class="word-topic-head">
                  <b class="topic-title">{{ formatTopicTitle(t.title, i) }}</b>
                  <span class="topic-stars">{{ t.heat || '⭐⭐⭐⭐⭐' }}</span>
                </div>

                <ul class="word-topic-bullets">
                  <li><b class="label-bold">🕒 时间点：</b>{{ cleanText(t.time_period) || '全天交流' }}</li>
                  <li>
                    <b class="label-bold">📝 内容摘要：</b>
                    <div v-if="formatTopicSummaryLines(t.content_summary).length > 1" class="topic-summary-bullets">
                      <div v-for="(subLine, sIdx) in formatTopicSummaryLines(t.content_summary)" :key="sIdx" class="summary-sub-line">
                        • {{ subLine.replace(/^[•\-\*\s]+/, '') }}
                      </div>
                    </div>
                    <span v-else>{{ cleanText(t.content_summary) }}</span>
                  </li>
                  <li v-if="t.comment" class="comment-bullet"><b class="label-bold">💬 群友金句观点：</b>{{ cleanText(t.comment) }}</li>
                </ul>
              </div>
            </div>
          </section>

          <!-- 4. 🤣 趣味互动 -->
          <section v-if="reportData.funny_quotes && reportData.funny_quotes.length" class="word-section">
            <h2 class="word-section-title">🤣 趣味互动</h2>
            <ul class="word-bullet-list funny-quotes-list">
              <li v-for="(quote, i) in reportData.funny_quotes" :key="i">
                <template v-if="parseFunnyQuote(quote).title">
                  <b class="quote-title">{{ parseFunnyQuote(quote).title }}</b> {{ parseFunnyQuote(quote).body }}
                </template>
                <template v-else>
                  {{ cleanText(quote) }}
                </template>
              </li>
            </ul>
          </section>


          <!-- 5. 🛠️ 工具及观点看法 -->
          <section v-if="parsedToolsTable.length || (reportData.insights && reportData.insights.length)" class="word-section">
            <h2 class="word-section-title">🛠️ 工具及观点看法</h2>

            <!-- Clean Word Grid Table -->
            <div v-if="parsedToolsTable.length" class="word-table-wrapper">
              <table class="word-table">
                <thead>
                  <tr>
                    <th v-for="(cell, idx) in parsedToolsTable[0]" :key="idx">{{ cleanText(cell) }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, rIdx) in parsedToolsTable.slice(1)" :key="rIdx">
                    <td v-for="(cell, cIdx) in row" :key="cIdx">{{ cleanText(cell) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <!-- Insights Bullet List -->
            <div v-if="reportData.insights && reportData.insights.length" class="word-insights">
              <p class="insights-label">💡 <strong>核心观点 / 避坑指南：</strong></p>
              <ul class="word-bullet-list">
                <li v-for="(insight, idx) in reportData.insights" :key="idx">
                  {{ cleanText(insight) }}
                </li>
              </ul>
            </div>
          </section>

          <!-- 6. 🔗 相关链接 / 参考资源 -->
          <section v-if="reportData.related_links && reportData.related_links.length" class="word-section">
            <h2 class="word-section-title">🔗 相关链接 / 参考资源</h2>
            <ul class="word-bullet-list">
              <li v-for="(linkItem, idx) in reportData.related_links" :key="idx">
                {{ cleanText(linkItem) }}
              </li>
            </ul>
          </section>

          <!-- 6. 📌 其他讨论话题 -->
          <section v-if="reportData.other_topics && reportData.other_topics.length" class="word-section">
            <h2 class="word-section-title">📌 其他讨论话题</h2>
            <ul class="word-bullet-list">
              <li v-for="(topic, idx) in reportData.other_topics" :key="idx">
                {{ cleanText(topic) }}
              </li>
            </ul>
          </section>

          <!-- 7. 🌙 结语 -->
          <footer v-if="reportData.ending_quote" class="word-footer">
            <h2 class="word-section-title">🌙 结语</h2>
            <p class="word-ending-text">{{ cleanText(reportData.ending_quote) }}</p>

            <div class="word-doc-disclaimer">本日报由 AI 自动提炼生成，仅供内部交流使用。</div>
          </footer>
        </article>


        <!-- Right Column: Permanent Inline AI Refinement Panel (常显面板) -->
        <aside class="refine-sidebar-panel">
          <header class="panel-head">
            <h3>✨ 日报 AI 增量微调</h3>
            <div class="panel-subtitle">按板块打分提意见，1 秒极速局部润色</div>
          </header>

          <div class="panel-body">
            <!-- Toast Notification -->
            <div v-if="showSuccessToast" class="toast-success-badge">✓ 【{{ sectionOptions.find((s) => s.key === selectedSectionKey)?.name }}】微调更新成功！</div>

            <div v-if="refineError" class="error-toast">⚠️ {{ refineError }}</div>

            <!-- Step 1: Select Section -->
            <div class="drawer-field-group">
              <label>1. 选择待优化的板块</label>
              <select v-model="selectedSectionKey" class="drawer-select">
                <option v-for="opt in sectionOptions" :key="opt.key" :value="opt.key">
                  {{ opt.name }}
                </option>
              </select>
            </div>

            <!-- Step 2: Rating Stars -->
            <div class="drawer-field-group">
              <label>2. 板块满意度评分</label>
              <div class="star-rating-row">
                <button v-for="star in 5" :key="star" type="button" class="star-btn" :class="{ active: star <= selectedRating }" @click="selectedRating = star">★</button>
              </div>
            </div>

            <!-- Step 3: Quick Tags -->
            <div class="drawer-field-group">
              <label>3. 快捷优化提示词</label>
              <div class="quick-tags-grid">
                <button v-for="tag in quickTags" :key="tag.label" type="button" class="quick-tag-chip" @click="applyQuickTag(tag.text)">+ {{ tag.label }}</button>
              </div>
            </div>

            <!-- Step 4: Custom Feedback Textarea -->
            <div class="drawer-field-group">
              <label>4. 具体修改意见 / 补充说明</label>
              <textarea v-model="refineInstruction" class="drawer-textarea" placeholder="请输入对此板块的具体修改提示（如：补全xx论点、语气调整更加活泼）..."></textarea>
            </div>

            <button class="refine-submit-btn" :disabled="isRefining || !refineInstruction.trim()" @click="submitRefinement">
              <span v-if="isRefining">⚡ AI 局部增量微调中...</span>
              <span v-else>🚀 启动 AI 增量优化</span>
            </button>

            <!-- Step 5: Persistent AI Refinement History Timeline (过往微调会话轨迹) -->
            <div class="refine-history-section">
              <div class="history-head" @click="showHistory = !showHistory">
                <span>📜 每日 AI 修改轨迹 ({{ task?.refine_history?.length || 0 }}条)</span>
                <span class="toggle-icon">{{ showHistory ? '▲' : '▼' }}</span>
              </div>

              <div v-if="showHistory" class="history-list">
                <div v-if="!task?.refine_history || task.refine_history.length === 0" class="history-empty">
                  暂无修改轨迹（首次微调后自动保留记录）
                </div>
                <div v-else v-for="(item, idx) in [...task.refine_history].reverse()" :key="item.id || idx" class="history-item-card">
                  <div class="history-item-meta">
                    <span class="history-sec-badge">{{ item.section_name }}</span>
                    <span class="history-stars" v-if="item.rating">★ {{ item.rating }}</span>
                    <span class="history-time">{{ item.timestamp?.split(' ')[1] || item.timestamp }}</span>
                  </div>
                  <div class="history-instruction">“{{ item.instruction }}”</div>
                  <button type="button" class="restore-link-btn" @click="restoreSectionVersion(item)">↩ 撤销恢复旧版</button>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>
