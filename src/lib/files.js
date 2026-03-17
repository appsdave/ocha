/**
 * @module files
 * Centralized file management utilities for ocha.
 * Provides safe, atomic, and error-tolerant file operations
 * with automatic directory creation and consistent error handling.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync, renameSync, readdirSync, statSync } from 'fs';
import { dirname, resolve, join } from 'path';
import { randomBytes } from 'crypto';

/**
 * Ensures a directory exists, creating it (and parents) if necessary.
 * @param {string} dirPath - Absolute path to the directory.
 */
export function ensureDir(dirPath) {
  if (!existsSync(dirPath)) {
    mkdirSync(dirPath, { recursive: true });
  }
}

/**
 * Ensures the parent directory of a file path exists.
 * @param {string} filePath - Absolute path to the file.
 */
export function ensureParentDir(filePath) {
  ensureDir(dirname(filePath));
}

/**
 * Reads a text file safely.
 * @param {string} filePath - Absolute path to the file.
 * @param {string} [fallback=null] - Value to return if file doesn't exist or read fails.
 * @returns {string|null} File contents as a string, or fallback on failure.
 */
export function readText(filePath, fallback = null) {
  if (!existsSync(filePath)) return fallback;
  try {
    return readFileSync(filePath, 'utf-8');
  } catch {
    return fallback;
  }
}

/**
 * Writes a text file safely, ensuring the parent directory exists.
 * @param {string} filePath - Absolute path to the file.
 * @param {string} content - Text content to write.
 */
export function writeText(filePath, content) {
  ensureParentDir(filePath);
  writeFileSync(filePath, content, 'utf-8');
}

/**
 * Reads and parses a JSON file safely.
 * Returns the fallback value if the file doesn't exist or contains invalid JSON.
 * @param {string} filePath - Absolute path to the JSON file.
 * @param {*} [fallback=null] - Value to return on failure.
 * @returns {*} Parsed JSON data, or fallback on failure.
 */
export function readJSON(filePath, fallback = null) {
  if (!existsSync(filePath)) return fallback;
  try {
    const raw = readFileSync(filePath, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

/**
 * Writes a JSON file atomically — writes to a temporary file first, then
 * renames it into place. This prevents partial/corrupt files on crash.
 * Ensures the parent directory exists before writing.
 * @param {string} filePath - Absolute path to the JSON file.
 * @param {*} data - Data to serialize as JSON.
 */
export function writeJSON(filePath, data) {
  ensureParentDir(filePath);
  const tmpFile = filePath + '.tmp.' + randomBytes(4).toString('hex');
  try {
    writeFileSync(tmpFile, JSON.stringify(data, null, 2), 'utf-8');
    renameSync(tmpFile, filePath);
  } catch (err) {
    // Clean up temp file on failure
    try { rmSync(tmpFile, { force: true }); } catch {}
    throw err;
  }
}

/**
 * Safely deletes a file or directory. Does nothing if the path doesn't exist.
 * @param {string} targetPath - Absolute path to the file or directory.
 * @param {object} [opts] - Options.
 * @param {boolean} [opts.recursive=false] - Whether to remove directories recursively.
 */
export function safeDelete(targetPath, opts = {}) {
  if (!existsSync(targetPath)) return;
  try {
    rmSync(targetPath, { recursive: !!opts.recursive, force: true });
  } catch {
    // Silently ignore deletion errors
  }
}

/**
 * Removes all contents within a directory without removing the directory itself.
 * @param {string} dirPath - Absolute path to the directory to clean.
 */
export function cleanDir(dirPath) {
  if (!existsSync(dirPath)) return;
  const entries = readdirSync(dirPath);
  for (const entry of entries) {
    safeDelete(join(dirPath, entry), { recursive: true });
  }
}

/**
 * Checks whether a path exists.
 * @param {string} targetPath - Path to check.
 * @returns {boolean} True if the path exists.
 */
export function pathExists(targetPath) {
  return existsSync(targetPath);
}

/**
 * Lists files in a directory (non-recursive).
 * Returns an empty array if the directory doesn't exist.
 * @param {string} dirPath - Absolute path to the directory.
 * @returns {string[]} Array of filenames in the directory.
 */
export function listFiles(dirPath) {
  if (!existsSync(dirPath)) return [];
  try {
    return readdirSync(dirPath);
  } catch {
    return [];
  }
}

/**
 * Returns basic info about a file or directory.
 * @param {string} targetPath - Path to inspect.
 * @returns {{ exists: boolean, isFile?: boolean, isDirectory?: boolean, size?: number } | null}
 */
export function fileInfo(targetPath) {
  if (!existsSync(targetPath)) return { exists: false };
  try {
    const stats = statSync(targetPath);
    return {
      exists: true,
      isFile: stats.isFile(),
      isDirectory: stats.isDirectory(),
      size: stats.size,
    };
  } catch {
    return { exists: false };
  }
}
