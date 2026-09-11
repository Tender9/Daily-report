export interface HotTopic {
  title: string
  heat?: string
  time_period?: string
  content_summary: string
  comment?: string
}

export interface ReportData {
  group_name?: string
  elapsed_seconds?: number
  ai_provider?: string
  member_count?: number
  summary?: string
  important_notices?: string[]
  hot_topics?: HotTopic[]
  funny_quotes?: string[]
  tools_table_markdown?: string
  insights?: string[]
  related_links?: string[]
  other_topics?: string[]
  ending_quote?: string
}

export interface RefineHistoryItem {
  id: string
  timestamp: string
  section_key: string
  section_name: string
  rating?: number
  instruction: string
  previous_content?: any
  refined_content?: any
}

export interface TaskState {
  id: string
  status: 'pending' | 'parsing' | 'generating' | 'completed' | 'failed'
  stage_index?: number
  progress?: number
  message?: string
  report?: ReportData | null
  detail?: string
  file_path?: string
  refine_history?: RefineHistoryItem[]
}

export interface CalendarDay {
  label: string | number
  muted: boolean
  date: string
  isCompleted?: boolean
  isSelected?: boolean
}

export interface SectionFeedback {
  section_key: string
  rating?: number
  instruction: string
}

export interface RefineTaskRequest {
  section_feedback: SectionFeedback
}
