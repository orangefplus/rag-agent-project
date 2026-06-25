import { useMemo, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, CircleMarker } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// 修复 Leaflet 默认图标问题
import iconUrl from 'leaflet/dist/images/marker-icon.png'
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png'
import shadowUrl from 'leaflet/dist/images/marker-shadow.png'

L.Icon.Default.mergeOptions({
  iconUrl,
  iconRetinaUrl,
  shadowUrl,
})

/**
 * 减少瓦片中止产生的 net::ERR_ABORTED 控制台噪音：
 * - updateWhenZooming=false → 缩放期间不取消已有瓦片请求
 * - updateWhenIdle=true → 平移/缩放结束后再加载新瓦片（避免快速操作期间反复 abort）
 * - keepBuffer=6 → 视野外多保留 6 圈瓦片（默认 2），减少来回重新加载
 */
function MapTileLoadOptimizer() {
  const map = useMap()
  useEffect(() => {
    ;(map as any).options.updateWhenZooming = false
    ;(map as any).options.updateWhenIdle = true
    ;(map as any).options.keepBuffer = 6
    ;(map as any).options.loadingTimeout = 20000
  }, [map])
  return null
}

// 高德瓦片源（无需 Key，免费使用）
const AMAP_TILE_URLS = {
  vector: 'https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
  satellite: 'https://webst0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=6&x={x}&y={y}&z={z}',
}

export interface MapPOI {
  name: string
  address: string
  lng: number
  lat: number
  distance?: number
  category?: string
}

export interface MapRoute {
  points: [number, number][]
  distance?: number
  duration?: number
  origin?: string
  destination?: string
}

export interface UserLocation {
  lng: number
  lat: number
  city?: string
  district?: string
}

/** 地图自动适配组件 */
function FitBounds({
  pois,
  route,
  userLocation,
}: {
  pois: MapPOI[]
  route?: MapRoute
  userLocation?: UserLocation | null
}) {
  const map = useMap()
  const points = useMemo(() => {
    const pts: [number, number][] = []
    pois.forEach((p) => pts.push([p.lat, p.lng]))
    if (route) pts.push(...route.points)
    if (userLocation) pts.push([userLocation.lat, userLocation.lng])
    return pts
  }, [pois, route, userLocation])

  useEffect(() => {
    if (points.length === 0) return
    if (points.length === 1) {
      map.setView(points[0], 14, { animate: true })
      return
    }
    const bounds = L.latLngBounds(points)
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15, animate: true })
  }, [points, map])

  return null
}

/** 数字图标（POI 序号） */
function createNumberedIcon(num: number, color: string = '#00ff88') {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      width:32px;height:32px;border-radius:50%;
      background:${color};color:#0a0e1a;
      display:flex;align-items:center;justify-content:center;
      font-weight:bold;font-size:14px;
      box-shadow:0 0 8px ${color}80, 0 0 2px #000;
      border:2px solid #fff;
    ">${num}</div>`,
    iconSize: [32, 32],
    iconAnchor: [16, 16],
  })
}

/** 起点图标（绿色S） */
const startIcon = L.divIcon({
  className: 'custom-marker',
  html: `<div style="
    width:28px;height:28px;border-radius:50%;
    background:#00cc66;color:#fff;
    display:flex;align-items:center;justify-content:center;
    font-weight:bold;font-size:11px;
    box-shadow:0 0 12px #00cc66cc, 0 0 4px #000;
    border:3px solid #fff;
  ">起</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
})

/** 终点图标（红色E） */
const endIcon = L.divIcon({
  className: 'custom-marker',
  html: `<div style="
    width:28px;height:28px;border-radius:50%;
    background:#ff3344;color:#fff;
    display:flex;align-items:center;justify-content:center;
    font-weight:bold;font-size:11px;
    box-shadow:0 0 12px #ff3344cc, 0 0 4px #000;
    border:3px solid #fff;
  ">终</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
})

interface MapViewProps {
  pois?: MapPOI[]
  route?: MapRoute
  userLocation?: UserLocation | null
  height?: string | number
  initialCenter?: [number, number]
  initialZoom?: number
  mapType?: 'vector' | 'satellite'
}

/**
 * 高德地图组件
 * - 常驻显示用户位置（蓝色脉冲圆点）
 * - 显示 POI 标记（数字编号）
 * - 显示路径规划（绿色 polyline + 起终点标记）
 */
