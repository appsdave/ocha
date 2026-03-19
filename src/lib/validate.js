/**
 * @module validate
 * Input validation utilities for ocha CLI commands and internal APIs.
 * Provides reusable validators with clear error messages.
 */

/**
 * Validates that a branch name is safe for git operations.
 * Rejects names with shell metacharacters, spaces, or control characters.
 *
 * @param {string} branch - Branch name to validate.
 * @returns {string} The validated branch name.
 * @throws {Error} If the branch name is invalid.
 */
export function validateBranchName(branch) {
  if (!branch || typeof branch !== 'string') {
    throw new Error('Branch name is required');
  }
  const trimmed = branch.trim();
  if (!trimmed) {
    throw new Error('Branch name cannot be empty');
  }
  // Git branch name rules: no space, ~, ^, :, ?, *, [, \, control chars, ".."
  if (/[\s~^:?*[\]\\]/.test(trimmed) || trimmed.includes('..')) {
    throw new Error(`Invalid branch name: "${trimmed}" — contains forbidden characters`);
  }
  if (trimmed.startsWith('-') || trimmed.startsWith('/') || trimmed.endsWith('/') || trimmed.endsWith('.lock')) {
    throw new Error(`Invalid branch name: "${trimmed}" — invalid start/end`);
  }
  return trimmed;
}

/**
 * Validates that maxAgents is a positive integer.
 *
 * @param {string|number} value - The value to validate.
 * @returns {number} The parsed positive integer.
 * @throws {Error} If the value is not a valid positive integer.
 */
export function validateMaxAgents(value) {
  const n = typeof value === 'string' ? parseInt(value, 10) : value;
  if (!Number.isFinite(n) || n < 1) {
    throw new Error(`Invalid max-agents value: "${value}" — must be a positive integer`);
  }
  return n;
}

/**
 * Validates that a task description is non-empty.
 *
 * @param {string} task - Task description to validate.
 * @returns {string} The trimmed task description.
 * @throws {Error} If the task is empty or not a string.
 */
export function validateTask(task) {
  if (!task || typeof task !== 'string') {
    throw new Error('Task description is required');
  }
  const trimmed = task.trim();
  if (!trimmed) {
    throw new Error('Task description cannot be empty');
  }
  return trimmed;
}

/**
 * Validates that a priority value is in the valid range (0-4).
 *
 * @param {string|number} value - The priority value.
 * @returns {number} The validated priority.
 * @throws {Error} If the priority is out of range.
 */
export function validatePriority(value) {
  const n = typeof value === 'string' ? parseInt(value, 10) : value;
  if (!Number.isFinite(n) || n < 0 || n > 4) {
    throw new Error(`Invalid priority: "${value}" — must be 0-4`);
  }
  return n;
}
