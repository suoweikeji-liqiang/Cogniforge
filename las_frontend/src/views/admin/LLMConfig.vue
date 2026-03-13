<template>
  <div class="llm-config-page">
    <div class="config-header">
      <h1>{{ t('llm.title') }}</h1>
    </div>

    <div class="routes-panel">
      <div class="panel-header">
        <div>
          <h2>{{ t('llm.taskRoutes') }}</h2>
          <p class="routes-hint">{{ t('llm.taskRoutesHint') }}</p>
        </div>
        <button class="btn btn-primary" @click="saveTaskRoutes">
          {{ t('common.save') }}
        </button>
      </div>

      <div
        v-if="routeStatusNotice"
        class="route-status-banner"
        :class="routeStatusNotice.kind"
        data-testid="llm-route-status-banner"
      >
        <strong>{{ routeStatusNotice.title }}</strong>
        <p>{{ routeStatusNotice.message }}</p>
      </div>

      <div class="route-grid">
        <div v-for="route in routeCards" :key="route.key" class="route-card">
          <h3>{{ t(`llm.routeLabels.${route.key}`) }}</h3>
          <p class="route-description">{{ t(`llm.routeDescriptions.${route.key}`) }}</p>

          <div class="form-group">
            <label>{{ t('llm.routeProvider') }}</label>
            <select v-model="taskRoutes[route.key].provider_id" @change="onTaskRouteProviderChange(route.key)">
              <option :value="null">{{ t(`llm.routeProviderOptions.${route.key}`) }}</option>
              <option
                v-for="provider in enabledProviders"
                :key="`route-provider-${route.key}-${provider.id}`"
                :value="provider.id"
              >
                {{ provider.name }}
              </option>
            </select>
          </div>

          <div class="form-group">
            <label>{{ t('llm.routeModel') }}</label>
            <select
              v-model="taskRoutes[route.key].model_record_id"
              :disabled="!taskRoutes[route.key].provider_id"
            >
              <option :value="null">
                {{ route.key === 'fallback' ? t('llm.routeDisabled') : t('llm.routeUseProviderDefault') }}
              </option>
              <option
                v-for="model in getEnabledModels(taskRoutes[route.key].provider_id)"
                :key="`route-model-${route.key}-${model.id}`"
                :value="model.id"
              >
                {{ model.model_name }} ({{ model.model_id }})
              </option>
            </select>
          </div>

          <p class="route-card-status">{{ getRouteStatusCopy(route.key) }}</p>
        </div>
      </div>
    </div>
    
    <div class="config-content">
      <div class="providers-panel">
        <div class="panel-header">
          <h2>{{ t('llm.providers') }}</h2>
          <button class="btn btn-primary" @click="showProviderModal = true">
            + {{ t('llm.addProvider') }}
          </button>
        </div>
        
        <div class="providers-list">
          <div 
            v-for="provider in providers" 
            :key="provider.id"
            class="provider-item"
            :class="{ active: selectedProvider?.id === provider.id, disabled: !provider.enabled }"
            @click="selectProvider(provider)"
          >
            <div class="provider-info">
              <span class="provider-name">{{ provider.name }}</span>
              <span class="provider-type">{{ t(`llm.types.${provider.provider_type}`) }}</span>
            </div>
            <div class="provider-status">
              <span class="status-badge" :class="{ enabled: provider.enabled }">
                {{ provider.enabled ? t('llm.enabled') : t('llm.disabled') }}
              </span>
            </div>
          </div>
          
          <div v-if="!providers.length" class="empty-state">
            <p>{{ t('llm.noProviders') }}</p>
            <p class="hint">{{ t('llm.createFirst') }}</p>
          </div>
        </div>
      </div>
      
      <div class="details-panel">
        <template v-if="selectedProvider">
          <div class="details-header">
            <h2>{{ selectedProvider.name }}</h2>
            <div class="details-actions">
              <button class="btn btn-secondary" @click="testConnection">
                {{ t('llm.testConnection') }}
              </button>
              <button class="btn btn-secondary" @click="editProvider">
                {{ t('common.edit') }}
              </button>
              <button class="btn btn-danger" @click="deleteProvider">
                {{ t('common.delete') }}
              </button>
            </div>
          </div>

          <div
            v-if="selectedProvider && !selectedProvider.enabled"
            class="provider-warning"
            data-testid="llm-disabled-provider-warning"
          >
            <div>
              <strong>{{ t('llm.providerDisabledTitle') }}</strong>
              <p>{{ t('llm.providerDisabledHint') }}</p>
            </div>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              data-testid="llm-enable-provider"
              @click="enableSelectedProvider"
            >
              {{ t('llm.enableProviderNow') }}
            </button>
          </div>
          
          <div class="provider-details">
            <div class="detail-row">
              <span class="label">{{ t('llm.providerType') }}:</span>
              <span class="value">{{ t(`llm.types.${selectedProvider.provider_type}`) }}</span>
            </div>
            <div class="detail-row">
              <span class="label">{{ t('llm.apiKey') }}:</span>
              <span class="value">{{ maskApiKey(selectedProvider.api_key) }}</span>
            </div>
            <div class="detail-row">
              <span class="label">{{ t('llm.baseUrl') }}:</span>
              <span class="value">{{ selectedProvider.base_url || '-' }}</span>
            </div>
            <div class="detail-row">
              <span class="label">{{ t('llm.priority') }}:</span>
              <span class="value">{{ selectedProvider.priority }}</span>
            </div>
          </div>
          
          <div class="models-section">
            <div class="section-header">
              <h3>{{ t('llm.models') }}</h3>
              <button class="btn btn-primary btn-sm" @click="showModelModal = true">
                + {{ t('llm.addModel') }}
              </button>
            </div>
            
            <div class="models-list">
              <div 
                v-for="model in selectedProvider.models" 
                :key="model.id"
                class="model-item"
              >
                <div class="model-info">
                  <span class="model-name">{{ model.model_name }}</span>
                  <span class="model-id">{{ model.model_id }}</span>
                </div>
                <div class="model-actions">
                  <span v-if="model.is_default" class="default-badge">
                    {{ t('llm.defaultModel') }}
                  </span>
                  <button class="btn-icon" @click="editModel(model)">✏️</button>
                  <button class="btn-icon" @click="deleteModel(model)">🗑️</button>
                </div>
              </div>
              
              <div v-if="!selectedProvider.models?.length" class="empty-models">
                {{ t('llm.noModels') }}
              </div>
            </div>
          </div>
        </template>
        
        <div v-else class="no-selection">
          <p>{{ noSelectionTitle }}</p>
          <p class="hint">{{ noSelectionHint }}</p>
        </div>
      </div>
    </div>
    
    <div v-if="showProviderModal" class="modal-overlay" @click.self="closeProviderModal">
      <div class="modal">
        <h2>{{ editingProvider ? t('llm.editProvider') : t('llm.addProvider') }}</h2>
        <form @submit.prevent="saveProvider">
          <div class="form-group">
            <label>{{ t('llm.providerName') }}</label>
            <input v-model="providerForm.name" type="text" required />
          </div>
          <div class="form-group">
            <label>{{ t('llm.providerType') }}</label>
            <select v-model="providerForm.provider_type" required @change="onProviderTypeChange">
              <option value="openai">OpenAI</option>
              <option value="qwen">Qwen / 千问</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama</option>
              <option value="azure">Azure OpenAI</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div class="form-group" v-if="providerForm.provider_type !== 'ollama'">
            <label>{{ t('llm.apiKey') }}</label>
            <input v-model="providerForm.api_key" type="password" />
          </div>
          <div class="form-group">
            <label>{{ t('llm.baseUrl') }}</label>
            <input v-model="providerForm.base_url" type="text" :placeholder="getBaseUrlPlaceholder()" />
          </div>
          <div class="form-group">
            <label>{{ t('llm.priority') }}</label>
            <input v-model.number="providerForm.priority" type="number" min="0" />
          </div>
          <div class="form-group checkbox">
            <label>
              <input v-model="providerForm.enabled" type="checkbox" />
              {{ t('llm.enabled') }}
            </label>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="closeProviderModal">
              {{ t('common.cancel') }}
            </button>
            <button type="submit" class="btn btn-primary">
              {{ t('common.save') }}
            </button>
          </div>
        </form>
      </div>
    </div>
    
    <div v-if="showModelModal" class="modal-overlay" @click.self="showModelModal = false">
      <div class="modal">
        <h2>{{ editingModel ? t('llm.editModel') : t('llm.addModel') }}</h2>
        <form @submit.prevent="saveModel">
          <div class="form-group">
            <label>{{ t('llm.modelName') }}</label>
            <input v-model="modelForm.model_name" type="text" required />
          </div>
          <div class="form-group">
            <label>{{ t('llm.modelId') }}</label>
            <input v-model="modelForm.model_id" type="text" required :placeholder="getModelIdPlaceholder()" />
          </div>
          <div class="form-group checkbox">
            <label>
              <input v-model="modelForm.is_default" type="checkbox" />
              {{ t('llm.defaultModel') }}
            </label>
          </div>
          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="showModelModal = false">
              {{ t('common.cancel') }}
            </button>
            <button type="submit" class="btn btn-primary">
              {{ t('common.save') }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()

const providers = ref([])
const selectedProvider = ref(null)
const showProviderModal = ref(false)
const showModelModal = ref(false)
const editingProvider = ref(null)
const editingModel = ref(null)
const taskRoutes = ref({
  interactive: { provider_id: null, model_record_id: null },
  structured_heavy: { provider_id: null, model_record_id: null },
  fallback: { provider_id: null, model_record_id: null },
})

const routeCards = [
  { key: 'interactive' },
  { key: 'structured_heavy' },
  { key: 'fallback' },
]

const enabledProviders = computed(() => providers.value.filter(provider => provider.enabled))
const hasProviders = computed(() => providers.value.length > 0)
const hasEnabledProviders = computed(() => enabledProviders.value.length > 0)

const routeStatusNotice = computed(() => {
  if (!hasProviders.value) {
    return {
      kind: 'warning',
      title: t('llm.routeStatusNoProvidersTitle'),
      message: t('llm.routeStatusNoProvidersMessage'),
    }
  }
  if (!hasEnabledProviders.value) {
    return {
      kind: 'warning',
      title: t('llm.routeStatusNoEnabledProvidersTitle'),
      message: t('llm.routeStatusNoEnabledProvidersMessage'),
    }
  }
  return {
    kind: 'info',
    title: t('llm.routeStatusReadyTitle', { count: enabledProviders.value.length }),
    message: t('llm.routeStatusReadyMessage'),
  }
})

const noSelectionTitle = computed(() => (
  hasProviders.value ? t('llm.selectProviderTitle') : t('llm.noProviders')
))

const noSelectionHint = computed(() => (
  hasProviders.value ? t('llm.selectProviderHint') : t('llm.createFirst')
))

const providerForm = ref({
  name: '',
  provider_type: 'openai',
  api_key: '',
  base_url: '',
  priority: 0,
  enabled: true
})

const modelForm = ref({
  model_name: '',
  model_id: '',
  is_default: false
})

const loadProviders = async () => {
  try {
    const response = await api.get('/admin/llm-config/providers')
    providers.value = response.data
    if (selectedProvider.value) {
      selectedProvider.value = providers.value.find(p => p.id === selectedProvider.value.id) || null
    } else if (providers.value.length) {
      selectedProvider.value = providers.value[0]
    }
  } catch (e) {
    console.error('Failed to load providers:', e)
  }
}

const normalizeTaskRoutes = (routes = {}) => ({
  interactive: {
    provider_id: routes.interactive?.provider_id ?? null,
    model_record_id: routes.interactive?.model_record_id ?? null,
  },
  structured_heavy: {
    provider_id: routes.structured_heavy?.provider_id ?? null,
    model_record_id: routes.structured_heavy?.model_record_id ?? null,
  },
  fallback: {
    provider_id: routes.fallback?.provider_id ?? null,
    model_record_id: routes.fallback?.model_record_id ?? null,
  },
})

const loadTaskRoutes = async () => {
  try {
    const response = await api.get('/admin/llm-config/routes')
    taskRoutes.value = normalizeTaskRoutes(response.data)
  } catch (e) {
    console.error('Failed to load task routes:', e)
  }
}

const saveTaskRoutes = async () => {
  try {
    const payload = normalizeTaskRoutes(taskRoutes.value)
    const response = await api.put('/admin/llm-config/routes', payload)
    taskRoutes.value = normalizeTaskRoutes(response.data)
    alert(t('llm.saveSuccess'))
  } catch (e) {
    console.error('Failed to save task routes:', e)
    alert(e.response?.data?.detail || 'Error saving task routes')
  }
}

const selectProvider = (provider) => {
  selectedProvider.value = provider
}

const getEnabledModels = (providerId) => {
  const provider = providers.value.find(item => item.id === providerId)
  return provider?.models?.filter(model => model.enabled) || []
}

const getRouteStatusCopy = (routeKey) => {
  const route = taskRoutes.value[routeKey]
  if (!hasProviders.value) return t('llm.routeNeedsProvider')
  if (!hasEnabledProviders.value) return t('llm.routeNeedsEnabledProvider')
  if (!route?.provider_id) {
    return routeKey === 'fallback'
      ? t('llm.routeStatusFallbackOff')
      : t('llm.routeStatusUseGlobalDefault')
  }
  const provider = providers.value.find(item => item.id === route.provider_id)
  if (!provider?.enabled) return t('llm.routeStatusProviderDisabled')
  const enabledModels = getEnabledModels(route.provider_id)
  if (!enabledModels.length) return t('llm.routeStatusNoEnabledModels')
  if (!route.model_record_id) return t('llm.routeStatusProviderDefault')
  const model = enabledModels.find(item => item.id === route.model_record_id)
  return model
    ? t('llm.routeStatusSpecificModel', { model: model.model_name })
    : t('llm.routeStatusProviderDefault')
}

const onTaskRouteProviderChange = (routeKey) => {
  if (!taskRoutes.value[routeKey]?.provider_id) {
    taskRoutes.value[routeKey].model_record_id = null
    return
  }
  const validModels = getEnabledModels(taskRoutes.value[routeKey].provider_id)
  const stillValid = validModels.some(model => model.id === taskRoutes.value[routeKey].model_record_id)
  if (!stillValid) {
    taskRoutes.value[routeKey].model_record_id = null
  }
}

const closeProviderModal = () => {
  showProviderModal.value = false
  editingProvider.value = null
  providerForm.value = {
    name: '',
    provider_type: 'openai',
    api_key: '',
    base_url: '',
    priority: 0,
    enabled: true
  }
}

const editProvider = () => {
  editingProvider.value = selectedProvider.value
  providerForm.value = {
    name: selectedProvider.value.name,
    provider_type: selectedProvider.value.provider_type,
    api_key: '',
    base_url: selectedProvider.value.base_url || '',
    priority: selectedProvider.value.priority,
    enabled: selectedProvider.value.enabled
  }
  showProviderModal.value = true
}

const enableSelectedProvider = async () => {
  if (!selectedProvider.value || selectedProvider.value.enabled) return
  try {
    await api.put(`/admin/llm-config/providers/${selectedProvider.value.id}`, {
      name: selectedProvider.value.name,
      provider_type: selectedProvider.value.provider_type,
      api_key: '',
      base_url: selectedProvider.value.base_url || '',
      priority: selectedProvider.value.priority,
      enabled: true,
    })
    await loadProviders()
    await loadTaskRoutes()
  } catch (e) {
    console.error('Failed to enable provider:', e)
    alert(e.response?.data?.detail || t('llm.enableProviderFailed'))
  }
}

const saveProvider = async () => {
  try {
    if (editingProvider.value) {
      await api.put(`/admin/llm-config/providers/${editingProvider.value.id}`, providerForm.value)
    } else {
      await api.post('/admin/llm-config/providers', providerForm.value)
    }
    await loadProviders()
    await loadTaskRoutes()
    closeProviderModal()
    if (editingProvider.value) {
      selectedProvider.value = providers.value.find(p => p.id === editingProvider.value.id)
    }
  } catch (e) {
    console.error('Failed to save provider:', e)
    alert(e.response?.data?.detail || 'Error saving provider')
  }
}

const deleteProvider = async () => {
  if (!confirm(t('llm.confirmDelete'))) return
  try {
    await api.delete(`/admin/llm-config/providers/${selectedProvider.value.id}`)
    selectedProvider.value = null
    await loadProviders()
    await loadTaskRoutes()
  } catch (e) {
    console.error('Failed to delete provider:', e)
  }
}

const testConnection = async () => {
  try {
    const response = await api.get(`/admin/llm-config/providers/${selectedProvider.value.id}/test`, {
      timeout: 15000,
    })
    if (response.data.status === 'success') {
      alert(t('llm.testSuccess'))
    } else {
      alert(t('llm.testFailed') + ': ' + response.data.message)
    }
  } catch (e) {
    if (e.code === 'ECONNABORTED') {
      alert(t('llm.testTimeout'))
      return
    }
    alert(t('llm.testFailed') + ': ' + (e.response?.data?.detail || e.message))
  }
}

const getBaseUrlPlaceholder = () => {
  const type = providerForm.value.provider_type
  if (type === 'openai') return 'https://api.openai.com/v1'
  if (type === 'qwen') return 'https://dashscope.aliyuncs.com/compatible-mode/v1'
  if (type === 'anthropic') return 'https://api.anthropic.com'
  if (type === 'ollama') return 'http://localhost:11434'
  return 'https://api.example.com/v1'
}

const getModelIdPlaceholder = () => {
  const type = selectedProvider.value?.provider_type || providerForm.value.provider_type
  if (type === 'openai') return 'gpt-4o-mini'
  if (type === 'qwen') return 'qwen-plus'
  if (type === 'anthropic') return 'claude-3-5-sonnet-20241022'
  if (type === 'ollama') return 'llama2'
  return 'model-id'
}

const onProviderTypeChange = () => {
  const type = providerForm.value.provider_type
  providerForm.value.base_url = type === 'qwen' ? 'https://dashscope.aliyuncs.com/compatible-mode/v1' : ''
}

const saveModel = async () => {
  try {
    if (editingModel.value) {
      await api.put(`/admin/llm-config/models/${editingModel.value.id}`, modelForm.value)
    } else {
      await api.post('/admin/llm-config/models', {
        provider_id: selectedProvider.value.id,
        ...modelForm.value
      })
    }
    await loadProviders()
    selectedProvider.value = providers.value.find(p => p.id === selectedProvider.value.id)
    await loadTaskRoutes()
    showModelModal.value = false
    editingModel.value = null
    modelForm.value = { model_name: '', model_id: '', is_default: false }
  } catch (e) {
    console.error('Failed to save model:', e)
    alert(e.response?.data?.detail || 'Error saving model')
  }
}

const editModel = (model) => {
  editingModel.value = model
  modelForm.value = {
    model_name: model.model_name,
    model_id: model.model_id,
    is_default: model.is_default
  }
  showModelModal.value = true
}

const deleteModel = async (model) => {
  if (!confirm(t('llm.confirmDelete'))) return
  try {
    await api.delete(`/admin/llm-config/models/${model.id}`)
    await loadProviders()
    selectedProvider.value = providers.value.find(p => p.id === selectedProvider.value.id)
    await loadTaskRoutes()
  } catch (e) {
    console.error('Failed to delete model:', e)
  }
}

const maskApiKey = (key) => {
  if (!key) return '-'
  if (key.length <= 8) return '****'
  return key.slice(0, 4) + '****' + key.slice(-4)
}

onMounted(async () => {
  await loadProviders()
  await loadTaskRoutes()
})
</script>

<style scoped>
.llm-config-page {
  max-width: 1200px;
  margin: 0 auto;
}

.llm-config-page h1 {
  color: var(--text);
  margin-bottom: 1.5rem;
}

.routes-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.5rem;
}

