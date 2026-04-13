import { ref } from 'vue';

const editorRef = ref<{ clearEditor: () => void } | null>(null);

export function useEditor() {
  function registerEditor(ref: { clearEditor: () => void }) {
    editorRef.value = ref;
  }

  function clearEditor() {
    editorRef.value?.clearEditor();
  }

  return { editorRef, registerEditor, clearEditor };
}
