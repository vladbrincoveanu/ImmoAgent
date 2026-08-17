import { describe, expect, it } from '@jest/globals';
import { alertTestEmail } from './mailer';

describe('alertTestEmail', () => {
  it('escapes alert keywords before putting them in HTML', () => {
    const html = alertTestEmail(['<script>alert(1)</script>']);

    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });
});
