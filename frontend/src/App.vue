<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import SearchBox from './components/SearchBox.vue'
import StockChart from './components/StockChart.vue'
import { Settings, Users, X, Plus, LayoutGrid, Wifi, Globe, TrendingUp, Maximize2, Minimize2 } from 'lucide-vue-next'

// [Decision] 종목명 매핑: 앱 로딩 시 백엔드에서 종목 마스터를 가져와 로컬 캐시
const stockNames = ref<Record<string, string>>({})
const fetchStockNames = async () => {
  try {
    const res = await fetch('/api/stocks/names')
    const data: Record<string, string> = await res.json()
    stockNames.value = data
  } catch (e) { console.error('Failed to fetch stock names') }
}

// [Decision] localStorage 영속화: 그룹/설정을 저장하여 재접속 시 복원
const STORAGE_KEYS = { groups: 'kiwoom_groups', groupName: 'kiwoom_current_group', config: 'kiwoom_config' }

const loadFromStorage = <T>(key: string, fallback: T): T => {
  try {
    const saved = localStorage.getItem(key)
    return saved ? JSON.parse(saved) : fallback
  } catch { return fallback }
}

const DEFAULT_GROUPS: Record<string, string[]> = {
  'Main': ['005930', '000660', '035420', '035720', '005380', '005490', '051910', '000270', '012330', '068270', '105560', '055550', '000810', '034220', '017670', '018260'],
  'Tech': ['000660', '035420', '035720', '066570']
}

const DEFAULT_CONFIG = {
  preferSOR: false,
  timeframe: 'D',
  subIndicator: 'none' as string, // 'RSI' | 'MACD' | 'none'
  visibleCandles: 60,
  indicators: {
    ma1: { type: 'SMA', period: 5, color: '#fb923c', active: true },
    ma2: { type: 'SMA', period: 20, color: '#facc15', active: true },
    ma3: { type: 'EMA', period: 60, color: '#a855f7', active: false },
    ma4: { type: 'WMA', period: 120, color: '#22d3ee', active: false },
    bb1: { type: 'BB', period: 20, color: '#8b5cf6', active: false, mult: 2 },
  } as Record<string, any>
}

const groups = ref<Record<string, string[]>>(loadFromStorage(STORAGE_KEYS.groups, DEFAULT_GROUPS))
const currentGroupName = ref(loadFromStorage(STORAGE_KEYS.groupName, 'Main'))
const currentGroup = computed(() => groups.value[currentGroupName.value] || [])

const INDICATOR_TYPES = ['SMA', 'EMA', 'WMA', 'BB'] as const
const config = ref(loadFromStorage(STORAGE_KEYS.config, DEFAULT_CONFIG))

// 변경 시 자동 저장
watch(groups, (v) => localStorage.setItem(STORAGE_KEYS.groups, JSON.stringify(v)), { deep: true })
watch(currentGroupName, (v) => localStorage.setItem(STORAGE_KEYS.groupName, JSON.stringify(v)))
watch(config, (v) => localStorage.setItem(STORAGE_KEYS.config, JSON.stringify(v)), { deep: true })

const showSettings = ref(false)
const showGroupEditor = ref(false)

const addGroup = () => {
  const name = prompt('New Group Name:')
  if (name && !groups.value[name]) groups.value[name] = []
}

const deleteGroup = (name: string) => {
  if (Object.keys(groups.value).length <= 1) return
  if (confirm(`Delete group "${name}"?`)) {
    delete groups.value[name]
    currentGroupName.value = Object.keys(groups.value)[0]
  }
}

const addStockToGroup = (symbol: string) => {
  if (!currentGroup.value.includes(symbol)) groups.value[currentGroupName.value].push(symbol)
}

const removeStockFromGroup = (symbol: string) => {
  groups.value[currentGroupName.value] = currentGroup.value.filter(s => s !== symbol)
}

const getSymbol = (baseSymbol: string) => {
  return config.value.preferSOR ? `${baseSymbol}_AL` : baseSymbol
}

const getStockName = (code: string) => {
  return stockNames.value[code] || ''
}

// [Decision] 마우스 추적: body에 CSS 변수 업데이트 → radial-gradient 글로우 이동
const onMouseMove = (e: MouseEvent) => {
  document.body.style.setProperty('--mx', `${e.clientX}px`)
  document.body.style.setProperty('--my', `${e.clientY}px`)
}

