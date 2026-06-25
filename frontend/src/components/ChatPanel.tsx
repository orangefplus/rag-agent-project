import { useState, useRef, useEffect, useCallback } from 'react'
import { useChatStore } from '../store/chatStore'
import { useSpeechSynthesis } from '../hooks/useVoice'
import MessageBubble from './MessageBubble'
import VoiceInput from './VoiceInput'

export default function ChatPanel() {
  const [input, setInput] = useState('')
  const messages = useChatStore((s) => s.messages)
  const isThinking = useChatStore((s) => s.isThinking)
  const thinkingContent = useChatStore((s) => s.thinkingContent)
  const connectionStatus = useChatStore((s) => s.connectionStatus)
  const sendMessage = useChatStore((s) => s.sendMessage)
  const speechSynthesisEnabled = useChatStore((s) => s.speechSynthesisEnabled)
  const toggleSpeechSynthesis = useChatStore((s) => s.toggleSpeechSynthesis)
  const phoneModeActive = useChatStore((s) => s.phoneModeActive)
  const setPhoneMode = useChatStore((s) => s.setPhoneMode)
  const lastCompletedMessageId = useChatStore((s) => s.lastCompletedMessageId)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const { speak } = useSpeechSynthesis()
  // 记录已播报过的消息ID，避免重复
  const spokenIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isThinking])

  // 监听 AI 回复完成，按需语音播报
  useEffect(() => {
    if (!lastCompletedMessageId) return
    if (!speechSynthesisEnabled) return
    if (spokenIdsRef.current.has(lastCompletedMessageId)) return
    const msg = messages.find((m) => m.id === lastCompletedMessageId)
    if (!msg || msg.role !== 'assistant') return
    spokenIdsRef.current.add(lastCompletedMessageId)
    const text = msg.content?.trim()
    if (text) {
      speak(text)
    }
  }, [lastCompletedMessageId, speechSynthesisEnabled, messages, speak])

  const handleSend = useCallback(() => {
    const content = input.trim()
    if (!content) return
    sendMessage(content)
    setInput('')
  }, [input, sendMessage])

  const handleNewChat = useCallback(() => {
    if (window.confirm('确定开启新对话？当前对话历史将被清空。')) {
      useChatStore.getState().clearMessages()
    }
  }, [])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // 语音识别结果实时回填输入框
  const handleTranscript = useCallback((text: string) => {
    setInput(text)
  }, [])

  // 语音识别最终结果：直接发送
  const handleFinalResult = useCallback(
    (text: string) => {
      const content = text.trim()
      if (!content) return
      sendMessage(content)
      setInput('')
    },
    [sendMessage],
  )

  const statusColor =
    connectionStatus === 'connected'
      ? 'bg-neon-green'
      : connectionStatus === 'connecting'
        ? 'bg-neon-yellow'
        : 'bg-gray-500'

  const statusText =
    connectionStatus === 'connected'
      ? '在线'
      : connectionStatus === 'connecting'
        ? '连接中...'
        : '离线'

  return (
    <div className="flex flex-col h-full bg-bg-card/40 backdrop-blur-xl border-r border-white/5">
      {/* 标题栏 */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-white/5 bg-bg-base/30">
        <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-neon-blue/30 to-neon-green/20 flex items-center justify-center border border-neon-blue/30 shadow-lg shadow-neon-blue/10">
          <svg className="w-6 h-6 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
            <circle cx="7" cy="17" r="2" />
            <path d="M9 17h6" />
            <circle cx="17" cy="17" r="2" />
          </svg>
        </div>
        <div className="flex-1">
          <h1 className="text-white font-semibold text-lg leading-tight">车载智能客服 · 小智</h1>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`w-1.5 h-1.5 rounded-full ${statusColor} ${connectionStatus === 'connected' ? 'animate-pulse' : ''}`} />
            <span className="text-xs text-gray-400">{statusText}</span>
          </div>
        </div>

        {/* 语音播报开关 */}
        <button
          onClick={toggleSpeechSynthesis}
          title={speechSynthesisEnabled ? '关闭语音播报' : '开启语音播报'}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-all ${
            speechSynthesisEnabled
              ? 'bg-neon-green/15 border-neon-green/40 text-neon-green'
              : 'bg-white/5 border-white/10 text-gray-500 hover:text-gray-300'
          }`}
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
          </svg>
          <span className="text-[10px] font-medium">播报</span>
        </button>

        {/* 电话对话模式按钮 */}
        <button
          onClick={() => setPhoneMode(true)}
          title="电话对话模式"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border bg-white/5 border-white/10 text-gray-400 hover:text-neon-blue hover:border-neon-blue/40 hover:bg-neon-blue/10 transition-all"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91" />
          </svg>
          <span className="text-[10px] font-medium">电话</span>
        </button>

        {/* 新对话按钮 */}
        <button
          onClick={handleNewChat}
          title="开启新对话（清空当前历史）"
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border bg-white/5 border-white/10 text-gray-400 hover:text-neon-green hover:border-neon-green/40 hover:bg-neon-green/10 transition-all"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
          <span className="text-[10px] font-medium">新对话</span>
        </button>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 custom-scroll">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-neon-blue/20 to-neon-green/10 flex items-center justify-center mb-4 border border-neon-blue/20 animate-float">
              <svg className="w-8 h-8 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
                <circle cx="7" cy="17" r="2" />
                <circle cx="17" cy="17" r="2" />
              </svg>
            </div>
            <p className="text-gray-300 text-sm font-medium">您好！我是小智，您的车载智能客服</p>
            <p className="text-gray-500 text-xs mt-2 leading-relaxed">
              可以问我车辆状态、空调控制、导航路线、<br />故障诊断、保养预约等问题
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* 思考状态指示器 */}
        {isThinking && (
          <div className="flex justify-start animate-fade-in">
            <div className="bg-bg-card-hover/80 border border-neon-blue/20 rounded-2xl rounded-tl-sm px-4 py-3 backdrop-blur-sm">
              <div className="flex items-center gap-2.5">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-neon-blue rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-neon-blue rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-neon-blue rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs text-gray-400">{thinkingContent || '小智正在思考...'}</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入框 */}
      <div className="px-4 py-3 border-t border-white/5 bg-bg-base/30">
        <div className="flex items-center gap-2 bg-bg-base/60 border border-white/10 rounded-xl px-3 py-2 focus-within:border-neon-blue/40 focus-within:shadow-lg focus-within:shadow-neon-blue/10 transition-all">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={phoneModeActive ? '电话模式中，已禁用手动输入' : '输入您的问题...'}
            disabled={phoneModeActive}
            className="flex-1 bg-transparent text-white text-sm placeholder-gray-500 outline-none disabled:opacity-40"
          />
          {/* 语音输入麦克风按钮 */}
          <VoiceInput
            onTranscript={handleTranscript}
            onFinalResult={handleFinalResult}
            size="md"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || phoneModeActive}
            className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-blue to-neon-blue/60 flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed hover:shadow-lg hover:shadow-neon-blue/30 transition-all shrink-0"
          >
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
        <p className="text-[10px] text-gray-600 mt-1.5 text-center">
          回车发送 · Shift+回车换行 · 点击麦克风语音输入
        </p>
      </div>
    </div>
  )
}
