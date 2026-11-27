/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

/** 外评证据受控凭证：授权凭证 */
export type EvidenceGrant = {
  id: number
  凭证编号: string
  评估报告ID: number
  档案ID: number
  外部收件人: string
  发放人: string
  发放日期: string
  用途说明: string
  权限范围: string
  状态: string
  失效原因: string
  签收状态: string
  档案快照: Record<string, string>
}

/** 受理回执：材料验票通过后出具，是接收报告时填写引用的凭据 */
export type EvidenceTicket = {
  id: number
  回执编号: string
  凭证编号: string
  评估报告ID: number
  档案ID: number
  外部收件人: string
  受理日期: string
  受理结论: string
  状态: string
  引用填写状态: string
  阻断原因: string
}

/** 外评补件待办：档案资格变化（注销）自动生成 */
export type EvalSupplement = {
  id: number
  补件编号: string
  评估报告ID: number
  档案ID: number
  来源凭证编号: string
  来源回执编号: string
  外部收件人: string
  触发原因: string
  生成日期: string
  状态: string
  替代凭证编号: string
  替代回执编号: string
  完成日期: string
  备注说明: string
}

export type ReceiveDiagnosis = {
  评估报告ID: number
  可接收: boolean
  提示: string
  受理回执: Pick<EvidenceTicket, '回执编号' | '凭证编号' | '档案ID' | '外部收件人' | '状态' | '引用填写状态' | '阻断原因'>[]
  阻断数: number
  待补件数: number
}

export type EvidenceApiResult<T = Record<string, unknown>> = {
  ok: boolean
  message: string
  entry?: T
  items?: T[]
  diagnosis?: ReceiveDiagnosis
  access_logs?: Record<string, string | number>[]
}
