/**
 * @module tree
 * Live agent tree display.
 * Renders a hierarchical view of the coordinator → lead → builders → reviewers
 * pipeline to the terminal, updating in-place as agents change state.
 */
import chalk from 'chalk';
import { getTerminalWidth, stripAnsi, wrapText } from './ui.js';

const STATE_ICONS = {
  pending:   chalk.gray('⏳'),
  running:   chalk.yellow('🔄'),
  completed: chalk.green('✅'),
  failed:    chalk.red('❌'),
  stopped:   chalk.gray('🛑'),
  reviewing: chalk.magenta('🔍'),
};

/**
 * @typedef {object} AgentNode
 * @property {string} id
 * @property {string} role        - 'coordinator' | 'lead' | 'builder' | 'reviewer'
 * @property {string} label       - Short display label
 * @property {string} state       - pending | running | completed | failed | stopped | reviewing
 * @property {AgentNode[]} children
 */

/** In-memory tree root */
let _tree = null;
/** Whether we've printed the tree at least once (for in-place redraw) */
let _lineCount = 0;

/**
 * Initialises the tree with a coordinator root node.
 * @param {string} task - The high-level task description (for display).
 */
export function initTree(task) {
  _tree = {
    id: 'coordinator',
    role: 'coordinator',
    label: shortLabel(task),
    state: 'running',
    children: [],
  };
  _lineCount = 0;
}

/**
 * Adds or updates the lead node under the coordinator.
 * @param {string} state - Agent state.
 * @param {string} [label] - Optional display label.
 */
export function setLeadNode(state, label) {
  if (!_tree) return;
  let lead = _tree.children.find(c => c.role === 'lead');
  if (!lead) {
    lead = { id: 'lead', role: 'lead', label: label || 'Planning & assigning tasks', state, children: [] };
    _tree.children.push(lead);
  } else {
    lead.state = state;
    if (label) lead.label = label;
  }
  renderTree();
}

/**
 * Adds or updates a builder node under the lead.
 * @param {string} taskId - Unique task ID.
 * @param {string} state  - Agent state.
 * @param {string} label  - Short task description.
 */
export function setBuilderNode(taskId, state, label) {
  if (!_tree) return;
  let lead = _tree.children.find(c => c.role === 'lead');
  if (!lead) {
    lead = { id: 'lead', role: 'lead', label: 'Planning & assigning tasks', state: 'running', children: [] };
    _tree.children.push(lead);
  }
  let node = lead.children.find(c => c.id === taskId);
  if (!node) {
    node = { id: taskId, role: 'builder', label: label || taskId, state, children: [] };
    lead.children.push(node);
  } else {
    node.state = state;
    if (label) node.label = label;
  }
  renderTree();
}

/**
 * Adds or updates a reviewer node under a builder.
 * @param {string} taskId   - Parent builder task ID.
 * @param {string} state    - Agent state.
 */
export function setReviewerNode(taskId, state) {
  if (!_tree) return;
  const lead = _tree.children.find(c => c.role === 'lead');
  if (!lead) return;
  const builder = lead.children.find(c => c.id === taskId);
  if (!builder) return;
  let reviewer = builder.children.find(c => c.role === 'reviewer');
  if (!reviewer) {
    reviewer = { id: `${taskId}-review`, role: 'reviewer', label: 'Reviewing changes', state, children: [] };
    builder.children.push(reviewer);
  } else {
    reviewer.state = state;
  }
  renderTree();
}

/**
 * Updates the coordinator root state and re-renders.
 * @param {string} state
 */
export function setCoordinatorState(state) {
  if (!_tree) return;
  _tree.state = state;
  renderTree();
}

/**
 * Renders the full tree to stdout, overwriting the previous render.
 */
export function renderTree() {
  if (!_tree) return;

  const lines = buildLines(_tree, '', true);

  // Move cursor up to overwrite previous render
  if (_lineCount > 0) {
    process.stdout.write(`\x1B[${_lineCount}A\x1B[0J`);
  }

  const output = lines.join('\n') + '\n';
  process.stdout.write(output);
  _lineCount = lines.length;
}

/**
 * Prints the final tree (no overwrite after this).
 */
export function finalizeTree() {
  renderTree();
  _lineCount = 0; // Don't overwrite on next call
}

// ─── Internal helpers ────────────────────────────────────────────────────────

function buildLines(node, prefix, isLast) {
  const termWidth = getTerminalWidth();
  const icon = STATE_ICONS[node.state] || chalk.gray('?');
  const roleColor = {
    coordinator: chalk.blue,
    lead:        chalk.cyan,
    builder:     chalk.yellow,
    reviewer:    chalk.magenta,
  }[node.role] || chalk.white;

  const connector = isLast ? '└─' : '├─';
  const prefixStr = prefix ? connector + ' ' : '';

  // Calculate visible overhead to find available width for the label.
  // Emoji icons occupy 2 terminal columns; role tag is plain ASCII.
  const visiblePrefixLen = stripAnsi(prefix).length + stripAnsi(prefixStr).length;
  const roleTag = `[${node.role}]`;
  const overhead = visiblePrefixLen + 2 /* emoji */ + 1 /* space */ + roleTag.length + 1 /* space */;
  const labelWidth = Math.max(10, termWidth - overhead);

  const labelLines = wrapText(node.label, labelWidth);
  const firstLine = `${prefix}${prefixStr}${icon} ${roleColor(roleTag)} ${chalk.white(labelLines[0])}`;
  const lines = [firstLine];

  // Continuation lines are indented to align with the label start.
  if (labelLines.length > 1) {
    const indent = ' '.repeat(overhead);
    for (let i = 1; i < labelLines.length; i++) {
      lines.push(indent + chalk.white(labelLines[i]));
    }
  }

  const childPrefix = prefix + (isLast ? '   ' : '│  ');
  for (let i = 0; i < node.children.length; i++) {
    const child = node.children[i];
    const childIsLast = i === node.children.length - 1;
    lines.push(...buildLines(child, childPrefix, childIsLast));
  }

  return lines;
}

function shortLabel(text) {
  // Normalise whitespace; wrapping in buildLines handles display width.
  return text.trim().replace(/\s+/g, ' ');
}
