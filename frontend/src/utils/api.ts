import type { AgentTopology, FeedbackRating } from '../types/events'

const API_BASE = '/api'

/** 健康检查 */
export async function fetchHealth(): Promise<{ status: string; service: string; time: string }> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) {
    throw new Error(`健康检查失败: ${res.status}`)
  }
  return res.json()
}

/** 获取 Agent 拓扑结构 */
export async function fetchAgents(): Promise<AgentTopology> {
  const res = await fetch(`${API_BASE}/agents`)
  if (!res.ok) {
    throw new Error(`获取Agent拓扑失败: ${res.status}`)
  }
  return res.json()
}

/** 创建新会话 */
export async function createSession(): Promise<{ session_id: string }> {
  const res = await fetch(`${API_BASE}/session`, { method: 'POST' })
  if (!res.ok) {
    throw new Error(`创建会话失败: ${res.status}`)
  }
  return res.json()
}

/** 生成唯一ID */
export function genId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

// ============ 反馈相关 ============

/** 提交反馈请求体 */
export interface FeedbackRequest {
  message_id: string
  rating: FeedbackRating
  session_id: string
  query: string
  response: string
}

/** 提交反馈响应体 */
export interface FeedbackResponse {
  id: number
  message_id: string
  rating: FeedbackRating
  status: string
}

/** 提交点赞/踩反馈 */
export async function submitFeedback(payload: FeedbackRequest): Promise<FeedbackResponse> {
  const res = await fetch(`${API_BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(`提交反馈失败: ${res.status}`)
  }
  return res.json()
}

/** 反馈统计 */
export interface FeedbackStats {
  total: number
  likes: number
  dislikes: number
  satisfaction_rate: number
  by_intent: Record<string, unknown>
}

/** 获取反馈统计 */
export async function fetchFeedbackStats(): Promise<FeedbackStats> {
  const res = await fetch(`${API_BASE}/feedback/stats`)
  if (!res.ok) {
    throw new Error(`获取反馈统计失败: ${res.status}`)
  }
  return res.json()
}
