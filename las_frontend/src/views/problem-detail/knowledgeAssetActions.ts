type RefLike<T> = {
  value: T
}

type ApiClient = {
  post: (url: string, data?: any, config?: any) => Promise<{ data: any }>
}

type RouterLike = {
  push: (to: string) => unknown
}

type ProblemDetailKnowledgeActionDeps = {
  api: ApiClient
  problemId: string
  router: RouterLike
  candidateSubmittingId: RefLike<string | null>
  handoffSubmittingId: RefLike<string | null>
  fetchConceptCandidates: () => Promise<void>
  fetchReviewSchedules: () => Promise<void>
  syncProblemSnapshot: () => Promise<any>
}

export const createProblemDetailKnowledgeAssetActions = ({
  api,
  problemId,
  router,
  candidateSubmittingId,
  handoffSubmittingId,
  fetchConceptCandidates,
  fetchReviewSchedules,
  syncProblemSnapshot,
}: ProblemDetailKnowledgeActionDeps) => {
  const acceptCandidate = async (candidateId: string) => {
    candidateSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concept-candidates/${candidateId}/accept`)
      await Promise.all([
        fetchConceptCandidates(),
        syncProblemSnapshot(),
      ])
    } catch (e) {
      console.error('Failed to accept concept candidate:', e)
    } finally {
      candidateSubmittingId.value = null
    }
  }

  const rejectCandidate = async (candidateId: string) => {
    candidateSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concept-candidates/${candidateId}/reject`)
      await fetchConceptCandidates()
    } catch (e) {
      console.error('Failed to reject concept candidate:', e)
    } finally {
      candidateSubmittingId.value = null
    }
  }

  const postponeCandidate = async (candidateId: string) => {
    candidateSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concept-candidates/${candidateId}/postpone`)
      await fetchConceptCandidates()
    } catch (e) {
      console.error('Failed to postpone concept candidate:', e)
    } finally {
      candidateSubmittingId.value = null
    }
  }

  const mergeCandidate = async ({ candidateId, targetConcept }: { candidateId: string; targetConcept: string }) => {
    candidateSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concept-candidates/${candidateId}/merge`, {
        target_concept_text: targetConcept,
      })
      await Promise.all([
        fetchConceptCandidates(),
        syncProblemSnapshot(),
      ])
    } catch (e) {
      console.error('Failed to merge concept candidate:', e)
    } finally {
      candidateSubmittingId.value = null
    }
  }

  const rollbackConcept = async ({ candidateId, conceptText }: { candidateId: string; conceptText: string }) => {
    candidateSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concepts/rollback`, {
        concept_text: conceptText,
        reason: 'Manual rollback from UI',
      })
      await Promise.all([
        fetchConceptCandidates(),
        syncProblemSnapshot(),
      ])
    } catch (e) {
      console.error('Failed to rollback concept:', e)
    } finally {
      candidateSubmittingId.value = null
    }
  }

  const promoteCandidateToModelCard = async (candidateId: string) => {
    handoffSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concept-candidates/${candidateId}/promote`)
      await fetchConceptCandidates()
    } catch (e) {
      console.error('Failed to promote concept candidate to model card:', e)
    } finally {
      handoffSubmittingId.value = null
    }
  }

  const openModelCard = (modelCardId: string) => {
    if (!modelCardId) return
    router.push(`/model-cards/${modelCardId}`)
  }

  const scheduleCandidateReview = async (candidateId: string) => {
    handoffSubmittingId.value = candidateId
    try {
      await api.post(`/problems/${problemId}/concept-candidates/${candidateId}/schedule-review`)
      await Promise.all([
        fetchReviewSchedules(),
        fetchConceptCandidates(),
      ])
    } catch (e) {
      console.error('Failed to schedule concept candidate review:', e)
    } finally {
      handoffSubmittingId.value = null
    }
  }

  return {
    acceptCandidate,
    rejectCandidate,
    postponeCandidate,
    mergeCandidate,
    rollbackConcept,
    promoteCandidateToModelCard,
    openModelCard,
    scheduleCandidateReview,
  }
}
