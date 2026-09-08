<template>
  <button
    type="button"
    @click="emit('click')"
    :class="[
      'w-7 h-7 flex items-center justify-center rounded border transition-all duration-150',
      active
        ? 'text-[#F59E0B] bg-[#F59E0B]/15 border-[#F59E0B]/40 shadow-sm'
        : 'text-[#909095] border-transparent hover:text-[#DDE2F6] hover:bg-[#222733] hover:border-[#2D3342]'
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

