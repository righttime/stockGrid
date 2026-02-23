<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef, nextTick, watch } from 'vue'
import { createChart, ColorType, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts'
import type { IChartApi, ISeriesApi } from 'lightweight-charts'
import { useWebSocket } from '../composables/useWebSocket'

const props = defineProps<{
  symbol: string,
  timeframe: string,
  indicators: any,
  visibleCandles?: number,
  subIndicator?: string // 'RSI' | 'MACD' | 'none'
}>()

const emit = defineEmits<{
  (e: 'priceUpdate', data: { price: number, change: number, changePercent: number }): void
}>()

const chartContainer = ref<HTMLElement | null>(null)
const subChartContainer = ref<HTMLElement | null>(null)
const chart = shallowRef<IChartApi | null>(null)
const subChart = shallowRef<IChartApi | null>(null)
const candleSeries = shallowRef<ISeriesApi<"Candlestick"> | null>(null)
const volumeSeries = shallowRef<ISeriesApi<"Histogram"> | null>(null)
const indicatorSeries = ref<Record<string, ISeriesApi<"Line">>>({})

// 서브 차트 시리즈
const rsiSeries = shallowRef<ISeriesApi<"Line"> | null>(null)
const macdLineSeries = shallowRef<ISeriesApi<"Line"> | null>(null)
const macdSignalSeries = shallowRef<ISeriesApi<"Line"> | null>(null)
const macdHistSeries = shallowRef<ISeriesApi<"Histogram"> | null>(null)

// 수평선 (지지/저항)
const priceLines = ref<any[]>([])

// 크로스헤어 OHLCV 오버레이
const crosshairData = ref<{ t: number, o: number, h: number, l: number, c: number, v: number } | null>(null)

const { subscribe, unsubscribe, requestChart } = useWebSocket()

// === 보조 지표 계산 ===
const calculateSMA = (data: any[], period: number) => {
  if (data.length < period) return []
  return data.map((val, index) => {
    if (index < period - 1) return null
    const slice = data.slice(index - period + 1, index + 1)
    return { time: val.time, value: slice.reduce((a: number, b: any) => a + b.close, 0) / period }
  }).filter(v => v !== null) as any[]
}

const calculateEMA = (data: any[], period: number) => {
  if (data.length < period) return []
  const k = 2 / (period + 1)
  const result: any[] = []
  let ema = data.slice(0, period).reduce((a: number, b: any) => a + b.close, 0) / period
  result.push({ time: data[period - 1].time, value: ema })
  for (let i = period; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k)
    result.push({ time: data[i].time, value: ema })
  }
  return result
}

const calculateWMA = (data: any[], period: number) => {
  if (data.length < period) return []
  const denom = (period * (period + 1)) / 2
  return data.map((val, index) => {
    if (index < period - 1) return null
    const slice = data.slice(index - period + 1, index + 1)
    return { time: val.time, value: slice.reduce((sum: number, d: any, i: number) => sum + d.close * (i + 1), 0) / denom }
  }).filter(v => v !== null) as any[]
}

const calculateBB = (data: any[], period: number, mult: number = 2) => {
  if (data.length < period) return { upper: [], middle: [], lower: [] }
  const upper: any[] = [], middle: any[] = [], lower: any[] = []
  data.forEach((val, index) => {
    if (index < period - 1) return
    const slice = data.slice(index - period + 1, index + 1)
    const avg = slice.reduce((a: number, b: any) => a + b.close, 0) / period
    const std = Math.sqrt(slice.reduce((a: number, b: any) => a + (b.close - avg) ** 2, 0) / period)
    middle.push({ time: val.time, value: avg })
    upper.push({ time: val.time, value: avg + mult * std })
    lower.push({ time: val.time, value: avg - mult * std })
  })
  return { upper, middle, lower }
}

