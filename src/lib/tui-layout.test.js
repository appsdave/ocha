import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { getPromptDialogLayout } from './tui-layout.js';

describe('getPromptDialogLayout', () => {
  it('leaves enough room for the textarea to display at least one visible line', () => {
    for (const h of [7, 8, 10, 14, 24, 40]) {
      const layout = getPromptDialogLayout({ height: h });
      assert.ok(
        layout.textareaHeight >= 3,
        `textarea height should be >= 3 for screen height ${h}, got ${layout.textareaHeight}`
      );
    }
  });

  it('scales the overlay proportionally on taller terminals', () => {
    const layout = getPromptDialogLayout({ height: 40 });

    assert.equal(layout.overlayHeight, 22);
    assert.equal(layout.textareaTop, 3);
    assert.ok(layout.textareaHeight >= 14, 'taller terminals should get a larger textarea');
  });

  it('keeps a moderate overlay on medium terminals', () => {
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
    for (const h of [7, 10, 24, 40]) {
      const layout = getPromptDialogLayout({ height: h });

      assert.ok(layout.textareaTop >= 1, `textarea should leave room for the hint row (h=${h})`);
      assert.ok(
        layout.textareaTop + layout.textareaHeight <= layout.overlayHeight - 1,
        `textarea should stay fully inside the dialog body (h=${h})`
      );
    }
  });

  it('caps the overlay at 22 rows even for very tall terminals', () => {
    const layout = getPromptDialogLayout({ height: 80 });

    assert.equal(layout.overlayHeight, 22);
  });

  it('uses a sensible default when screen height is missing', () => {
    const layout = getPromptDialogLayout({});

    assert.equal(layout.overlayHeight, 18);
    assert.ok(layout.textareaHeight >= 3);
  });

  it('handles zero and negative screen heights gracefully', () => {
    for (const h of [0, -1, -100]) {
      const layout = getPromptDialogLayout({ height: h });
      assert.equal(layout.overlayHeight, 18, `should fall back to default for height=${h}`);
    }
  });
});
