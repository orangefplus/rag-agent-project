// ============ WebSocket 事件类型定义 ============

/** 开始事件 */
export interface StartEvent {
  type: 'start'
  query: string
  agent: string
  timestamp: number
}

/** 思考事件 */
export interface ThinkingEvent {
  type: 'thinking'
  content: string
  agent: string
  timestamp: number
}

/** 路由事件 */
export interface RouteEvent {
  type: 'route'
  from_agent: string
  to_agent: string
  to_agent_name: string
  reason: string
  timestamp: number
}

/** 工具调用事件 */
export interface ToolCallEvent {
  type: 'tool_call'
  agent: string
  tool: string
  args: Record<string, unknown>
  call_id?: string
  timestamp: number
}

/** 工具结果事件 */
export interface ToolResultEvent {
  type: 'tool_result'
  agent: string
  tool: string
  result: string
  call_id?: string
  actual_args?: Record<string, unknown>
  timestamp: number
}

/** Token 流式事件 */
export interface TokenEvent {
  type: 'token'
  content: string
  agent: string
  timestamp: number
}

/** 结束事件（已更新：包含 message_id, response, tools 字段） */
export interface EndEvent {
  type: 'end'
  agent: string
  message_id: string
  response: string
  tools: string[]
  timestamp: number
}

/** 错误事件 */
export interface ErrorEvent {
  type: 'error'
  message: string
  timestamp: number
}

/** 车辆状态更新事件 */
export interface VehicleStatusUpdateEvent {
  type: 'vehicle_status_update'
  status: Record<string, string>
  timestamp: number
}

/** 路线更新事件 - 后端在 navigate_to / plan_route 之后推送 */
export interface RouteUpdateEvent {
  type: 'route_update'
  points: Array<[number, number]>  // [[lat, lng], ...]
  distance?: number  // 米
  duration?: number  // 秒
  destination?: string
  timestamp: number
}

/** 所有事件联合类型 */
export type ChatEvent =
  | StartEvent
  | ThinkingEvent
  | RouteEvent
  | ToolCallEvent
  | ToolResultEvent
  | TokenEvent
  | EndEvent
  | ErrorEvent
  | VehicleStatusUpdateEvent
  | RouteUpdateEvent

// ============ 消息类型 ============

export type MessageRole = 'user' | 'assistant'

/** 消息内嵌的工具调用记录（用于在消息气泡中展示） */
export interface MessageToolCall {
  id: string
  tool: string
  agent: string
  args: Record<string, unknown>
  actualArgs?: Record<string, unknown>
  callId?: string
  result?: string
  status: 'loading' | 'done'
  timestamp: number
}

/** 反馈评分类型 */
export type FeedbackRating = 'like' | 'dislike'

export interface ChatMessage {
  id: string
  role: MessageRole
  content: string
  agent?: string
  streaming?: boolean
  timestamp: number
  // 服务端返回的消息ID（end 事件携带），用于反馈
  message_id?: string
  // 该消息关联的工具调用记录
  toolCalls?: MessageToolCall[]
  // 用户反馈评分
  feedback?: FeedbackRating
  // 反馈是否已提交（已提交则按钮不可点击）
  feedbackSubmitted?: boolean
  // 关联的用户提问（assistant 消息使用，用于反馈接口）
  query?: string
}

// ============ Agent 拓扑类型 ============

export type AgentNodeType = 'orchestrator' | 'sub_agent'

export interface AgentInfo {
  id: string
  name: string
  type: AgentNodeType
  desc: string
  tools?: string[]
  has_rag?: boolean
  available?: boolean
}

export interface AgentEdge {
  from: string
  to: string
}

export interface AgentTopology {
  nodes: AgentInfo[]
  edges: AgentEdge[]
}

// ============ 工具调用记录 ============

export interface ToolRecord {
  id: string
  agent: string
  tool: string
  args: Record<string, unknown>
  actualArgs?: Record<string, unknown>
  callId?: string
  result?: string
  status: 'loading' | 'done'
  timestamp: number
}

// ============ 车辆状态 ============

export interface VehicleStatusData {
  model: string
  battery: number
  range: number
  mileage: number
  tirePressure: {
    fl: number
    fr: number
    rl: number
    rr: number
  }
  location: string
  acStatus: string
  driveMode: string
}

// ============ 连接状态 ============

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected'

export {}
