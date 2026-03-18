import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getPromptDialogLayout } from './tui-layout.js';

describe('getPromptDialogLayout', () => {
  it('keeps the full-size dialog on taller terminals', () => {
    const layout = getPromptDialogLayout({ height: 24 });

    assert.equal(layout.overlayHeight, 14);
    assert.equal(layout.overlayTop, 5);
    assert.equal(layout.textareaTop, 3);
  });

  it('keeps the prompt dialog fully on screen in shorter terminals', () => {
    const layout = getPromptDialogLayout({ height: 10 });

    assert.ok(layout.overlayTop >= 0, 'prompt dialog should not start above the screen');
    assert.ok(
      layout.overlayTop + layout.overlayHeight <= 10,
      'prompt dialog should fit within the screen height'
    );
  });

  it('keeps the textarea fully inside the prompt dialog', () => {
    const layout = getPromptDialogLayout({ height: 10 });

    assert.ok(layout.textareaTop >= 1, 'textarea should leave room for the hint row');
    assert.ok(
      layout.textareaTop + layout.textareaHeight <= layout.overlayHeight - 1,
      'textarea should stay fully inside the dialog body'
    );
  });
});