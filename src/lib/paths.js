/**
 * @module paths
 * Shared path constants used across ocha.
 * All paths are resolved relative to the current working directory.
 */
import { resolve } from 'path';

/** Root ocha configuration directory (.ocha/) */
export const OCHA_DIR = resolve(process.cwd(), '.ocha');

/** Path to the session status file tracking all tasks */
export const STATUS_FILE = resolve(OCHA_DIR, 'status.json');

/** Path to the session metadata file */
export const SESSION_FILE = resolve(OCHA_DIR, 'session.json');

/** Directory containing agent role prompt markdown files */
export const ROLES_DIR = resolve(OCHA_DIR, 'roles');

/** Directory where git worktrees are created for each agent */
export const WORKTREES_DIR = resolve(process.cwd(), '.ocha-worktrees');

/** Directory where agent log files are written after each run */
export const LOGS_DIR = resolve(OCHA_DIR, 'logs');

/** Path to the agent issues feed file */
export const ISSUES_FILE = resolve(OCHA_DIR, 'issues.json');
