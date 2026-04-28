<template>
  <div class="app-shell">
    <MainWorkspace />
  </div>
</template>

<script setup lang="ts">
import MainWorkspace from './components/layout/MainWorkspace.vue';
</script>

<style>
.app-shell {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #121B26 0%, #0F1720 100%);
  overflow: hidden;
}
</style>