.routes-hint {
  margin: 0.25rem 0 0;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.route-status-banner {
  display: grid;
  gap: 0.35rem;
  margin-bottom: 1rem;
  padding: 0.9rem 1rem;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.03);
}

.route-status-banner.warning {
  border-color: rgba(250, 204, 21, 0.28);
  background: rgba(250, 204, 21, 0.08);
}

.route-status-banner.info {
  border-color: rgba(96, 165, 250, 0.24);
  background: rgba(96, 165, 250, 0.08);
}

.route-status-banner p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.route-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}

.route-card {
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg-dark);
}

.route-card h3 {
  margin: 0 0 0.5rem;
  color: var(--text);
  font-size: 0.95rem;
}

.route-description {
  margin: 0 0 1rem;
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.route-card-status {
  margin: 0.75rem 0 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.config-content {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 1.5rem;
  min-height: 600px;
}

.providers-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.panel-header h2 {
  color: var(--text);
  font-size: 1rem;
  margin: 0;
}

.providers-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.provider-item {
  padding: 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.provider-item:hover {
  background: var(--bg-dark);
}

.provider-item.active {
  background: var(--bg-dark);
  border-color: var(--primary);
}

.provider-item.disabled {
  opacity: 0.5;
}

.provider-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.provider-name {
  color: var(--text);
  font-weight: 500;
}

.provider-type {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.provider-status {
  margin-top: 0.5rem;
}

.status-badge {
  font-size: 0.625rem;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  background: var(--bg-dark);
  color: var(--text-muted);
}

.status-badge.enabled {
  background: var(--primary);
  color: var(--bg-dark);
}

.details-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
}

.details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border);
}

.details-header h2 {
  color: var(--text);
  margin: 0;
}

.provider-warning {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 0.95rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(250, 204, 21, 0.28);
  background: rgba(250, 204, 21, 0.08);
}

.provider-warning p {
  margin: 0.25rem 0 0;
  color: var(--text-muted);
}

.details-actions {
  display: flex;
  gap: 0.5rem;
}

.provider-details {
  margin-bottom: 2rem;
}

.detail-row {
  display: flex;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--border);
}

