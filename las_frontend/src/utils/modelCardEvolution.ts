export type ModelCardEvolutionStateKey =
  | 'first_recall_queued'
  | 'needs_revision'
  | 'rebuilding'
  | 'reinforced_recently'
  | 'stable_base'
  | 'repeated_confusion'

export type ModelCardEvolutionStateTone = 'neutral' | 'danger' | 'warning' | 'success'

export type ModelCardEvolutionState = {
  key: ModelCardEvolutionStateKey
  tone: ModelCardEvolutionStateTone
  reinforcementEventCount: number
}

export type ModelCardRevisionFocusKey =
  | 'revise_notes'
  | 'revisit_example'
  | 'clarify_boundary'
  | 'add_counter_example'
  | 'revisit_comparison'

export type ModelCardRevisionFocus = {
  key: ModelCardRevisionFocusKey
  cue: string
}

const countRecallReinforcementEvents = (logs: any[]) => {
  return (logs || []).filter((log) => String(log?.action_taken || '') === 'recall_reinforcement').length
}

const normalizeInlineText = (value: unknown) => String(value ?? '').replace(/\s+/g, ' ').trim()

const clipInlineText = (value: string, max = 120) => {
  const normalized = normalizeInlineText(value)
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, Math.max(0, max - 1)).trimEnd()}…`
}

const splitSignalChunks = (value: string) => {
  return normalizeInlineText(value)
    .split(/(?<=[.!?])\s+/)
    .map((chunk) => clipInlineText(chunk))
    .filter(Boolean)
}

const firstMatchingCue = (signals: string[], pattern: RegExp) => {
  for (const signal of signals) {
    const match = splitSignalChunks(signal).find((chunk) => pattern.test(chunk))
    if (match) return match
  }
  return ''
}

export const deriveModelCardEvolutionState = (
  schedule: any | null | undefined,
  evolutionLogs: any[] = [],
): ModelCardEvolutionState | null => {
  if (!schedule) return null

  const reinforcementEventCount = countRecallReinforcementEvents(evolutionLogs)

  if (schedule.needs_reinforcement && reinforcementEventCount >= 2) {
    return {
      key: 'repeated_confusion',
      tone: 'danger',
      reinforcementEventCount,
    }
  }

  if (schedule.recall_state === 'fragile') {
    return {
      key: 'needs_revision',
      tone: 'danger',
      reinforcementEventCount,
    }
  }

  if (schedule.recall_state === 'rebuilding') {
    return {
      key: 'rebuilding',
      tone: 'warning',
      reinforcementEventCount,
    }
  }

  if (schedule.recall_state === 'reinforcing') {
    return {
      key: 'reinforced_recently',
      tone: 'success',
      reinforcementEventCount,
    }
  }

  if (schedule.recall_state === 'stable') {
    return {
      key: 'stable_base',
      tone: 'success',
      reinforcementEventCount,
    }
  }

  return {
    key: 'first_recall_queued',
    tone: 'neutral',
    reinforcementEventCount,
  }
}

export const deriveModelCardRevisionFocus = ({
  schedule,
  evolutionState,
  card,
}: {
  schedule: any | null | undefined
  evolutionState: ModelCardEvolutionState | null | undefined
  card: any | null | undefined
}): ModelCardRevisionFocus | null => {
  if (!schedule || !evolutionState) return null
  if (!['needs_revision', 'rebuilding', 'repeated_confusion'].includes(evolutionState.key)) return null

  const sourcePathKind = String(
    schedule?.reinforcement_target?.resume_path_kind
      || schedule?.origin?.source_path_kind
      || '',
  ).trim()
  const sourcePreview = String(
    schedule?.reinforcement_target?.source_turn_preview
      || schedule?.origin?.source_turn_preview
      || '',
  ).trim()
  const evidenceSnippet = String(schedule?.origin?.evidence_snippet || '').trim()
  const combinedSignals = [sourcePreview, evidenceSnippet].filter(Boolean)
  const lacksExamples = !Array.isArray(card?.examples) || card.examples.length === 0
  const lacksCounterExamples = !Array.isArray(card?.counter_examples) || card.counter_examples.length === 0

  if (evolutionState.key === 'repeated_confusion' && lacksCounterExamples) {
    return {
      key: 'add_counter_example',
      cue: firstMatchingCue(combinedSignals, /false positives|false negatives|tradeoff|boundary|edge case|applies|fails|threshold|example/i),
    }
  }

  if (
    sourcePathKind === 'comparison'
    || /compare|comparison|difference between|tradeoff|vs\.?|versus/i.test(`${sourcePreview} ${evidenceSnippet}`)
  ) {
    return {
      key: 'revisit_comparison',
      cue: firstMatchingCue(combinedSignals, /compare|comparison|difference between|tradeoff|false positives|false negatives|threshold/i),
    }
  }

  if (/always|never|only|whenever|applies|stops applying|fails|breaks|edge case|boundary|except/i.test(`${sourcePreview} ${evidenceSnippet}`)) {
    return {
      key: 'clarify_boundary',
      cue: firstMatchingCue(combinedSignals, /always|never|only|whenever|applies|stops applying|fails|breaks|edge case|boundary|except/i),
    }
  }

  if (lacksExamples || /example|threshold|case|worked/i.test(`${sourcePreview} ${evidenceSnippet}`)) {
    return {
      key: 'revisit_example',
      cue: firstMatchingCue(combinedSignals, /example|threshold|case|worked|false positives|false negatives/i),
    }
  }

  return {
    key: 'revise_notes',
    cue: clipInlineText(sourcePreview || evidenceSnippet || schedule?.origin?.concept_text || ''),
  }
}
