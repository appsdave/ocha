import { resolve } from 'path';

export const OCHA_DIR = resolve(process.cwd(), '.ocha');
export const STATUS_FILE = resolve(OCHA_DIR, 'status.json');
export const SESSION_FILE = resolve(OCHA_DIR, 'session.json');
export const ROLES_DIR = resolve(OCHA_DIR, 'roles');
export const WORKTREES_DIR = resolve(process.cwd(), '.ocha-worktrees');
