<template>
  <button
    type="button"
    @click="emit('click')"
    class="w-8 h-8 flex items-center justify-center glass-btn rounded-lg text-text-muted hover:text-accent-blue transition-all duration-150"
    :title="title"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
defineProps<{ title?: string }>();
const emit = defineEmits<{ click: [] }>();
</script>
