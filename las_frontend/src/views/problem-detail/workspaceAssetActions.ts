type RefLike<T> = {
  value: T
}

type ApiClient = {
  get: (url: string, config?: any) => Promise<{ data: any }>
  post: (url: string, data?: any, config?: any) => Promise<{ data: any }>
  delete: (url: string, config?: any) => Promise<{ data: any }>
}

type WorkspaceAssetSnapshot = {
  reviewSchedules?: any[]
  notes?: any[]
  resources?: any[]
}

type ProblemDetailWorkspaceAssetDeps = {
  api: ApiClient
  problemId: string
  activeConceptTurnId: RefLike<string | null>
  scheduledModelCardIds: RefLike<string[]>
  scheduledReviews: RefLike<any[]>
  workspaceNotes: RefLike<any[]>
  noteSaving: RefLike<boolean>
  workspaceResources: RefLike<any[]>
  resourceSaving: RefLike<boolean>
  resourceInterpretingId: RefLike<string | null>
}

export const createProblemDetailWorkspaceAssetActions = ({
  api,
  problemId,
  activeConceptTurnId,
  scheduledModelCardIds,
  scheduledReviews,
  workspaceNotes,
  noteSaving,
  workspaceResources,
  resourceSaving,
  resourceInterpretingId,
}: ProblemDetailWorkspaceAssetDeps) => {
  const applyReviewSchedules = (reviewSchedules: any[]) => {
    scheduledReviews.value = reviewSchedules
    scheduledModelCardIds.value = reviewSchedules.map((schedule: any) => String(schedule.model_card_id))
  }

  const hydrateWorkspaceSnapshot = ({
    reviewSchedules = [],
    notes = [],
    resources = [],
  }: WorkspaceAssetSnapshot) => {
    applyReviewSchedules(reviewSchedules)
    workspaceNotes.value = notes
    workspaceResources.value = resources
  }

  const fetchReviewSchedules = async () => {
    try {
      const response = await api.get('/srs/schedules')
      applyReviewSchedules(response.data || [])
    } catch (e) {
      console.error('Failed to fetch review schedules:', e)
      applyReviewSchedules([])
    }
  }

  const fetchWorkspaceNotes = async () => {
    try {
      const response = await api.get('/notes/', {
        params: {
          problem_id: problemId,
        },
      })
      workspaceNotes.value = response.data || []
    } catch (e) {
      console.error('Failed to fetch workspace notes:', e)
      workspaceNotes.value = []
    }
  }

  const fetchWorkspaceResources = async () => {
    try {
      const response = await api.get('/resources/', {
        params: {
          problem_id: problemId,
        },
      })
      workspaceResources.value = response.data || []
    } catch (e) {
      console.error('Failed to fetch workspace resources:', e)
      workspaceResources.value = []
    }
  }

  const saveWorkspaceNote = async ({ content, tags }: { content: string; tags: string[] }) => {
    noteSaving.value = true
    try {
      await api.post('/notes/', {
        content,
        source: 'text',
        tags,
        problem_id: problemId,
        source_turn_id: activeConceptTurnId.value || undefined,
      })
      await fetchWorkspaceNotes()
    } catch (e) {
      console.error('Failed to save workspace note:', e)
    } finally {
      noteSaving.value = false
    }
  }

  const deleteWorkspaceNote = async (noteId: string) => {
    try {
      await api.delete(`/notes/${noteId}`)
      workspaceNotes.value = workspaceNotes.value.filter((note) => note.id !== noteId)
    } catch (e) {
      console.error('Failed to delete workspace note:', e)
    }
  }

  const saveWorkspaceResource = async ({ url, title, linkType }: { url: string; title: string; linkType: string }) => {
    resourceSaving.value = true
    try {
      await api.post('/resources/', {
        url,
        title: title || null,
        link_type: linkType,
        problem_id: problemId,
        source_turn_id: activeConceptTurnId.value || undefined,
      })
      await fetchWorkspaceResources()
    } catch (e) {
      console.error('Failed to save workspace resource:', e)
    } finally {
      resourceSaving.value = false
    }
  }

  const deleteWorkspaceResource = async (resourceId: string) => {
    try {
      await api.delete(`/resources/${resourceId}`)
      workspaceResources.value = workspaceResources.value.filter((resource) => resource.id !== resourceId)
    } catch (e) {
      console.error('Failed to delete workspace resource:', e)
    }
  }

  const interpretWorkspaceResource = async (resourceId: string) => {
    resourceInterpretingId.value = resourceId
    try {
      const response = await api.post(`/resources/${resourceId}/interpret`)
      workspaceResources.value = workspaceResources.value.map((resource) =>
        resource.id === resourceId ? response.data : resource
      )
    } catch (e) {
      console.error('Failed to interpret workspace resource:', e)
    } finally {
      resourceInterpretingId.value = null
    }
  }

  return {
    fetchReviewSchedules,
    fetchWorkspaceNotes,
    fetchWorkspaceResources,
    hydrateWorkspaceSnapshot,
    saveWorkspaceNote,
    deleteWorkspaceNote,
    saveWorkspaceResource,
    deleteWorkspaceResource,
    interpretWorkspaceResource,
  }
}