export default function MapView({
  pois = [],
  route,
  userLocation,
  height = '400px',
  initialCenter,
  initialZoom = 13,
  mapType = 'vector',
}: MapViewProps) {
  const tileUrl = mapType === 'satellite' ? AMAP_TILE_URLS.satellite : AMAP_TILE_URLS.vector

  // 默认中心：用户位置 > POI 第一个 > 北京中关村
  const defaultCenter: [number, number] =
    initialCenter ||
    (userLocation ? [userLocation.lat, userLocation.lng] : null) ||
    (pois.length > 0 ? [pois[0].lat, pois[0].lng] : null) ||
    [39.9847, 116.3076]

  return (
    <div
      className="rounded-xl overflow-hidden border border-neon-blue/30 shadow-lg shadow-neon-blue/10 relative"
      style={{ height }}
    >
      <MapContainer
        center={defaultCenter}
        zoom={initialZoom}
        scrollWheelZoom
        style={{ height: '100%', width: '100%', background: '#0a0e1a' }}
        zoomControl={false}
      >
        <MapTileLoadOptimizer />
        <TileLayer
          url={tileUrl}
          subdomains={['1', '2', '3', '4']}
          attribution='&copy; 高德地图 AutoNavi'
          eventHandlers={{
            tileerror: (e) => {
              // 浏览器会打 net::ERR_ABORTED 是网络层日志，Leaflet 这边静默即可
              const err = e.error as Error | undefined
              if (err && /abort/i.test(err.message || '')) {
                return
              }
              console.warn('[Map] 瓦片加载失败:', err?.message || e)
            },
          }}
        />

        {/* 我的位置（蓝色脉冲圆点） */}
        {userLocation && (
          <>
            <CircleMarker
              center={[userLocation.lat, userLocation.lng]}
              radius={20}
              pathOptions={{
                color: '#00aaff',
                fillColor: '#00aaff',
                fillOpacity: 0.15,
                weight: 1,
              }}
            />
            <CircleMarker
              center={[userLocation.lat, userLocation.lng]}
              radius={10}
              pathOptions={{
                color: '#00aaff',
                fillColor: '#00aaff',
                fillOpacity: 0.4,
                weight: 2,
              }}
            />
            <CircleMarker
              center={[userLocation.lat, userLocation.lng]}
              radius={5}
              pathOptions={{
                color: '#fff',
                fillColor: '#00aaff',
                fillOpacity: 1,
                weight: 2,
              }}
            >
              <Popup>
                <div style={{ color: '#0a0e1a', fontSize: '12px' }}>
                  <div style={{ fontWeight: 'bold' }}>📍 我的位置</div>
                  {userLocation.city && (
                    <div style={{ color: '#555' }}>
                      {userLocation.city}
                      {userLocation.district}
                    </div>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          </>
        )}

        {/* 路径规划 polyline */}
        {route && route.points.length > 0 && (
          <Polyline
            positions={route.points}
            pathOptions={{
              color: '#00ff88',
              weight: 5,
              opacity: 0.85,
              lineCap: 'round',
              lineJoin: 'round',
            }}
          />
        )}

        {/* 路径起点 */}
        {route && route.points.length > 0 && userLocation && (
          <Marker
            position={[userLocation.lat, userLocation.lng]}
            icon={startIcon}
          />
        )}

        {/* 路径终点 + 起终点标记（独立于 POI 列表） */}
        {route && route.destination && (
          <Marker
            position={[
              route.points[route.points.length - 1][0],
              route.points[route.points.length - 1][1],
            ]}
            icon={endIcon}
          />
        )}

        {/* 搜索 POI 标记（按 category 区分颜色） */}
        {pois.map((poi, idx) => {
          // 起点/终点用专用图标
          if (poi.category === 'origin') {
            return (
              <Marker key={`poi-${idx}`} position={[poi.lat, poi.lng]} icon={startIcon}>
                <Popup>
                  <div style={{ color: '#0a0e1a', fontSize: '12px' }}>
                    <div style={{ fontWeight: 'bold' }}>起点</div>
                    <div style={{ color: '#555' }}>{poi.name}</div>
                  </div>
                </Popup>
              </Marker>
            )
          }
          if (poi.category === 'destination') {
            return (
              <Marker key={`poi-${idx}`} position={[poi.lat, poi.lng]} icon={endIcon}>
                <Popup>
                  <div style={{ color: '#0a0e1a', fontSize: '12px' }}>
                    <div style={{ fontWeight: 'bold' }}>终点</div>
                    <div style={{ color: '#555' }}>{poi.name}</div>
                  </div>
                </Popup>
              </Marker>
            )
          }
          // 普通 POI
          return (
            <Marker
              key={`poi-${idx}`}
              position={[poi.lat, poi.lng]}
              icon={createNumberedIcon(idx + 1, '#00aaff')}
            >
              <Popup>
                <div style={{ color: '#0a0e1a', fontSize: '12px' }}>
                  <div style={{ fontWeight: 'bold', marginBottom: 4 }}>{poi.name}</div>
                  {poi.address && <div style={{ color: '#555' }}>{poi.address}</div>}
                  {poi.distance !== undefined && (
                    <div style={{ color: '#888', marginTop: 2 }}>距离：{poi.distance}米</div>
                  )}
                </div>
              </Popup>
            </Marker>
          )
        })}

        <FitBounds pois={pois} route={route} userLocation={userLocation} />
      </MapContainer>
    </div>
  )
}
