import { useState } from 'react'
import type { ChatMessage, MessageToolCall } from '../types/events'
import { useChatStore } from '../store/chatStore'
import MapView from './MapView'
import { parseAmapPOIs } from '../utils/parseAmap'
import type { MapPOI } from './MapView'

interface Props {
  message: ChatMessage
}

/** Agent ID 到中文名称的映射 */
const agentNames: Record<string, string> = {
  orchestrator: '主控编排器',
  vehicle_status: '车况查询',
  vehicle_control: '车控操作',
  navigation: '导航服务',
  diagnosis: '故障诊断',
  appointment: '预约服务',
  customer_service: '售后咨询',
}

/** 工具名到中文可读名（用于对话中展示"正在调用XX"） */
const toolDisplayNames: Record<string, string> = {
  get_vehicle_status: '查询车辆状态',
  get_battery_status: '查询电量',
  get_mileage_info: '查询里程',
  get_tire_pressure: '查询胎压',
  get_fault_codes: '查询故障码',
  get_location: '查询位置',
  control_air_conditioner: '控制空调',
  control_window: '控制车窗',
  control_sunroof: '控制天窗',
  control_seat: '控制座椅',
  control_ambient_light: '控制氛围灯',
  set_driving_mode: '设置驾驶模式',
  get_common_addresses: '获取常用地址',
  navigate_to: '发起导航',
  get_traffic_info: '查询路况',
  search_poi: '搜索兴趣点',
  search_around: '周边搜索',
  geocode: '地址解析',
  plan_route: '规划路线',
  get_weather: '查询天气',
  get_weather_forecast: '查询天气预报',
  get_location_info: '查询位置信息',
  query_service_centers: '查询服务网点',
  get_available_slots: '查询预约时段',
  book_maintenance: '预约保养',
  book_test_drive: '预约试驾',
  request_road_rescue: '请求道路救援',
  get_appointment_status: '查询预约',
  cancel_appointment: '取消预约',
  rag_summarize: '检索知识库',
  _rag_summarize: '检索知识库',
}

