from __future__ import annotations

import subprocess
import platform


def copy_html_to_clipboard(html_content: str, fallback_text: str | None = None) -> bool:
    """Gets HTML text and sets it to the system clipboard as `text/html`.

    If `fallback_text` is provided, some clipboards may also store it as plain text.
    Currently focuses on xclip (Linux) but includes a stub for macOS/Windows logic.
    """
    sys_plat = platform.system()

    if sys_plat == "Linux":
        # Tentaremos usar o xclip
        try:
            # Primeiro inserimos o HTML puro
            process = subprocess.Popen(
                ["xclip", "-selection", "c", "-t", "text/html"],
                stdin=subprocess.PIPE,
                close_fds=True,
            )
            process.communicate(input=html_content.encode("utf-8"))
            return process.returncode == 0
        except Exception as e:
            print(f"[DEBUG] erro ao tentar xclip html: {e}")
            return False

    elif sys_plat == "Darwin":
        # macOS pbcopy
        try:
            # Requer um hex encoding ou applescript para RTF/HTML que é complexo.
            # Focaremos na conversão crua simples ou fallback se falhar.
            # Um truque comum:
            apple_script_cmd = f"set the clipboard to record {{HTML:«data HTML{html_content.encode('utf-8').hex()}»}}"
            subprocess.run(["osascript", "-e", apple_script_cmd])
            return True
        except Exception:
            return False

    elif sys_plat == "Windows":
        # Windows API
        # A implementação no Windows exige win32clipboard e montagem detalhada do buffer HTML.
        # Fica como stub, já que no momento o dev usa Linux.
        print("[DEBUG] HTML clipboard no Windows ainda n. implementado!")
        return False

    return False
