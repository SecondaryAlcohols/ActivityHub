<script setup lang="ts">
import { toasts } from '@/toast'
</script>

<template>
  <div class="toast-stack">
    <TransitionGroup name="toast">
      <div
        v-for="item in toasts"
        :key="item.id"
        class="toast"
        :class="item.type"
      >
        {{ item.message }}
      </div>
    </TransitionGroup>
  </div>
</template>
