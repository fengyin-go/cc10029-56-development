<template>
  <section class="page" data-module="evidence">
    <header class="page-head">
      <div>
        <h2>外评证据凭证</h2>
        <p class="page-desc">
          按评估报告发放教学档案只读授权：凭证受报告与档案双重归属限制，外部收件人仅可核对；
          档案注销会冻结凭证、阻断受理回执并生成外评补件待办。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-grant" type="button" @click="openGrantModal">
          发放授权凭证
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">授权凭证</span>
        <strong class="stat-value">{{ grants.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">有效凭证</span>
        <strong class="stat-value">{{ activeGrantCount }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">受理回执</span>
        <strong class="stat-value">{{ tickets.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待办补件</span>
        <strong class="stat-value">{{ pendingSupplementCount }}</strong>
      </article>
    </div>

    <nav class="tab-bar" data-testid="evidence-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        :data-testid="`tab-${tab.key}`"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <p v-if="message" class="inline-message" :class="messageKind" data-testid="evidence-message">
      {{ message }}
    </p>

    <!-- 凭证台账 -->
    <table v-if="activeTab === 'grants'" class="data-table" data-testid="grant-table">
      <thead>
        <tr>
          <th>凭证编号</th><th>评估报告</th><th>档案</th><th>外部收件人</th>
          <th>发放人</th><th>权限</th><th>状态</th><th>签收</th><th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="grant in grants" :key="grant.id" :data-status="grant.状态">
          <td>{{ grant.凭证编号 }}</td>
          <td>R-{{ grant.评估报告ID }}</td>
          <td>#{{ grant.档案ID }}（{{ grant.档案快照?.['教师姓名'] ?? '—' }}）</td>
          <td>{{ grant.外部收件人 }}</td>
          <td>{{ grant.发放人 }}</td>
          <td>{{ grant.权限范围 }}</td>
          <td>{{ grant.状态 }}<small v-if="grant.失效原因">：{{ grant.失效原因 }}</small></td>
          <td>{{ grant.签收状态 }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="inspectGrant(grant)">凭证详情</button>
            <button
              class="link" type="button"
              :disabled="grant.状态 !== '有效'"
              @click="openReadModal(grant)"
            >只读核对</button>
            <button
              class="link" type="button"
              :disabled="grant.状态 !== '有效'"
              @click="openTicketModal(grant)"
            >材料验票</button>
          </td>
        </tr>
        <tr v-if="!grants.length">
          <td colspan="9" class="empty-state">暂无授权凭证，先按评估报告发放</td>
        </tr>
      </tbody>
    </table>

    <!-- 受理回执 -->
    <table v-else-if="activeTab === 'tickets'" class="data-table" data-testid="ticket-table">
      <thead>
        <tr>
          <th>回执编号</th><th>来源凭证</th><th>评估报告</th><th>档案</th>
          <th>收件人</th><th>受理日期</th><th>状态</th><th>引用填写</th><th>阻断原因</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="ticket in tickets" :key="ticket.id" :data-status="ticket.状态">
          <td>{{ ticket.回执编号 }}</td>
          <td>{{ ticket.凭证编号 }}</td>
          <td>R-{{ ticket.评估报告ID }}</td>
          <td>#{{ ticket.档案ID }}</td>
          <td>{{ ticket.外部收件人 }}</td>
          <td>{{ ticket.受理日期 }}</td>
          <td>{{ ticket.状态 }}</td>
          <td>{{ ticket.引用填写状态 }}</td>
          <td>{{ ticket.阻断原因 || '—' }}</td>
        </tr>
        <tr v-if="!tickets.length">
          <td colspan="9" class="empty-state">暂无受理回执，评审员完成材料验票后自动出具</td>
        </tr>
      </tbody>
    </table>

    <!-- 外评补件待办 -->
    <table v-else-if="activeTab === 'supplements'" class="data-table" data-testid="supplement-table">
      <thead>
        <tr>
          <th>补件编号</th><th>评估报告</th><th>注销档案</th><th>来源凭证</th>
          <th>来源回执</th><th>收件人</th><th>触发原因</th><th>状态</th><th>替代办理</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in supplements" :key="item.id" :data-status="item.状态">
          <td>{{ item.补件编号 }}</td>
          <td>R-{{ item.评估报告ID }}</td>
          <td>#{{ item.档案ID }}</td>
          <td>{{ item.来源凭证编号 }}</td>
          <td>{{ item.来源回执编号 }}</td>
          <td>{{ item.外部收件人 }}</td>
          <td>{{ item.触发原因 }}</td>
          <td>{{ item.状态 }}</td>
          <td class="row-actions">
            <button
              v-if="item.状态 === '待补件'"
              class="link" type="button"
              @click="openSupplementModal(item)"
            >用新凭证办结</button>
            <span v-else>
              {{ item.替代凭证编号 }} / {{ item.替代回执编号 }}
            </span>
          </td>
        </tr>
        <tr v-if="!supplements.length">
          <td colspan="9" class="empty-state">暂无补件待办；档案注销时会自动生成</td>
        </tr>
      </tbody>
    </table>

    <!-- 接收报告校验 -->
    <div v-else class="receive-panel" data-testid="receive-panel">
      <form class="filter-bar" @submit.prevent="runReceiveCheck">
        <label class="filter-item">
          <span>评估报告 ID</span>
          <input v-model="checkEvalId" data-testid="receive-eval-id" placeholder="例如 R-26 填 26" />
        </label>
        <button class="btn primary" data-testid="receive-check-btn" type="submit">接收前凭证体检</button>
      </form>
      <template v-if="diagnosis">
        <article class="stat-card" :class="diagnosis.可接收 ? 'ok' : 'blocked'">
          <span class="stat-label">体检结论（R-{{ diagnosis.评估报告ID }}）</span>
          <strong class="stat-value">{{ diagnosis.可接收 ? '可以接收报告' : '暂缓接收' }}</strong>
          <p class="page-desc">{{ diagnosis.提示 }}</p>
        </article>
        <table class="data-table">
          <thead>
            <tr><th>回执编号</th><th>凭证编号</th><th>档案</th><th>收件人</th><th>状态</th><th>引用填写</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in diagnosis.受理回执" :key="t.回执编号" :data-status="t.状态">
              <td>{{ t.回执编号 }}</td>
              <td>{{ t.凭证编号 }}</td>
              <td>#{{ t.档案ID }}</td>
              <td>{{ t.外部收件人 }}</td>
              <td>{{ t.状态 }}<small v-if="t.阻断原因">：{{ t.阻断原因 }}</small></td>
              <td>{{ t.引用填写状态 }}</td>
            </tr>
            <tr v-if="!diagnosis.受理回执.length">
              <td colspan="6" class="empty-state">该报告暂无凭证验票记录</td>
            </tr>
          </tbody>
        </table>
      </template>
    </div>

    <!-- 发放授权 -->
    <div v-if="showGrantModal" class="modal-backdrop" data-testid="grant-modal">
      <form class="modal" @submit.prevent="submitGrant">
        <h3>发放授权凭证（外部收件人只读）</h3>
        <label class="create-field"><span>评估报告 ID</span><input v-model="grantForm.eval_id" required /></label>
        <label class="create-field"><span>教学档案 ID（须已归档）</span><input v-model="grantForm.record_id" required /></label>
        <label class="create-field"><span>外部收件人</span><input v-model="grantForm.recipient" required /></label>
        <label class="create-field"><span>发放人（资料员）</span><input v-model="grantForm.issuer" required /></label>
        <label class="create-field"><span>用途说明</span><input v-model="grantForm.purpose" placeholder="例如：R-26 材料验票" /></label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showGrantModal = false">取消</button>
          <button class="btn primary" data-testid="submit-grant" type="submit">确认发放</button>
        </div>
      </form>
    </div>

    <!-- 受控只读核对 -->
    <div v-if="readTarget" class="modal-backdrop" data-testid="read-modal">
      <div class="modal">
        <h3>凭证 {{ readTarget.凭证编号 }} 只读核对</h3>
        <p class="page-desc">
          归属报告 R-{{ readTarget.评估报告ID }}，授权档案 #{{ readTarget.档案ID }}；
          跨报告或跨档案使用将被拒绝。
        </p>
        <div class="page-actions">
          <button class="btn" type="button" @click="readTarget = null">关闭</button>
          <button class="btn primary" data-testid="submit-read" type="button" @click="submitRead">
            按归属读取档案
          </button>
        </div>
        <pre v-if="readResult" class="read-result">{{ readResult }}</pre>
      </div>
    </div>

    <!-- 材料验票 -->
    <div v-if="ticketTarget" class="modal-backdrop" data-testid="ticket-modal">
      <div class="modal">
        <h3>材料验票：{{ ticketTarget.凭证编号 }}</h3>
        <p class="page-desc">
          校验凭证与报告 R-{{ ticketTarget.评估报告ID }}、档案 #{{ ticketTarget.档案ID }}
          的归属一致性，通过后出具受理回执，评审员据此填写报告引用。
        </p>
        <div class="page-actions">
          <button class="btn" type="button" @click="ticketTarget = null">取消</button>
          <button class="btn primary" data-testid="submit-ticket" type="button" @click="submitTicket">
            完成验票
          </button>
        </div>
      </div>
    </div>

    <!-- 凭证详情（历史追溯） -->
    <div v-if="detailGrant" class="modal-backdrop" data-testid="detail-modal">
      <div class="modal">
        <h3>凭证详情：{{ detailGrant.凭证编号 }}</h3>
        <dl class="detail-list">
          <dt>发给谁</dt><dd>{{ detailGrant.外部收件人 }}</dd>
          <dt>实际使用档案</dt><dd>#{{ detailGrant.档案ID }}（{{ detailGrant.档案快照?.['教师姓名'] ?? '—' }}）</dd>
          <dt>归属报告</dt><dd>R-{{ detailGrant.评估报告ID }}</dd>
          <dt>发放日期 / 状态</dt><dd>{{ detailGrant.发放日期 }} / {{ detailGrant.状态 }} {{ detailGrant.失效原因 }}</dd>
          <dt>发放时点档案快照</dt><dd>{{ detailGrant.档案快照 }}</dd>
        </dl>
        <h4>访问审计</h4>
        <table class="data-table">
          <thead><tr><th>时间</th><th>报告</th><th>档案</th><th>结果</th></tr></thead>
          <tbody>
            <tr v-for="(log, idx) in detailLogs" :key="idx">
              <td>{{ log['读取时间'] }}</td><td>R-{{ log['评估报告ID'] }}</td>
              <td>#{{ log['档案ID'] }}</td><td>{{ log['读取结果'] }}</td>
            </tr>
            <tr v-if="!detailLogs.length"><td colspan="4" class="empty-state">暂无访问记录</td></tr>
          </tbody>
        </table>
        <div class="page-actions">
          <button class="btn primary" type="button" @click="detailGrant = null">关闭</button>
        </div>
      </div>
    </div>

    <!-- 补件办结 -->
    <div v-if="supplementTarget" class="modal-backdrop" data-testid="supplement-modal">
      <form class="modal" @submit.prevent="submitSupplement">
        <h3>补件 {{ supplementTarget.补件编号 }} 替代办理</h3>
        <p class="page-desc">
          注销档案 #{{ supplementTarget.档案ID }} 的原授权已失效；请填写同报告下
          替代档案的新凭证编号（须已完成验票）。补件不能跨报告沿用旧授权。
        </p>
        <label class="create-field">
          <span>替代凭证编号</span>
          <input v-model="newGrantNo" data-testid="supplement-grant-no" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="supplementTarget = null">取消</button>
          <button class="btn primary" data-testid="submit-supplement" type="submit">办结补件</button>
        </div>
      </form>
    </div>

    <footer class="page-foot">
      <span>外部收件人对教学档案仅只读；授权、回执、补件全程留痕可按原编号追溯</span>
      <span v-if="message" :class="messageKind">{{ message }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  acceptTicket,
  completeSupplement,
  getGrant,
  issueGrant,
  listGrants,
  listSupplements,
  listTickets,
  readEvidence,
  receiveCheck,
} from '@/api/evidence-service'
import type {
  EvalSupplement,
  EvidenceGrant,
  EvidenceTicket,
  ReceiveDiagnosis,
} from '@/data/types'

const tabs = [
  { key: 'grants', label: '授权凭证' },
  { key: 'tickets', label: '受理回执' },
  { key: 'supplements', label: '外评补件待办' },
  { key: 'receive', label: '接收报告校验' },
] as const

const activeTab = ref<(typeof tabs)[number]['key']>('grants')
const grants = ref<EvidenceGrant[]>([])
const tickets = ref<EvidenceTicket[]>([])
const supplements = ref<EvalSupplement[]>([])
const message = ref('')
const messageKind = ref<'ok' | 'error-text'>('ok')

const showGrantModal = ref(false)
const grantForm = ref({ eval_id: '', record_id: '', recipient: '', issuer: '', purpose: '' })
const readTarget = ref<EvidenceGrant | null>(null)
const readResult = ref('')
const ticketTarget = ref<EvidenceGrant | null>(null)
const detailGrant = ref<EvidenceGrant | null>(null)
const detailLogs = ref<Record<string, string | number>[]>([])
const supplementTarget = ref<EvalSupplement | null>(null)
const newGrantNo = ref('')
const checkEvalId = ref('')
const diagnosis = ref<ReceiveDiagnosis | null>(null)

const activeGrantCount = computed(() => grants.value.filter((g) => g.状态 === '有效').length)
const pendingSupplementCount = computed(() => supplements.value.filter((s) => s.状态 === '待补件').length)

function notify(text: string, ok = true) {
  message.value = text
  messageKind.value = ok ? 'ok' : 'error-text'
}

async function reload() {
  const [grantRows, ticketRows, supplementRows] = await Promise.all([
    listGrants(),
    listTickets(),
    listSupplements(),
  ])
  grants.value = grantRows
  tickets.value = ticketRows
  supplements.value = supplementRows
}

function openGrantModal() {
  grantForm.value = { eval_id: '', record_id: '', recipient: '', issuer: '', purpose: '' }
  showGrantModal.value = true
}

async function submitGrant() {
  const result = await issueGrant({
    eval_id: Number(grantForm.value.eval_id),
    record_id: Number(grantForm.value.record_id),
    recipient: grantForm.value.recipient,
    issuer: grantForm.value.issuer,
    purpose: grantForm.value.purpose,
  })
  notify(result.message, result.ok)
  if (result.ok) {
    showGrantModal.value = false
    await reload()
  }
}

function openReadModal(grant: EvidenceGrant) {
  readTarget.value = grant
  readResult.value = ''
}

async function submitRead() {
  if (!readTarget.value) return
  const result = await readEvidence(
    readTarget.value.凭证编号,
    readTarget.value.评估报告ID,
    readTarget.value.档案ID,
  )
  notify(result.message, result.ok)
  if (result.ok && result.entry) readResult.value = JSON.stringify(result.entry, null, 2)
}

function openTicketModal(grant: EvidenceGrant) {
  ticketTarget.value = grant
}

async function submitTicket() {
  if (!ticketTarget.value) return
  const result = await acceptTicket(
    ticketTarget.value.凭证编号,
    ticketTarget.value.评估报告ID,
    ticketTarget.value.档案ID,
  )
  notify(result.message, result.ok)
  if (result.ok) {
    ticketTarget.value = null
    await reload()
  }
}

async function inspectGrant(grant: EvidenceGrant) {
  const result = await getGrant(grant.凭证编号)
  if (!result.ok || !result.entry) {
    notify(result.message, false)
    return
  }
  detailGrant.value = result.entry
  detailLogs.value = result.access_logs ?? []
}

function openSupplementModal(item: EvalSupplement) {
  supplementTarget.value = item
  newGrantNo.value = ''
}

async function submitSupplement() {
  if (!supplementTarget.value) return
  const result = await completeSupplement(supplementTarget.value.id, newGrantNo.value.trim())
  notify(result.message, result.ok)
  if (result.ok) {
    supplementTarget.value = null
    await reload()
  }
}

async function runReceiveCheck() {
  try {
    diagnosis.value = await receiveCheck(Number(checkEvalId.value))
    notify(diagnosis.value.提示, diagnosis.value.可接收)
  } catch (error) {
    diagnosis.value = null
    notify(error instanceof Error ? error.message : '接收体检失败', false)
  }
}

onMounted(reload)
</script>

<style scoped>
.tab-bar {
  display: flex;
  gap: 8px;
  margin: 8px 0 14px;
  border-bottom: 1px solid var(--border);
}
.tab-btn {
  border: none;
  background: none;
  padding: 8px 14px;
  cursor: pointer;
  font-size: 13px;
  color: var(--muted);
  border-bottom: 2px solid transparent;
}
.tab-btn.active {
  color: var(--brand);
  border-bottom-color: var(--brand);
  font-weight: 600;
}
.inline-message {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  background: #ecfdf3;
  color: #027a48;
  border: 1px solid #abefc6;
}
.inline-message.error-text {
  background: #fef3f2;
  color: #b42318;
  border-color: #fda29b;
}
.stat-card.ok { border-color: #abefc6; }
.stat-card.blocked { border-color: #fda29b; }
.read-result {
  margin-top: 12px;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  padding: 12px;
  font-size: 12px;
  max-height: 260px;
  overflow: auto;
}
.detail-list {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 6px 12px;
  font-size: 13px;
}
.detail-list dt { color: var(--muted); }
.detail-list dd { margin: 0; }
.receive-panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
small { color: var(--muted); }
</style>
