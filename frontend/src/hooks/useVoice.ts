import { useCallback, useEffect, useRef, useState } from 'react'

// ============ 语音识别 Hook ============

interface UseVoiceInputOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
  onFinalResult?: (text: string) => void
}

interface UseVoiceInputReturn {
  supported: boolean
  listening: boolean
  transcript: string
  start: () => void
  stop: () => void
  reset: () => void
}

/**
 * 语音输入 Hook，封装 Web Speech API 的 SpeechRecognition。
 * 识别结果（含中间结果）会实时写入 transcript；
 * 最终结果通过 onFinalResult 回调返回。
 */
export function useVoiceInput(options: UseVoiceInputOptions = {}): UseVoiceInputReturn {
  const {
    lang = 'zh-CN',
    continuous = false,
    interimResults = true,
    onFinalResult,
  } = options

  const recognitionRef = useRef<SpeechRecognition | null>(null)
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  // 标记是否由用户主动停止（避免 onend 自动重启）
  const userStoppedRef = useRef(false)
  // 保存最新回调
  const onFinalResultRef = useRef(onFinalResult)
  useEffect(() => {
    onFinalResultRef.current = onFinalResult
  }, [onFinalResult])

  const supported =
    typeof window !== 'undefined' &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition)

  // 创建识别实例
  const ensureRecognition = useCallback(() => {
    if (recognitionRef.current) return recognitionRef.current
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!Ctor) return null
    const recognition = new Ctor()
    recognition.lang = lang
    recognition.continuous = continuous
    recognition.interimResults = interimResults
    recognition.maxAlternatives = 1

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = ''
      let final = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          final += result[0].transcript
        } else {
          interim += result[0].transcript
        }
      }
      if (final) {
        setTranscript((prev) => prev + final)
        onFinalResultRef.current?.(final)
      } else if (interim) {
        setTranscript((prev) => prev + interim)
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error('语音识别错误:', event.error, event.message)
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        userStoppedRef.current = true
        setListening(false)
      }
    }

    recognition.onend = () => {
      // 若非用户主动停止且应保持连续，则自动重启
      if (!userStoppedRef.current && continuous) {
        try {
          recognition.start()
        } catch {
          setListening(false)
        }
      } else {
        setListening(false)
      }
    }

    recognitionRef.current = recognition
    return recognition
  }, [lang, continuous, interimResults])

  const start = useCallback(() => {
    if (!supported) return
    const recognition = ensureRecognition()
    if (!recognition) return
    userStoppedRef.current = false
    try {
      recognition.start()
      setListening(true)
    } catch {
      // 可能已启动，忽略
    }
  }, [ensureRecognition, supported])

  const stop = useCallback(() => {
    userStoppedRef.current = true
    const recognition = recognitionRef.current
    if (recognition) {
      try {
        recognition.stop()
      } catch {
        // 忽略
      }
    }
    setListening(false)
  }, [])

  const reset = useCallback(() => {
    setTranscript('')
  }, [])

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      userStoppedRef.current = true
      const recognition = recognitionRef.current
      if (recognition) {
        try {
          recognition.abort()
        } catch {
          // 忽略
        }
        recognitionRef.current = null
      }
    }
  }, [])

  return { supported, listening, transcript, start, stop, reset }
}

// ============ 语音播报 Hook ============

interface UseSpeechSynthesisReturn {
  supported: boolean
  speaking: boolean
  speak: (text: string, onEnd?: () => void) => void
  cancel: () => void
}

/**
 * 语音播报 Hook，封装 window.speechSynthesis。
 * 自动选择中文女声。
 */
export function useSpeechSynthesis(): UseSpeechSynthesisReturn {
  const [speaking, setSpeaking] = useState(false)
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window

  const pickVoice = useCallback((): SpeechSynthesisVoice | null => {
    if (!supported) return null
    const voices = window.speechSynthesis.getVoices()
    if (!voices || voices.length === 0) return null
    // 优先选择中文女声
    const zhVoices = voices.filter((v) => v.lang && v.lang.toLowerCase().startsWith('zh'))
    const female =
      zhVoices.find((v) => /female|女|xiaoxiao|tingting|huihui|yaoyao/i.test(v.name)) ||
      zhVoices.find((v) => /xiaoxiao|tingting|huihui|yaoyao|kangkang/i.test(v.name)) ||
      zhVoices[0]
    return female || voices[0]
  }, [supported])

  const speak = useCallback(
    (text: string, onEnd?: () => void) => {
      if (!supported || !text.trim()) {
        onEnd?.()
        return
      }
      // 取消正在进行的播报
      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'zh-CN'
      const voice = pickVoice()
      if (voice) {
        utterance.voice = voice
      }
      utterance.rate = 1
      utterance.pitch = 1

      utterance.onstart = () => setSpeaking(true)
      utterance.onend = () => {
        setSpeaking(false)
        onEnd?.()
      }
      utterance.onerror = () => {
        setSpeaking(false)
        onEnd?.()
      }

      window.speechSynthesis.speak(utterance)
    },
    [supported, pickVoice],
  )

  const cancel = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  // 组件卸载时停止播报
  useEffect(() => {
    return () => {
      if (supported) {
        window.speechSynthesis.cancel()
      }
    }
  }, [supported])

  return { supported, speaking, speak, cancel }
}
