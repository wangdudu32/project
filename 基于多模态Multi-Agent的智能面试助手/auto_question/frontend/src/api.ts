import axios from 'axios'

export type Difficulty = 'easy' | 'medium' | 'hard'
export type Language = 'zh' | 'en'
export interface Evaluation {
  score: number
  correctness: number
  depth: number
  clarity: number
  feedback: string
  strengths: string[]
  improvements: string[]
}
export interface Question {
  id: string
  question: string
  page: number
  difficulty: Difficulty
  status: 'verified' | 'needs_revision'
  parent_id: string | null
  answer?: string
  analysis?: string
  feedback?: string
  user_answer?: string
  evaluation?: Evaluation
}
export interface Report extends Omit<Evaluation, 'feedback'> {
  question_count: number
  unverified_count: number
  completed_at: string
}
export interface Interview {
  id: string
  filename: string
  difficulty: Difficulty
  language: Language
  status: 'active' | 'completed'
  created_at: string
  updated_at: string
  source_pages: number[]
  questions: Question[]
  report?: Report
}
export interface HistoryItem extends Omit<Interview, 'questions' | 'source_pages' | 'report'> {
  question_count: number
  answered_count: number
  score: number | null
}
export interface UploadedDocument {
  document_id: string
  filename: string
  page_count: number
}
export interface Health {
  status: string
  model_provider: string
  model_configured: boolean
}

export const api = axios.create({ baseURL: '/api', timeout: 900_000 })

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return '参数不正确，请检查题目数量、难度和答案内容。'
    if (error.code === 'ECONNABORTED') return '请求等待超时。任务可能仍在处理中，请先查看历史记录。'
    return '无法连接服务，请确认后端已启动。'
  }
  return error instanceof Error ? error.message : '操作失败，请重试。'
}
