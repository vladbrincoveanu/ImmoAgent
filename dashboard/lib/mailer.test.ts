import { describe, expect, it } from '@jest/globals';
import { alertTestEmail, confirmationEmail } from './mailer';

describe('alertTestEmail', () => {
  it('escapes alert keywords before putting them in HTML', () => {
    const html = alertTestEmail(['<script>alert(1)</script>']);

    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).toContain('passende Anzeigen');
    expect(html).not.toContain('Genossenschaft');
  });
});

describe('confirmationEmail', () => {
  it('escapes the email, params, and confirmation URL', () => {
    const html = confirmationEmail(
      '"><img src=x onerror=alert(1)>',
      { '<img src=x>': '"><script>alert(1)</script>' },
      'https://example.test/confirm?token=a&next="unsafe"',
    );

    expect(html).not.toContain('<img');
    expect(html).not.toContain('<script>');
    expect(html).toContain('&quot;&gt;&lt;img src=x onerror=alert(1)&gt;');
    expect(html).toContain('&lt;img src=x&gt;');
    expect(html).toContain('&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(html).toContain('token=a&amp;next=&quot;unsafe&quot;');
  });
});
