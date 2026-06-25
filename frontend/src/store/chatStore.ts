import { create } from 'zustand'
import type {
  ChatEvent,
  ChatMessage,
  ToolRecord,
  AgentTopology,
  ConnectionStatus,
  VehicleStatusData,
  FeedbackRating,
  MessageToolCall,
} from '../types/events'
import { fetchAgents, genId, submitFeedback } from '../utils/api'
import { parseAmapPOIs, parseAmapRoute, parseCommonAddresses } from '../utils/parseAmap'

// WebSocket 实例（不放入 state，避免序列化问题）
let ws: WebSocket | null = null
// 自动重连状态
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let reconnectAttempts = 0
const MAX_RECONNECT_DELAY = 15000  // 最大退避 15 秒

function scheduleReconnect() {
  if (reconnectTimer) return
  // 指数退避：1s, 2s, 4s, 8s, max 15s
  const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), MAX_RECONNECT_DELAY)
  reconnectAttempts += 1
  console.log(`[WS] 将在 ${delay}ms 后尝试重连（第 ${reconnectAttempts} 次）`)
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    // 重新触发 connect 流程
    useChatStore.getState().connect()
  }, delay)
}
// 当前流式消息ID
let currentStreamingMessageId: string | null = null
// 最近一次用户提问内容（用于关联到 assistant 消息，供反馈接口使用）
let lastUserQuery: string = ''

const defaultVehicleStatus: VehicleStatusData = {
  model: '智行X9 纯电版',
  battery: 78,
  range: 412,
  mileage: 15680,
  tirePressure: { fl: 2.3, fr: 2.3, rl: 2.2, rr: 2.2 },
  location: '北京市海淀区中关村',
  acStatus: '关闭',
  driveMode: '经济模式',
}

// 全局地图 POI（POI 坐标 + 名称 + 地址）
export interface MapPOI {
  name: string
  address?: string
  lng: number
  lat: number
  category?: string
}

// 导航上下文：用于支持"立即开启导航"按钮的上下文感知
export interface NavigationContext {
  // 当前等待用户确认的常用地址列表（来自 get_common_addresses）
  pendingAddresses: Array<{ name: string; address: string }>
  // 用户选中的目标名称（点击按钮后填充）
  selectedTarget: string | null
  // 是否处于"刚讨论过导航但未启动"的状态
  awaitingNavigation: boolean
}

interface ChatState {
  // 连接状态
  connectionStatus: ConnectionStatus
  sessionId: string
  // 对话数据
  messages: ChatMessage[]
  events: ChatEvent[]
  toolRecords: ToolRecord[]
  // Agent 状态
  activeAgent: string | null
  agentTopology: AgentTopology | null
  // 思考状态
  isThinking: boolean
  thinkingContent: string
  // 车辆状态
  vehicleStatus: VehicleStatusData
  // 语音相关
  speechSynthesisEnabled: boolean
  phoneModeActive: boolean
  // 中间面板 Tab
  centerTab: 'map' | 'orchestration'
  // 全局地图 POI 数据（聚合所有工具结果）
  mapPois: MapPOI[]
  // 当前路线（plan_route 工具结果）
  currentRoute: { points: [number, number][]; distance?: number; duration?: number } | null
  // 浏览器定位的用户位置
  userLocation: { lng: number; lat: number; city?: string; district?: string } | null
  // 定位错误信息
  locationError: string | null
  // 定位状态：idle/requesting/success/error
  locationStatus: 'idle' | 'requesting' | 'success' | 'error'
  // 最近完成的 AI 消息ID（用于触发语音播报）
  lastCompletedMessageId: string | null
  // 导航上下文：跟踪常用地址与待启动导航
  navigationContext: NavigationContext

