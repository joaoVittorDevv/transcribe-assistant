import re
from pathlib import Path

path = Path("electron/src/renderer/composables/useTranscriptionState.ts")
content = path.read_text()

# Extract resetInsertionPoint from useEditor
if "const { insertTextWithAck } = useEditor();" in content:
    content = content.replace(
        "const { insertTextWithAck } = useEditor();",
        "const { insertTextWithAck, resetInsertionPoint } = useEditor();"
    )
elif "import { useEditor } from './useEditor';" in content:
    # If it's not destructured globally or in init, let's just make it available
    # Actually I put it in initSocketListeners: 
    # const { insertTextWithAck } = useEditor();
    pass

# We will just import it globally at the top level of the composable
# Let's find "export function useTranscriptionState() {"
func_start = "export function useTranscriptionState() {"
replacement = "export function useTranscriptionState() {\n  const { resetInsertionPoint } = useEditor();"
content = content.replace(func_start, replacement)

# Replace all api.resetInsertionPoint()
content = content.replace("api.resetInsertionPoint();", "resetInsertionPoint();")

path.write_text(content)
print("done")
