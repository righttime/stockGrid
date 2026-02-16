<script setup lang="ts">
import { ref } from 'vue'
import { Search } from 'lucide-vue-next'

const emit = defineEmits<{ (e: 'search', symbol: string): void }>()

const query = ref('')
const suggestions = ref<{ code: string, name: string }[]>([])
const showSuggestions = ref(false)
const selectedIndex = ref(-1)
let debounceTimer: any = null

const fetchSuggestions = async () => {
  if (query.value.length < 1) {
    suggestions.value = []
    showSuggestions.value = false
    return
  }
  try {
    const res = await fetch(`/api/stocks/search?q=${encodeURIComponent(query.value)}`)
    suggestions.value = await res.json()
    showSuggestions.value = suggestions.value.length > 0
    selectedIndex.value = -1
  } catch (e) {
    suggestions.value = []
  }
}

const onInput = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchSuggestions, 200)
}

const selectStock = (stock: { code: string, name: string }) => {
  emit('search', stock.code)
  query.value = ''
  showSuggestions.value = false
  suggestions.value = []
}

const handleSearch = () => {
  // 키보드 선택 중이면 해당 항목 선택
  if (selectedIndex.value >= 0 && selectedIndex.value < suggestions.value.length) {
    selectStock(suggestions.value[selectedIndex.value])
    return
  }
  if (query.value.length >= 2) {
    // 정확한 코드 매칭이 있으면 바로 추가
    const exact = suggestions.value.find(s => s.code === query.value)
    if (exact) {
      selectStock(exact)
    } else if (query.value.length >= 6) {
      emit('search', query.value)
      query.value = ''
      showSuggestions.value = false
    }
  }
}

const onKeyDown = (e: KeyboardEvent) => {
  if (!showSuggestions.value || suggestions.value.length === 0) return
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    selectedIndex.value = Math.min(selectedIndex.value + 1, suggestions.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    selectedIndex.value = Math.max(selectedIndex.value - 1, 0)
  } else if (e.key === 'Escape') {
    showSuggestions.value = false
  }
}

const onBlur = () => {
  setTimeout(() => { showSuggestions.value = false }, 200)
}
</script>

<template>
  <div class="relative flex items-center w-full">
    <div class="relative flex items-center flex-1">
      <Search :size="14" class="absolute left-3 text-slate-600 pointer-events-none z-10" />
      <input v-model="query" @input="onInput" @keyup.enter="handleSearch" @keydown="onKeyDown"
        @focus="query.length >= 1 && fetchSuggestions()" @blur="onBlur" type="text" placeholder="종목 검색 (코드 또는 이름)..."
        class="search-input pl-9 pr-3 py-2 text-xs w-full" />
    </div>

    <!-- Suggestions Dropdown -->
    <ul v-if="showSuggestions"
      class="absolute top-full left-0 w-full bg-[#141820] border border-white/10 rounded-lg mt-1 z-50 max-h-56 overflow-y-auto shadow-2xl backdrop-blur-sm">
      <li v-for="(s, i) in suggestions" :key="s.code" @click="selectStock(s)" :class="[
        'px-3 py-2.5 text-xs cursor-pointer flex justify-between items-center transition-all border-b border-white/[0.03] last:border-b-0',
        i === selectedIndex ? 'bg-blue-500/10 text-blue-400' : 'text-slate-300 hover:bg-white/[0.04]'
      ]">
        <div class="flex items-center gap-2.5">
          <span class="font-mono font-bold text-[11px] text-slate-400 w-16">{{ s.code }}</span>
          <span class="font-medium">{{ s.name }}</span>
        </div>
        <span class="text-[9px] text-slate-600 font-bold uppercase tracking-wider">Add</span>
      </li>
      <li v-if="suggestions.length === 0" class="px-3 py-3 text-xs text-slate-600 text-center">
        검색 결과 없음
      </li>
    </ul>
  </div>
</template>
