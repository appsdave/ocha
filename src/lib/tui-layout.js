/**
 * @module tui-layout
 * Creates and returns all blessed widgets for the ocha TUI.
 * Keeps widget construction separate from business logic.
 */
import blessed from 'blessed';

/**
 * Build the full screen and all widgets.
 * @returns {{ screen, agentList, logBox, inputBar, statusBar }}
 */
export function buildLayout() {
  const screen = blessed.screen({
    smartCSR: true,
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
    style: { border: { fg: 'blue' }, bg: 'black' },
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
    style: { bg: 'black', border: { fg: 'blue' } },
    label: ' Output ',
    tags: false,
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
    content: '{grey-fg}  {bold}n{/bold} new   {bold}↑↓{/bold} navigate   {bold}K{/bold} kill   {bold}C{/bold} clear done   {bold}←→{/bold} switch pane   {bold}q{/bold} quit{/grey-fg}',
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
 * Supports Enter to submit, Escape to cancel.
 *
 * @param {object} screen - blessed screen instance
 * @param {Function} onSubmit - called with the trimmed task string (or null if cancelled)
 */
export function openPromptDialog(screen, onSubmit) {
  // Overlay backdrop
  const overlay = blessed.box({
    top: 'center',
    left: 'center',
    width: '70%',
    height: 12,
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

  const hint = blessed.box({
    parent: overlay,
    top: 0,
    left: 1,
    width: '100%-4',
    height: 1,
    tags: true,
    style: { bg: 'black' },
    content: '{grey-fg}Describe your task below. {bold}Enter{/bold} to submit · {bold}Esc{/bold} to cancel{/grey-fg}',
  });

  const textarea = blessed.textarea({
    parent: overlay,
    top: 2,
    left: 1,
    width: '100%-4',
    height: 7,
    style: {
      fg: 'white',
      bg: 'black',
      focus: { bg: 'black', border: { fg: 'cyan' } },
    },
    border: { type: 'line' },
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

  // Enter submits, Escape cancels
  const close = (value) => {
    screen.remove(overlay);
    screen.render();
    onSubmit(value || null);
  };

  textarea.key(['enter'], () => {
    close(textarea.getValue().replace(/\r?\n/g, ' ').trim());
  });

  textarea.key(['escape'], () => {
    close(null);
  });
}
