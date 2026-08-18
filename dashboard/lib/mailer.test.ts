import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';

const mockSendMail = jest.fn<() => Promise<void>>();
const mockCreateTransport = jest.fn<() => { sendMail: typeof mockSendMail }>();

jest.mock('nodemailer', () => ({
  __esModule: true,
  default: { createTransport: mockCreateTransport },
}));

import { SMTP_TIMEOUT_MS, alertTestEmail, confirmationEmail, sendMail } from './mailer';

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

describe('sendMail transport deadlines', () => {
  beforeEach(() => {
    mockCreateTransport.mockReset();
    mockSendMail.mockReset().mockResolvedValue(undefined);
    mockCreateTransport.mockReturnValue({ sendMail: mockSendMail });
    process.env.SMTP_USER = 'smtp@example.at';
    process.env.SMTP_PASSWORD = 'password';
  });

  afterEach(() => {
    delete process.env.SMTP_USER;
    delete process.env.SMTP_PASSWORD;
  });

  it('sets connection, greeting, and socket deadlines on the transporter', async () => {
    await expect(sendMail({
      to: 'u@example.at',
      subject: 'Alert test',
      html: '<p>test</p>',
    })).resolves.toEqual({ ok: true });

    expect(mockCreateTransport).toHaveBeenCalledWith(expect.objectContaining({
      connectionTimeout: SMTP_TIMEOUT_MS,
      greetingTimeout: SMTP_TIMEOUT_MS,
      socketTimeout: SMTP_TIMEOUT_MS,
    }));
  });
});
