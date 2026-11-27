/** 外评证据受控凭证接口：授权发放、受控只读、验票回执、补件闭环、接收体检。 */
import { request } from './client'
import type {
  EvalSupplement,
  EvidenceApiResult,
  EvidenceGrant,
  EvidenceTicket,
  ReceiveDiagnosis,
} from '@/data/types'

async function call<T>(path: string, init?: RequestInit): Promise<EvidenceApiResult<T>> {
  const response = await request(path, init)
  return (await response.json()) as EvidenceApiResult<T>
}

/** 授权入口：按评估报告发放针对指定档案的只读凭证。 */
export function issueGrant(payload: {
  eval_id: number
  record_id: number
  recipient: string
  issuer: string
  purpose?: string
}): Promise<EvidenceApiResult<EvidenceGrant>> {
  return call('/api/evidence/grants', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 凭证台账：可按评估报告过滤；已签收/已失效凭证均保留原编号。 */
export async function listGrants(evalId?: number): Promise<EvidenceGrant[]> {
  const query = evalId ? `?eval_id=${evalId}` : ''
  const result = await call<EvidenceGrant>(`/api/evidence/grants${query}`)
  return result.items ?? []
}

/** 按原编号查凭证：发给谁、实际用了哪件档案、访问审计。 */
export async function getGrant(grantNo: string): Promise<EvidenceApiResult<EvidenceGrant>> {
  return call<EvidenceGrant>(`/api/evidence/grants/${encodeURIComponent(grantNo)}`)
}

/** 受控只读：外部收件人持凭证按报告/档案归属核对档案。 */
export function readEvidence(
  grantNo: string,
  evalId: number,
  recordId: number,
): Promise<EvidenceApiResult> {
  return call(`/api/evidence/grants/${encodeURIComponent(grantNo)}/read`, {
    method: 'POST',
    body: JSON.stringify({ eval_id: evalId, record_id: recordId }),
  })
}

/** 材料验票：校验凭证与报告引用归属，通过后出具受理回执。 */
export function acceptTicket(
  grantNo: string,
  evalId: number,
  recordId: number,
): Promise<EvidenceApiResult<EvidenceTicket>> {
  return call(`/api/evidence/grants/${encodeURIComponent(grantNo)}/tickets`, {
    method: 'POST',
    body: JSON.stringify({ eval_id: evalId, record_id: recordId }),
  })
}

/** 受理回执台账。 */
export async function listTickets(evalId?: number): Promise<EvidenceTicket[]> {
  const query = evalId ? `?eval_id=${evalId}` : ''
  const result = await call<EvidenceTicket>(`/api/evidence/tickets${query}`)
  return result.items ?? []
}

/** 外评补件待办台账。 */
export async function listSupplements(params?: {
  evalId?: number
  status?: string
}): Promise<EvalSupplement[]> {
  const search = new URLSearchParams()
  if (params?.evalId) search.set('eval_id', String(params.evalId))
  if (params?.status) search.set('status', params.status)
  const query = search.toString() ? `?${search.toString()}` : ''
  const result = await call<EvalSupplement>(`/api/evidence/supplements${query}`)
  return result.items ?? []
}

/** 补件闭环：用替代档案的新凭证办结，旧授权不得跨报告沿用。 */
export function completeSupplement(
  supplementId: number,
  newGrantNo: string,
): Promise<EvidenceApiResult<EvalSupplement>> {
  return call(`/api/evidence/supplements/${supplementId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ new_grant_no: newGrantNo }),
  })
}

/** 接收报告入口前置体检：原授权能否完成已受理引用。 */
export async function receiveCheck(evalId: number): Promise<ReceiveDiagnosis> {
  const result = await call(`/api/evidence/reports/${evalId}/receive-check`)
  if (!result.ok || !result.diagnosis) throw new Error(result.message || '接收体检失败')
  return result.diagnosis
}
