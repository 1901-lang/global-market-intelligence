'use client'

import SignalBadge from './SignalBadge'

interface ModelResult {
  signal: string
  confidence: number
  reasoning: string[]
}

interface ConsensusData {
  asset: string
  final_signal: string
  confidence: number
  agreement_level: string
  models?: Record<string, ModelResult>
  dissenting_models?: string[]
}

interface ConsensusViewProps {
  consensus: ConsensusData[]
}

const MODEL_ICONS: Record<string, string> = {
  openai: '🤖',
  claude: '🧠',
  gemini: '💎',
}

const MODEL_LABELS: Record<string, string> = {
  openai: 'GPT-5.4',
  claude: 'Claude Opus 4.6',
  gemini: 'Gemini 3.1 Pro',
}

function ModelCard({
  modelName,
  result,
  isFinal = false,
}: {
  modelName: string
  result: ModelResult
  isFinal?: boolean
}) {
  return (
    <div className={`rounded-lg p-3 border ${isFinal ? 'border-[#58a6ff]/50 bg-[#58a6ff]/5' : 'border-[#30363d] bg-[#21262d]'}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <span>{MODEL_ICONS[modelName] || '🤖'}</span>
          <span className="text-sm font-semibold text-white">
            {MODEL_LABELS[modelName] || modelName}
          </span>
          {isFinal && <span className="text-xs text-[#58a6ff] font-medium ml-1">(Consensus)</span>}
        </div>
        <div className="flex items-center gap-2">
          <SignalBadge signal={result.signal} size="sm" />
          <span className="text-xs text-gray-400">{(result.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
      {result.reasoning && result.reasoning.length > 0 && (
        <ul className="text-xs text-gray-400 space-y-0.5">
          {result.reasoning.slice(0, 2).map((r, i) => (
            <li key={i} className="truncate">• {r}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function ConsensusView({ consensus }: ConsensusViewProps) {
  if (!consensus || consensus.length === 0) {
    return (
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
        <h2 className="font-bold text-white mb-3 flex items-center gap-2">
          <span>🎯</span> AI Consensus
        </h2>
        <div className="text-center text-gray-500 text-sm py-6">
          Awaiting model consensus…
        </div>
      </div>
    )
  }

  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
      <h2 className="font-bold text-white mb-4 flex items-center gap-2">
        <span>🎯</span> AI Consensus — Multi-Model Debate
      </h2>
      <div className="space-y-5">
        {consensus.map((item) => (
          <div key={item.asset} className="border border-[#30363d] rounded-lg p-3">
            <div className="flex items-center justify-between mb-3">
              <span className="font-bold text-white">{item.asset}</span>
              <div className="flex items-center gap-2">
                <SignalBadge signal={item.final_signal} size="md" />
                <span className="text-xs text-gray-400">
                  {(item.confidence * 100).toFixed(0)}% conf.
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 mb-2">
              {Object.entries(item.models || {}).map(([model, result]) => (
                <ModelCard key={model} modelName={model} result={result} />
              ))}
            </div>

            {/* Final consensus row */}
            <ModelCard
              modelName="consensus"
              result={{
                signal: item.final_signal,
                confidence: item.confidence,
                reasoning: [
                  `${item.agreement_level.charAt(0).toUpperCase() + item.agreement_level.slice(1)} model agreement`,
                  item.dissenting_models && item.dissenting_models.length > 0
                    ? `Dissent: ${item.dissenting_models.join(', ')}`
                    : 'All models aligned',
                ],
              }}
              isFinal
            />
          </div>
        ))}
      </div>
    </div>
  )
}
