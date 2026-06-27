<template>
  <div v-if="loading" class="text-slate-500">加载中…</div>
  <div v-else class="space-y-8">
    <section class="card space-y-4 p-6">
      <h2 class="text-lg font-semibold">Skill 分层</h2>
      <div class="grid gap-4 md:grid-cols-3">
        <div class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
          <div class="font-medium text-brand-700">平台层</div>
          <p class="mt-1 text-slate-600">通用 Twitter 操作（登录、浏览等），所有账号默认继承。</p>
          <ul v-if="catalog.platform.length" class="mt-2 space-y-1 text-xs text-slate-500">
            <li v-for="s in catalog.platform" :key="s.id">{{ s.name }}</li>
          </ul>
        </div>
        <div class="rounded-lg border border-slate-200 p-4 text-sm">
          <div class="font-medium">空间层</div>
          <p class="mt-1 text-slate-600">团队共享 Skill 库（Tactile Skill Plaza），可批量装到账号。</p>
          <p class="mt-2 text-xs text-slate-500">{{ catalog.workspace.length }} 个空间 Skill</p>
        </div>
        <div class="rounded-lg border border-slate-200 p-4 text-sm">
          <div class="font-medium">账号层</div>
          <p class="mt-1 text-slate-600">挂在具体账号下，同步到该账号专属 Tactile Agent。</p>
        </div>
      </div>
    </section>

    <section class="card space-y-4 p-6">
      <h2 class="text-lg font-semibold">创作新 Skill</h2>
      <p class="text-sm text-slate-500">
        描述养号策略或发文逻辑（建议写明输入、输出），将派发到 Tactile Skill 制作助手进行创作。
      </p>
      <input v-model="createTitle" class="input" placeholder="Skill 名称" />
      <textarea
        v-model="createPrompt"
        class="input min-h-[120px] font-mono text-xs"
        placeholder="例如：输入：账号人设 + 当日热点；输出：3 条推文草稿 + 互动建议…"
      />
      <div class="flex flex-wrap items-end gap-3">
        <div>
          <label class="mb-1 block text-xs text-slate-500">参考账号（可选）</label>
          <select v-model.number="createAccountId" class="input w-48">
            <option :value="0">不指定</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">@{{ a.handle }}</option>
          </select>
        </div>
        <button class="btn-primary" :disabled="creating" @click="startCreate">
          {{ creating ? '派发中…' : '开始创作' }}
        </button>
      </div>
      <p v-if="createMsg" class="text-sm text-green-600">{{ createMsg }}</p>
    </section>

    <section class="card space-y-4 p-6">
      <h2 class="text-lg font-semibold">批量安装到账号</h2>
      <div class="grid gap-4 lg:grid-cols-2">
        <div>
          <label class="mb-1 block text-sm font-medium">选择 Skill（空间层 / 我的）</label>
          <select v-model="selectedSkillKey" class="input w-full">
            <option value="">请选择…</option>
            <optgroup label="空间 Skill">
              <option v-for="s in catalog.workspace" :key="'w' + s.id" :value="skillKey(s)">
                {{ s.name }} ({{ s.slug }})
              </option>
            </optgroup>
            <optgroup label="我的 Skill">
              <option v-for="s in catalog.mine" :key="'m' + s.id" :value="skillKey(s)">
                {{ s.name }} ({{ s.slug }})
              </option>
            </optgroup>
          </select>
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">输入契约 JSON（可选）</label>
          <input v-model="inputsJson" class="input font-mono text-xs" placeholder='["persona","topic"]' />
        </div>
        <div>
          <label class="mb-1 block text-sm font-medium">输出契约 JSON（可选）</label>
          <input v-model="outputsJson" class="input font-mono text-xs" placeholder='["drafts","actions"]' />
        </div>
      </div>

      <div>
        <div class="mb-2 flex items-center justify-between">
          <label class="text-sm font-medium">目标账号</label>
          <button type="button" class="text-xs text-brand-600 hover:underline" @click="toggleAllAccounts">
            {{ allSelected ? '取消全选' : '全选' }}
          </button>
        </div>
        <div class="max-h-48 space-y-2 overflow-y-auto rounded-lg border border-slate-200 p-3">
          <label
            v-for="a in accounts"
            :key="a.id"
            class="flex cursor-pointer items-center gap-2 text-sm"
          >
            <input v-model="selectedAccountIds" type="checkbox" :value="a.id" />
            <span>@{{ a.handle }}</span>
            <span v-if="a.tactile_agent_id" class="text-xs text-slate-400">agent {{ a.tactile_agent_id }}</span>
          </label>
        </div>
      </div>

      <button
        class="btn-primary"
        :disabled="installing || !selectedSkill || !selectedAccountIds.length"
        @click="batchInstall"
      >
        {{ installing ? '安装中…' : `安装到 ${selectedAccountIds.length} 个账号` }}
      </button>
      <p v-if="installMsg" class="text-sm" :class="installError ? 'text-red-600' : 'text-green-600'">
        {{ installMsg }}
      </p>
    </section>

    <section class="card space-y-3 p-6">
      <h2 class="text-lg font-semibold">空间 Skill 库</h2>
      <div v-if="!catalog.workspace.length && !catalog.mine.length" class="text-sm text-slate-500">
        暂无 Skill，请先创作或从 Tactile Skill Plaza 上传。
      </div>
      <div v-else class="divide-y divide-slate-100">
        <div
          v-for="s in [...catalog.workspace, ...catalog.mine]"
          :key="s.id + s.slug"
          class="flex flex-wrap items-start justify-between gap-2 py-3 text-sm"
        >
          <div>
            <div class="font-medium">{{ s.name }}</div>
            <div class="text-xs text-slate-500">{{ s.slug }} · v{{ s.current_version || '—' }}</div>
            <p v-if="s.description" class="mt-1 text-slate-600">{{ s.description }}</p>
          </div>
          <span class="badge bg-slate-100 text-slate-600">{{ s.layer }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type SkillCatalog, type SkillCatalogItem, type SocialAccount } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(true)
