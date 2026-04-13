"""Utilitários para manipulação de texto com sintaxe Markdown.

Este módulo contém funções puras (sem dependências do Flet) para:
- Envolver seleções com sintaxe Markdown
- Prefixar linhas com marcadores
- Inserir conteúdo na posição do cursor

Todas as funções retornam tuplas ``(novo_texto, novo_start, novo_end)`` para
permitir atualização eficiente do cursor/seleção após a modificação.
"""

from __future__ import annotations


def wrap_selection(
    text: str,
    start: int,
    end: int,
    prefix: str,
    suffix: str | None = None,
    placeholder: str = "texto",
) -> tuple[str, int, int]:
    """Envolve o texto selecionado com prefixo e sufixo Markdown.

    Se não houver seleção (start == end), insere prefixo, placeholder e sufixo
    na posição do cursor, selecionando o placeholder para fácil substituição.

    Args:
        text: Texto completo do campo.
        start: Índice inicial da seleção (base_offset).
        end: Índice final da seleção (extent_offset).
        prefix: String a inserir antes da seleção.
        suffix: String a inserir após a seleção. Se None, usa o mesmo valor de prefix.
        placeholder: Texto a inserir quando não há seleção.

    Returns:
        Tupla (novo_texto, novo_start, novo_end) com o texto modificado e
        os novos índices de seleção.
    """
    suffix = suffix if suffix is not None else prefix

    if start == end:
        # Sem seleção: insere prefix + placeholder + suffix
        # Seleciona o placeholder para o usuário poder digitar diretamente
        inserted = prefix + placeholder + suffix
        new_text = text[:start] + inserted + text[end:]
        new_start = start + len(prefix)
        new_end = new_start + len(placeholder)
    else:
        # Com seleção: envolve o texto selecionado
        selected = text[start:end]
        new_text = text[:start] + prefix + selected + suffix + text[end:]
        new_start = start + len(prefix)
        new_end = new_start + len(selected)

    return new_text, new_start, new_end


def prefix_line(
    text: str,
    start: int,
    end: int,
    prefix: str,
) -> tuple[str, int, int]:
    """Adiciona um prefixo ao início da linha que contém o cursor/seleção.

    Se múltiplas linhas estiverem selecionadas, aplica o prefixo a cada uma.

    Args:
        text: Texto completo do campo.
        start: Índice inicial da seleção.
        end: Índice final da seleção.
        prefix: Prefixo a adicionar (ex: "# ", "- ", "> ").

    Returns:
        Tupla (novo_texto, novo_start, novo_end).
    """
    lines = text.split("\n")

    # Encontra os índices das linhas que contêm start e end
    char_count = 0
    start_line_idx = 0
    end_line_idx = len(lines) - 1
    found_start = False
    found_end = False

    for i, line in enumerate(lines):
        line_start = char_count
        line_end = char_count + len(line)

        # Verifica se start está nesta linha
        if not found_start and line_start <= start <= line_end:
            start_line_idx = i
            found_start = True

        # Verifica se end está nesta linha
        if not found_end and line_start <= end <= line_end:
            end_line_idx = i
            found_end = True

        # Se ambos foram encontrados, podemos parar
        if found_start and found_end:
            break

        char_count = line_end + 1  # +1 para o \n

    # Aplica prefixo a cada linha no intervalo
    offset = 0
    for i in range(start_line_idx, end_line_idx + 1):
        lines[i] = prefix + lines[i]
        offset += len(prefix)

    new_text = "\n".join(lines)
    new_start = start + len(prefix)
    new_end = end + offset

    return new_text, new_start, new_end


def insert_at_cursor(
    text: str,
    position: int,
    content: str,
) -> tuple[str, int, int]:
    """Insere conteúdo na posição do cursor.

    Args:
        text: Texto completo do campo.
        position: Posição do cursor.
        content: Conteúdo a inserir.

    Returns:
        Tupla (novo_texto, novo_start, novo_end) com cursor após o conteúdo inserido.
    """
    new_text = text[:position] + content + text[position:]
    new_pos = position + len(content)
    return new_text, new_pos, new_pos


# --------------------------------------------------------------------------- #
#  Funções de Formatação Inline                                              #
# --------------------------------------------------------------------------- #


def apply_bold(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica formatação negrito (**texto**)."""
    return wrap_selection(text, start, end, "**", "**")


def apply_italic(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica formatação itálico (_texto_)."""
    return wrap_selection(text, start, end, "_", "_")


def apply_strikethrough(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica formatação tachado (~~texto~~)."""
    return wrap_selection(text, start, end, "~~", "~~")


def apply_code(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica formatação código inline (`texto`)."""
    return wrap_selection(text, start, end, "`", "`")


def apply_link(
    text: str,
    start: int,
    end: int,
    url: str = "url",
) -> tuple[str, int, int]:
    """Aplica formatação de link ([texto](url)).

    Se não houver seleção, insere [link text](url) com placeholder.

    Args:
        text: Texto completo.
        start: Início da seleção.
        end: Fim da seleção.
        url: URL do link (placeholder "url" por padrão).

    Returns:
        Tupla (novo_texto, novo_start, novo_end).
    """
    if start == end:
        # Sem seleção: insere template completo
        link_md = f"[link text]({url})"
        new_text = text[:start] + link_md + text[end:]
        # Seleciona "link text" para edição
        new_start = start + 1  # após [
        new_end = new_start + len("link text")
    else:
        # Com seleção: usa texto selecionado como link text
        selected = text[start:end]
        link_md = f"[{selected}]({url})"
        new_text = text[:start] + link_md + text[end:]
        # Seleciona a URL para edição
        new_start = start + len(f"[{selected}](")
        new_end = new_start + len(url)

    return new_text, new_start, new_end


# --------------------------------------------------------------------------- #
#  Funções de Formatação de Bloco                                            #
# --------------------------------------------------------------------------- #


def apply_heading(
    text: str,
    start: int,
    end: int,
    level: int = 1,
) -> tuple[str, int, int]:
    """Aplica cabeçalho Markdown (# a ######).

    Args:
        text: Texto completo.
        start: Início da seleção.
        end: Fim da seleção.
        level: Nível do cabeçalho (1-6).

    Returns:
        Tupla (novo_texto, novo_start, novo_end).
    """
    level = max(1, min(6, level))
    prefix = "#" * level + " "
    return prefix_line(text, start, end, prefix)


def apply_blockquote(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica formatação de blockquote (> texto)."""
    return prefix_line(text, start, end, "> ")


def apply_bullet_list(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica lista com marcadores (- item)."""
    return prefix_line(text, start, end, "- ")


def apply_numbered_list(text: str, start: int, end: int) -> tuple[str, int, int]:
    """Aplica lista numerada (1. item).

    Nota: Para simplicidade, usa sempre "1. " como prefixo.
    Renderizadores Markdown tratam a numeração automaticamente.
    """
    return prefix_line(text, start, end, "1. ")


def insert_horizontal_rule(text: str, position: int) -> tuple[str, int, int]:
    """Insere uma linha horizontal (---) na posição do cursor.

    Adiciona quebras de linha antes e depois para garantir isolamento.
    """
    rule = "\n\n---\n\n"
    return insert_at_cursor(text, position, rule)
