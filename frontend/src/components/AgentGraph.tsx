import { useMemo, useState, useCallback } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
  type NodeMouseHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useChatStore } from '../store/chatStore'
import type { AgentInfo, AgentTopology } from '../types/events'

// ============ 兜底拓扑数据（API不可用时使用） ============

const fallbackTopology: AgentTopology = {
  nodes: [
    { id: 'orchestrator', name: '主控编排器', type: 'orchestrator', desc: '意图识别与路由分发' },
    { id: 'vehicle_status', name: '车况查询Agent', type: 'sub_agent', desc: '查询电量、续航、里程、胎压、故障码等车辆状态', tools: ['get_vehicle_status', 'get_battery_status', 'get_tire_pressure'], has_rag: false, available: true },
    { id: 'vehicle_control', name: '车控操作Agent', type: 'sub_agent', desc: '控制空调、车窗、天窗、座椅、氛围灯、驾驶模式', tools: ['control_ac', 'control_window', 'control_sunroof', 'set_drive_mode'], has_rag: false, available: true },
    { id: 'navigation', name: '导航服务Agent', type: 'sub_agent', desc: '路线规划、POI搜索、天气查询、常用地址', tools: ['plan_route', 'search_poi', 'get_weather'], has_rag: false, available: true },
    { id: 'diagnosis', name: '故障诊断Agent', type: 'sub_agent', desc: '故障码解读、故障排查建议、紧急处理', tools: ['read_dtc', 'diagnose_fault'], has_rag: true, available: true },
    { id: 'appointment', name: '预约服务Agent', type: 'sub_agent', desc: '保养预约、试驾预约、道路救援、网点查询', tools: ['book_appointment', 'find_dealer', 'request_rescue'], has_rag: false, available: true },
    { id: 'customer_service', name: '售后咨询Agent', type: 'sub_agent', desc: '质保政策、保养周期、车主权益咨询', tools: [], has_rag: true, available: true },
  ],
  edges: [
    { from: 'orchestrator', to: 'vehicle_status' },
    { from: 'orchestrator', to: 'vehicle_control' },
    { from: 'orchestrator', to: 'navigation' },
    { from: 'orchestrator', to: 'diagnosis' },
    { from: 'orchestrator', to: 'appointment' },
    { from: 'orchestrator', to: 'customer_service' },
  ],
}

// ============ 节点布局位置 ============

const NODE_WIDTH = 210
const COL_GAP = 270
const ROW_GAP = 210

const subAgentPositions = [
  { x: 0, y: ROW_GAP },
  { x: COL_GAP, y: ROW_GAP },
  { x: COL_GAP * 2, y: ROW_GAP },
  { x: 0, y: ROW_GAP * 2 },
  { x: COL_GAP, y: ROW_GAP * 2 },
  { x: COL_GAP * 2, y: ROW_GAP * 2 },
]

// ============ 自定义节点数据类型 ============

interface AgentNodeData {
  [key: string]: unknown
  name: string
  desc: string
  type: string
  tools?: string[]
  hasRag?: boolean
  available?: boolean
  isActive: boolean
  isOrchestrator: boolean
  activeToolCalls: number
  isSelected?: boolean
}

// ============ 自定义节点组件 ============