// 설정 창에 지표 추가/삭제
const addIndicator = () => {
  const keys = Object.keys(config.value.indicators)
  const nextNum = keys.length + 1
  const id = `ma${nextNum}`
  config.value.indicators[id] = { type: 'SMA', period: 20, color: '#94a3b8', active: true }
}
const removeIndicator = (key: string) => {
  delete config.value.indicators[key]
}

// [Decision] 현재가/등락률 상태: 종목별 캐시
const priceData = ref<Record<string, { price: number, change: number, changePercent: number }>>({})
const onPriceUpdate = (symbol: string, data: { price: number, change: number, changePercent: number }) => {
  priceData.value[symbol] = data
}

const formatPrice = (n: number) => n ? n.toLocaleString('ko-KR') : ''
const formatPercent = (n: number) => n ? (n > 0 ? '+' : '') + n.toFixed(2) + '%' : ''

// [Decision] 더블클릭 풀스크린: 특정 종목을 풀화면 표시
const fullscreenSymbol = ref<string | null>(null)
const toggleFullscreen = (symbol: string) => {
  fullscreenSymbol.value = fullscreenSymbol.value === symbol ? null : symbol
  // 풀스크린 해제 시 모든 차트 리사이즈 트리거
  nextTick(() => window.dispatchEvent(new Event('resize')))
}
const exitFullscreen = () => { fullscreenSymbol.value = null }

// ESC로 풀스크린 종료
const onKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Escape') exitFullscreen()
}

onMounted(() => {
  fetchStockNames()
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('keydown', onKeyDown)
})
</script>

