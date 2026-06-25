import { useCallback, useEffect, useRef, useState } from 'react'
import { useChatStore } from '../store/chatStore'
import { useVoiceInput, useSpeechSynthesis } from '../hooks/useVoice'

/** 电话模式阶段 */
type PhonePhase = 'listening' | 'processing' | 'speaking'

interface PhoneCallModeProps {
  /** 挂断回调 */
  onHangup: () => void
}

/**
 * 电话对话模式全屏组件。
 * - 自动开启语音识别，识别完成后自动发送
 * - AI 回复完成后自动语音播报
 * - 播报完成后自动重新开始语音识别（连续对话）
 * - 点击"挂断"按钮退出
 */
export default function PhoneCallMode({ onHangup }: PhoneCallModeProps) {
  const sendMessage = useChatStore((s) => s.sendMessage)
  const messages = useChatStore((s) => s.messages)
  const lastCompletedMessageId = useChatStore((s) => s.lastCompletedMessageId)
  const isThinking = useChatStore((s) => s.isThinking)

  const [phase, setPhase] = useState<PhonePhase>('listening')
  const [recognizedText, setRecognizedText] = useState('')
  const [aiText, setAiText] = useState('')
  const phaseRef = useRef<PhonePhase>('listening')
  // 防止同一条完成消息重复触发播报
  const spokenMessageIdRef = useRef<string | null>(null)
  // 标记是否已对本次识别发送过消息
  const sentRef = useRef(false)

  const { speak, cancel: cancelSpeak, supported: ttsSupported } = useSpeechSynthesis()

  const setPhaseSafe = (p: PhonePhase) => {
    phaseRef.current = p
    setPhase(p)
  }

  // 语音识别：识别完成后自动发送
  const { supported: asrSupported, listening, start, stop, reset } = useVoiceInput({
    lang: 'zh-CN',
    continuous: false,
    interimResults: true,
    onFinalResult: (text) => {
      // 仅在 listening 阶段处理，避免重复发送
      if (phaseRef.current !== 'listening') return
      if (sentRef.current) return
      const trimmed = text.trim()
      if (!trimmed) return
      sentRef.current = true
      setRecognizedText(trimmed)
      stop()
      setPhaseSafe('processing')
      sendMessage(trimmed)
    },
  })

  // 组件挂载：自动开始语音识别
  useEffect(() => {
    sentRef.current = false
    setPhaseSafe('listening')
    // 稍延迟启动，避免组件动画干扰
    const timer = setTimeout(() => {
      reset()
      start()
    }, 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 监听 AI 回复完成，触发语音播报
  useEffect(() => {
    if (!lastCompletedMessageId) return
    if (phaseRef.current !== 'processing') return
    if (spokenMessageIdRef.current === lastCompletedMessageId) return

    const msg = messages.find((m) => m.id === lastCompletedMessageId)
    if (!msg) return

    spokenMessageIdRef.current = lastCompletedMessageId
    const text = msg.content || ''
    setAiText(text)
    setPhaseSafe('speaking')
    stop()

    if (ttsSupported && text.trim()) {
      speak(text, () => {
        // 播报完成，重新开始语音识别
        if (phaseRef.current !== 'speaking') return
        sentRef.current = false
        setRecognizedText('')
        setAiText('')
        setPhaseSafe('listening')
        reset()
        start()
      })
    } else {
      // 不支持 TTS，直接进入下一轮识别
      sentRef.current = false
      setRecognizedText('')
      setAiText('')
      setPhaseSafe('listening')
      reset()
      start()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastCompletedMessageId])

  // 挂断处理
  const handleHangup = useCallback(() => {
    stop()
    cancelSpeak()
    onHangup()
  }, [stop, cancelSpeak, onHangup])

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      stop()
      cancelSpeak()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const phaseLabel =
    phase === 'listening'
      ? listening
        ? '正在聆听...'
        : '准备中...'
      : phase === 'processing'
        ? isThinking
          ? '小智思考中...'
          : '处理中...'
        : '小智回复中...'

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-between bg-bg-base/95 backdrop-blur-2xl animate-fade-in py-12 px-6">
      {/* 顶部：状态信息 */}
      <div className="flex flex-col items-center gap-2">
        <div className="text-xs text-gray-500 font-mono">电话对话模式 · 免提</div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-neon-green animate-pulse" />
          <span className="text-xs text-neon-green">通话中</span>
        </div>
      </div>

      {/* 中部：头像 + 波纹动画 */}
      <div className="flex flex-col items-center gap-6">
        <div className="relative w-40 h-40 flex items-center justify-center">
          {/* 波纹动画层 */}
          {phase === 'listening' && listening && (
            <>
              <span className="absolute inset-0 rounded-full bg-neon-blue/20 animate-ripple" />
              <span
                className="absolute inset-0 rounded-full bg-neon-blue/20 animate-ripple"
                style={{ animationDelay: '0.6s' }}
              />
              <span
                className="absolute inset-0 rounded-full bg-neon-blue/20 animate-ripple"
                style={{ animationDelay: '1.2s' }}
              />
            </>
          )}
          {phase === 'speaking' && (
            <>
              <span className="absolute inset-0 rounded-full bg-neon-green/20 animate-ripple" />
              <span
                className="absolute inset-0 rounded-full bg-neon-green/20 animate-ripple"
                style={{ animationDelay: '0.6s' }}
              />
              <span
                className="absolute inset-0 rounded-full bg-neon-green/20 animate-ripple"
                style={{ animationDelay: '1.2s' }}
              />
            </>
          )}
          {phase === 'processing' && (
            <span className="absolute inset-0 rounded-full bg-neon-yellow/15 animate-pulse" />
          )}

          {/* 头像主体 */}
          <div
            className={`relative w-28 h-28 rounded-full flex items-center justify-center border-2 transition-all ${
              phase === 'listening'
                ? 'border-neon-blue/60 bg-gradient-to-br from-neon-blue/30 to-neon-blue/10 shadow-lg shadow-neon-blue/30'
                : phase === 'speaking'
                  ? 'border-neon-green/60 bg-gradient-to-br from-neon-green/30 to-neon-green/10 shadow-lg shadow-neon-green/30'
                  : 'border-neon-yellow/50 bg-gradient-to-br from-neon-yellow/20 to-neon-orange/10 shadow-lg shadow-neon-yellow/20'
            }`}
          >
            <svg
              className={`w-14 h-14 ${
                phase === 'listening'
                  ? 'text-neon-blue'
                  : phase === 'speaking'
                    ? 'text-neon-green'
                    : 'text-neon-yellow'
              }`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2" />
              <circle cx="7" cy="17" r="2" />
              <circle cx="17" cy="17" r="2" />
            </svg>
          </div>
        </div>

        {/* 阶段标签 */}
        <div className="text-center">
          <div className="text-white font-semibold text-lg">小智</div>
          <div
            className={`text-sm mt-1 ${
              phase === 'listening'
                ? 'text-neon-blue'
                : phase === 'speaking'
                  ? 'text-neon-green'
                  : 'text-neon-yellow'
            }`}
          >
            {phaseLabel}
          </div>
        </div>

        {/* 实时识别/回复文本 */}
        <div className="w-full max-w-md min-h-[80px] rounded-2xl bg-bg-card/60 border border-white/10 p-4">
          {phase === 'listening' && (
            <div>
              <div className="text-[10px] text-gray-500 mb-1.5 flex items-center gap-1">
                <svg className="w-3 h-3 text-neon-blue" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                </svg>
                您说：
              </div>
              <p className="text-sm text-gray-200 leading-relaxed">
                {recognizedText || '请说话...'}
                {listening && (
                  <span className="inline-block w-[2px] h-4 bg-neon-blue ml-0.5 animate-blink align-middle rounded-full" />
                )}
              </p>
            </div>
          )}
          {phase === 'processing' && (
            <div>
              <div className="text-[10px] text-gray-500 mb-1.5">已发送：</div>
              <p className="text-sm text-gray-300 leading-relaxed mb-2">{recognizedText}</p>
              <div className="flex items-center gap-1.5 text-neon-yellow">
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-neon-yellow rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-neon-yellow rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-neon-yellow rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
                <span className="text-xs">小智正在处理...</span>
              </div>
            </div>
          )}
          {phase === 'speaking' && (
            <div>
              <div className="text-[10px] text-neon-green/70 mb-1.5 flex items-center gap-1">
                <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" />
                </svg>
                小智回复：
              </div>
              <p className="text-sm text-gray-100 leading-relaxed whitespace-pre-wrap break-words">
                {aiText}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 底部：挂断按钮 + 提示 */}
      <div className="flex flex-col items-center gap-3">
        {!asrSupported && (
          <p className="text-xs text-neon-red/80">当前浏览器不支持语音识别</p>
        )}
        {!ttsSupported && (
          <p className="text-xs text-neon-yellow/80">当前浏览器不支持语音播报</p>
        )}
        <button
          onClick={handleHangup}
          className="w-16 h-16 rounded-full bg-gradient-to-br from-neon-red to-neon-red/70 flex items-center justify-center shadow-lg shadow-neon-red/40 hover:scale-105 active:scale-95 transition-transform"
          title="挂断"
        >
          <svg className="w-7 h-7 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7 2 2 0 0 1 1.72 2v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91" />
            <line x1="23" y1="1" x2="1" y2="23" />
          </svg>
        </button>
        <span className="text-xs text-gray-500">挂断</span>
      </div>
    </div>
  )
}
