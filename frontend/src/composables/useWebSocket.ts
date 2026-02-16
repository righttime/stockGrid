import { ref } from 'vue'

// [Decision] WS 하나로 차트 스냅샷 + 실시간 tick 통합
export interface SymbolCallbacks {
  onChart?: (data: any) => void
  onTick?: (tick: any) => void
}

const isConnected = ref(false)
const listeners = new Map<string, SymbolCallbacks>()
// 재연결 시 subscribeInfo 복원용
const subscribeInfos = new Map<string, { timeframe: string }>()
let socket: WebSocket | null = null
let reconnectTimer: ReturnType<typeof setTimeout> | null = null

export function useWebSocket() {
  const connect = () => {
    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
      return
    }

    console.log('[WS] Connecting...')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/stocks`)

    socket.onopen = () => {
      isConnected.value = true
      console.log('[WS] Connected')
      // 재연결 시 기존 구독 종목을 서버에 다시 등록
      subscribeInfos.forEach((info, symbol) => {
        sendMessage({ type: 'subscribe', symbol, timeframe: info.timeframe })
      })
    }

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)

        // [Decision] 서버에서 차트 스냅샷 수신 → onChart 콜백
        if (message.type === 'chart') {
          const cbs = listeners.get(message.symbol)
          if (cbs?.onChart) cbs.onChart(message.data)
        }
        // 실시간 tick 수신 → onTick 콜백
        else if (message.type === 'tick') {
          const tick = message.data
          const cbs = listeners.get(tick.symbol)
          if (cbs?.onTick) cbs.onTick(tick)
        }
      } catch (e) {
        console.error('[WS] Message Parse Error:', e)
      }
    }

    socket.onclose = () => {
      isConnected.value = false
      console.log('[WS] Disconnected. Reconnecting in 3s...')
      if (reconnectTimer) clearTimeout(reconnectTimer)
      reconnectTimer = setTimeout(connect, 3000)
    }

    socket.onerror = (err) => {
      console.error('[WS] Error:', err)
    }
  }

  const sendMessage = (msg: any) => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(msg))
    }
  }

  /**
   * 종목 구독: 서버가 차트 스냅샷 → 실시간 tick 순으로 전송
   */
  const subscribe = (symbol: string, callbacks: SymbolCallbacks, timeframe: string = 'D') => {
    listeners.set(symbol, callbacks)
    subscribeInfos.set(symbol, { timeframe })

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      connect()
    } else {
      sendMessage({ type: 'subscribe', symbol, timeframe })
    }
  }

  /**
   * 차트 데이터만 재요청 (타임프레임/지표 변경 시)
   */
  const requestChart = (symbol: string, timeframe: string) => {
    subscribeInfos.set(symbol, { timeframe })
    sendMessage({ type: 'requestChart', symbol, timeframe })
  }

  const unsubscribe = (symbol: string) => {
    listeners.delete(symbol)
    subscribeInfos.delete(symbol)
    sendMessage({ type: 'unsubscribe', symbol })
  }

  return {
    isConnected,
    subscribe,
    unsubscribe,
    requestChart
  }
}