// [Decision] RSI 계산: 14일 기본, 0~100 범위
const calculateRSI = (data: any[], period: number = 14) => {
  if (data.length < period + 1) return []
  const result: any[] = []
  let gains = 0, losses = 0
  for (let i = 1; i <= period; i++) {
    const diff = data[i].close - data[i - 1].close
    if (diff > 0) gains += diff; else losses -= diff
  }
  let avgGain = gains / period, avgLoss = losses / period
  const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
  result.push({ time: data[period].time, value: rsi })
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close
    avgGain = (avgGain * (period - 1) + (diff > 0 ? diff : 0)) / period
    avgLoss = (avgLoss * (period - 1) + (diff < 0 ? -diff : 0)) / period
    const r = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    result.push({ time: data[i].time, value: r })
  }
  return result
}

// [Decision] MACD 계산: 12/26/9 표준 파라미터
const calculateMACD = (data: any[], fast = 12, slow = 26, signal = 9) => {
  const emaFast = calculateEMAFromCloses(data, fast)
  const emaSlow = calculateEMAFromCloses(data, slow)
  if (emaFast.length === 0 || emaSlow.length === 0) return { macd: [], signal: [], histogram: [] }

  // MACD 라인 = EMA(fast) - EMA(slow)
  const macdLine: any[] = []
  const slowMap = new Map(emaSlow.map((d: any) => [d.time, d.value]))
  emaFast.forEach((d: any) => {
    const sv = slowMap.get(d.time)
    if (sv !== undefined) macdLine.push({ time: d.time, value: d.value - sv })
  })

  // 시그널 라인 = MACD의 EMA(9)
  if (macdLine.length < signal) return { macd: macdLine, signal: [], histogram: [] }
  const k = 2 / (signal + 1)
  let ema = macdLine.slice(0, signal).reduce((a: number, b: any) => a + b.value, 0) / signal
  const sigLine: any[] = [{ time: macdLine[signal - 1].time, value: ema }]
  for (let i = signal; i < macdLine.length; i++) {
    ema = macdLine[i].value * k + ema * (1 - k)
    sigLine.push({ time: macdLine[i].time, value: ema })
  }

  // 히스토그램 = MACD - Signal
  const sigMap = new Map(sigLine.map((d: any) => [d.time, d.value]))
  const hist: any[] = macdLine.map((d: any) => {
    const sv = sigMap.get(d.time)
    const val = sv !== undefined ? d.value - sv : 0
    return { time: d.time, value: val, color: val >= 0 ? 'rgba(16, 185, 129, 0.6)' : 'rgba(244, 63, 94, 0.6)' }
  })

  return { macd: macdLine, signal: sigLine, histogram: hist }
}

const calculateEMAFromCloses = (data: any[], period: number) => {
  if (data.length < period) return []
  const k = 2 / (period + 1)
  let ema = data.slice(0, period).reduce((a: number, b: any) => a + b.close, 0) / period
  const result: any[] = [{ time: data[period - 1].time, value: ema }]
  for (let i = period; i < data.length; i++) {
    ema = data[i].close * k + ema * (1 - k)
    result.push({ time: data[i].time, value: ema })
  }
  return result
}

const computeIndicator = (data: any[], conf: any) => {
  const type = conf.type || 'SMA'
  const period = conf.period || 20
  if (type === 'SMA') return calculateSMA(data, period)
  if (type === 'EMA') return calculateEMA(data, period)
  if (type === 'WMA') return calculateWMA(data, period)
  return calculateSMA(data, period)
}

// 데이터 캐시
let cachedData: any[] = []

