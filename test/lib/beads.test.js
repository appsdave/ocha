import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { isBeadsInitialized, createBeadsIssue, claimBeadsIssue, closeBeadsIssue, getReadyIssues, ensureDoltServer, pushBeadsData } from '../../src/lib/beads.js';

describe('beads integration', () => {
  describe('isBeadsInitialized', () => {
    it('returns false for a non-existent directory', () => {
      assert.equal(isBeadsInitialized('/tmp/nonexistent-beads-test-dir'), false);
    });

    it('returns a boolean', () => {
      const result = isBeadsInitialized('/tmp');
      assert.equal(typeof result, 'boolean');
    });
  });

  describe('createBeadsIssue', () => {
    it('returns null when bd is not initialized in the directory', () => {
      const id = createBeadsIssue('Test issue', 'Description', { cwd: '/tmp/nonexistent-beads-test-dir' });
      assert.equal(id, null);
    });
  });

  describe('claimBeadsIssue', () => {
    it('returns false for a non-existent issue', () => {
      assert.equal(claimBeadsIssue('fake-id-999', '/tmp'), false);
    });
  });

  describe('closeBeadsIssue', () => {
    it('returns false for a non-existent issue', () => {
      assert.equal(closeBeadsIssue('fake-id-999', 'Done', '/tmp'), false);
    });
  });

  describe('getReadyIssues', () => {
    it('returns empty array when bd is not available', () => {
      const issues = getReadyIssues('/tmp/nonexistent-beads-test-dir');
      assert.deepEqual(issues, []);
    });
  });

  describe('pushBeadsData', () => {
    it('returns false when no beads repo exists', () => {
      assert.equal(pushBeadsData('/tmp/nonexistent-beads-test-dir'), false);
    });
  });

  describe('ensureDoltServer', () => {
    it('does not throw even if dolt is not configured', () => {
      assert.doesNotThrow(() => ensureDoltServer('/tmp/nonexistent-beads-test-dir'));
    });
  });
});
