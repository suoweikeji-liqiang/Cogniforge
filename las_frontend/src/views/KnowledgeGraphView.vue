<template>
  <div class="knowledge-graph">
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
          v-for="(node, i) in positionedNodes"
          :key="node.id"
          :transform="`translate(${node.x}, ${node.y})`"
          class="graph-node"
          @click="$router.push(`/model-cards/${node.id}`)"
        >
          <circle :r="20 + node.examples_count * 3" />
          <text dy="4" text-anchor="middle">{{ truncate(node.label, 12) }}</text>
          <text dy="18" text-anchor="middle" class="node-version">v{{ node.version }}</text>
        </g>
      </svg>
    </div>

    <p v-else class="empty">{{ t('graph.noData') }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/api'

const { t } = useI18n()

const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const loading = ref(true)
const svgRef = ref<SVGElement | null>(null)

const truncate = (s: string, n: number) => s.length > n ? s.slice(0, n) + '...' : s

const positionedNodes = computed(() => {
  const count = nodes.value.length
  const cx = 400, cy = 300, r = Math.min(250, count * 40)
  return nodes.value.map((node, i) => ({
    ...node,
    x: cx + r * Math.cos((2 * Math.PI * i) / count),
    y: cy + r * Math.sin((2 * Math.PI * i) / count),
  }))
})

const viewBox = computed(() => '0 0 800 600')

const getNodePos = (id: string) => {
  const node = positionedNodes.value.find((n) => n.id === id)
  return node ? { x: node.x, y: node.y } : { x: 400, y: 300 }
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
.knowledge-graph h1 { margin-bottom: 1.5rem; }

.graph-container {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  overflow: hidden;
}

.graph-svg { width: 100%; height: 600px; }

.graph-edge { stroke: var(--border); stroke-width: 1.5; }

.graph-node { cursor: pointer; }
.graph-node circle {
  fill: var(--bg-dark);
  stroke: var(--primary);
  stroke-width: 2;
  transition: all 0.2s;
}
.graph-node:hover circle { fill: var(--primary); opacity: 0.8; }
.graph-node text { fill: var(--text); font-size: 10px; }
.node-version { fill: var(--text-muted); font-size: 8px; }

.loading, .empty {
  text-align: center;
  padding: 3rem;
  color: var(--text-muted);
}
</style>
