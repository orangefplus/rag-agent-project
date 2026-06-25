// 解析高德 API 返回的 POI 文本
// 支持格式：
//   "1. 名称 - 地址 (坐标: 116.3141,39.9854)"
//   "1. **特来电** - 地址 (坐标: 116.3141,39.9854)"
//   "终点坐标：116.3141,39.9854"
export interface ParsedPOI {
  name: string
  address: string
  lng: number
  lat: number
}

export interface ParsedRoute {
  origin?: { lng: number; lat: number; name?: string }
  destination?: { lng: number; lat: number; name?: string }
  polyline: [number, number][] // [[lat, lng], ...]
  distance?: number
  duration?: number
}

export function parseAmapPOIs(text: string): ParsedPOI[] {
  if (!text) return []
  const pois: ParsedPOI[] = []
  const seen = new Set<string>()

  // 格式1: "1. 名称 - 地址 (坐标: lng,lat)"
  const re1 = /(\d+)\.\s+\*?\*?(.+?)\*?\*?\s+-\s+(.+?)\s*[（(]坐标[:\s]*([\d.]+)[,，]\s*([\d.]+)[)）]/g
  let m: RegExpExecArray | null
  while ((m = re1.exec(text)) !== null) {
    const key = `${m[4]},${m[5]}`
    if (seen.has(key)) continue
    seen.add(key)
    pois.push({
      name: m[2].trim(),
      address: m[3].trim(),
      lng: parseFloat(m[4]),
      lat: parseFloat(m[5]),
    })
  }

  // 格式2: 兜底 "（坐标：lng,lat）" 不带编号
  if (pois.length === 0) {
    const re2 = /(.+?)\s*[（(]坐标[:\s]*([\d.]+)[,，]\s*([\d.]+)[)）]/g
    while ((m = re2.exec(text)) !== null) {
      const key = `${m[2]},${m[3]}`
      if (seen.has(key)) continue
      seen.add(key)
      const name = m[1].replace(/^[\d\.\s\*]+/, '').replace(/\*+$/, '').trim()
      pois.push({
        name: name || '位置',
        address: '',
        lng: parseFloat(m[2]),
        lat: parseFloat(m[3]),
      })
    }
  }

  // 格式3: 兜底 "终点坐标：lng,lat"
  if (pois.length === 0) {
    const re3 = /终点坐标[：:]\s*([\d.]+)[,，]\s*([\d.]+)/
    m = re3.exec(text)
    if (m) {
      const key = `${m[1]},${m[2]}`
      if (!seen.has(key)) {
        pois.push({
          name: '终点',
          address: '',
          lng: parseFloat(m[1]),
          lat: parseFloat(m[2]),
        })
      }
    }
  }

  return pois
}

/**
 * 解析高德 path 工具结果中的路线信息
 * @param text 工具返回文本（含 "起点坐标："、"终点坐标："、"路线坐标："）
 */
export function parseAmapRoute(text: string): ParsedRoute | null {
  if (!text) return null

  // 起点坐标：116.3076,39.9847
  const oMatch = text.match(/起点坐标[：:]\s*([\d.]+)[,，]\s*([\d.]+)/)
  // 终点坐标：116.3151,39.9828
  const dMatch = text.match(/终点坐标[：:]\s*([\d.]+)[,，]\s*([\d.]+)/)
  // 路线坐标：lng,lat;lng,lat;...
  const pMatch = text.match(/路线坐标[：:]\s*([\d.,;\s]+)/)
  // 距离：12.5公里（12500米）
  const distMatch = text.match(/距离[：:]\s*([\d.]+)\s*公里[（(]?(\d+)?[米)）]?/)
  // 耗时：1小时30分钟
  const durMatch = text.match(/耗时[：:]\s*(\d+)小时(\d+)分钟/)

  if (!oMatch && !dMatch && !pMatch) return null

  const polyline: [number, number][] = []
  if (pMatch) {
    for (const coord of pMatch[1].split(';')) {
      const parts = coord.trim().split(',')
      if (parts.length === 2) {
        const lng = parseFloat(parts[0])
        const lat = parseFloat(parts[1])
        if (!isNaN(lng) && !isNaN(lat)) {
          polyline.push([lat, lng]) // Leaflet 用 [lat, lng]
        }
      }
    }
  }

  // 起点名称
  const oNameMatch = text.match(/起点[：:]\s*([^\n]+)/)
  const dNameMatch = text.match(/终点[：:]\s*([^\n]+)/)

  return {
    origin: oMatch ? {
      lng: parseFloat(oMatch[1]),
      lat: parseFloat(oMatch[2]),
      name: oNameMatch?.[1]?.trim(),
    } : undefined,
    destination: dMatch ? {
      lng: parseFloat(dMatch[1]),
      lat: parseFloat(dMatch[2]),
      name: dNameMatch?.[1]?.trim(),
    } : undefined,
    polyline,
    distance: distMatch ? Math.round(parseFloat(distMatch[1]) * 1000) : undefined,
    duration: durMatch ? parseInt(durMatch[1]) * 3600 + parseInt(durMatch[2]) * 60 : undefined,
  }
}

/**
 * 解析 get_common_addresses 工具返回的常用地址列表
 * 支持格式：
 *   "1. 家: 北京市海淀区中关村大街1号"     (英文冒号+空格)
 *   "1. 家：北京市海淀区中关村大街1号"     (全角冒号无空格)
 *   "1. 家 - 北京市海淀区中关村大街1号"    (横线+空格)
 *   "1. 家  北京市海淀区中关村大街1号"     (多空格)
 *   "1. 家—北京市海淀区中关村大街1号"     (破折号)
 */
export function parseCommonAddresses(text: string): Array<{ name: string; address: string }> {
  if (!text) return []
  const results: Array<{ name: string; address: string }> = []
  // 编号. 名称（不含冒号/横线/换行） + 可选空白 + 分隔符(:：-—之一) + 可选空白 + 地址
  const re = /(\d+)\.\s*([^\n:：\-—]+?)\s*[:：\-—]\s*([^\n]+)/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    const name = m[2].trim()
    const address = m[3].trim()
    // 过滤：避免误匹配正文，地址至少要含中文，长度合理
    if (name.length > 0 && name.length < 20 && address.length > 4 && /[\u4e00-\u9fa5]/.test(address)) {
      results.push({ name, address })
    }
  }
  return results
}

