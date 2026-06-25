// ============ Web Speech API 类型声明 ============
// 补充 TypeScript DOM 库中缺失的 SpeechRecognition 相关类型。
// 注意：SpeechRecognitionAlternative / SpeechRecognitionResult /
// SpeechRecognitionResultList 已由 lib.dom.d.ts 提供，此处不再重复声明。
// 本文件为环境声明文件（无 import/export），所有声明均为全局。

/** 语音识别事件 */
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number
  readonly results: SpeechRecognitionResultList
}

/** 语音识别错误事件 */
interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string
  readonly message: string
}

/** SpeechRecognition 构造函数类型 */
interface SpeechRecognitionConstructor {
  new (): SpeechRecognition
  prototype: SpeechRecognition
}

/** 语音识别器接口 */
interface SpeechRecognition extends EventTarget {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start(): void
  stop(): void
  abort(): void
  onresult: ((this: SpeechRecognition, ev: SpeechRecognitionEvent) => void) | null
  onerror: ((this: SpeechRecognition, ev: SpeechRecognitionErrorEvent) => void) | null
  onend: ((this: SpeechRecognition, ev: Event) => void) | null
  onstart: ((this: SpeechRecognition, ev: Event) => void) | null
  onspeechstart: ((this: SpeechRecognition, ev: Event) => void) | null
  onspeechend: ((this: SpeechRecognition, ev: Event) => void) | null
  onnomatch: ((this: SpeechRecognition, ev: Event) => void) | null
}

/** 为 Window 添加 SpeechRecognition 属性 */
interface Window {
  SpeechRecognition?: SpeechRecognitionConstructor
  webkitSpeechRecognition?: SpeechRecognitionConstructor
}
