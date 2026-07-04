import nodemailer from 'nodemailer';

let _transporter: ReturnType<typeof nodemailer.createTransport> | null = null;

function getTransporter() {
  if (_transporter) return _transporter;
  const host = process.env.SMTP_HOST ?? 'smtp.gmail.com';
  const port = Number(process.env.SMTP_PORT ?? 587);
  const user = process.env.SMTP_USER ?? '';
  const pass = process.env.SMTP_PASSWORD ?? '';
  if (!user || !pass) return null;
  _transporter = nodemailer.createTransport({ host, port, secure: port === 465, auth: { user, pass } });
  return _transporter;
}

export async function sendMail(opts: {
  to: string;
  subject: string;
  html: string;
}): Promise<{ ok: boolean; error?: string }> {
  const t = getTransporter();
  if (!t) return { ok: false, error: 'SMTP not configured (set SMTP_USER + SMTP_PASSWORD)' };
  try {
    const from = process.env.SMTP_FROM ?? process.env.SMTP_USER ?? 'alerts@immoscouter.com';
    await t.sendMail({ from, to: opts.to, subject: opts.subject, html: opts.html });
    return { ok: true };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

export function confirmationEmail(email: string, params: Record<string, string>, confirmUrl: string): string {
  const filterLines = Object.entries(params)
    .filter(([, v]) => v)
    .map(([k, v]) => `<li style="margin:4px 0"><b>${k}:</b> ${v}</li>`)
    .join('');

  return `
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#16243a">
      <h2 style="font-size:20px;margin-bottom:8px">Confirm your ImmoScouter alert</h2>
      <p style="color:#5b6b80;font-size:14px;margin-bottom:16px">
        You signed up for <b>${email}</b> to receive listing alerts.
        Click below to confirm and activate your alert.
      </p>
      ${filterLines ? `<ul style="font-size:13px;color:#5b6b80;padding-left:16px;margin-bottom:20px">${filterLines}</ul>` : ''}
      <a href="${confirmUrl}"
        style="display:inline-block;background:#2456e6;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">
        Confirm alert
      </a>
      <p style="font-size:11px;color:#93a1b3;margin-top:24px">
        If you didn't request this, ignore this email.
      </p>
    </div>
  `;
}
