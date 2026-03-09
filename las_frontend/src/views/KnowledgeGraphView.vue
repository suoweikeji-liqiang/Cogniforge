<template>
  <div class="knowledge-graph">
    <SecondarySurfaceBanner
      test-id="graph-secondary-banner"
      :eyebrow="t('graph.secondaryTitle')"
      :title="t('graph.secondaryHeading')"
      :message="t('graph.secondaryMessage')"
      :primary-label="t('graph.openModelCards')"
      primary-to="/model-cards"
      :secondary-label="t('nav.problems')"
      secondary-to="/problems"
    />
    <h1>{{ t('graph.title') }}</h1>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>

    <div v-else-if="nodes.length" class="graph-container">
      <svg ref="svgRef" class="graph-svg" :viewBox="viewBox">
        <line
          v-for="(edge, i) in edges"
          :key="'e' + i"
          :x1="getNodePos(edge.source).x"
          :y1="getNodePos(edge.source).y"
          :x2="getNodePos(edge.target).x"
          :y2="getNodePos(edge.target).y"
          class="graph-edge"
        />
        <g
          v-for="node in positionedNodes"
          :key="node.id"
          :transform="`translate(${node.x}, ${node.y})`"
          :class="['graph-node', `node-${node.node_type || 'model_card'}`]"
          @click="onNodeClick(node)"
        >
          <circle :r="getNodeRadius(node)" />
          <text dy="4" text-anchor="middle">{{ truncate(node.label, 14) }}</text>
          <text dy="18" text-anchor="middle" class="node-version">{{ nodeBadge(node) }}</text>
        </g>
      </svg>
    </div>

    <p v-else class="empty">{{ t('graph.noData') }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import api from '@/api'
import SecondarySurfaceBanner from '@/components/SecondarySurfaceBanner.vue'

const { t } = useI18n()
const router = useRouter()

const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const loading = ref(true)
const svgRef = ref<SVGElement | null>(null)

const truncate = (s: string, n: number) => (s.length > n ? s.slice(0, n) + '...' : s)

const positionedNodes = computed(() => {
  const count = nodes.value.length
  const cx = 400
  const cy = 300
  const r = Math.min(250, count * 40)
  return nodes.value.map((node, i) => ({
    ...node,
    x: cx + r * Math.cos((2 * Math.PI * i) / Math.max(count, 1)),
    y: cy + r * Math.sin((2 * Math.PI * i) / Math.max(count, 1)),
  }))
})

const viewBox = computed(() => '0 0 800 600')

const getNodePos = (id: string) => {
  const node = positionedNodes.value.find((n) => n.id === id)
  return node ? { x: node.x, y: node.y } : { x: 400, y: 300 }
}

const getNodeRadius = (node: any) => {
  if (node.node_type === 'problem') return 28
  if (node.node_type === 'learning_step') return 22
  if (node.node_type === 'concept') return 18
  return 20 + (node.examples_count || 0) * 3
}

const nodeBadge = (node: any) => {
  if (node.node_type === 'problem') return 'P'
  if (node.node_type === 'learning_step') return `S${node.version || 1}`
  if (node.node_type === 'concept') return 'C'
  return `v${node.version || 1}`
}

const onNodeClick = (node: any) => {
  const nodeType = node?.node_type
  const routeId = node?.route_id
  if (!routeId && nodeType !== undefined) return

  if (nodeType === 'problem' || nodeType === 'learning_step') {
    router.push(`/problems/${routeId}`)
    return
  }

  if (nodeType === 'model_card' || nodeType === undefined) {
    router.push(`/model-cards/${routeId || node.id}`)
  }
}

const fetchGraph = async () => {
  try {
    const res = await api.get('/statistics/knowledge-graph')
    nodes.value = res.data.nodes
    edges.value = res.data.edges
  } catch (e) {
    console.error('Failed to fetch knowledge graph:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchGraph)
</script>

<style scoped>
.knowledge-graph h1 {
  margin-bottom: 1.5rem;
}

.graph-container {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  overflow: hidden;
}

.graph-svg {
  width: 100%;
  height: 600px;
}

.graph-edge {
  stroke: var(--border);
  stroke-width: 1.5;
}

.graph-node {
  cursor: pointer;
}

.graph-node circle {
  fill: var(--bg-dark);
  stroke-width: 2;
  transition: all 0.2s;
}

.graph-node:hover circle {
  opacity: 0.86;
}

.graph-node text {
  fill: var(--text);
  font-size: 10px;
}

.node-version {
  fill: var(--text-muted);
  font-size: 8px;
}

.node-model_card circle {
  stroke: #60a5fa;
}

.node-problem circle {
  stroke: #22c55e;
}

.node-learning_step circle {
  stroke: #f59e0b;
}

.node-concept circle {
  stroke: #a78bfa;
}

.node-concept {
  cursor: default;
}

.loading,
.empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
