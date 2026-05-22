import { ref } from 'vue';

interface EditorAPI {
  clearEditor: () => void;
  getMarkdown: () => string;
  undo: () => void;
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

  function undo() {
    editorRef.value?.undo();
  }

  return { editorRef, registerEditor, clearEditor, getMarkdown, undo };
}
