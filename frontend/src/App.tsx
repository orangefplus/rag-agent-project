import { useEffect } from 'react'
import { useChatStore } from './store/chatStore'
import { useGeolocation } from './hooks/useGeolocation'
import ChatPanel from './components/ChatPanel'
import CenterPanel from './components/CenterPanel'
import VehicleStatus from './components/VehicleStatus'
import PhoneCallMode from './components/PhoneCallMode'

// 控制台错误过滤器（兜底 - 但浏览器层网络错误如 net::ERR_ABORTED 不走 console.error，
// 真正治本看 MapView.tsx 里的 MapTileLoadOptimizer 组件）
if (typeof window !== 'undefined') {
  const w = window as any
  if (!w.__tileErrorFilterInstalled) {
    w.__tileErrorFilterInstalled = true
    const origError = console.error.bind(console)
    console.error = (...args: any[]) => {
      const all = args
        .map((a) => {
          if (typeof a === 'string') return a
          if (a && typeof a === 'object') {
            return (a.message || a.toString?.() || '') + ' ' + (a.stack || '')
          }
          return String(a)
        })
        .join(' || ')
      const isAbort = /ERR_ABORTED|abort\(\)|Failed to load resource/i.test(all)
      const isAmapTile = /(autonavi|appmaptile|webrd\d|webst\d|amap)/i.test(all)
      if (isAbort && isAmapTile) {
        return
      }
      origError(...args)
    }
  }
}

export default function App() {
  const connect = useChatStore((s) => s.connect)
  const loadAgents = useChatStore((s) => s.loadAgents)
  const loadVehicleStatus = useChatStore((s) => s.loadVehicleStatus)
  const phoneModeActive = useChatStore((s) => s.phoneModeActive)
  const setPhoneMode = useChatStore((s) => s.setPhoneMode)

  const { requestLocation } = useGeolocation()

  useEffect(() => {
    connect()
    loadAgents()
    loadVehicleStatus()
    // 首次尝试浏览器定位
    requestLocation()

    return () => {
      useChatStore.getState().disconnect()
    }
  }, [connect, loadAgents, loadVehicleStatus, requestLocation])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg-base text-white">
      {/* 左栏：对话面板 35% */}
      <div className="w-[35%] min-w-[400px] h-full">
        <ChatPanel />
      </div>

      {/* 中栏：可切换的地图/编排视图 40% */}
      <div className="w-[40%] min-w-[450px] h-full flex flex-col bg-bg-base/50">
        <CenterPanel />
      </div>

      {/* 右栏：车辆状态 25% */}
      <div className="w-[25%] min-w-[300px] h-full">
        <VehicleStatus />
      </div>

      {/* 电话对话模式全屏遮罩 */}
      {phoneModeActive && <PhoneCallMode onHangup={() => setPhoneMode(false)} />}
    </div>
  )
}
