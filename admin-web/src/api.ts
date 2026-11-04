// 本地开发直连 API，避免 Vite 代理在 Chrome 的并发请求下挂起。
// 生产环境通过 VITE_ADMIN_API_BASE 指向同域网关或正式 API。
const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env
const API_BASE = env?.VITE_ADMIN_API_BASE || 'http://127.0.0.1:8200'

export type AdminIdentity = {
  id: string
  username: string
  role: string
  permissions: string[]
}

export type AdminUser = {
  id: string
  name: string
  gender: string
  city: string
  source: string
  profile: number
  verification: string
  membership: string
  membership_status: string
  status: string
  updated: string
  created_at: number
}

export type Metric = { label: string; value: number; hint: string; tone: string }
export type AuditLog = { id: string; created_at: string; username: string; role: string; action: string; subject_type: string; subject_id: string; metadata: Record<string, unknown> }
export type VerificationItem = AdminUser & { note: string; reviewed_at: number | null; queue_reason: string }
export type SafetyReport = { id: string; group_id: string; room_id: string; reporter_id: string; reporter_name: string; detail: string; status: 'received' | 'under_review' | 'resolved' | 'dismissed'; created_at: number; review_note: string; reviewed_at: number | null }
export type PremeetReview = { id: string; candidate_id: string; candidate_name: string; member_id: string; member_name: string; status: string; reason: string; rounds: number; started: number | null; deadline: number | null; created_at: number; decisions: Record<string, boolean | null>; analysis: string; analysis_mode: string; review_status: 'pending' | 'follow_up' | 'completed' | 'no_action'; review_note: string; reviewed_at: number | null; reviewed_by: string }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  })
  const payload = await response.json().catch(() => ({ detail: '服务未返回有效数据。' }))
  if (!response.ok) throw new Error(payload.detail || '请求失败。')
  return payload as T
}

export const adminApi = {
  login: (username: string, password: string) => request<AdminIdentity>('/admin/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => request<{ ok: boolean }>('/admin/auth/logout', { method: 'POST' }),
  me: () => request<AdminIdentity>('/admin/me'),
  dashboard: () => request<{ metrics: Metric[]; pending_tasks: { title: string; count: number; description: string; action: string }[] }>('/admin/dashboard'),
  users: () => request<{ items: AdminUser[] }>('/admin/users'),
  verifications: () => request<{ items: VerificationItem[] }>('/admin/verifications'),
  reviewVerification: (userId: string, payload: { verification_status: string; note: string }) => request(`/admin/verifications/${userId}/review`, { method: 'POST', body: JSON.stringify(payload) }),
  safetyReports: () => request<{ items: SafetyReport[] }>('/admin/safety-reports'),
  reviewSafetyReport: (groupId: string, reportId: string, payload: { status: string; note: string }) => request(`/admin/safety-reports/${groupId}/${reportId}/review`, { method: 'POST', body: JSON.stringify(payload) }),
  closeRoom: (roomId: string, payload: { note: string }) => request(`/admin/rooms/${roomId}/close`, { method: 'POST', body: JSON.stringify(payload) }),
  premeetReviews: () => request<{ items: PremeetReview[] }>('/admin/premeet-reviews'),
  reviewPremeet: (roomId: string, payload: { status: string; note: string }) => request(`/admin/premeet-reviews/${roomId}`, { method: 'POST', body: JSON.stringify(payload) }),
  auditLogs: () => request<{ items: AuditLog[] }>('/admin/audit-logs'),
  accountState: (userId: string, payload: { account_status: string; verification_status: string; note: string }) => request(`/admin/users/${userId}/account-state`, { method: 'POST', body: JSON.stringify(payload) }),
  membership: (userId: string, payload: { status: string; plan: string; expires_at?: number | null; note?: string }) => request(`/admin/users/${userId}/membership`, { method: 'POST', body: JSON.stringify(payload) })
}
