export type UserStatus = '正常' | '待审核' | '已冻结'

export const pendingTasks = [
  { title: '资料核验待处理', count: 12, description: '实名认证、照片一致性与资料补充', action: '进入核验队列' },
  { title: '异常预会面', count: 3, description: '需检查敏感内容拦截与房间状态', action: '查看房间' },
  { title: '用户投诉', count: 2, description: '举报、拉黑与人工协助请求', action: '处理工单' }
]

export const roles = [
  { role: '超级管理员', scope: '全站配置与高风险操作', permissions: '全部权限；含角色授权、导出、冻结与审计查看' },
  { role: '运营专员', scope: '用户与推荐运营', permissions: '查看用户；审核资料；运营推荐；不可导出敏感信息' },
  { role: '安全审核员', scope: '认证、举报、异常事件', permissions: '查看必要资料；冻结/解冻建议；处理工单；全量留痕' },
  { role: '红娘顾问', scope: '被分配的真人继续服务', permissions: '仅查看获授权用户与服务摘要；不可查看完整敏感档案' }
]