.detail-row .label {
  color: var(--text-muted);
  width: 140px;
  font-size: 0.875rem;
}

.detail-row .value {
  color: var(--text);
  font-size: 0.875rem;
}

.models-section {
  margin-top: 1.5rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h3 {
  color: var(--text);
  font-size: 1rem;
  margin: 0;
}

.models-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.model-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: var(--bg-dark);
  border-radius: 8px;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.model-name {
  color: var(--text);
  font-weight: 500;
}

.model-id {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.model-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.default-badge {
  font-size: 0.625rem;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  background: var(--primary);
  color: var(--bg-dark);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  opacity: 0.6;
}

.btn-icon:hover {
  opacity: 1;
}

.empty-state, .empty-models, .no-selection {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}

.empty-state .hint,
.no-selection .hint {
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
}

.modal {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  width: 100%;
  max-width: 480px;
}

.modal h2 {
  color: var(--text);
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.form-group input, .form-group select {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-dark);
  color: var(--text);
  font-size: 0.875rem;
}

.form-group input:focus, .form-group select:focus {
  outline: none;
  border-color: var(--primary);
}

.form-group.checkbox label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.form-group.checkbox input {
  width: auto;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  opacity: 0.9;
}

.btn-sm {
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
}

@media (max-width: 900px) {
  .config-content {
    grid-template-columns: 1fr;
  }

  .details-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .provider-warning {
    flex-direction: column;
  }
}
</style>
