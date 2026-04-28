import { ref } from 'vue';

interface EditorAPI {
  clearEditor: () => void;
  getMarkdown: () => string;
}

const editorRef = ref<EditorAPI | null>(null);

export function useEditor() {
  function registerEditor(ref: EditorAPI) {
    editorRef.value = ref;
  }

  function clearEditor() {
    editorRef.value?.clearEditor();
  }

  function getMarkdown(): string {
    return editorRef.value?.getMarkdown() ?? '';
  }

  return { editorRef, registerEditor, clearEditor, getMarkdown };
}