// [Decision] REST fetch 제거, WS onChart 콜백에서 호출
const applyChartData = (result: any) => {
  if (!candleSeries.value || !chart.value || !volumeSeries.value) return
  if (!result || !result.output || result.output.length === 0) return

  // [Fix] dt 포맷별 파싱 분리:
  //   8자리  → YYYYMMDD   (일봉/주봉)
  //   14자리 → YYYYMMDDHHMMSS (분봉, 백엔드에서 base_dt 붙여 통일)
  //   12자리 → YYYYMMDDHHMM  (혹시 모를 12자리 케이스)
  //   기타   → 순서 기반 fallback (데이터 누락 방지)
  const parseTime = (s: string, idx: number): number => {
    if (s.length === 8) {
      return Math.floor(Date.UTC(
        parseInt(s.substring(0, 4)),
        parseInt(s.substring(4, 6)) - 1,
        parseInt(s.substring(6, 8))
      ) / 1000)
    } else if (s.length >= 14) {
      return Math.floor(Date.UTC(
        parseInt(s.substring(0, 4)),
        parseInt(s.substring(4, 6)) - 1,
        parseInt(s.substring(6, 8)),
        parseInt(s.substring(8, 10)),
        parseInt(s.substring(10, 12)),
        parseInt(s.substring(12, 14))
      ) / 1000)
    } else if (s.length >= 12) {
      return Math.floor(Date.UTC(
        parseInt(s.substring(0, 4)),
        parseInt(s.substring(4, 6)) - 1,
        parseInt(s.substring(6, 8)),
        parseInt(s.substring(8, 10)),
        parseInt(s.substring(10, 12))
      ) / 1000)
    }
    // fallback: 순서 기반 (데이터 보존 우선)
    return Math.floor(Date.now() / 1000) - (result.output.length - idx) * 60
  }

  const rawParsed = result.output.map((d: any, idx: number) => ({
    time: parseTime(d.dt || '', idx) as any,
    open: d.open, high: d.high, low: d.low, close: d.close, volume: d.volume
  }))

  // [Fix] 중복 time 제거 시 마지막(최신) 값 우선 보존 (Map 활용)
  // 기존 filter는 첫 번째 값 유지였는데, 뒤에 오는 값이 더 정확한 경우 있음
  const dedupMap = new Map<number, any>()
  rawParsed.forEach((d: any) => dedupMap.set(d.time, d))
  const parsedData = Array.from(dedupMap.values()).sort((a: any, b: any) => a.time - b.time)

  cachedData = parsedData
  candleSeries.value.setData(parsedData)
  volumeSeries.value.setData(parsedData.map((d: any) => ({
    time: d.time, value: d.volume,
    color: d.close >= d.open ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)'
  })))

  // 이동평균/볼린저밴드
  Object.keys(props.indicators).forEach(key => {
    const conf = props.indicators[key]
    if (conf.type === 'BB') {
      const bb = calculateBB(parsedData, conf.period, conf.mult || 2)
      const bbKeys = [`${key}_upper`, `${key}_middle`, `${key}_lower`]
      const bbData = [bb.upper, bb.middle, bb.lower]
      bbKeys.forEach((bk, bi) => {
        if (indicatorSeries.value[bk]) {
          indicatorSeries.value[bk].setData(conf.active ? (bbData[bi] as any) : [])
          indicatorSeries.value[bk].applyOptions({ visible: conf.active })
        }
      })
    } else if (indicatorSeries.value[key]) {
      indicatorSeries.value[key].setData(conf.active ? computeIndicator(parsedData, conf) : [])
      indicatorSeries.value[key].applyOptions({ visible: conf.active, color: conf.color })
    }
  })

  // [Decision] 서브 인디케이터 (RSI / MACD) 렌더링
  updateSubIndicator(parsedData)

  // 현재가/등락률 emit
  const last = parsedData[parsedData.length - 1]
  const prev = parsedData.length >= 2 ? parsedData[parsedData.length - 2] : last
  const change = last.close - prev.close
  const changePercent = prev.close ? (change / prev.close) * 100 : 0
  emit('priceUpdate', { price: last.close, change, changePercent })

  // 캔들 수 조절
  const visCount = props.visibleCandles || 60
  const total = parsedData.length
  if (total > visCount) chart.value.timeScale().setVisibleLogicalRange({ from: total - visCount, to: total })
  else chart.value.timeScale().fitContent()

  // 서브 차트 타임스케일 동기화
  if (subChart.value && total > visCount) {
    subChart.value.timeScale().setVisibleLogicalRange({ from: total - visCount, to: total })
  }
}

// [Decision] 서브 차트 시간축 정렬: whitespace 패딩으로 메인 차트와 logical index 동기화
const padWithWhitespace = (baseData: any[], indicatorData: any[]) => {
  const valMap = new Map(indicatorData.map((d: any) => [d.time, d]))
  return baseData.map((d: any) => valMap.get(d.time) || { time: d.time })
}