const catalog = ref<SkillCatalog>({ platform: [], workspace: [], mine: [] })
const accounts = ref<SocialAccount[]>([])

const createTitle = ref('养号 Skill')
const createPrompt = ref('')
const createAccountId = ref(0)
const creating = ref(false)
const createMsg = ref('')

const selectedSkillKey = ref('')
const selectedAccountIds = ref<number[]>([])
const inputsJson = ref('')
const outputsJson = ref('')
const installing = ref(false)
const installMsg = ref('')
const installError = ref(false)

const skillMap = computed(() => {
  const m = new Map<string, SkillCatalogItem>()
  for (const s of [...catalog.value.workspace, ...catalog.value.mine]) {
    m.set(skillKey(s), s)
  }
  return m
})

const selectedSkill = computed(() => skillMap.value.get(selectedSkillKey.value) ?? null)
const allSelected = computed(
  () => accounts.value.length > 0 && selectedAccountIds.value.length === accounts.value.length,
)

function skillKey(s: SkillCatalogItem) {
  return `${s.id}:${s.current_version_id ?? 0}`
}

function toggleAllAccounts() {
  if (allSelected.value) {
    selectedAccountIds.value = []
  } else {
    selectedAccountIds.value = accounts.value.map((a) => a.id)
  }
}

async function load() {
  if (!auth.token) return
  const [cat, accs] = await Promise.all([
    api.skillCatalog(auth.token),
    api.myAccounts(auth.token),
  ])
  catalog.value = cat
  accounts.value = accs
  loading.value = false
}

async function startCreate() {
  if (!auth.token || !createPrompt.value.trim()) return
  creating.value = true
  createMsg.value = ''
  try {
    const res = await api.createSkillSession(auth.token, {
      title: createTitle.value,
      prompt: createPrompt.value,
      account_id: createAccountId.value || undefined,
    })
    createMsg.value = `${res.message} · work_id=${res.tactile_work_id}`
  } catch (e) {
    createMsg.value = e instanceof Error ? e.message : '创作派发失败'
  }
  creating.value = false
}

async function batchInstall() {
  if (!auth.token || !selectedSkill.value) return
  const skill = selectedSkill.value
  if (!skill.current_version_id) {
    installError.value = true
    installMsg.value = 'Skill 缺少 version_id，无法安装'
    return
  }
  installing.value = true
  installMsg.value = ''
  installError.value = false
  try {
    const res = await api.batchInstallSkill(auth.token, {
      skill_id: skill.id,
      version_id: skill.current_version_id,
      account_ids: selectedAccountIds.value,
      slug: skill.slug,
      name: skill.name,
      inputs_json: inputsJson.value.trim() || undefined,
      outputs_json: outputsJson.value.trim() || undefined,
    })
    installMsg.value = `已安装到 ${res.installed_count} 个账号`
  } catch (e) {
    installError.value = true
    installMsg.value = e instanceof Error ? e.message : '批量安装失败'
  }
  installing.value = false
}

onMounted(load)
</script>
