/**
 * @module exec
 * Safe shell execution utilities for ocha.
 * Wraps child_process with proper argument escaping to prevent shell injection,
 * consistent error handling, and configurable defaults.
 */
import { execFileSync, execSync } from 'child_process';

/**
 * Escapes a string for safe use in a shell command.
 * Wraps the value in single quotes and escapes any embedded single quotes.
 *
 * @param {string} arg - The argument to escape.
 * @returns {string} Shell-safe escaped string.
 */
export function shellEscape(arg) {
  return `'${String(arg).replace(/'/g, "'\\''")}'`;
}

/**
 * Executes a git command safely using execFileSync (no shell interpolation).
 *
 * @param {string[]} args - Git subcommand and arguments (e.g. ['worktree', 'add', '-b', branch]).
 * @param {object} [opts] - Options.
 * @param {string} [opts.cwd] - Working directory for the command.
 * @param {boolean} [opts.silent=true] - If true, suppresses stdio (pipes to /dev/null).
 * @param {string} [opts.encoding='utf-8'] - Output encoding.
 * @returns {string} Command stdout as a string.
 * @throws {Error} If the command fails.
 */
export function git(args, opts = {}) {
  const { cwd, silent = true, encoding = 'utf-8' } = opts;
  const stdio = silent ? 'pipe' : 'inherit';
  return execFileSync('git', args, {
    cwd,
    encoding,
    stdio,
    timeout: opts.timeout ?? 60_000,
  });
}

/**
 * Executes a git command safely, returning null on failure instead of throwing.
 *
 * @param {string[]} args - Git subcommand and arguments.
 * @param {object} [opts] - Options (same as `git()`).
 * @returns {string|null} Command stdout, or null if the command failed.
 */
export function gitSafe(args, opts = {}) {
  try {
    return git(args, opts);
  } catch {
    return null;
  }
}

/**
 * Executes an arbitrary command safely using execFileSync (no shell).
 *
 * @param {string} cmd - The command to run.
 * @param {string[]} args - Command arguments.
 * @param {object} [opts] - Options.
 * @param {string} [opts.cwd] - Working directory.
 * @param {string} [opts.encoding='utf-8'] - Output encoding.
 * @param {number} [opts.timeout=60000] - Timeout in ms.
 * @returns {string} Command stdout.
 * @throws {Error} If the command fails.
 */
export function exec(cmd, args, opts = {}) {
  const { cwd, encoding = 'utf-8', timeout = 60_000 } = opts;
  return execFileSync(cmd, args, {
    cwd,
    encoding,
    stdio: 'pipe',
    timeout,
  });
}

/**
 * Executes an arbitrary command, returning null on failure.
 *
 * @param {string} cmd - The command to run.
 * @param {string[]} args - Command arguments.
 * @param {object} [opts] - Options (same as `exec()`).
 * @returns {string|null} Command stdout, or null on failure.
 */
export function execSafe(cmd, args, opts = {}) {
  try {
    return exec(cmd, args, opts);
  } catch {
    return null;
  }
}

/**
 * Executes a shell command string (use only when shell features like pipes are needed).
 * Prefer `exec()` or `git()` for simple commands.
 *
 * @param {string} command - Shell command string.
 * @param {object} [opts] - Options.
 * @param {string} [opts.cwd] - Working directory.
 * @param {string} [opts.encoding='utf-8'] - Output encoding.
 * @returns {string} Command stdout.
 */
export function shell(command, opts = {}) {
  const { cwd, encoding = 'utf-8' } = opts;
  return execSync(command, {
    cwd,
    encoding,
    stdio: ['pipe', 'pipe', 'pipe'],
    timeout: opts.timeout ?? 60_000,
  });
}

/**
 * Executes a shell command, returning null on failure.
 *
 * @param {string} command - Shell command string.
 * @param {object} [opts] - Options (same as `shell()`).
 * @returns {string|null} Command stdout, or null on failure.
 */
export function shellSafe(command, opts = {}) {
  try {
    return shell(command, opts);
  } catch {
    return null;
  }
}