function AgentNodeComponent({ data, selected }: NodeProps) {
  const d = data as unknown as AgentNodeData
  const isOrch = d.isOrchestrator
  const isActive = d.isActive
  const toolCount = d.tools?.length || 0
  const isSelected = selected || d.isSelected

  const nodeClass = isOrch
    ? `relative px-4 py-3 rounded-2xl border-2 transition-all duration-300 cursor-pointer ${
        isActive
          ? 'border-neon-green bg-bg-card animate-pulse-green'
          : isSelected
            ? 'border-neon-blue bg-bg-card shadow-lg shadow-neon-blue/30'
            : 'border-neon-blue/50 bg-bg-card shadow-lg shadow-neon-blue/20 hover:border-neon-blue'
      }`
    : `relative px-3.5 py-3 rounded-xl border transition-all duration-300 cursor-pointer ${
        isActive
          ? 'border-neon-green bg-bg-card animate-pulse-green'
          : isSelected
            ? 'border-neon-blue/60 bg-bg-card shadow-lg shadow-neon-blue/20'
            : 'border-white/10 bg-bg-card hover:border-white/30 hover:bg-bg-card-hover'
      }`

  const width = isOrch ? NODE_WIDTH + 30 : NODE_WIDTH

  return (
    <div className={nodeClass} style={{ width }}>
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-neon-blue/60 !border-none"
      />

      {/* 活跃工具调用徽标 */}
      {d.activeToolCalls > 0 && (
        <div className="absolute -top-2 -right-2 w-5 h-5 rounded-full bg-neon-green flex items-center justify-center animate-pulse">
          <span className="text-[10px] font-bold text-bg-base">{d.activeToolCalls}</span>
        </div>
      )}

      {/* 节点头部 */}
      <div className="flex items-center gap-2 mb-1.5">
        <div
          className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
            isOrch
              ? 'bg-neon-blue/20 border border-neon-blue/40'
              : isActive
                ? 'bg-neon-green/20 border border-neon-green/40'
                : 'bg-white/5 border border-white/10'
          }`}
        >
          {isOrch ? (
            <svg className="w-4 h-4 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1m15.5-7.5l-4.2 4.2m-4.6 4.6l-4.2 4.2m12.4 0l-4.2-4.2m-4.6-4.6L3.5 4.5" />
            </svg>
          ) : (
            <svg className={`w-4 h-4 ${isActive ? 'text-neon-green' : 'text-gray-400'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className={`text-sm font-semibold truncate ${isActive ? 'text-neon-green' : isOrch ? 'text-neon-blue' : 'text-gray-200'}`}>
              {d.name}
            </span>
            {d.hasRag && (
              <span className="text-[9px] px-1 py-0.5 rounded bg-neon-purple/20 text-neon-purple border border-neon-purple/30 font-mono shrink-0">
                RAG
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 描述 */}
      <p className="text-[11px] text-gray-400 leading-snug mb-1.5 line-clamp-2">{d.desc}</p>

      {/* 工具数量 */}
      {!isOrch && (
        <div className="flex items-center gap-1 text-[10px] text-gray-500">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
          </svg>
          <span>工具: {toolCount}</span>
          {d.available === false && <span className="text-neon-red">· 不可用</span>}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-neon-blue/60 !border-none"
      />
    </div>
  )
}

const nodeTypes = { agent: AgentNodeComponent }

// ============ 节点详情面板 ============

function NodeDetailPanel({ node, onClose }: { node: AgentInfo | null; onClose: () => void }) {
  if (!node) return null

  return (
    <div className="absolute top-3 right-3 w-64 max-h-[80%] overflow-y-auto rounded-xl bg-bg-card/95 border border-neon-blue/30 backdrop-blur-md shadow-xl shadow-neon-blue/10 animate-fade-in z-10">
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-white/10">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${node.type === 'orchestrator' ? 'bg-neon-blue' : 'bg-neon-green'}`} />
          <span className="text-sm font-semibold text-white">{node.name}</span>
        </div>
        <button
          onClick={onClose}
          className="w-5 h-5 rounded flex items-center justify-center text-gray-500 hover:text-white hover:bg-white/10 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      <div className="px-3 py-2.5 space-y-2.5">
        {/* 描述 */}
        <div>
          <div className="text-[10px] text-gray-500 mb-1">描述</div>
          <p className="text-[11px] text-gray-300 leading-relaxed">{node.desc}</p>
        </div>

        {/* 类型 */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-gray-500">类型:</span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
            node.type === 'orchestrator'
              ? 'bg-neon-blue/20 text-neon-blue border border-neon-blue/30'
              : 'bg-neon-green/20 text-neon-green border border-neon-green/30'
          }`}>
            {node.type === 'orchestrator' ? '主控' : '子Agent'}
          </span>
          {node.has_rag && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-purple/20 text-neon-purple border border-neon-purple/30 font-mono">
              RAG
            </span>
          )}
          {node.available === false && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-neon-red/20 text-neon-red border border-neon-red/30 font-mono">
              不可用
            </span>
          )}
        </div>

        {/* 工具列表 */}
        {node.tools && node.tools.length > 0 && (
          <div>
            <div className="text-[10px] text-gray-500 mb-1.5">可用工具 ({node.tools.length})</div>
            <div className="space-y-1">
              {node.tools.map((tool, i) => (
                <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-base/50 border border-white/5">
                  <svg className="w-2.5 h-2.5 text-neon-blue/60 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                  </svg>
                  <span className="text-[10px] text-gray-300 font-mono truncate">{tool}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 无工具提示 */}
        {(!node.tools || node.tools.length === 0) && node.type !== 'orchestrator' && (
          <div className="text-[10px] text-gray-500 italic">该Agent主要通过RAG知识库回答</div>
        )}
      </div>
    </div>
  )
}

// ============ 拓扑转换函数 ============

function buildNodes(
  topology: AgentTopology,
  activeAgent: string | null,
  toolCallCounts: Record<string, number>,
  selectedNodeId: string | null,
): Node[] {
  const orchestrator = topology.nodes.find((n) => n.type === 'orchestrator')
  const subAgents = topology.nodes.filter((n) => n.type !== 'orchestrator')
  const nodes: Node[] = []

  if (orchestrator) {
    nodes.push({
      id: orchestrator.id,
      type: 'agent',
      position: { x: COL_GAP, y: 0 },
      data: {
        name: orchestrator.name,
        desc: orchestrator.desc,
        type: orchestrator.type,
        tools: orchestrator.tools,
        hasRag: orchestrator.has_rag,
        available: orchestrator.available,
        isActive: activeAgent === orchestrator.id,
        isOrchestrator: true,
        activeToolCalls: toolCallCounts[orchestrator.id] || 0,
        isSelected: selectedNodeId === orchestrator.id,
      } as AgentNodeData,
      selected: selectedNodeId === orchestrator.id,
    })
  }

  subAgents.forEach((agent: AgentInfo, index: number) => {
    const pos = subAgentPositions[index] || { x: 0, y: ROW_GAP }
    nodes.push({
      id: agent.id,
      type: 'agent',
      position: pos,
      data: {
        name: agent.name,
        desc: agent.desc,
        type: agent.type,
        tools: agent.tools,
        hasRag: agent.has_rag,
        available: agent.available,
        isActive: activeAgent === agent.id,
        isOrchestrator: false,
        activeToolCalls: toolCallCounts[agent.id] || 0,
        isSelected: selectedNodeId === agent.id,
      } as AgentNodeData,
      selected: selectedNodeId === agent.id,
    })
  })

  return nodes
}

function buildEdges(topology: AgentTopology, activeAgent: string | null): Edge[] {
  return topology.edges.map((edge) => {
    const isActive = activeAgent === edge.to
    return {
      id: `${edge.from}-${edge.to}`,
      source: edge.from,
      target: edge.to,
      type: 'smoothstep',
      animated: isActive,
      style: {
        stroke: isActive ? '#00ff88' : '#3b4252',
        strokeWidth: isActive ? 2.5 : 1.5,
      },
    }
  })
}

// ============ 主组件 ============

export default function AgentGraph() {
  const topology = useChatStore((s) => s.agentTopology)
  const activeAgent = useChatStore((s) => s.activeAgent)
  const toolRecords = useChatStore((s) => s.toolRecords)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const effectiveTopology = topology || fallbackTopology

  const toolCallCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    toolRecords.forEach((r) => {
      if (r.status === 'loading') {
        counts[r.agent] = (counts[r.agent] || 0) + 1
      }
    })
    return counts
  }, [toolRecords])

  const nodes = useMemo(
    () => buildNodes(effectiveTopology, activeAgent, toolCallCounts, selectedNodeId),
    [effectiveTopology, activeAgent, toolCallCounts, selectedNodeId],
  )

  const edges = useMemo(
    () => buildEdges(effectiveTopology, activeAgent),
    [effectiveTopology, activeAgent],
  )

  const onNodeClick: NodeMouseHandler = useCallback((_, node) => {
    setSelectedNodeId((prev) => (prev === node.id ? null : node.id))
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNodeId(null)
  }, [])

  // 选中的节点详情
  const selectedNode = selectedNodeId
    ? effectiveTopology.nodes.find((n) => n.id === selectedNodeId) || null
    : null

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        panOnDrag
        zoomOnScroll
        minZoom={0.4}
        maxZoom={1.5}
      >
        <Background color="#1a1f2e" gap={20} size={1} />
        <Controls
          className="!bg-bg-card/80 !border-white/10 !rounded-lg !backdrop-blur-sm"
          showInteractive={false}
        />
      </ReactFlow>

      {/* 节点详情面板 */}
      <NodeDetailPanel node={selectedNode} onClose={() => setSelectedNodeId(null)} />

      {/* 活跃Agent提示 */}
      {activeAgent && (
        <div className="absolute top-3 left-3 px-3 py-1.5 rounded-lg bg-neon-green/10 border border-neon-green/30 backdrop-blur-sm animate-fade-in">
          <span className="text-xs text-neon-green flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse" />
            当前路由: {activeAgent}
          </span>
        </div>
      )}

      {/* 操作提示 */}
      {!selectedNodeId && !activeAgent && (
        <div className="absolute bottom-3 left-3 px-2.5 py-1 rounded-lg bg-bg-card/60 border border-white/5 backdrop-blur-sm">
          <span className="text-[10px] text-gray-500">点击节点查看详情</span>
        </div>
      )}
    </div>
  )
}
