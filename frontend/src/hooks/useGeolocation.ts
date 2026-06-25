import { useState, useCallback } from 'react'
import { useChatStore } from '../store/chatStore'

export interface LocationError {
  code: number
  message: string
  hint: string
}

const ERROR_MAP: Record<number, { message: string; hint: string }> = {
  1: {
    message: '用户拒绝了定位权限',
    hint: '请点击地址栏左侧🔒图标，重新授予位置权限',
  },
  2: {
    message: '位置不可用',
    hint: '请检查系统位置服务是否开启，或稍后重试',
  },
  3: {
    message: '定位超时',
    hint: 'GPS信号弱或网络不稳定，请到开阔处重试',
  },
}

export function useGeolocation() {
  const setUserLocation = useChatStore((s) => s.setUserLocation)
  const setLocationError = useChatStore((s) => s.setLocationError)
  const setLocationStatus = useChatStore((s) => s.setLocationStatus)
  const [isRequesting, setIsRequesting] = useState(false)

  // 初始定位：先尝试浏览器定位，失败时自动用 IP 定位
  const requestLocation = useCallback(async () => {
    if (!('geolocation' in navigator)) {
      setLocationError('当前浏览器不支持定位 API，正在使用 IP 定位...')
      const ok = await fallbackIPLocation()
      if (!ok) {
        setLocationError('浏览器不支持定位，IP 定位也失败，请手动输入位置')
      }
      return
    }

    setIsRequesting(true)
    setLocationStatus('requesting')
    setLocationError(null)

    try {
      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: false, // 先用低精度，提高成功率
          timeout: 10000,
          maximumAge: 60000,
        })
      })

      const { longitude, latitude, accuracy } = pos.coords
      console.log('[Geo] 浏览器定位成功:', longitude, latitude, accuracy)
      setUserLocation({ lng: longitude, lat: latitude })

      // 上报后端
      try {
        const r = await fetch('/api/vehicle/location', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lng: longitude, lat: latitude, accuracy }),
        })
        const data = await r.json()
        if (data.ok && data.location) {
          setUserLocation(data.location)
        }
      } catch (e) {
        console.warn('[Geo] 上报位置失败:', e)
      }
    } catch (err: any) {
      const code = err?.code ?? 0
      const mapped = ERROR_MAP[code] || {
        message: err?.message || '未知定位错误',
        hint: '请重试或使用其他定位方式',
      }
      console.warn(`[Geo] 浏览器定位失败 (code=${code}): ${mapped.message}，自动降级到 IP 定位...`)

      // ============ 自动降级到 IP 定位 ============
      const ok = await fallbackIPLocation()
      if (ok) {
        setLocationError(
          `浏览器定位失败：${mapped.message}。已自动使用 IP 定位（精度较低，城市级）`,
        )
      } else {
        setLocationError(
          `浏览器定位失败：${mapped.message}（${mapped.hint}）。IP 定位也失败，请点击"手动输入"。`,
        )
      }
    } finally {
      setIsRequesting(false)
    }
  }, [setUserLocation, setLocationError, setLocationStatus])

  return { requestLocation, isRequesting }
}

/** 降级方案：使用后端 IP 定位 */
export async function fallbackIPLocation(): Promise<boolean> {
  try {
    const r = await fetch('/api/vehicle/location-by-ip', { method: 'POST' })
    const data = await r.json()
    if (data.ok && data.location) {
      useChatStore.getState().setUserLocation(data.location)
      return true
    }
    return false
  } catch {
    return false
  }
}