  // Actions
  connect: () => void
  disconnect: () => void
  sendMessage: (content: string) => void
  loadAgents: () => Promise<void>
  loadVehicleStatus: () => Promise<void>
  handleEvent: (event: ChatEvent) => void
  resetChat: () => void
  toggleSpeechSynthesis: () => void
  setPhoneMode: (active: boolean) => void
  submitMessageFeedback: (messageId: string, rating: FeedbackRating) => Promise<void>
  setCenterTab: (tab: 'map' | 'orchestration') => void
  pushMapPois: (pois: MapPOI[]) => void
  clearMapPois: () => void
  setCurrentRoute: (route: ChatState['currentRoute']) => void
  setUserLocation: (loc: { lng: number; lat: number; city?: string; district?: string } | null) => void
  setLocationError: (err: string | null) => void
  setLocationStatus: (status: 'idle' | 'requesting' | 'success' | 'error') => void
  setPendingAddresses: (addresses: Array<{ name: string; address: string }>) => void
  selectNavigationTarget: (target: string) => void
  clearNavigationContext: () => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  connectionStatus: 'disconnected',
  sessionId: genId(),
  messages: [],
  events: [],
  toolRecords: [],
  activeAgent: null,
  agentTopology: null,
  isThinking: false,
  thinkingContent: '',
  vehicleStatus: defaultVehicleStatus,
  speechSynthesisEnabled: false,
  phoneModeActive: false,
  centerTab: 'map',  // 默认显示地图
  mapPois: [],
  currentRoute: null,
  userLocation: null,
  locationError: null,
  locationStatus: 'idle',
  lastCompletedMessageId: null,
  navigationContext: {
    pendingAddresses: [],
    selectedTarget: null,
    awaitingNavigation: false,
  },

