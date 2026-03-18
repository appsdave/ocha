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
  });

  // ── Left sidebar: agent list ──────────────────────────────────────────────
  const agentList = blessed.box({
    top: 0,
    left: 0,
    width: '25%',
    height: '100%-3',
    border: { type: 'line' },
    style: {
      border: { fg: 'blue' },
      focus: { border: { fg: 'cyan' } },
    },
    label: ' Agents ',
    tags: true,
    scrollable: true,
    alwaysScroll: true,
    keys: true,
    vi: true,
  });

  // ── Right pane: log output ────────────────────────────────────────────────
  const logBox = blessed.log({
    top: 0,
    left: '25%',
    width: '75%',
    height: '100%-3',
    border: { type: 'line' },
    style: { border: { fg: 'blue' } },
    label: ' Log ',
    tags: false,
    scrollable: true,
    alwaysScroll: true,
    scrollbar: { ch: '│', style: { fg: 'grey' } },
    keys: true,
    vi: true,
  });

  // ── Bottom hint bar ───────────────────────────────────────────────────────
  const inputBar = blessed.box({
    bottom: 1,
    left: 0,
    width: '100%',
    height: 1,
    style: { fg: 'white', bg: 'black' },
    tags: true,
    content: '{grey-fg}  {bold}n{/bold} new task   {bold}↑↓{/bold} navigate   {bold}K{/bold} kill   {bold}C{/bold} clear done   {bold}l/r{/bold} switch pane   {bold}q{/bold} quit{/grey-fg}',
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
  screen.append(logBox);
  screen.append(inputBar);
  screen.append(statusBar);

  return { screen, agentList, logBox, inputBar, statusBar };
}

/**
 * Open a styled multi-line prompt dialog for task input.
 * Supports Shift+Enter for newlines, Enter to submit.
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
    },
    label: ' {cyan-fg}{bold} New Task {/bold}{/cyan-fg} ',
    tags: true,
  });

  const hint = blessed.box({
    parent: overlay,
    top: 0,
    left: 1,
    width: '100%-4',
    height: 1,
    tags: true,
    style: { bg: 'black' },
    content: '{grey-fg}Describe your task. {bold}Enter{/bold} to submit · {bold}Esc{/bold} to cancel{/grey-fg}',
  });

  const textarea = blessed.textarea({
    parent: overlay,
    top: 2,
    left: 1,
    width: '100%-4',
    height: 7,
    style: {
      fg: 'white',
      bg: '#1e1e1e',
      focus: { bg: '#2a2a2a', border: { fg: 'cyan' } },
    },
    border: { type: 'line' },
    inputOnFocus: true,
    keys: true,
    mouse: true,
    scrollable: true,
    alwaysScroll: true,
  });

  screen.append(overlay);
  textarea.focus();
  screen.render();

  // Clear any stale value from previous open
  textarea.setValue('');
  screen.render();

  // Enter submits, Escape cancels
  textarea.key(['enter'], () => {
    const value = textarea.getValue().trim();
    screen.remove(overlay);
    screen.render();
    onSubmit(value || null);
  });

  textarea.key(['escape'], () => {
    screen.remove(overlay);
    screen.render();
    onSubmit(null);
  });
}
