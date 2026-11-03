// What a key handler reads of a KeyboardEvent, and where the person is typing. The stage's keymap and
// the book's keymap both ask; a key that lands in a field belongs to the field.

/** The part of a KeyboardEvent a keymap reads. */
export interface KeyLike {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  isComposing?: boolean;
  keyCode?: number;
  target: EventTarget | null;
}

/** Whether the key lands in a place the person types: a field, a text area, a select or editable text. */
export function typingIn(target: EventTarget | null): boolean {
  if (!target || !(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}
