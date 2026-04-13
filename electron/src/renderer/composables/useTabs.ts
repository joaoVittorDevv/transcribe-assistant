import { reactive, ref } from 'vue';

export interface Tab {
  id: string;
  title: string;
  content: string;
}

const tabs = reactive<Tab[]>([{ id: '1', title: 'Tab 1', content: '' }]);
const activeTabId = ref('1');

export function useTabs() {
  function addTab(): void {
    const id = Date.now().toString();
    tabs.push({ id, title: `Tab ${tabs.length + 1}`, content: '' });
    activeTabId.value = id;
  }

  function closeTab(id: string): void {
    if (tabs.length <= 1) return;
    const index = tabs.findIndex((t) => t.id === id);
    if (index === -1) return;
    tabs.splice(index, 1);
    if (activeTabId.value === id) {
      activeTabId.value = tabs[Math.max(0, index - 1)].id;
    }
  }

  function setActive(id: string): void {
    activeTabId.value = id;
  }

  function updateContent(id: string, content: string): void {
    const tab = tabs.find((t) => t.id === id);
    if (tab) tab.content = content;
  }

  function getActiveTab(): Tab | undefined {
    return tabs.find((t) => t.id === activeTabId.value);
  }

  function resetActiveTab(): void {
    const tab = getActiveTab();
    if (tab) tab.content = '';
  }

  return { tabs, activeTabId, addTab, closeTab, setActive, updateContent, getActiveTab, resetActiveTab };
}
