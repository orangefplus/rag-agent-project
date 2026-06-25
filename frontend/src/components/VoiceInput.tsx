import { useEffect } from 'react'
import { useVoiceInput } from '../hooks/useVoice'

interface VoiceInputProps {
  /** 识别结果实时回填到输入框的回调 */
  onTranscript: (text: string) => void
  /** 最终识别结果回调（一句话说完） */
  onFinalResult?: (text: string) => void
  /** 按钮尺寸 */
  size?: 'sm' | 'md'
}

/**
 * 语音输入麦克风按钮组件。
 * 点击开始识别，再次点击停止。识别中显示红色脉冲动画。
 * 识别结果实时通过 onTranscript 回填到输入框。
 */
export default function VoiceInput({
  onTranscript,
  onFinalResult,
  size = 'md',
}: VoiceInputProps) {
  const { supported, listening, transcript, start, stop, reset } = useVoiceInput({
    lang: 'zh-CN',
    continuous: false,
    interimResults: true,
    onFinalResult,
  })

  // 实时把识别文本回填给父组件
  useEffect(() => {
    if (transcript) {
      onTranscript(transcript)
    }
  }, [transcript, onTranscript])

  const handleClick = () => {
    if (listening) {
      stop()
      reset()
    } else {
      reset()
      start()
    }
  }

  if (!supported) {
    return (
      <button
        disabled
        title="当前浏览器不支持语音识别"
        className={`${
          size === 'sm' ? 'w-7 h-7' : 'w-8 h-8'
        } rounded-lg bg-white/5 flex items-center justify-center text-gray-600 cursor-not-allowed shrink-0`}
      >
        <svg className={size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
          <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
          <line x1="12" y1="19" x2="12" y2="23" />
          <line x1="8" y1="23" x2="16" y2="23" />
        </svg>
      </button>
    )
  }

  return (
    <button
      onClick={handleClick}
      title={listening ? '停止语音输入' : '语音输入'}
      className={`${
        size === 'sm' ? 'w-7 h-7' : 'w-8 h-8'
      } rounded-lg flex items-center justify-center shrink-0 transition-all ${
        listening
          ? 'bg-neon-red/20 text-neon-red animate-pulse-red'
          : 'bg-white/5 text-gray-400 hover:bg-neon-blue/15 hover:text-neon-blue'
      }`}
    >
      <svg className={size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4'} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
    </button>
  )
}
