import { useState } from 'react'
import { useChatStore } from '../store/chatStore'
import type { ToolRecord } from '../types/events'

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

function formatTime(ts: number): string {
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

function ToolRecordItem({ record }: { record: ToolRecord }) {
  const [expanded, setExpanded] = useState(false)
  const isLoading = record.status === 'loading'

  return (
    <div
      className={`rounded-lg border transition-all animate-slide-up ${
        isLoading
          ? 'border-neon-blue/30 bg-neon-blue/5'
          : 'border-white/10 bg-bg-card-hover/50'
      }`}
    >
      {/* 头部 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left"
      >
        {/* 状态图标 */}
        <div className="shrink-0">
          {isLoading ? (
            <div className="w-4 h-4 rounded-full border-2 border-neon-blue/30 border-t-neon-blue animate-spin-slow" />
          ) : (
            <svg className="w-4 h-4 text-neon-green" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          )}
        </div>

        {/* 工具名 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-mono font-medium text-neon-blue truncate">
              {record.tool}
            </span>
            <span className="text-[10px] text-gray-500 shrink-0">
              {agentNames[record.agent] || record.agent}
            </span>
          </div>
        </div>

        {/* 时间 */}
        <span className="text-[10px] text-gray-600 font-mono shrink-0">
          {formatTime(record.timestamp)}
        </span>

        {/* 展开图标 */}
        <svg
          className={`w-3.5 h-3.5 text-gray-500 transition-transform shrink-0 ${expanded ? 'rotate-180' : ''}`}
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

      {/* 展开内容 */}
      {expanded && (
        <div className="px-3 pb-2.5 space-y-2 animate-fade-in">
          {/* 参数 */}
          <div>
            <div className="text-[10px] text-gray-500 mb-0.5 flex items-center gap-1">
              <span>参数</span>
              {record.actualArgs && Object.keys(record.actualArgs).length > 0 && Object.keys(record.args).length === 0 && (
                <span className="text-[9px] text-neon-green">(已从查询推断)</span>
              )}
            </div>
            <pre className="text-[11px] text-gray-300 bg-bg-base/60 rounded p-2 overflow-x-auto font-mono leading-relaxed">
              {record.actualArgs && Object.keys(record.actualArgs).length > 0
                ? JSON.stringify(record.actualArgs, null, 2)
                : Object.keys(record.args).length > 0
                  ? JSON.stringify(record.args, null, 2)
                  : '{}'}
            </pre>
          </div>

          {/* 结果 */}
          <div>
            <div className="text-[10px] text-gray-500 mb-0.5">结果</div>
            {isLoading ? (
              <div className="text-[11px] text-neon-blue/70 bg-bg-base/60 rounded p-2 flex items-center gap-1.5">
                <span className="w-1 h-1 rounded-full bg-neon-blue animate-pulse" />
                <span>执行中...</span>
              </div>
            ) : (
              <pre className="text-[11px] text-neon-green/90 bg-bg-base/60 rounded p-2 overflow-x-auto font-mono leading-relaxed whitespace-pre-wrap break-all">
                {record.result}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ToolTimeline() {
  const toolRecords = useChatStore((s) => s.toolRecords)

  return (
    <div className="flex flex-col h-full">
      {/* 标题 */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
          <h3 className="text-sm font-semibold text-gray-200">工具调用时间线</h3>
        </div>
        <span className="text-[10px] text-gray-500 px-2 py-0.5 rounded-full bg-white/5">
          {toolRecords.length} 次调用
        </span>
      </div>

      {/* 时间线列表 */}
      <div className="flex-1 overflow-y-auto px-3 py-2.5 space-y-2 custom-scroll">
        {toolRecords.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-600 py-8">
            <svg className="w-10 h-10 mb-2 opacity-40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            <p className="text-xs">暂无工具调用记录</p>
          </div>
        ) : (
          toolRecords
            .slice()
            .reverse()
            .map((record) => <ToolRecordItem key={record.id} record={record} />)
        )}
      </div>
    </div>
  )
}