/** 工具调用简要状态（默认折叠，只显示工具名+loading/结果状态） */
function InlineToolCall({ call }: { call: MessageToolCall }) {
  // 默认折叠：只在用户主动点击时展开详情
  const [expanded, setExpanded] = useState(false)
  const isLoading = call.status === 'loading'
  const hasActualArgs = call.actualArgs && Object.keys(call.actualArgs).length > 0
  const hasOriginalArgs = Object.keys(call.args).length > 0
  const showArgsDiff = hasActualArgs && !hasOriginalArgs
  const displayName = toolDisplayNames[call.tool] || call.tool

  return (
    <div
      className={`rounded-md border text-[11px] transition-all ${
        isLoading
          ? 'border-neon-blue/30 bg-neon-blue/5'
          : 'border-white/10 bg-bg-base/40'
      }`}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-1.5 px-2 py-1 text-left"
      >
        {isLoading ? (
          <div className="w-2.5 h-2.5 rounded-full border border-neon-blue/30 border-t-neon-blue animate-spin-slow shrink-0" />
        ) : (
          <svg className="w-2.5 h-2.5 text-neon-green shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
        <span className="text-gray-500 text-[10px]">
          {isLoading ? '调用中' : '已完成'}
        </span>
        <span className="text-gray-300 truncate flex-1">
          {displayName}
          {showArgsDiff && !isLoading && (
            <span className="text-[9px] px-1 py-0.5 rounded bg-neon-green/15 text-neon-green border border-neon-green/20 font-mono ml-1">
              参数已推断
            </span>
          )}
        </span>
        <svg
          className={`w-3 h-3 text-gray-500 transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {expanded && (
        <div className="px-2 pb-2 space-y-1.5 animate-fade-in">
          {/* 参数显示 */}
          <div>
            <div className="text-[10px] text-gray-500 mb-0.5 flex items-center gap-1">
              <span>参数</span>
              {showArgsDiff && (
                <span className="text-[9px] text-neon-green">(已从用户查询推断)</span>
              )}
            </div>
            <pre className="text-[10px] text-gray-300 bg-bg-base/60 rounded p-1.5 overflow-x-auto font-mono leading-relaxed">
              {hasActualArgs
                ? JSON.stringify(call.actualArgs, null, 2)
                : hasOriginalArgs
                  ? JSON.stringify(call.args, null, 2)
                  : '{}'}
            </pre>
          </div>
          {/* 结果 */}
          <div>
            <div className="text-[10px] text-gray-500 mb-0.5">结果</div>
            {isLoading ? (
              <div className="text-[10px] text-neon-blue/70 bg-bg-base/60 rounded p-1.5 flex items-center gap-1">
                <span className="w-1 h-1 rounded-full bg-neon-blue animate-pulse" />
                <span>执行中...</span>
              </div>
            ) : (
              <pre className="text-[10px] text-neon-green/90 bg-bg-base/60 rounded p-1.5 overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap break-all">
                {call.result}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/** 点赞/踩反馈按钮组 */
function FeedbackButtons({ message }: { message: ChatMessage }) {
  const submitMessageFeedback = useChatStore((s) => s.submitMessageFeedback)
  const submitted = message.feedbackSubmitted
  const current = message.feedback

  const handleRate = (rating: 'like' | 'dislike') => {
    if (submitted) return
    submitMessageFeedback(message.id, rating)
  }

  return (
    <div className="flex items-center gap-1.5 mt-1.5">
      <button
        onClick={() => handleRate('like')}
        disabled={submitted}
        className={`w-6 h-6 rounded-md flex items-center justify-center transition-all ${
          submitted
            ? current === 'like'
              ? 'bg-neon-green/20 text-neon-green cursor-default'
              : 'bg-white/5 text-gray-600 cursor-default'
            : 'bg-white/5 text-gray-400 hover:bg-neon-green/15 hover:text-neon-green'
        }`}
        title={submitted ? (current === 'like' ? '已点赞' : '已评价') : '点赞'}
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill={current === 'like' && submitted ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
        </svg>
      </button>
      <button
        onClick={() => handleRate('dislike')}
        disabled={submitted}
        className={`w-6 h-6 rounded-md flex items-center justify-center transition-all ${
          submitted
            ? current === 'dislike'
              ? 'bg-neon-red/20 text-neon-red cursor-default'
              : 'bg-white/5 text-gray-600 cursor-default'
            : 'bg-white/5 text-gray-400 hover:bg-neon-red/15 hover:text-neon-red'
        }`}
        title={submitted ? (current === 'dislike' ? '已踩' : '已评价') : '踩'}
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill={current === 'dislike' && submitted ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17" />
        </svg>
      </button>
    </div>
  )
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === 'user'
  const hasToolCalls = !isUser && message.toolCalls && message.toolCalls.length > 0
  // 仅在 AI 消息流式结束且拥有 message_id 时显示反馈按钮
  const showFeedback = !isUser && !message.streaming && !!message.message_id

  // 导航上下文：用于支持"立即开启导航"按钮
  const navigationContext = useChatStore((s) => s.navigationContext)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const selectNavigationTarget = useChatStore((s) => s.selectNavigationTarget)

  // 当前消息内是否包含已完成的 get_common_addresses
  const hasCommonAddresses = !isUser && message.toolCalls?.some(
    (c) => c.tool === 'get_common_addresses' && c.status === 'done' && c.result
  )

  // 检测是否有高德 POI/路线结果，自动渲染地图
  const allPois = !isUser && message.toolCalls
    ? (() => {
        const collected: MapPOI[] = []
        for (const call of message.toolCalls) {
          if (
            (call.tool === 'search_poi' || call.tool === 'search_around' || call.tool === 'plan_route') &&
            call.status === 'done' &&
            call.result
          ) {
            // 解析 POI 列表（包含坐标的行）
            collected.push(...parseAmapPOIs(call.result))
            // 兜底：从"终点坐标：lng,lat"提取
            const coordMatch = call.result.match(/终点坐标[：:]\s*([\d.]+)[,，]\s*([\d.]+)/)
            if (coordMatch) {
              collected.push({
                name: '终点',
                address: '',
                lng: parseFloat(coordMatch[1]),
                lat: parseFloat(coordMatch[2]),
              })
            }
          }
        }
        // 去重
        const seen = new Set<string>()
        return collected.filter(p => {
          const key = `${p.lng},${p.lat}`
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
      })()
    : []
  const showMap = allPois.length > 0 && !message.streaming

  // 一行式工具调用概要：开始时显示"正在调用XX"，结束后显示"已使用XX YY"
  const toolSummary = hasToolCalls
    ? (() => {
        const calls = message.toolCalls!
        const hasLoading = calls.some((c) => c.status === 'loading')
        if (hasLoading && message.streaming) {
          const loading = calls.find((c) => c.status === 'loading')!
          return {
            prefix: '🔧 正在',
            verb: '调用',
            text: toolDisplayNames[loading.tool] || loading.tool,
            loading: true,
          }
        }
        // 全部完成时，列出已用工具
        const names = calls.map((c) => toolDisplayNames[c.tool] || c.tool)
        const unique = Array.from(new Set(names)).slice(0, 4)
        return {
          prefix: '🔧 已使用工具',
          verb: '',
          text: unique.join(' · '),
          loading: false,
        }
      })()
    : null

  // "立即开启导航" 按钮：使用上一次选中的目标（如有），否则用第一个常用地址
  const navButton = (() => {
    if (isUser) return null
    if (message.streaming) return null
    const target = navigationContext.selectedTarget
      || (navigationContext.pendingAddresses[0]?.name)
    if (!target) return null
    return target
  })()

  const handleStartNavigation = (target: string) => {
    selectNavigationTarget(target)
    // 触发系统化导航：发送"导航到<目标>"消息，复用上下文
    sendMessage(`导航到${target}`)
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`max-w-[85%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
        {!isUser && message.agent && (
          <div className="text-[10px] text-neon-blue/60 mb-1 ml-2 font-mono">
            {agentNames[message.agent] || message.agent}
          </div>
        )}
        <div
          className={
            isUser
              ? 'bg-gradient-to-br from-neon-blue/25 to-neon-blue/10 border border-neon-blue/40 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-lg shadow-neon-blue/10'
              : 'bg-bg-card-hover/80 border border-white/10 text-gray-100 rounded-2xl rounded-tl-sm px-4 py-2.5 backdrop-blur-sm'
          }
        >
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
            {message.streaming && (
              <span className="inline-block w-[2px] h-4 bg-neon-green ml-0.5 animate-blink align-middle rounded-full" />
            )}
          </p>

          {/* 一行式工具调用概要（默认展示，不展开） */}
          {toolSummary && (
            <div className={`mt-1.5 text-[11px] flex items-center gap-1 ${
              toolSummary.loading ? 'text-neon-blue/80' : 'text-gray-500'
            }`}>
              <span>{toolSummary.prefix}{toolSummary.verb}</span>
              {toolSummary.loading && (
                <span className="font-mono text-neon-blue">{toolSummary.text}</span>
              )}
              {!toolSummary.loading && (
                <span className="font-mono">{toolSummary.text}</span>
              )}
              {toolSummary.loading && (
                <span className="flex gap-0.5 ml-1">
                  <span className="w-1 h-1 rounded-full bg-neon-blue animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1 h-1 rounded-full bg-neon-blue animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1 h-1 rounded-full bg-neon-blue animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
              )}
            </div>
          )}

          {/* 工具调用详情（默认折叠，用户主动展开） */}
          {hasToolCalls && (
            <div className="mt-1.5 space-y-1 border-t border-white/5 pt-1.5">
              {message.toolCalls!.map((call) => (
                <InlineToolCall key={call.id} call={call} />
              ))}
            </div>
          )}

          {/* 地图展示（POI搜索结果自动渲染） */}
          {showMap && (
            <div className="mt-3 border-t border-white/5 pt-3">
              <div className="flex items-center gap-1.5 mb-2 text-[11px] text-neon-blue">
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
                <span>地图显示 - 高德地图</span>
                <span className="text-gray-500">({allPois.length}个地点)</span>
              </div>
              <MapView pois={allPois} height="300px" />
            </div>
          )}

          {/* 立即开启导航按钮：上下文感知，接续上一次导航讨论 */}
          {navButton && !showMap && (
            <div className="mt-3 border-t border-white/5 pt-3 flex items-center gap-2">
              <button
                onClick={() => handleStartNavigation(navButton)}
                className="flex-1 bg-neon-blue/20 hover:bg-neon-blue/30 text-neon-blue text-sm font-medium rounded-lg px-3 py-2 transition-colors flex items-center justify-center gap-1.5 border border-neon-blue/30"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="3 11 22 2 13 21 11 13 3 11" />
                </svg>
                立即开启导航到「{navButton}」
              </button>
              {navigationContext.pendingAddresses.length > 1 && (
                <div className="flex flex-col gap-1 text-[10px]">
                  {navigationContext.pendingAddresses.slice(1, 4).map((addr) => (
                    <button
                      key={addr.name}
                      onClick={() => handleStartNavigation(addr.name)}
                      className="bg-white/5 hover:bg-white/10 text-gray-300 rounded px-2 py-1 border border-white/10 transition-colors text-left"
                      title={addr.address}
                    >
                      换：{addr.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 常用地址列表：点击任意一个即可开始导航（与"立即开启导航"按钮互补） */}
          {hasCommonAddresses && navigationContext.pendingAddresses.length > 0 && !showMap && (
            <div className="mt-2 border-t border-white/5 pt-2">
              <div className="text-[10px] text-gray-500 mb-1.5">点击下方地址开始导航：</div>
              <div className="grid grid-cols-2 gap-1.5">
                {navigationContext.pendingAddresses.map((addr) => (
                  <button
                    key={addr.name}
                    onClick={() => handleStartNavigation(addr.name)}
                    className={`text-left rounded-md px-2 py-1.5 border transition-all ${
                      (navigationContext.selectedTarget || navigationContext.pendingAddresses[0]?.name) === addr.name
                        ? 'bg-neon-blue/15 text-neon-blue border-neon-blue/30'
                        : 'bg-white/5 hover:bg-neon-blue/15 text-gray-200 hover:text-neon-blue border-white/10 hover:border-neon-blue/30'
                    }`}
                  >
                    <div className="text-xs font-medium">{addr.name}</div>
                    <div className="text-[9px] text-gray-500 truncate">{addr.address}</div>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 反馈按钮 */}
        {showFeedback && <FeedbackButtons message={message} />}
      </div>
    </div>
  )
}
