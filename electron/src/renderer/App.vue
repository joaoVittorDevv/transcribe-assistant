<template>
  <div class="app-shell">
    <MainWorkspace />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import MainWorkspace from './components/layout/MainWorkspace.vue';
import { useSocket } from './composables/useSocket';

const { connect, disconnect } = useSocket();

onMounted(() => {
  connect();
});

onUnmounted(() => {
  disconnect();
});
</script>

<style>
.app-shell {
  display: flex;
  flex-direction: row;
  width: 100%;
  height: 100%;
  background-color: #13151A;
  overflow: hidden;
}
</style>