const updateSubIndicator = (data: any[]) => {
  const subType = props.subIndicator || 'none'
  if (subType === 'RSI' && rsiSeries.value) {
    rsiSeries.value.setData(padWithWhitespace(data, calculateRSI(data, 14)))
  }
  if (subType === 'MACD') {
    const macd = calculateMACD(data)
    if (macdLineSeries.value) macdLineSeries.value.setData(padWithWhitespace(data, macd.macd))
    if (macdSignalSeries.value) macdSignalSeries.value.setData(padWithWhitespace(data, macd.signal))
    if (macdHistSeries.value) macdHistSeries.value.setData(padWithWhitespace(data, macd.histogram))
  }
}

const formatNum = (n: number) => n.toLocaleString('ko-KR')

// [Decision] 우클릭 → 수평선(지지/저항) 추가
const addPriceLine = (e: MouseEvent) => {
  e.preventDefault()
  if (!chart.value || !candleSeries.value) return
  // 마우스 Y 좌표 → 가격 변환
  const rect = chartContainer.value?.getBoundingClientRect()
  if (!rect) return
  const localY = e.clientY - rect.top
  const price = (candleSeries.value as any).coordinateToPrice(localY)
  if (!price || price <= 0) return

  const line = candleSeries.value.createPriceLine({
    price: Math.round(price),
    color: '#facc15',
    lineWidth: 1,
    lineStyle: 2, // dashed
    axisLabelVisible: true,
    title: `${Math.round(price).toLocaleString()}`,
  })
  priceLines.value.push({ price: Math.round(price), line })
}

// 수평선 전체 삭제
const clearPriceLines = () => {
  priceLines.value.forEach(pl => {
    if (candleSeries.value) candleSeries.value.removePriceLine(pl.line)
  })
  priceLines.value = []
}

