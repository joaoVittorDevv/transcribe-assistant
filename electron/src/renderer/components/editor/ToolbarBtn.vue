<template>
  <button
    type="button"
    @click="emit('click')"
    :class="[
      'w-8 h-8 flex items-center justify-center glass-btn rounded-lg transition-all duration-150',
      active
        ? 'text-accent-blue bg-accent-blue/15'
        : 'text-text-muted hover:text-accent-blue'
    ]"
    :title="title"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
defineProps<{ title?: string; active?: boolean }>();
const emit = defineEmits<{ click: [] }>();
</script>
