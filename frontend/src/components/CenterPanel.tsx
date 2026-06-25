import { useState } from 'react'
import { useChatStore } from '../store/chatStore'
import AgentGraph from './AgentGraph'
import MapView from './MapView'
import ToolTimeline from './ToolTimeline'
import { useGeolocation, fallbackIPLocation } from '../hooks/useGeolocation'

export default function CenterPanel() {
  const centerTab = useChatStore((s) => s.centerTab)
  const setCenterTab = useChatStore((s) => s.setCenterTab)
  const mapPois = useChatStore((s) => s.mapPois)
  const clearMapPois = useChatStore((s) => s.clearMapPois)
  const activeAgent = useChatStore((s) => s.activeAgent)
  const currentRoute = useChatStore((s) => s.currentRoute)
  const userLocation = useChatStore((s) => s.userLocation)
  const setUserLocation = useChatStore((s) => s.setUserLocation)
  const setLocationError = useChatStore((s) => s.setLocationError)
  const locationError = useChatStore((s) => s.locationError)
  const locationStatus = useChatStore((s) => s.locationStatus)
  const setCurrentRoute = useChatStore((s) => s.setCurrentRoute)

  const { requestLocation, isRequesting } = useGeolocation()
  const [showManualInput, setShowManualInput] = useState(false)
  const [manualLng, setManualLng] = useState('116.3076')
  const [manualLat, setManualLat] = useState('39.9847')
  const [manualCity, setManualCity] = useState('北京')
  const [manualDistrict, setManualDistrict] = useState('海淀区')

  const handleManualSubmit = async () => {
    const lng = parseFloat(manualLng)
    const lat = parseFloat(manualLat)
    if (isNaN(lng) || isNaN(lat)) {
      alert('请输入有效的经纬度')
      return
    }
    setUserLocation({ lng, lat, city: manualCity, district: manualDistrict })
    // 上报后端
    try {
      await fetch('/api/vehicle/location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lng, lat, city: manualCity, district: manualDistrict }),
      })
    } catch (e) {
      console.warn('上报位置失败:', e)
    }
    setShowManualInput(false)
  }

  // 标题根据 Tab 动态变化
  const title = centerTab === 'map' ? '🗺️ 地图视图' : '🧩 智能体编排可视化'
  const subtitle =
    centerTab === 'map'
      ? `已显示 ${mapPois.length} 个兴趣点`
      : activeAgent
      ? `当前路由: ${activeAgent}`
      : '等待路由中...'

  return (
    <div className="h-full flex flex-col">
      {/* 标题栏 + Tab 切换 */}
      <div className="flex items-center justify-between gap-2.5 px-5 py-4 border-b border-white/5 bg-bg-card/30 shrink-0">
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <div
            className={`w-8 h-8 rounded-lg flex items-center justify-center border shrink-0 ${
              centerTab === 'map'
                ? 'bg-gradient-to-br from-neon-blue/20 to-neon-purple/10 border-neon-blue/20'
                : 'bg-gradient-to-br from-neon-purple/20 to-neon-pink/10 border-neon-purple/20'
            }`}
          >
            {centerTab === 'map' ? (
              <svg
                className="w-4 h-4 text-neon-blue"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
            ) : (
              <svg
                className="w-4 h-4 text-neon-purple"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="6" cy="6" r="3" />
                <circle cx="6" cy="18" r="3" />
                <circle cx="18" cy="18" r="3" />
                <line x1="20" y1="4" x2="8.12" y2="15.88" />
                <line x1="14.47" y1="14.48" x2="20" y2="20" />
                <line x1="8.12" y1="8.12" x2="12" y2="12" />
              </svg>
            )}
          </div>
          <div className="min-w-0">
            <h2 className="text-white font-semibold text-base whitespace-nowrap">{title}</h2>
            <div className="text-xs text-white/40 whitespace-nowrap truncate">{subtitle}</div>
          </div>
        </div>

        {/* Tab 切换按钮组 */}
        <div className="flex items-center gap-1 p-1 bg-white/5 rounded-lg border border-white/10 shrink-0">
          <button
            onClick={() => setCenterTab('map')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5 ${
              centerTab === 'map'
                ? 'bg-neon-blue/20 text-neon-blue shadow-sm shadow-neon-blue/20'
                : 'text-white/60 hover:text-white/90 hover:bg-white/5'
            }`}
            title="切换到地图视图"
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            地图
          </button>
          <button
            onClick={() => setCenterTab('orchestration')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all flex items-center gap-1.5 ${
              centerTab === 'orchestration'
                ? 'bg-neon-purple/20 text-neon-purple shadow-sm shadow-neon-purple/20'
                : 'text-white/60 hover:text-white/90 hover:bg-white/5'
            }`}
            title="切换到智能体编排视图"
          >
            <svg
              className="w-3.5 h-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="6" cy="6" r="3" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="18" r="3" />
              <line x1="20" y1="4" x2="8.12" y2="15.88" />
              <line x1="14.47" y1="14.48" x2="20" y2="20" />
              <line x1="8.12" y1="8.12" x2="12" y2="12" />
            </svg>
            编排
          </button>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 min-h-0 relative bg-bg-base/30">
        {centerTab === 'map' ? (
          <div className="absolute inset-0 flex flex-col">
            {/* 顶部状态栏 */}
            <div className="flex items-center justify-between gap-2 px-4 py-2 border-b border-white/5 bg-bg-card/30 shrink-0">
              <div className="flex items-center gap-2 text-xs text-white/60 min-w-0 flex-1">
                {locationStatus === 'requesting' ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
                    <span className="text-yellow-300">正在定位...</span>
                  </>
                ) : userLocation ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse" />
                    <span className="truncate">
                      {userLocation.city || '已定位'}
                      {userLocation.district ? `·${userLocation.district}` : ''}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
                    <span className="text-red-300">未获取到定位</span>
                  </>
                )}
                {mapPois.length > 0 && (
                  <span className="text-white/40 whitespace-nowrap">· {mapPois.length} 个兴趣点</span>
                )}
                {currentRoute && (
                  <span className="text-neon-blue whitespace-nowrap">
                    · 路线 {currentRoute.distance ? `${(currentRoute.distance / 1000).toFixed(1)}km` : ''}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {/* 重新定位按钮 */}
                <button
                  onClick={requestLocation}
                  disabled={isRequesting}
                  className="text-xs text-white/40 hover:text-white/80 px-2 py-1 rounded hover:bg-white/5 transition-colors flex items-center gap-1 disabled:opacity-50"
                  title="重新定位"
                >
                  <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
                  </svg>
                  {isRequesting ? '定位中' : '重新定位'}
                </button>
                {/* IP 降级按钮 */}
                <button
                  onClick={async () => {
                    const ok = await fallbackIPLocation()
                    if (!ok) {
                      setLocationError('IP定位也失败了，请检查高德API Key或手动输入')
                    }
                  }}
                  className="text-xs text-white/40 hover:text-white/80 px-2 py-1 rounded hover:bg-white/5 transition-colors"
                  title="使用IP定位（精度较低）"
                >
                  IP定位
                </button>
                {/* 手动输入按钮 */}
                <button
                  onClick={() => setShowManualInput(true)}
                  className="text-xs text-white/40 hover:text-white/80 px-2 py-1 rounded hover:bg-white/5 transition-colors"
                  title="手动输入经纬度"
                >
                  手动输入
                </button>
                {currentRoute && (
                  <button
                    onClick={() => setCurrentRoute(null)}
                    className="text-xs text-white/40 hover:text-white/80 px-2 py-1 rounded hover:bg-white/5 transition-colors"
                    title="清除当前路线"
                  >
                    清除路线
                  </button>
                )}
                {mapPois.length > 0 && (
                  <button
                    onClick={() => clearMapPois()}
                    className="text-xs text-white/40 hover:text-white/80 px-2 py-1 rounded hover:bg-white/5 transition-colors"
                    title="清空所有 POI"
                  >
                    清空 POI
                  </button>
                )}
              </div>
            </div>

            {/* 错误提示条 */}
            {locationError && (
              <div className="px-4 py-2 bg-red-500/10 border-b border-red-500/20 text-xs text-red-300 flex items-center gap-2 flex-wrap">
                <svg className="w-3.5 h-3.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span className="flex-1 min-w-0">{locationError}</span>
                {/* 快速操作按钮 */}
                <button
                  onClick={async () => {
                    const ok = await fallbackIPLocation()
                    if (!ok) {
                      setLocationError('IP 定位也失败了，请手动输入位置')
                    } else {
                      setLocationError(null)
                    }
                  }}
                  className="px-2 py-0.5 bg-neon-blue/20 hover:bg-neon-blue/30 text-neon-blue rounded transition-colors font-medium"
                >
                  使用 IP 定位
                </button>
                <button
                  onClick={() => setShowManualInput(true)}
                  className="px-2 py-0.5 bg-neon-purple/20 hover:bg-neon-purple/30 text-neon-purple rounded transition-colors font-medium"
                >
                  手动输入
                </button>
                <button
                  onClick={() => setLocationError(null)}
                  className="text-red-300/60 hover:text-red-300"
                >
                  ✕
                </button>
              </div>
            )}

            {/* 手动输入对话框 */}
            {showManualInput && (
              <div className="absolute top-12 right-4 z-[1000] bg-bg-card/95 backdrop-blur border border-white/10 rounded-lg p-4 shadow-2xl w-80">
                <div className="text-sm font-medium text-white mb-3">手动输入位置</div>
                <div className="space-y-2">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-white/50">经度(lng)</label>
                      <input
                        type="text"
                        value={manualLng}
                        onChange={(e) => setManualLng(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm text-white"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-white/50">纬度(lat)</label>
                      <input
                        type="text"
                        value={manualLat}
                        onChange={(e) => setManualLat(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm text-white"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-white/50">城市</label>
                      <input
                        type="text"
                        value={manualCity}
                        onChange={(e) => setManualCity(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm text-white"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-white/50">区县</label>
                      <input
                        type="text"
                        value={manualDistrict}
                        onChange={(e) => setManualDistrict(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded px-2 py-1 text-sm text-white"
                      />
                    </div>
                  </div>
                  <div className="text-[10px] text-white/40">
                    提示：高德坐标系，火星坐标。可从高德地图拾取坐标。
                  </div>
                  <div className="flex gap-2 pt-1">
                    <button
                      onClick={handleManualSubmit}
                      className="flex-1 bg-neon-blue/20 hover:bg-neon-blue/30 text-neon-blue text-sm rounded px-3 py-1.5 transition-colors"
                    >
                      确认
                    </button>
                    <button
                      onClick={() => setShowManualInput(false)}
                      className="flex-1 bg-white/5 hover:bg-white/10 text-white/70 text-sm rounded px-3 py-1.5 transition-colors"
                    >
                      取消
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 地图主体（始终显示） */}
            <div className="flex-1 min-h-0 p-2">
              <MapView
                pois={mapPois as any}
                route={currentRoute ?? undefined}
                userLocation={userLocation}
                height="100%"
              />
            </div>
          </div>
        ) : (
          <AgentGraph />
        )}
      </div>

      {/* 工具调用时间线 */}
      <div className="h-[33%] min-h-[180px] max-h-[300px] border-t border-white/5 bg-bg-card/20 shrink-0">
        <ToolTimeline />
      </div>
    </div>
  )
}