const initChart = async () => {
  await nextTick()
  if (!chartContainer.value) return

  const chartOpts = {
    layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#334155', fontSize: 9, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(255,255,255,0.015)' } },
    width: chartContainer.value.offsetWidth, height: chartContainer.value.offsetHeight,
    timeScale: { visible: false }, rightPriceScale: { borderVisible: false, autoScale: true },
    handleScale: true, handleScroll: true,
    crosshair: {
      vertLine: { color: 'rgba(59, 130, 246, 0.15)', width: 1, style: 2, labelVisible: false },
      horzLine: { color: 'rgba(59, 130, 246, 0.15)', width: 1, style: 2, labelVisible: true, labelBackgroundColor: 'rgba(59, 130, 246, 0.8)' },
    },
  }
  chart.value = createChart(chartContainer.value, chartOpts as any)

  // 크로스헤어 OHLCV 오버레이
  chart.value.subscribeCrosshairMove((param) => {
    if (!param || !param.time || !candleSeries.value) { crosshairData.value = null; return }
    const candle = param.seriesData.get(candleSeries.value) as any
    if (candle) {
      const matched = cachedData.find(d => d.time === param.time)
      crosshairData.value = {
        t: param.time as number,
        o: candle.open, h: candle.high, l: candle.low, c: candle.close,
        v: matched?.volume || 0
      }
    }
  })

  candleSeries.value = chart.value.addSeries(CandlestickSeries, {
    upColor: '#10B981', downColor: '#F43F5E', borderVisible: false, wickUpColor: '#10B981', wickDownColor: '#F43F5E',
    priceFormat: { type: 'price', precision: 0, minMove: 1 },
  })
  volumeSeries.value = chart.value.addSeries(HistogramSeries, { priceFormat: { type: 'volume' }, priceScaleId: 'volume' })
  chart.value.priceScale('volume').applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } })

  // 이동평균/볼린저밴드 시리즈 생성
  Object.keys(props.indicators).forEach(key => {
    const conf = props.indicators[key]
    if (conf.type === 'BB') {
      ;['_upper', '_middle', '_lower'].forEach((suffix) => {
        indicatorSeries.value[`${key}${suffix}`] = chart.value!.addSeries(LineSeries, {
          lineWidth: 1, lineStyle: suffix === '_middle' ? 0 : 2, color: conf.color || '#8b5cf6',
          lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false,
        })
      })
    } else {
      indicatorSeries.value[key] = chart.value!.addSeries(LineSeries, {
        lineWidth: 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false, color: conf.color,
      })
    }
  })

  // [Decision] 서브 인디케이터 차트 (RSI / MACD)
  initSubChart()

  // [Decision] WS 단일 채널: subscribe → 서버가 차트 스냅샷 전송 → onChart → 이후 tick
  let _chartRetryCount = 0
  // [Fix] 거래량 추적: tick.volume = 하루 누적거래량 → 분봉은 틱 간 델타를 봉에 누적
  let _prevTickAccVol = -1   // 이전 틱의 누적거래량 (델타 계산용)
  subscribe(props.symbol, {
    onChart: (chartResult) => {
      // 차트 재로드 시 거래량 추적 초기화
      _prevTickAccVol = -1
      // [Fix] 빈 데이터(429 Rate Limit 등) 수신 시 자동 재시도 (최대 5회, 3초 간격)
      if (!chartResult?.output?.length) {
        if (_chartRetryCount < 5) {
          _chartRetryCount++
          console.warn(`[Chart] ${props.symbol} 빈 데이터 수신, ${_chartRetryCount}회 재시도 예정 (3초 후)`)
          setTimeout(() => requestChart(props.symbol, props.timeframe), 3000)
        }
        return
      }
      _chartRetryCount = 0
      applyChartData(chartResult)
    },
    onTick: (tick) => {
      if (!candleSeries.value || !volumeSeries.value || cachedData.length === 0) return

      // [Fix] 타임프레임에 맞춰 현재 봉 시간(unix seconds, UTC) 계산
      // tick.timestamp = "HHMMSS" (KST = UTC+9)
      const ts = String(tick.timestamp || '').padStart(6, '0')
      const hh = parseInt(ts.substring(0, 2))
      const mm = parseInt(ts.substring(2, 4))
      const nowKST = new Date()
      const yy = nowKST.getUTCFullYear()
      const mo = nowKST.getUTCMonth()
      const dd = nowKST.getUTCDate()
      const tf = props.timeframe
      const tfMin = tf === 'D' || tf === 'W' ? 0 : parseInt(tf)

      let candleTimeUTC: number
      if (tf === 'D' || tf === 'W') {
        const kstDate = new Date(Date.UTC(yy, mo, dd, hh - 9, mm, 0))
        kstDate.setUTCHours(0, 0, 0, 0)
        candleTimeUTC = Math.floor(kstDate.getTime() / 1000)
      } else {
        const totalMinKST = hh * 60 + mm
        const bucketMinKST = Math.floor(totalMinKST / tfMin) * tfMin
        const bucketHH = Math.floor(bucketMinKST / 60)
        const bucketMM = bucketMinKST % 60
        const candleDate = new Date(Date.UTC(yy, mo, dd, bucketHH - 9, bucketMM, 0))
        candleTimeUTC = Math.floor(candleDate.getTime() / 1000)
      }

      // [Fix] 거래량 계산
      // tick.volume = 하루 누적거래량(13번 필드)
      // - 일봉/주봉: 누적거래량 = 당일 전체 → 그대로 사용
      // - 분봉: 틱 간 델타를 계산하여 봉 내 거래량에 누적
      const accVol = tick.volume || 0
      const tickDelta = _prevTickAccVol < 0 ? 0 : Math.max(0, accVol - _prevTickAccVol)
      _prevTickAccVol = accVol

      const lastCandle = cachedData[cachedData.length - 1]
      const prevClose = cachedData.length >= 2 ? cachedData[cachedData.length - 2].close : lastCandle.close

      if (candleTimeUTC <= lastCandle.time) {
        // ── 같은 봉 업데이트 ──
        // 거래량: 일봉은 누적값 직접, 분봉은 기존 봉 거래량 + 이번 틱 증분
        const newVol = (tf === 'D' || tf === 'W')
          ? accVol
          : lastCandle.volume + tickDelta
        const updatedCandle = {
          time: lastCandle.time,
          open: lastCandle.open,
          high: Math.max(lastCandle.high, tick.price),
          low: Math.min(lastCandle.low, tick.price),
          close: tick.price,
        }
        cachedData[cachedData.length - 1] = { ...updatedCandle, volume: newVol }
        candleSeries.value.update(updatedCandle as any)
        volumeSeries.value.update({
          time: lastCandle.time as any,
          value: newVol,
          color: tick.price >= lastCandle.open ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)'
        })
      } else {
        // ── 새 봉 생성 ──
        // 새 봉은 첫 틱의 델타 거래량부터 시작
        const newVol = (tf === 'D' || tf === 'W') ? accVol : tickDelta
        const newCandle = {
          time: candleTimeUTC,
          open: tick.price,
          high: tick.price,
          low: tick.price,
          close: tick.price,
        }
        cachedData.push({ ...newCandle, volume: newVol })
        candleSeries.value.update(newCandle as any)
        volumeSeries.value.update({
          time: candleTimeUTC as any,
          value: newVol,
          color: 'rgba(16, 185, 129, 0.45)'
        })
      }

      const change = tick.price - prevClose
      const changePercent = prevClose ? (change / prevClose) * 100 : 0
      emit('priceUpdate', { price: tick.price, change, changePercent })
    }
  }, props.timeframe)

  // [Decision] 메인 차트 시간축 변경 시 서브 차트 동기화
  chart.value.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (range && subChart.value) {
      subChart.value.timeScale().setVisibleLogicalRange(range)
    }
  })
}

