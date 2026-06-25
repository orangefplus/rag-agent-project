import { useChatStore } from '../store/chatStore'

/** 快捷操作预设问题 */
const quickActions = [
  { icon: 'battery', text: '我的车还有多少电？' },
  { icon: 'ac', text: '帮我打开空调到24度' },
  { icon: 'nav', text: '导航到最近的充电桩' },
  { icon: 'diagnose', text: '空调不制冷怎么办' },
  { icon: 'appointment', text: '帮我预约保养' },
  { icon: 'warranty', text: '质保政策是什么' },
]

function QuickActionIcon({ name }: { name: string }) {
  const className = 'w-3.5 h-3.5'
  switch (name) {
    case 'battery':
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="1" y="6" width="18" height="12" rx="2" ry="2" />
          <line x1="23" y1="13" x2="23" y2="11" />
        </svg>
      )
    case 'ac':
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="12" y1="2" x2="12" y2="22" />
          <path d="M5 5l14 14M19 5L5 19" />
        </svg>
      )
    case 'nav':
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="3 11 22 2 13 21 11 13 3 11" />
        </svg>
      )
    case 'diagnose':
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      )
    case 'appointment':
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      )
    case 'warranty':
      return (
        <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      )
    default:
      return null
  }
}

function InfoRow({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-gray-500">{label}</span>
      <span className={`text-xs font-medium ${accent || 'text-gray-200'}`}>{value}</span>
    </div>
  )
}

export default function VehicleStatus() {
  const vehicleStatus = useChatStore((s) => s.vehicleStatus)
  const sendMessage = useChatStore((s) => s.sendMessage)

  const battery = vehicleStatus.battery
  const batteryColor =
    battery > 50 ? 'bg-neon-green' : battery > 20 ? 'bg-neon-yellow' : 'bg-neon-red'
  const batteryTextColor =
    battery > 50 ? 'text-neon-green' : battery > 20 ? 'text-neon-yellow' : 'text-neon-red'

  const tires = [
    { label: '左前', value: vehicleStatus.tirePressure.fl },
    { label: '右前', value: vehicleStatus.tirePressure.fr },
    { label: '左后', value: vehicleStatus.tirePressure.rl },
    { label: '右后', value: vehicleStatus.tirePressure.rr },
  ]

  return (
    <div className="flex flex-col h-full bg-bg-card/40 backdrop-blur-xl border-l border-white/5">
      {/* 标题 */}
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-white/5 bg-bg-base/30">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-green/20 to-neon-blue/10 flex items-center justify-center border border-neon-green/20">
          <svg className="w-4 h-4 text-neon-green" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
            <circle cx="7" cy="17" r="2" />
            <circle cx="17" cy="17" r="2" />
          </svg>
        </div>
        <h2 className="text-white font-semibold text-base">车辆状态</h2>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 custom-scroll">
        {/* 车型卡片 */}
        <div className="rounded-xl bg-gradient-to-br from-bg-card-hover to-bg-card border border-white/10 p-3">
          <div className="flex items-center gap-2 mb-1">
            <svg className="w-4 h-4 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
              <circle cx="7" cy="17" r="2" />
              <circle cx="17" cy="17" r="2" />
            </svg>
            <span className="text-xs text-gray-400">车型</span>
          </div>
          <p className="text-sm font-semibold text-white">{vehicleStatus.model}</p>
        </div>

        {/* 电池电量 */}
        <div className="rounded-xl bg-bg-card-hover/50 border border-white/10 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-neon-green" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="1" y="6" width="18" height="12" rx="2" ry="2" />
                <line x1="23" y1="13" x2="23" y2="11" />
              </svg>
              <span className="text-xs text-gray-400">电池电量</span>
            </div>
            <span className={`text-sm font-bold ${batteryTextColor}`}>{battery}%</span>
          </div>
          <div className="h-2.5 rounded-full bg-bg-base/80 overflow-hidden">
            <div
              className={`h-full rounded-full ${batteryColor} transition-all duration-500 relative overflow-hidden`}
              style={{ width: `${battery}%` }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse" />
            </div>
          </div>
          <div className="flex justify-between mt-1.5">
            <span className="text-[10px] text-gray-600">0%</span>
            <span className="text-[10px] text-gray-600">100%</span>
          </div>
        </div>

        {/* 续航 & 里程 */}
        <div className="grid grid-cols-2 gap-2.5">
          <div className="rounded-xl bg-bg-card-hover/50 border border-white/10 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <svg className="w-3.5 h-3.5 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span className="text-[10px] text-gray-500">续航里程</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-white">{vehicleStatus.range}</span>
              <span className="text-[10px] text-gray-500">km</span>
            </div>
          </div>
          <div className="rounded-xl bg-bg-card-hover/50 border border-white/10 p-3">
            <div className="flex items-center gap-1.5 mb-1">
              <svg className="w-3.5 h-3.5 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span className="text-[10px] text-gray-500">总里程</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-white">
                {vehicleStatus.mileage.toLocaleString()}
              </span>
              <span className="text-[10px] text-gray-500">km</span>
            </div>
          </div>
        </div>

        {/* 胎压 */}
        <div className="rounded-xl bg-bg-card-hover/50 border border-white/10 p-3">
          <div className="flex items-center gap-2 mb-2.5">
            <svg className="w-4 h-4 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="4" />
            </svg>
            <span className="text-xs text-gray-400">胎压监测 (bar)</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {tires.map((tire) => (
              <div
                key={tire.label}
                className="flex items-center justify-between bg-bg-base/40 rounded-lg px-2.5 py-1.5"
              >
                <span className="text-[10px] text-gray-500">{tire.label}</span>
                <span className="text-xs font-mono font-medium text-neon-green">{tire.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 其他信息 */}
        <div className="rounded-xl bg-bg-card-hover/50 border border-white/10 p-3">
          <InfoRow label="当前位置" value={vehicleStatus.location} accent="text-neon-blue" />
          <div className="border-t border-white/5" />
          <InfoRow label="空调状态" value={vehicleStatus.acStatus} />
          <div className="border-t border-white/5" />
          <InfoRow label="驾驶模式" value={vehicleStatus.driveMode} accent="text-neon-purple" />
        </div>

        {/* 快捷操作 */}
        <div>
          <div className="flex items-center gap-2 mb-2 px-1">
            <svg className="w-3.5 h-3.5 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
            <span className="text-xs font-medium text-gray-300">快捷操作</span>
          </div>
          <div className="space-y-1.5">
            {quickActions.map((action) => (
              <button
                key={action.text}
                onClick={() => sendMessage(action.text)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-card-hover/40 border border-white/5 hover:border-neon-blue/30 hover:bg-neon-blue/5 transition-all text-left group"
              >
                <span className="text-gray-500 group-hover:text-neon-blue transition-colors">
                  <QuickActionIcon name={action.icon} />
                </span>
                <span className="text-xs text-gray-300 group-hover:text-white transition-colors flex-1">
                  {action.text}
                </span>
                <svg className="w-3 h-3 text-gray-600 group-hover:text-neon-blue transition-colors" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
