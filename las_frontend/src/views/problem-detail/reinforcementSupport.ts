export type LearningMode = 'socratic' | 'exploration'

export type ReinforcementActionTemplate = {
  key: string
  preferredMode: LearningMode
  title: string
  description: string
  starter: string
  sourceCue?: string
  sourceClue?: string
  likelyConfusion?: string
  evidenceCue?: string
}

export type ReinforcementStarterContext = {
  questionCue: string
  answerCue: string
  comparisonCue: string
  primaryCue: string
}

export type ReinforcementErrorHint = {
  kind: 'comparison' | 'boundary' | 'misconception'
  text: string
}

type TranslateFn = (key: string, params?: Record<string, unknown>) => string

export const normalizeInlineText = (value: unknown) => String(value ?? '').replace(/\s+/g, ' ').trim()

export const clipInlineText = (value: string, max = 96) => {
  const normalized = normalizeInlineText(value)
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, Math.max(0, max - 1)).trimEnd()}…`
}

const stripTrailingPunctuation = (value: string) => normalizeInlineText(value).replace(/[.?!,:;]+$/g, '').trim()
const stripQuestionLead = (value: string) => normalizeInlineText(value).replace(
  /^(what is|what's|what are|how should i|how do i|how can i|why does|why do|why is|when should i|when does|can you explain|could you explain|explain|tell me about|is it true that|is|are)\s+/i,
  '',
)
const isQuestionLike = (value: string) => /\?$/.test(normalizeInlineText(value))

export const uniqueContextConcepts = (values: unknown[], exclude: string[] = []) => {
  const excluded = new Set(exclude.map((value) => normalizeInlineText(value).toLowerCase()).filter(Boolean))
  const seen = new Set<string>()
  return values
    .map((value) => normalizeInlineText(value))
    .filter((value) => {
      const normalized = value.toLowerCase()
      if (!value || excluded.has(normalized) || seen.has(normalized)) return false
      seen.add(normalized)
      return true
    })
}

const extractQuestionCue = (question: string, answerType: string, contextConcepts: string[]) => {
  const normalized = normalizeInlineText(question)
  if (!normalized) return ''

  if (answerType === 'comparison') {
    const betweenMatch = normalized.match(/\bdifference between\s+(.+?)\s+and\s+(.+?)(?:[?.!,]|$)/i)
    if (betweenMatch) {
      return clipInlineText(`${stripTrailingPunctuation(betweenMatch[1])} vs ${stripTrailingPunctuation(betweenMatch[2])}`)
    }
    const compareMatch = normalized.match(/\bcompare\s+(.+?)(?:[?.!,]|$)/i)
    if (compareMatch) {
      return clipInlineText(stripTrailingPunctuation(compareMatch[1]))
    }
    const versusMatch = normalized.match(/\b(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:[?.!,]|$)/i)
    if (versusMatch) {
      return clipInlineText(`${stripTrailingPunctuation(versusMatch[1])} vs ${stripTrailingPunctuation(versusMatch[2])}`)
    }
    if (contextConcepts.length >= 2) {
      return clipInlineText(`${contextConcepts[0]} vs ${contextConcepts[1]}`)
    }
  }

  const stripped = stripQuestionLead(normalized)
  return clipInlineText(stripTrailingPunctuation(stripped || normalized))
}

const extractAnswerCue = (answer: string) => {
  const sentences = normalizeInlineText(answer)
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => clipInlineText(sentence, 120))
    .filter(Boolean)
  if (!sentences.length) return ''
  const preferred = sentences.find((sentence) => /example|because|instead|raises|lowers|depends|tradeoff|boundary|fails|applies/i.test(sentence))
  return preferred || sentences[0]
}

export const isLowSignalAnswerCue = (value: string) => {
  const normalized = normalizeInlineText(value).toLowerCase()
  return !normalized || /start from the current step concept|define it briefly|test it with one concrete example/.test(normalized)
}

const extractSentenceWithPattern = (value: string, pattern: RegExp) => {
  const sentence = normalizeInlineText(value)
    .split(/(?<=[.!?])\s+/)
    .find((item) => pattern.test(item))
  return sentence ? clipInlineText(sentence, 120) : ''
}

const splitEvidenceChunks = (value: string) => {
  const normalized = String(value || '').trim()
  if (!normalized) return []

  const chunks = normalized
    .split(/\n+/)
    .flatMap((line) => normalizeInlineText(line).split(/(?<=[.!?])\s+/))
    .map((chunk) => clipInlineText(chunk, 140))
    .filter(Boolean)

  return uniqueContextConcepts(chunks)
}

const extractBoundaryCue = (question: string, answer: string) => {
  const explicitQuestionCue = extractSentenceWithPattern(question, /\b(always|never|only|every|all|whenever|must|cannot|can't)\b/i)
  if (explicitQuestionCue) return stripTrailingPunctuation(explicitQuestionCue)
  const explicitAnswerCue = extractSentenceWithPattern(answer, /\b(always|never|only|every|all|whenever|must|cannot|can't|fails|breaks|edge case)\b/i)
  if (explicitAnswerCue) return stripTrailingPunctuation(explicitAnswerCue)
  return ''
}

const extractMisconceptionCue = (question: string, answer: string) => {
  const normalizedQuestion = normalizeInlineText(question)
  if (/\b(same as|equivalent to|means|just|only|always|never)\b/i.test(normalizedQuestion)) {
    return clipInlineText(stripTrailingPunctuation(stripQuestionLead(normalizedQuestion)), 110)
  }

  const correctiveSentence = extractSentenceWithPattern(answer, /\bnot\b.+\bbut\b|\brather than\b|\binstead of\b/i)
  if (correctiveSentence) return stripTrailingPunctuation(correctiveSentence)

  return ''
}

export const buildReinforcementStarterContext = ({
  question,
  answer,
  answerType,
  turnPreview,
  contextConcepts,
}: {
  question: string
  answer: string
  answerType: string
  turnPreview: string
  contextConcepts: string[]
}): ReinforcementStarterContext => {
  const questionCue = extractQuestionCue(question, answerType, contextConcepts)
  const answerCue = extractAnswerCue(answer)
  const comparisonCue = answerType === 'comparison'
    ? questionCue || clipInlineText(contextConcepts.slice(0, 2).join(' vs '))
    : ''
  const primaryCue = questionCue
    || clipInlineText(turnPreview, 110)
    || answerCue
    || clipInlineText(contextConcepts.join(', '), 90)

  return {
    questionCue,
    answerCue,
    comparisonCue,
    primaryCue,
  }
}

export const deriveReinforcementErrorHint = ({
  answerType,
  question,
  answer,
  questionCue,
  comparisonCue,
  t,
}: {
  answerType: string
  question: string
  answer: string
  questionCue: string
  comparisonCue: string
  t: TranslateFn
}): ReinforcementErrorHint | null => {
  if (answerType === 'comparison' && /\b(compare|difference between|vs\.?|versus)\b/i.test(question)) {
    const cue = comparisonCue || questionCue
    if (!cue) return null
    return {
      kind: 'comparison',
      text: t('problemDetail.reinforcementComparisonLikelyConfusion', { cue }),
    }
  }

  if (answerType === 'boundary_clarification') {
    const cue = extractBoundaryCue(question, answer)
    if (!cue) return null
    return {
      kind: 'boundary',
      text: t('problemDetail.reinforcementBoundaryLikelyConfusion', { cue }),
    }
  }

  if (answerType === 'misconception_correction') {
    const cue = extractMisconceptionCue(question, answer)
    if (!cue) return null
    return {
      kind: 'misconception',
      text: t('problemDetail.reinforcementMisconceptionLikelyConfusion', { cue }),
    }
  }

  return null
}

export const extractEvidenceCue = ({
  evidenceSnippet,
  concept,
  sourceCue,
  sourceClue,
  likelyConfusion,
  anchor,
}: {
  evidenceSnippet: string
  concept: string
  sourceCue: string
  sourceClue: string
  likelyConfusion: string
  anchor: string
}) => {
  const conceptKey = normalizeInlineText(concept).toLowerCase()
  const anchorKey = normalizeInlineText(anchor).toLowerCase()
  const seen = new Set<string>()
  const chunks = splitEvidenceChunks(evidenceSnippet).filter((chunk) => {
    const normalized = normalizeInlineText(chunk)
    const key = normalized.toLowerCase()
    if (!normalized || seen.has(key)) return false
    seen.add(key)
    if (isLowSignalAnswerCue(normalized)) return false
    if (key === normalizeInlineText(sourceCue).toLowerCase()) return false
    if (key === normalizeInlineText(sourceClue).toLowerCase()) return false
    if (key === normalizeInlineText(likelyConfusion).toLowerCase()) return false
    if (key === conceptKey || key === anchorKey) return false
    return true
  })

  if (!chunks.length) return ''

  const statementChunks = chunks.filter((chunk) => !isQuestionLike(chunk))
  const candidates = statementChunks.length ? statementChunks : chunks

  const conceptSpecific = candidates.find((chunk) => conceptKey && chunk.toLowerCase().includes(conceptKey))
  if (conceptSpecific) return conceptSpecific

  const evidenceSpecific = candidates.find((chunk) => /because|raises|lowers|drop|drops|rise|rises|tradeoff|instead|rather than|not|but|applies|fails|edge case|example|predicted positives|actual positives|false positives|false negatives/i.test(chunk))
  if (evidenceSpecific) return evidenceSpecific

  return ''
}

const buildEvidenceAwareStarter = (starter: string, evidenceCue: string, t: TranslateFn) => {
  if (!evidenceCue) return starter
  return `${t('problemDetail.reinforcementStarterEvidencePrefix', { evidence: evidenceCue })}\n${starter}`
}

export const buildReinforcementActionTemplate = ({
  activeReinforcementEntry,
  activeReinforcementTarget,
  focusedTurnAnswerType,
  originMode,
  concept,
  anchor,
  comparisonCue,
  sourceCue,
  sourceClue,
  likelyConfusion,
  evidenceCue,
  t,
}: {
  activeReinforcementEntry: unknown
  activeReinforcementTarget: any
  focusedTurnAnswerType: string
  originMode: string
  concept: string
  anchor: string
  comparisonCue: string
  sourceCue: string
  sourceClue: string
  likelyConfusion: string
  evidenceCue: string
  t: TranslateFn
}): ReinforcementActionTemplate | null => {
  if (!activeReinforcementEntry || !activeReinforcementTarget) return null

  const withEvidence = (starter: string) => buildEvidenceAwareStarter(starter, evidenceCue, t)
  const normalizedSourceClue = !isLowSignalAnswerCue(sourceClue) && sourceClue && sourceClue !== sourceCue
    ? sourceClue
    : ''

  if (focusedTurnAnswerType === 'comparison' || activeReinforcementTarget?.resume_path_kind === 'comparison') {
    const comparisonSource = comparisonCue || sourceCue
    return {
      key: 'compare',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateCompareTitle'),
      description: t('problemDetail.reinforcementTemplateCompareBody', { concept, anchor }),
      starter: withEvidence(likelyConfusion
        ? t('problemDetail.reinforcementTemplateCompareErrorStarter', { concept, error: likelyConfusion })
        : comparisonSource
        ? t('problemDetail.reinforcementTemplateCompareSourceStarter', { concept, cue: comparisonSource })
        : t('problemDetail.reinforcementTemplateCompareStarter', { concept, anchor })),
      sourceCue: comparisonSource,
      sourceClue: normalizedSourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (focusedTurnAnswerType === 'misconception_correction') {
    return {
      key: 'correct',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateCorrectTitle'),
      description: t('problemDetail.reinforcementTemplateCorrectBody', { concept, anchor }),
      starter: withEvidence(likelyConfusion
        ? t('problemDetail.reinforcementTemplateCorrectErrorStarter', { concept, error: likelyConfusion })
        : sourceCue
        ? t('problemDetail.reinforcementTemplateCorrectSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateCorrectStarter', { concept, anchor })),
      sourceCue,
      sourceClue: normalizedSourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (focusedTurnAnswerType === 'worked_example') {
    return {
      key: 'example',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateExampleTitle'),
      description: t('problemDetail.reinforcementTemplateExampleBody', { concept, anchor }),
      starter: withEvidence(sourceCue
        ? t('problemDetail.reinforcementTemplateExampleSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateExampleStarter', { concept, anchor })),
      sourceCue,
      sourceClue: normalizedSourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (focusedTurnAnswerType === 'boundary_clarification') {
    return {
      key: 'boundary',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateBoundaryTitle'),
      description: t('problemDetail.reinforcementTemplateBoundaryBody', { concept, anchor }),
      starter: withEvidence(likelyConfusion
        ? t('problemDetail.reinforcementTemplateBoundaryErrorStarter', { concept, error: likelyConfusion })
        : sourceCue
        ? t('problemDetail.reinforcementTemplateBoundarySourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateBoundaryStarter', { concept, anchor })),
      sourceCue,
      sourceClue: normalizedSourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (focusedTurnAnswerType === 'prerequisite_explanation') {
    return {
      key: 'prerequisite',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplatePrerequisiteTitle'),
      description: t('problemDetail.reinforcementTemplatePrerequisiteBody', { concept, anchor }),
      starter: withEvidence(sourceCue
        ? t('problemDetail.reinforcementTemplatePrerequisiteSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplatePrerequisiteStarter', { concept, anchor })),
      sourceCue,
      sourceClue: normalizedSourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  if (originMode === 'socratic') {
    return {
      key: 'probe',
      preferredMode: 'socratic',
      title: t('problemDetail.reinforcementTemplateProbeTitle'),
      description: t('problemDetail.reinforcementTemplateProbeBody', { concept, anchor }),
      starter: withEvidence(sourceCue
        ? t('problemDetail.reinforcementTemplateProbeSourceStarter', { concept, cue: sourceCue })
        : t('problemDetail.reinforcementTemplateProbeStarter', { concept, anchor })),
      sourceCue,
      sourceClue: normalizedSourceClue,
      likelyConfusion,
      evidenceCue,
    }
  }
  return {
    key: 'restate',
    preferredMode: 'socratic',
    title: t('problemDetail.reinforcementTemplateRestateTitle'),
    description: t('problemDetail.reinforcementTemplateRestateBody', { concept, anchor }),
    starter: withEvidence(sourceCue
      ? t('problemDetail.reinforcementTemplateRestateSourceStarter', { concept, cue: sourceCue })
      : t('problemDetail.reinforcementTemplateRestateStarter', { concept, anchor })),
    sourceCue,
    sourceClue: normalizedSourceClue,
    likelyConfusion,
    evidenceCue,
  }
}