<template>
  <div class="h-screen w-screen flex flex-col text-slate-300 overflow-hidden" @mousemove="onMouseMove">

    <!-- Top Navigation Bar -->
    <header class="h-11 flex items-center justify-between px-4">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <LayoutGrid :size="15" class="text-blue-500" />
          <h1 class="font-black text-sm tracking-tighter text-slate-100">KIWOOM<span
              class="text-blue-500 logo-glow">PRO</span></h1>
        </div>

        <div class="flex items-center gap-2 ml-4">
          <select v-model="currentGroupName"
            class="bg-transparent text-[11px] font-bold text-slate-400 border-none outline-none cursor-pointer">
            <option v-for="(v, k) in groups" :key="k" :value="k" class="bg-[#0d1017]">{{ k }}</option>
          </select>
          <button @click="showGroupEditor = true" class="p-1 hover:bg-white/5 rounded-lg text-slate-500 transition-all">
            <Users :size="14" />
          </button>
        </div>

        <button @click="config.preferSOR = !config.preferSOR"
          :class="config.preferSOR ? 'text-blue-400' : 'text-slate-600'"
          class="text-[10px] font-black ml-4 tracking-tighter transition-colors">SOR</button>
      </div>

      <div class="flex items-center gap-6">
        <div class="flex items-center gap-4 text-[10px] font-bold text-slate-500">
          <div class="flex items-center gap-1.5">
            <Globe :size="11" class="text-emerald-500" /> OPEN
          </div>
          <div class="flex items-center gap-1.5">
            <Wifi :size="11" class="text-blue-500" /> STABLE
          </div>
        </div>

        <div class="flex items-center gap-0.5 p-0.5 bg-white/[0.02] rounded-lg">
          <button v-for="tf in ['1', '5', '15', '60', 'D', 'W']" :key="tf" @click="config.timeframe = tf"
            class="timeframe-btn" :class="{ active: config.timeframe === tf }">{{ tf }}</button>
        </div>

        <!-- 서브 인디케이터 선택 -->
        <div class="flex items-center gap-0.5 p-0.5 bg-white/[0.02] rounded-lg">
          <button v-for="si in ['none', 'RSI', 'MACD']" :key="si" @click="config.subIndicator = si"
            class="timeframe-btn" :class="{ active: config.subIndicator === si }">
            {{ si === 'none' ? '—' : si }}
          </button>
        </div>

        <!-- 캔들 수 -->
        <div class="flex items-center gap-0.5 p-0.5 bg-white/[0.02] rounded-lg">
          <button v-for="cnt in [30, 60, 120, 0]" :key="cnt" @click="config.visibleCandles = cnt" class="timeframe-btn"
            :class="{ active: config.visibleCandles === cnt }">
            {{ cnt === 0 ? 'All' : cnt }}
          </button>
        </div>

        <button @click="showSettings = true" class="p-1.5 hover:bg-white/5 rounded-lg text-slate-500 transition-all">
          <Settings :size="15" />
        </button>
      </div>
    </header>

    <!-- 4x4 Chart Grid -->
    <main :class="{ 'fullscreen-mode': fullscreenSymbol }">
      <div v-for="baseSymbol in currentGroup.slice(0, 16)" :key="baseSymbol + config.preferSOR" :class="[
        'chart-card group',
        fullscreenSymbol && fullscreenSymbol !== baseSymbol ? 'chart-hidden' : '',
        fullscreenSymbol === baseSymbol ? 'fullscreen-card' : ''
      ]" @dblclick="toggleFullscreen(baseSymbol)">
        <div class="stock-header">
          <div class="flex items-center gap-2">
            <div class="flex items-center">
              <span class="stock-code">{{ getSymbol(baseSymbol) }}</span>
              <span class="stock-name">{{ getStockName(baseSymbol) }}</span>
            </div>
            <!-- 현재가 / 등락률 -->
            <div v-if="priceData[baseSymbol]" class="flex items-center gap-1.5 ml-1">
              <span class="text-[10px] font-black"
                :class="priceData[baseSymbol].change >= 0 ? 'text-emerald-400' : 'text-rose-400'">
                {{ formatPrice(priceData[baseSymbol].price) }}
              </span>
              <span class="text-[9px] font-bold px-1 py-0.5 rounded"
                :class="priceData[baseSymbol].change >= 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10'">
                {{ formatPercent(priceData[baseSymbol].changePercent) }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button @click.stop="toggleFullscreen(baseSymbol)"
              class="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-blue-400 transition-all">
              <Maximize2 v-if="fullscreenSymbol !== baseSymbol" :size="10" />
              <Minimize2 v-else :size="10" />
            </button>
            <button @click.stop="removeStockFromGroup(baseSymbol)"
              class="opacity-0 group-hover:opacity-100 text-slate-700 hover:text-rose-500 transition-all">
              <X :size="10" />
            </button>
          </div>
        </div>
        <StockChart :symbol="getSymbol(baseSymbol)" :timeframe="config.timeframe" :indicators="config.indicators"
          :visibleCandles="config.visibleCandles" :subIndicator="config.subIndicator"
          @priceUpdate="(data) => onPriceUpdate(baseSymbol, data)" />
      </div>
      <!-- Empty Slot -->
      <div v-if="currentGroup.length < 16" class="empty-slot">
        <button @click="showGroupEditor = true" class="text-slate-500 flex flex-col items-center gap-1">
          <Plus :size="18" /> <span class="text-[9px] font-bold uppercase tracking-wider">Add</span>
        </button>
      </div>
    </main>

    <!-- Indicator Settings Modal -->
    <div v-if="showSettings" class="fixed inset-0 z-[100] flex items-center justify-center modal-overlay"
      @click.self="showSettings = false">
      <div class="modal-panel rounded-2xl w-96 overflow-hidden">
        <div class="flex items-center justify-between p-5 border-b border-white/5">
          <div class="flex items-center gap-3">
            <div class="p-2 bg-blue-500/10 rounded-xl">
              <TrendingUp :size="18" class="text-blue-400" />
            </div>
            <div>
              <h2 class="font-bold text-sm text-slate-100">Indicators</h2>
              <p class="text-[10px] text-slate-500 uppercase tracking-widest">Technical Analysis</p>
            </div>
          </div>
          <button @click="showSettings = false" class="text-slate-500 hover:text-white transition-colors">
            <X :size="18" />
          </button>
        </div>

        <div class="p-5 space-y-3 max-h-[400px] overflow-y-auto">
          <div v-for="(ind, k) in config.indicators" :key="k"
            class="flex items-center justify-between p-3 bg-white/[0.02] rounded-xl border border-white/5 hover:border-white/10 transition-all">
            <div class="flex items-center gap-3">
              <div class="indicator-toggle" :class="{ active: ind.active }" @click="ind.active = !ind.active"></div>
              <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" :style="{ backgroundColor: ind.color }"></div>
                <select v-model="ind.type"
                  class="bg-transparent text-[10px] font-black text-slate-300 uppercase tracking-wider border-none outline-none cursor-pointer">
                  <option v-for="t in INDICATOR_TYPES" :key="t" :value="t" class="bg-[#1a1e27]">{{ t }}</option>
                </select>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-1.5">
                <span class="text-[9px] text-slate-600 font-bold">P</span>
                <input type="number" v-model="ind.period"
                  class="w-10 bg-transparent border-b border-white/10 text-xs text-center font-mono py-0.5 text-slate-300 outline-none focus:border-blue-500/30" />
              </div>
              <div v-if="ind.type === 'BB'" class="flex items-center gap-1.5">
                <span class="text-[9px] text-slate-600 font-bold">M</span>
                <input type="number" v-model="ind.mult" step="0.5"
                  class="w-8 bg-transparent border-b border-white/10 text-xs text-center font-mono py-0.5 text-slate-300 outline-none" />
              </div>
              <input type="color" v-model="ind.color"
                class="w-5 h-5 rounded cursor-pointer border-none bg-transparent" />
              <button @click="removeIndicator(k as string)"
                class="text-slate-700 hover:text-rose-500 transition-colors">
                <X :size="12" />
              </button>
            </div>
          </div>
        </div>

        <div class="p-5 pt-0 flex gap-2">
          <button @click="addIndicator"
            class="flex-1 py-2.5 rounded-xl text-[10px] font-bold uppercase tracking-wider text-slate-400 border border-dashed border-white/10 hover:border-blue-500/30 hover:text-blue-400 transition-all">
            <Plus :size="12" class="inline mr-1" />Add Indicator
          </button>
          <button @click="showSettings = false"
            class="flex-1 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 rounded-xl font-bold text-[10px] text-white uppercase tracking-wider shadow-lg shadow-blue-900/20 active:scale-95 transition-all">
            Apply
          </button>
        </div>
      </div>
    </div>

    <!-- Group Editor Modal -->
    <div v-if="showGroupEditor" class="fixed inset-0 z-[100] flex items-center justify-center modal-overlay"
      @click.self="showGroupEditor = false">
      <div class="modal-panel rounded-2xl w-[450px] overflow-hidden">
        <div class="flex items-center justify-between p-4 border-b border-white/5">
          <div class="flex items-center gap-2">
            <div class="p-2 bg-blue-500/10 rounded-xl text-blue-400">
              <Users :size="18" />
            </div>
            <div>
              <h2 class="text-sm font-bold text-slate-100">Watchlist Manager</h2>
              <p class="text-[10px] text-slate-500 uppercase tracking-widest">Edit groups and symbols</p>
            </div>
          </div>
          <button @click="showGroupEditor = false" class="text-slate-500 hover:text-white transition-colors">
            <X :size="20" />
          </button>
        </div>

        <div class="p-6">
          <div class="flex items-center gap-2 mb-6 p-1 bg-black/40 rounded-xl">
            <button v-for="(v, k) in groups" :key="k" @click="currentGroupName = k as string"
              :class="currentGroupName === k ? 'bg-white/10 text-white shadow-sm' : 'text-slate-500 hover:text-slate-300'"
              class="flex-1 py-2 text-[11px] font-bold rounded-lg transition-all uppercase">
              {{ k }}
            </button>
            <button @click="addGroup" class="px-3 text-blue-500 hover:scale-110 transition-transform">
              <Plus :size="16" />
            </button>
          </div>

          <div class="mb-6">
            <h3 class="text-[10px] text-slate-500 font-bold mb-3 uppercase tracking-widest">Add New Symbol</h3>
            <SearchBox @search="addStockToGroup" />
          </div>

          <div class="bg-black/20 rounded-xl border border-white/5 p-4 min-h-[180px]">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Current Symbols</h3>
              <button @click="deleteGroup(currentGroupName)"
                class="text-[10px] text-rose-500/70 hover:text-rose-500 hover:underline transition-all">Delete
                Group</button>
            </div>
            <div class="flex flex-wrap gap-2">
              <div v-for="s in currentGroup" :key="s"
                class="flex items-center gap-2 bg-white/[0.03] border border-white/5 px-2.5 py-1.5 rounded-lg text-[11px] font-mono hover:border-blue-500/20 transition-all group/tag">
                <span class="text-slate-300 font-bold">{{ s }}</span>
                <span class="text-slate-600 text-[9px]">{{ getStockName(s) }}</span>
                <button @click="removeStockFromGroup(s)" class="text-slate-700 hover:text-rose-500 transition-colors">
                  <X :size="10" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>