  connect: () => {
    // 取消任何已排定的重连
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    set({ connectionStatus: 'connecting' })

    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      reconnectAttempts = 0  // 连接成功，重置重连计数
      set({ connectionStatus: 'connected' })

      // 关键：重连成功后清理临时系统提示
      // （用户消息保留 - 它就是这条对话的一部分，不该被吃掉）
      const pending = (window as any).__pendingWsMessage as string | undefined
      if (pending) {
        set((s) => ({
          messages: s.messages.filter(
            (m) => m.content !== '连接已断开，正在自动重连…',
          ),
        }))
        ws!.send(pending)
        ;(window as any).__pendingWsMessage = undefined
      }
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as ChatEvent
        get().handleEvent(data)
      } catch (e) {
        console.error('解析WebSocket消息失败:', e)
      }
    }

    ws.onerror = (_error) => {
      // onerror 总会紧跟 onclose 触发自动重连，无需打 error
      // 用 warn 而非 error，避免控制台噪音（用户看到的"5"条红色错误中的一条就来自这里）
      console.warn('[WS] 连接异常，将在 onclose 后自动重连')
    }

    ws.onclose = () => {
      set({ connectionStatus: 'disconnected' })
      ws = null
      // 自动尝试重连（不在初次未连接时重连，避免控制台噪音）
      if (reconnectAttempts > 0 || useChatStore.getState().connectionStatus !== 'disconnected') {
        scheduleReconnect()
      }
    }
  },

  disconnect: () => {
    if (ws) {
      ws.close()
      ws = null
    }
    set({ connectionStatus: 'disconnected' })
  },

  sendMessage: (content: string) => {
    const state = get()

    // 添加用户消息
    const userMessage: ChatMessage = {
      id: genId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    // 记录最近一次用户提问，供 assistant 消息反馈使用
    lastUserQuery = content

    // 关键：每次发新消息前清理上一轮残留
    // 1) 系统提示"连接已断开，正在自动重连…"（万一 onopen 漏处理）
    // 2) 孤儿用户消息：紧跟在 sysHint 后面的那条用户消息（之前断线期间发了但一直没收到响应）
    set((s) => {
      const cleaned = s.messages.filter(
        (m) => m.content !== '连接已断开，正在自动重连…',
      )
      // 检查末尾是否是"孤儿用户消息"——它必须满足：
      //   - 是用户消息
      //   - 后面没有助手响应（如果是数组最后一条）
      //   - 它的前面紧跟 sysHint（说明是在断线期间发的）
      // 这种情况下应该把它清掉，否则会一直挂在历史里
      const last = cleaned[cleaned.length - 1]
      const secondLast = cleaned[cleaned.length - 2]
      if (
        last && last.role === 'user' &&
        secondLast && secondLast.content === '连接已断开，正在自动重连…'
      ) {
        // 第二条 sysHint 已经被前面 filter 清掉了，这里只删孤儿用户消息
        cleaned.pop()
      }
      return { messages: [...cleaned, userMessage] }
    })

    // 通过 WebSocket 发送（连接断开时先触发重连）
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: 'message',
          content,
          session_id: state.sessionId,
        }),
      )
      return
    }

    // 连接断开：触发重连，待 onopen 后再发送
    if (!ws || ws.readyState === WebSocket.CLOSED) {
      const pendingMsg = JSON.stringify({
        type: 'message',
        content,
        session_id: state.sessionId,
      })
      // 排队一条待发消息：onopen 时如果还有待发则补发
      ;(window as any).__pendingWsMessage = pendingMsg
      // 显示"正在重连"提示（不写死"连接已断开请刷新"）
      const sysHint: ChatMessage = {
        id: genId(),
        role: 'assistant',
        content: '连接已断开，正在自动重连…',
        timestamp: Date.now(),
      }
      set({ messages: [...get().messages, sysHint] })
      // 触发 connect，onopen 时会自动 flush
      get().connect()
      return
    }

    // 未连接时提示
    {
      const errMsg: ChatMessage = {
        id: genId(),
        role: 'assistant',
        content: '正在建立连接，请稍候…',
        timestamp: Date.now(),
      }
      set({ messages: [...get().messages, errMsg] })
    }
  },

  loadAgents: async () => {
    try {
      const topology = await fetchAgents()
      set({ agentTopology: topology })
    } catch (e) {
      console.error('加载Agent拓扑失败:', e)
    }
  },

  loadVehicleStatus: async () => {
    try {
      const resp = await fetch('/api/vehicle/status')
      const data = await resp.json()
      const acStr = data['空调'] || ''
      const acStatus = acStr.includes('开启')
        ? `开启 ${acStr.split(',')[1]?.trim() || ''}`.trim()
        : '关闭'
      // 解析胎压：优先用结构化数据，回退到文本解析
      let tirePressure: VehicleStatusData['tirePressure'] = get().vehicleStatus.tirePressure
      if (data['胎压'] && typeof data['胎压'] === 'object') {
        tirePressure = {
          fl: Number(data['胎压'].fl) || tirePressure.fl,
          fr: Number(data['胎压'].fr) || tirePressure.fr,
          rl: Number(data['胎压'].rl) || tirePressure.rl,
          rr: Number(data['胎压'].rr) || tirePressure.rr,
        }
      } else if (typeof data['胎压'] === 'string') {
        // 回退：从文本解析"前左2.5bar/前右..."
        const m = data['胎压'].match(/前左([\d.]+)bar.*前右([\d.]+)bar.*后左([\d.]+)bar.*后右([\d.]+)bar/)
        if (m) {
          tirePressure = { fl: +m[1], fr: +m[2], rl: +m[3], rr: +m[4] }
        }
      }
      set({
        vehicleStatus: {
          model: data['车型'] || get().vehicleStatus.model,
          battery: parseInt(data['电池电量']?.replace('%', '')) || get().vehicleStatus.battery,
          range: parseInt(data['续航里程']?.replace('km', '')) || get().vehicleStatus.range,
          mileage: parseInt(data['总里程']?.replace('km', '')) || get().vehicleStatus.mileage,
          tirePressure,
          location: data['当前位置'] || get().vehicleStatus.location,
          acStatus,
          driveMode: data['驾驶模式'] || get().vehicleStatus.driveMode,
        },
      })
    } catch (e) {
      console.error('加载车辆状态失败:', e)
    }
  },

  handleEvent: (event: ChatEvent) => {
    const state = get()

    // 添加到事件列表
    set({ events: [...state.events, event] })

    switch (event.type) {
      case 'start': {
        // 创建新的流式 AI 消息
        const newMessage: ChatMessage = {
          id: genId(),
          role: 'assistant',
          content: '',
          agent: event.agent,
          streaming: true,
          timestamp: event.timestamp,
          query: lastUserQuery,
          toolCalls: [],
        }
        currentStreamingMessageId = newMessage.id
        set({
          messages: [...state.messages, newMessage],
          isThinking: true,
          thinkingContent: '',
        })
        break
      }

      case 'thinking': {
        set({
          isThinking: true,
          thinkingContent: event.content,
        })
        break
      }

      case 'route': {
        set({
          activeAgent: event.to_agent,
          isThinking: false,
        })
        break
      }

      case 'tool_call': {
        const callId = (event as any).call_id || genId()
        const record: ToolRecord = {
          id: genId(),
          agent: event.agent,
          tool: event.tool,
          args: event.args,
          callId,
          status: 'loading',
          timestamp: event.timestamp,
        }
        // 同时添加到全局工具记录和当前流式消息内嵌的工具调用
        const msgToolCall: MessageToolCall = {
          id: record.id,
          agent: record.agent,
          tool: record.tool,
          args: record.args,
          callId: record.callId,
          status: 'loading',
          timestamp: record.timestamp,
        }
        set({
          toolRecords: [...state.toolRecords, record],
          messages: state.messages.map((m) =>
            m.id === currentStreamingMessageId
              ? { ...m, toolCalls: [...(m.toolCalls || []), msgToolCall] }
              : m,
          ),
        })
        break
      }

      case 'route_update': {
        // 后端在 navigate_to / plan_route 之后通过 run_in_executor 调真实高德 plan_route
        // 解析出 polyline 后立即推送给前端画线（不再依赖 plan_route 工具的纯文本返回）
        const points = (event as any).points as Array<[number, number]> | undefined
        if (points && points.length > 0) {
          // 关键修复：切换目的地时先清掉所有旧 POI，
          // 避免上一个目的地的终点图钉 + 上一次 POI 搜索结果残留
          get().clearMapPois()

          set({
            currentRoute: {
              points,
              distance: (event as any).distance,
              duration: (event as any).duration,
            },
            centerTab: 'map',
          })

          // 终点：取 polyline 最后一个点 + 起点：第一个点
          if (points.length > 0) {
            const destName = (event as any).destination as string | undefined
            const last = points[points.length - 1]
            const first = points[0]
            get().pushMapPois([
              {
                name: '起点',
                address: '',
                lng: first[1],
                lat: first[0],
                category: 'origin',
              },
              {
                name: destName || '终点',
                address: '',
                lng: last[1],
                lat: last[0],
                category: 'destination',
              },
            ])
          }
        }
        break
      }

      case 'tool_result': {
        const callId = (event as any).call_id
        const actualArgs = (event as any).actual_args
        const records = [...state.toolRecords]
        let matched = false
        // 优先用 call_id 匹配
        if (callId) {
          for (let i = records.length - 1; i >= 0; i--) {
            if (records[i].callId === callId && records[i].status === 'loading') {
              records[i] = {
                ...records[i],
                result: event.result,
                actualArgs: actualArgs || records[i].args,
                status: 'done',
              }
              matched = true
              break
            }
          }
        }
        // 回退：用 tool name + agent 匹配
        if (!matched) {
          for (let i = records.length - 1; i >= 0; i--) {
            if (
              records[i].tool === event.tool &&
              records[i].agent === event.agent &&
              records[i].status === 'loading'
            ) {
              records[i] = {
                ...records[i],
                result: event.result,
                actualArgs: actualArgs || records[i].args,
                status: 'done',
              }
              break
            }
          }
        }
        // 同步更新当前流式消息内嵌的工具调用
        const updatedMessages = state.messages.map((m) => {
          if (m.id !== currentStreamingMessageId || !m.toolCalls) return m
          const updatedToolCalls = [...m.toolCalls]
          let msgMatched = false
          // 优先用 call_id 匹配
          if (callId) {
            for (let i = updatedToolCalls.length - 1; i >= 0; i--) {
              if (updatedToolCalls[i].callId === callId && updatedToolCalls[i].status === 'loading') {
                updatedToolCalls[i] = {
                  ...updatedToolCalls[i],
                  result: event.result,
                  actualArgs: actualArgs || updatedToolCalls[i].args,
                  status: 'done',
                }
                msgMatched = true
                break
              }
            }
          }
          // 回退匹配
          if (!msgMatched) {
            for (let i = updatedToolCalls.length - 1; i >= 0; i--) {
              if (
                updatedToolCalls[i].tool === event.tool &&
                updatedToolCalls[i].agent === event.agent &&
                updatedToolCalls[i].status === 'loading'
              ) {
                updatedToolCalls[i] = {
                  ...updatedToolCalls[i],
                  result: event.result,
                  actualArgs: actualArgs || updatedToolCalls[i].args,
                  status: 'done',
                }
                break
              }
            }
          }
          return { ...m, toolCalls: updatedToolCalls }
        })
        set({ toolRecords: records, messages: updatedMessages })

        // 解析工具结果中的 POI 坐标，自动推送到全局地图
        const amapTools = ['search_poi', 'search_around']
        if (event.tool === 'plan_route' && event.result) {
          const route = parseAmapRoute(event.result)
          if (route && (route.polyline.length > 0 || route.destination)) {
            set({
              currentRoute: {
                points: route.polyline,
                distance: route.distance,
                duration: route.duration,
              },
              centerTab: 'map',
            })
            // 终点也作为 POI 推送
            if (route.destination) {
              get().pushMapPois([{
                name: route.destination.name || '终点',
                address: '',
                lng: route.destination.lng,
                lat: route.destination.lat,
                category: 'destination',
              }])
            }
            // 起点也作为 POI 推送
            if (route.origin) {
              get().pushMapPois([{
                name: route.origin.name || '起点',
                address: '',
                lng: route.origin.lng,
                lat: route.origin.lat,
                category: 'origin',
              }])
            }
            // 路径规划成功：清除"立即开启导航"上下文
            get().clearNavigationContext()
          }
        } else if (event.tool === 'get_common_addresses' && event.result) {
          // 解析常用地址列表，更新导航上下文（触发"立即开启导航"按钮）
          const addrs = parseCommonAddresses(event.result)
          if (addrs.length > 0) {
            get().setPendingAddresses(addrs)
          }
        } else if (amapTools.includes(event.tool) && event.result) {
          const pois = parseAmapPOIs(event.result)
          if (pois.length > 0) {
            get().pushMapPois(pois)
          }
        }
        break
      }

      case 'vehicle_status_update': {
        const status = (event as any).status || {}
        // 解析后端返回的状态字典，更新前端车辆状态
        const acStr = status['空调'] || ''
        const acStatus = acStr.includes('开启') ? `开启 ${acStr.split(',')[1]?.trim() || ''}`.trim() : '关闭'
        // 解析胎压：优先结构化数据，回退文本
        let tirePressure = get().vehicleStatus.tirePressure
        if (status['胎压'] && typeof status['胎压'] === 'object') {
          tirePressure = {
            fl: Number(status['胎压'].fl) || tirePressure.fl,
            fr: Number(status['胎压'].fr) || tirePressure.fr,
            rl: Number(status['胎压'].rl) || tirePressure.rl,
            rr: Number(status['胎压'].rr) || tirePressure.rr,
          }
        } else if (typeof status['胎压'] === 'string') {
          const m = status['胎压'].match(/前左([\d.]+)bar.*前右([\d.]+)bar.*后左([\d.]+)bar.*后右([\d.]+)bar/)
          if (m) {
            tirePressure = { fl: +m[1], fr: +m[2], rl: +m[3], rr: +m[4] }
          }
        }
        set({
          vehicleStatus: {
            ...get().vehicleStatus,
            battery: parseInt(status['电池电量']?.replace('%', '')) || get().vehicleStatus.battery,
            range: parseInt(status['续航里程']?.replace('km', '')) || get().vehicleStatus.range,
            mileage: parseInt(status['总里程']?.replace('km', '')) || get().vehicleStatus.mileage,
            location: status['当前位置'] || get().vehicleStatus.location,
            acStatus,
            driveMode: status['驾驶模式'] || get().vehicleStatus.driveMode,
            tirePressure,
          },
        })
        break
      }

      case 'token': {
        if (currentStreamingMessageId) {
          set({
            messages: state.messages.map((m) =>
              m.id === currentStreamingMessageId
                ? { ...m, content: m.content + event.content, agent: event.agent }
                : m,
            ),
            isThinking: false,
          })
        }
        break
      }

      case 'end': {
        if (currentStreamingMessageId) {
          set({
            messages: state.messages.map((m) =>
              m.id === currentStreamingMessageId
                ? {
                    ...m,
                    streaming: false,
                    message_id: event.message_id,
                    // 用 end 事件的完整 response 兜底，避免漏字
                    content: event.response || m.content,
                  }
                : m,
            ),
            lastCompletedMessageId: currentStreamingMessageId,
          })
          currentStreamingMessageId = null
        }
        set({
          isThinking: false,
          activeAgent: null,
        })
        break
      }

      case 'error': {
        if (currentStreamingMessageId) {
          set({
            messages: state.messages.map((m) =>
              m.id === currentStreamingMessageId
                ? { ...m, content: m.content || `错误: ${event.message}`, streaming: false }
                : m,
            ),
          })
          currentStreamingMessageId = null
        } else {
          const errorMsg: ChatMessage = {
            id: genId(),
            role: 'assistant',
            content: `错误: ${event.message}`,
            timestamp: event.timestamp,
          }
          set({ messages: [...state.messages, errorMsg] })
        }
        set({
          isThinking: false,
          activeAgent: null,
        })
        break
      }
    }
  },

  resetChat: () => {
    set({
      messages: [],
      events: [],
      toolRecords: [],
      activeAgent: null,
      isThinking: false,
      thinkingContent: '',
      sessionId: genId(),
      lastCompletedMessageId: null,
    })
    currentStreamingMessageId = null
    lastUserQuery = ''
  },

  toggleSpeechSynthesis: () => {
    set({ speechSynthesisEnabled: !get().speechSynthesisEnabled })
  },

  setPhoneMode: (active: boolean) => {
    set({ phoneModeActive: active })
  },

  submitMessageFeedback: async (messageId: string, rating: FeedbackRating) => {
    const state = get()
    const message = state.messages.find((m) => m.id === messageId)
    if (!message) return
    if (message.feedbackSubmitted) return

    // 先乐观更新 UI
    set({
      messages: state.messages.map((m) =>
        m.id === messageId
          ? { ...m, feedback: rating, feedbackSubmitted: true }
          : m,
      ),
    })

    try {
      await submitFeedback({
        message_id: message.message_id || messageId,
        rating,
        session_id: state.sessionId,
        query: message.query || '',
        response: message.content,
      })
    } catch (e) {
      console.error('提交反馈失败:', e)
      // 失败时回滚
      set({
        messages: get().messages.map((m) =>
          m.id === messageId
            ? { ...m, feedback: undefined, feedbackSubmitted: false }
            : m,
        ),
      })
    }
  },

  setCenterTab: (tab) => {
    set({ centerTab: tab })
  },

  pushMapPois: (pois) => {
    if (!pois || pois.length === 0) return
    const existing = get().mapPois
    const seen = new Set(existing.map((p) => `${p.lng.toFixed(5)},${p.lat.toFixed(5)}`))
    const fresh = pois.filter((p) => {
      const key = `${p.lng.toFixed(5)},${p.lat.toFixed(5)}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    if (fresh.length === 0) return
    // 保留最近 50 个 POI
    const merged = [...existing, ...fresh].slice(-50)
    set({ mapPois: merged, centerTab: 'map' })
  },

  clearMapPois: () => {
    set({ mapPois: [] })
  },

  setCurrentRoute: (route) => {
    set({ currentRoute: route })
  },

  setUserLocation: (loc) => {
    set({ userLocation: loc, locationError: null, locationStatus: loc ? 'success' : 'idle' })
  },

  setLocationError: (err) => {
    set({ locationError: err, locationStatus: err ? 'error' : 'idle' })
  },

  setLocationStatus: (status) => {
    set({ locationStatus: status })
  },

  setPendingAddresses: (addresses) => {
    set({
      navigationContext: {
        pendingAddresses: addresses,
        selectedTarget: null,
        awaitingNavigation: addresses.length > 0,
      },
    })
  },

  selectNavigationTarget: (target) => {
    const ctx = get().navigationContext
    set({
      navigationContext: {
        ...ctx,
        selectedTarget: target,
        awaitingNavigation: true,
      },
    })
  },

  clearNavigationContext: () => {
    set({
      navigationContext: {
        pendingAddresses: [],
        selectedTarget: null,
        awaitingNavigation: false,
      },
    })
  },

  clearMessages: () => {
    // 关键：清空后重置 sessionId，让后端把这当成一次新会话
    // （否则带着旧 sessionId 继续对话，Agent 会把历史当成上下文，导致第一次消息总是"重演"）
    set({
      sessionId: genId(),
      messages: [],
      events: [],
      toolRecords: [],
      currentRoute: null,
      mapPois: [],
      navigationContext: {
        pendingAddresses: [],
        selectedTarget: null,
        awaitingNavigation: false,
      },
    })
  },
}))
