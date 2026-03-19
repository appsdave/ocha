/**
 * @module tui-layout
 * Creates and returns all blessed widgets for the ocha TUI.
 * Keeps widget construction separate from business logic.
 */
import blessed from 'blessed';

/**
 * Compute the geometry for the new-task prompt dialog.
 * Uses up to 60% of the terminal height so there is plenty of room
 * for multi-line task descriptions while still leaving visible
 * context behind the overlay.
 *
 * @param {{ height?: number }} screen
 * @returns {{ overlayHeight: number, overlayTop: number, textareaTop: number, textareaHeight: number }}
 */
export function getPromptDialogLayout(screen) {
  const screenHeight = Math.max(0, Math.floor(Number(screen?.height) || 0));
  const idealHeight = screenHeight > 0 ? Math.round(screenHeight * 0.6) : 18;
  const overlayHeight = screenHeight > 0
    ? Math.min(22, Math.max(7, idealHeight), screenHeight)
    : 18;
  // Row 0: hint line — leave a gap row before the textarea.
  const textareaTop = Math.max(2, overlayHeight >= 10 ? 3 : 2);
  // Reserve 1 row at the bottom of the overlay for the border.
  const textareaHeight = Math.max(3, overlayHeight - textareaTop - 1);

  return {
    overlayHeight,
    overlayTop: Math.max(0, Math.floor((screenHeight - overlayHeight) / 2)),
    textareaTop,
    textareaHeight,
  };
}

/**
 * Build the full screen and all widgets.
 * @returns {{ screen, agentList, logBox, inputBar, statusBar }}
 */
export function buildLayout() {
  const screen = blessed.screen({
    smartCSR: false,
    title: 'ocha',
    fullUnicode: true,
    forceUnicode: true,
    dockBorders: true,
    autoPadding: false,
    style: { bg: 'black' },
  });

  // ── Left sidebar: agent list ──────────────────────────────────────────────
  const agentList = blessed.box({
    top: 0,
    left: 0,
    width: '30%',
    height: '100%-3',
    border: { type: 'line' },
    style: {
      bg: 'black',
      border: { fg: 'blue' },
      focus: { border: { fg: 'cyan' } },
    },
    label: ' Agents ',
    tags: true,
    scrollable: true,
    alwaysScroll: true,
    keys: true,
    vi: false,
  });

  // ── Right pane: task header ─────────────────────────────────────────────
  const taskHeader = blessed.box({
    top: 0,
    left: '30%',
    width: '70%',
    height: 5,
    border: { type: 'line' },
    style: { border: { fg: 'blue' }, bg: 'black', fg: 'white' },
    label: ' Task ',
    tags: true,
  });

  // ── Right pane: log output ────────────────────────────────────────────────
  const logBox = blessed.box({
    top: 5,
    left: '30%',
    width: '70%',
    height: '100%-8',
    border: { type: 'line' },
    style: { bg: 'black', fg: 'white', border: { fg: 'blue' } },
    label: ' Output ',
    tags: true,
    scrollable: true,
    alwaysScroll: true,
    scrollbar: { ch: '│', style: { fg: 'grey' } },
    keys: true,
    vi: false,
    wrap: true,
  });

  // ── Bottom hint bar ───────────────────────────────────────────────────────
  const inputBar = blessed.box({
    bottom: 1,
    left: 0,
    width: '100%',
    height: 1,
    style: { fg: 'white', bg: 'black' },
    tags: true,
    content: '{grey-fg}  {bold}n{/bold} new   {bold}↑↓{/bold} navigate   {bold}k{/bold} kill   {bold}c{/bold} clear done   {bold}v{/bold} toggle view   {bold}←→{/bold} switch pane   {bold}q{/bold} quit{/grey-fg}',
  });

  // ── Status bar ────────────────────────────────────────────────────────────
  const statusBar = blessed.box({
    bottom: 0,
    left: 0,
    width: '100%',
    height: 1,
    style: { fg: 'black', bg: 'blue' },
    tags: true,
    content: ' ocha  |  0 agents ',
  });

  screen.append(agentList);
  screen.append(taskHeader);
  screen.append(logBox);
  screen.append(inputBar);
  screen.append(statusBar);

  return { screen, agentList, taskHeader, logBox, inputBar, statusBar };
}

/**
 * Open a styled multi-line prompt dialog for task input.
 * Enter inserts a newline so users can compose multi-line descriptions.
 * Ctrl-S submits the task; Escape cancels.
 *
 * @param {object} screen - blessed screen instance
 * @param {Function} onSubmit - called with the trimmed task string (or null if cancelled)
 */
export function openPromptDialog(screen, onSubmit) {
  const layout = getPromptDialogLayout(screen);

  // Overlay backdrop
  const overlay = blessed.box({
    top: layout.overlayTop,
    left: 'center',
    width: '80%',
    height: layout.overlayHeight,
    border: { type: 'line' },
    style: {
      border: { fg: 'cyan' },
      bg: 'black',
      fg: 'white',
    },
    label: ' {cyan-fg}{bold} New Task {/bold}{/cyan-fg} ',
    tags: true,
    filled: true,
  });

  /* eslint-disable-next-line no-unused-vars -- auto-appended to overlay via parent */
  const hint = blessed.box({
    parent: overlay,
    top: 0,
    left: 1,
    width: '100%-3',
    height: 1,
    tags: true,
    style: { bg: 'black' },
    content: '{grey-fg}Describe your task below. {bold}Ctrl-S{/bold} to submit · {bold}Esc{/bold} to cancel{/grey-fg}',
  });

  const textarea = blessed.textarea({
    parent: overlay,
    top: layout.textareaTop,
    left: 1,
    width: '100%-3',
    height: layout.textareaHeight,
    style: {
      fg: 'white',
      bg: 'black',
      border: { fg: 'green' },
      focus: { bg: 'black', border: { fg: 'green' } },
    },
    border: { type: 'line' },
    // Explicit padding prevents the first line of text from being hidden
    // behind the top border when the screen uses autoPadding: false.
    padding: { top: 0, right: 1, bottom: 0, left: 1 },
    inputOnFocus: true,
    keys: true,
    mouse: true,
    scrollable: true,
    alwaysScroll: true,
  });

  screen.append(overlay);

  // Clear any stale value from previous open, then focus
  textarea.setValue('');
  textarea.focus();
  screen.render();

  // Force a full screen redraw so the overlay renders cleanly without
  // bleached / stale content bleeding through from widgets underneath.
  screen.alloc();
  screen.render();

  let closed = false;
  const close = (value) => {
    if (closed) return;
    closed = true;
    screen.remove(overlay);
    // Force full redraw to clear any remnants of the overlay that blessed's
    // smart-CSR optimisation would otherwise leave on screen ("bleaching").
    screen.alloc();
    screen.render();
    onSubmit(value || null);
  };

  // Ctrl-S submits, Escape cancels.
  // Enter is intentionally left unbound so the textarea keeps its default
  // behaviour of inserting a newline, enabling multi-line task descriptions.
  textarea.key(['C-s'], () => {
    close(textarea.getValue().trim());
  });

  textarea.key(['escape'], () => {
    close(null);
  });
}
