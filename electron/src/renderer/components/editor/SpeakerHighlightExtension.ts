import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

export interface SpeakerHighlightOptions {
  onSpeakerClick?: (speakerTag: string) => void;
}

export const SpeakerHighlightExtension = Extension.create<SpeakerHighlightOptions>({
  name: 'speakerHighlight',

  addOptions() {
    return {
      onSpeakerClick: undefined,
    };
  },

  addProseMirrorPlugins() {
    const extension = this;

    return [
      new Plugin({
        key: new PluginKey('speakerHighlight'),
        props: {
          handleClick(view, pos, event) {
            const target = event.target as HTMLElement;
            if (target && target.closest('.speaker-badge-guest')) {
              const badge = target.closest('.speaker-badge-guest') as HTMLElement;
              const speaker = badge.getAttribute('data-speaker') || badge.textContent || '';
              if (speaker && extension.options.onSpeakerClick) {
                extension.options.onSpeakerClick(speaker);
                return true;
              }
            }
            return false;
          },
          decorations(state) {
            const decorations: Decoration[] = [];
            const doc = state.doc;

            doc.descendants((node, pos) => {
              if (node.isText && node.text) {
                const text = node.text;

                // Match @Usuario: or @User:
                const userRegex = /@(Usuario|User):/gi;
                let match: RegExpExecArray | null;
                while ((match = userRegex.exec(text)) !== null) {
                  const from = pos + match.index;
                  const to = from + match[0].length;
                  decorations.push(
                    Decoration.inline(from, to, {
                      class: 'speaker-badge-user',
                      'data-speaker': match[0],
                    })
                  );
                }

                // Match other speakers like @Interlocutor 1:, @Speaker 2:, etc.
                const guestRegex = /@([A-Za-z0-9_]+(?:\s+\d+)?):/gi;
                while ((match = guestRegex.exec(text)) !== null) {
                  const speakerTag = match[0].toLowerCase();
                  if (speakerTag.startsWith('@usuario:') || speakerTag.startsWith('@user:')) {
                    continue;
                  }
                  const from = pos + match.index;
                  const to = from + match[0].length;
                  decorations.push(
                    Decoration.inline(from, to, {
                      class: 'speaker-badge-guest cursor-pointer hover:opacity-90',
                      'data-speaker': match[0],
                      title: 'Clique para renomear este interlocutor',
                    })
                  );
                }
              }
            });

            return DecorationSet.create(doc, decorations);
          },
        },
      }),
    ];
  },
});
