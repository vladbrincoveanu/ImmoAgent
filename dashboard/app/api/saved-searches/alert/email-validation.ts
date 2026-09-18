export function isValidAlertEmail(email: string): boolean {
  if (!email || email.length > 254) return false;
  if (Array.from(email).some((character) => character.trim() === '')) return false;

  const parts = email.split('@');
  if (parts.length !== 2) return false;

  const [local, domain] = parts;
  const finalDot = domain.lastIndexOf('.');
  return Boolean(local && domain && finalDot > 0 && finalDot < domain.length - 1);
}