const initSubChart = () => {
  const subType = props.subIndicator || 'none'
  if (subType === 'none' || !subChartContainer.value) return

  subChart.value = createChart(subChartContainer.value, {
    layout: { background: { type: ColorType.Solid, color: 'transparent' }, textColor: '#334155', fontSize: 8, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { color: 'rgba(255,255,255,0.02)' } },
    width: subChartContainer.value.offsetWidth, height: subChartContainer.value.offsetHeight,
    timeScale: { visible: false }, rightPriceScale: { borderVisible: false, autoScale: true },
    handleScale: true, handleScroll: true, crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
  } as any)

  if (subType === 'RSI') {
    rsiSeries.value = subChart.value.addSeries(LineSeries, {
      lineWidth: 2, color: '#a855f7', lastValueVisible: true, priceLineVisible: false,
      priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
    })
    // RSI 기준선 (30/70)
    rsiSeries.value.createPriceLine({ price: 70, color: 'rgba(244, 63, 94, 0.3)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' })
    rsiSeries.value.createPriceLine({ price: 30, color: 'rgba(16, 185, 129, 0.3)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' })
    rsiSeries.value.createPriceLine({ price: 50, color: 'rgba(148, 163, 184, 0.15)', lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' })
  }
  if (subType === 'MACD') {
    macdHistSeries.value = subChart.value.addSeries(HistogramSeries, {
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
      priceScaleId: 'macd',
    })
    macdLineSeries.value = subChart.value.addSeries(LineSeries, {
      lineWidth: 2, color: '#3b82f6', lastValueVisible: false, priceLineVisible: false,
    })
    macdSignalSeries.value = subChart.value.addSeries(LineSeries, {
      lineWidth: 1, color: '#f97316', lastValueVisible: false, priceLineVisible: false,
    })
  }

  // 서브 차트 → 메인 차트 동기화
  subChart.value.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (range && chart.value) {
      chart.value.timeScale().setVisibleLogicalRange(range)
    }
  })
}

// [Decision] props 변경 시 서브 차트 라이프사이클 관리 + 차트 데이터 재요청
watch(() => [props.timeframe, props.indicators, props.visibleCandles, props.subIndicator], async () => {
  // 서브 차트 재구성 (subIndicator 변경 대응: none↔RSI↔MACD)
  if (subChart.value) {
    subChart.value.remove()
    subChart.value = null
  }
  rsiSeries.value = null
  macdLineSeries.value = null
  macdSignalSeries.value = null
  macdHistSeries.value = null

  await nextTick() // v-if DOM 업데이트 대기
  initSubChart()

  // 서브 차트 컨테이너가 새로 나타났으면 ResizeObserver에 등록
  if (subChartContainer.value && resizeObserver) {
    resizeObserver.observe(subChartContainer.value)
  }

  requestChart(props.symbol, props.timeframe)
}, { deep: true })

