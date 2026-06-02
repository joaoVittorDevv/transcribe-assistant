import { ref } from 'vue';

interface EditorAPI {
  clearEditor: () => void;
  getMarkdown: () => string;
  undo: () => void;
  insertTextWithAck: (text: string, tabId?: string) => Promise<void>;
  resetInsertionPoint: () => void;
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

  async function insertTextWithAck(text: string, tabId?: string): Promise<void> {
    if (editorRef.value?.insertTextWithAck) {
      await editorRef.value.insertTextWithAck(text, tabId);
    }
  }

  function resetInsertionPoint() {
    editorRef.value?.resetInsertionPoint();
  }

  return { editorRef, registerEditor, clearEditor, getMarkdown, undo, insertTextWithAck, resetInsertionPoint };
}
