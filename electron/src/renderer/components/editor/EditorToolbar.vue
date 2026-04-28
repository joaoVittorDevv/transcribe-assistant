<template>
  <div class="flex flex-wrap items-center gap-1 p-2 glass-surface mb-1">
    <ToolbarBtn
      :active="activeFormats.has('bold')"
      @click="format('bold')"
      title="Bold"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
        <path d="M6 4h8a4 4 0 014 4 4 4 0 01-4 4H6z"/><path d="M6 12h9a4 4 0 014 4 4 4 0 01-4 4H6z"/>
      </svg>
    </ToolbarBtn>
    <ToolbarBtn
      :active="activeFormats.has('italic')"
      @click="format('italic')"
      title="Italic"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
        <path d="M10 4l2 0-4 16-2 0zM8 4l6 0M6 20l6 0"/>
      </svg>
    </ToolbarBtn>
    <ToolbarBtn
      :active="activeFormats.has('strike')"
      @click="format('strike')"
      title="Strikethrough"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l0 14"/>
      </svg>
    </ToolbarBtn>
    <ToolbarBtn
      :active="activeFormats.has('code')"
      @click="format('code')"
      title="Inline Code"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
      </svg>
    </ToolbarBtn>

    <div class="w-px h-5 bg-white/10 mx-1"></div>

    <ToolbarBtn
      :active="activeFormats.has('header:1')"
      @click="heading(1)"
      title="H1"
    >
      <span class="text-xs font-bold font-plus-jakarta">H1</span>
    </ToolbarBtn>
    <ToolbarBtn
      :active="activeFormats.has('header:2')"
      @click="heading(2)"
      title="H2"
    >
      <span class="text-xs font-bold font-plus-jakarta">H2</span>
    </ToolbarBtn>
    <ToolbarBtn
      :active="activeFormats.has('header:3')"
      @click="heading(3)"
      title="H3"
    >
      <span class="text-xs font-bold font-plus-jakarta">H3</span>
    </ToolbarBtn>

    <div class="w-px h-5 bg-white/10 mx-1"></div>

    <ToolbarBtn
      :active="activeFormats.has('list:bullet')"
      @click="list('bullet')"
      title="Bullet List"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
      </svg>
    </ToolbarBtn>
    <ToolbarBtn
      :active="activeFormats.has('list:ordered')"
      @click="list('ordered')"
      title="Numbered List"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8.242 5.992h12m-12 6.003H20.24m-12 5.999h12M4.117 7.495v-3.75H2.99m1.125 3.75H2.99m1.125 0H5.24m-1.92 2.577a1.125 1.125 0 113.114 1.143L2.99 19.503H5.24M2.99 15.612h2.25" />
      </svg>
    </ToolbarBtn>
  </div>
</template>

<script setup lang="ts">
import ToolbarBtn from './ToolbarBtn.vue';

defineProps<{
  activeFormats: Set<string>;
}>();

const emit = defineEmits<{
  format: [type: string, value?: string | boolean | number];
}>();

function format(type: string) {
  emit('format', type);
}

function heading(level: number) {
  emit('format', 'header', level);
}

function list(type: string) {
  emit('format', 'list', type);
}
</script>
