<script setup lang="ts">
import { computed } from 'vue'

import type { RegistrationStatus } from '@/types'
import { STATUS_META } from '@/utils/format'

const props = defineProps<{ status: RegistrationStatus }>()
const meta = computed(() => STATUS_META[props.status] ?? { label: props.status, className: '' })
</script>

<template>
  <span class="tag" :class="meta.className">{{ meta.label }}</span>
</template>