let resizeObserver: ResizeObserver | null = null
onMounted(() => {
  setTimeout(() => initChart(), 100)
  resizeObserver = new ResizeObserver(() => {
    if (chart.value && chartContainer.value) {
      chart.value.resize(chartContainer.value.offsetWidth, chartContainer.value.offsetHeight)
    }
    if (subChart.value && subChartContainer.value) {
      subChart.value.resize(subChartContainer.value.offsetWidth, subChartContainer.value.offsetHeight)
    }
  })
  if (chartContainer.value) resizeObserver.observe(chartContainer.value)
  if (subChartContainer.value) resizeObserver.observe(subChartContainer.value)
})

onUnmounted(() => {
  unsubscribe(props.symbol)
  resizeObserver?.disconnect()
  chart.value?.remove()
  subChart.value?.remove()
})
</script>

<template>
  <div class="flex-1 w-full flex flex-col overflow-hidden">
    <!-- 메인 차트 -->
    <div class="relative overflow-hidden" :class="subIndicator && subIndicator !== 'none' ? 'h-[72%]' : 'h-full'"
      ref="chartContainer" @contextmenu="addPriceLine">
      <!-- OHLCV 오버레이 -->
      <div v-if="crosshairData"
        class="absolute top-1 left-1 z-10 flex items-center gap-1.5 text-[9px] font-mono pointer-events-none">
        <!-- 시간 -->
        <span class="text-slate-400 mr-0.5">{{ (() => {
          const d = new Date(crosshairData.t * 1000)
          const kstOffset = 9 * 60 * 60 * 1000
          const kst = new Date(d.getTime() + kstOffset)
          const tf = props.timeframe
          if (tf === 'D' || tf === 'W') {
            return `${kst.getUTCFullYear()}.${String(kst.getUTCMonth()+1).padStart(2,'0')}.${String(kst.getUTCDate()).padStart(2,'0')}`
          } else {
            return `${String(kst.getUTCMonth()+1).padStart(2,'0')}.${String(kst.getUTCDate()).padStart(2,'0')} ${String(kst.getUTCHours()).padStart(2,'0')}:${String(kst.getUTCMinutes()).padStart(2,'0')}`
          }
        })() }}</span>
        <span class="text-slate-600">|</span>
        <!-- OHLCV -->
        <span class="text-slate-500">O</span><span
          :class="crosshairData.c >= crosshairData.o ? 'text-emerald-400' : 'text-rose-400'">{{ formatNum(crosshairData.o) }}</span>
        <span class="text-slate-500">H</span><span
          :class="crosshairData.c >= crosshairData.o ? 'text-emerald-400' : 'text-rose-400'">{{ formatNum(crosshairData.h) }}</span>
        <span class="text-slate-500">L</span><span
          :class="crosshairData.c >= crosshairData.o ? 'text-emerald-400' : 'text-rose-400'">{{ formatNum(crosshairData.l) }}</span>
        <span class="text-slate-500">C</span><span
          :class="crosshairData.c >= crosshairData.o ? 'text-emerald-400' : 'text-rose-400'" class="font-bold">{{ formatNum(crosshairData.c) }}</span>
        <span v-if="crosshairData.v" class="text-slate-600 ml-0.5">Vol {{ formatNum(crosshairData.v) }}</span>
      </div>
      <!-- 수평선 클리어 버튼 -->
      <button v-if="priceLines.length > 0" @click="clearPriceLines"
        class="absolute top-1 right-1 z-10 text-[8px] text-slate-600 hover:text-yellow-400 bg-black/40 px-1.5 py-0.5 rounded transition-colors">
        Lines ×{{ priceLines.length }}
      </button>
    </div>
    <!-- 서브 인디케이터 차트 (RSI / MACD) -->
    <div v-if="subIndicator && subIndicator !== 'none'" class="h-[28%] border-t border-white/[0.04] relative"
      ref="subChartContainer">
      <span class="absolute top-0.5 left-1.5 z-10 text-[8px] font-bold text-slate-600 pointer-events-none">
        {{ subIndicator === 'RSI' ? 'RSI(14)' : 'MACD(12,26,9)' }}
      </span>
    </div>
  </div>
</template>
