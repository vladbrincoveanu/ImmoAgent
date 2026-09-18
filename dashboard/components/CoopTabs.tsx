/** Sub-navigation shared by the two co-op feeds.
 *
 * Both feeds used to be separate top-level nav entries, which read as two
 * unrelated products. They are the same hunt — a co-op flat in Vienna — split
 * only by who hands the keys over, so the header carries ONE "Co-op" tab and
 * the split lives here, inside that tab. */
export function CoopTabs({ active }: { active: 'offers' | 'private' }) {
  const tabs = [
    { key: 'offers', href: '/coop', label: 'Developer offers' },
    { key: 'private', href: '/coop/private', label: 'Private transfers' },
  ] as const;

  return (
    <nav
      data-testid="coop-tabs"
      aria-label="Co-op feeds"
      className="mb-4 flex gap-1 border-b border-[#E8E4E0]"
    >
      {tabs.map((t) => {
        const on = t.key === active;
        return (
          <a
            key={t.key}
            href={t.href}
            data-testid={`coop-tab-${t.key}`}
            aria-current={on ? 'page' : undefined}
            className={
              on
                ? 'border-b-2 border-[#3D405B] px-3 py-2 text-sm font-semibold text-[#3D405B]'
                : 'border-b-2 border-transparent px-3 py-2 text-sm font-medium text-[#6B6B6B] hover:text-[#3D405B]'
            }
          >
            {t.label}
          </a>
        );
      })}
    </nav>
  );
}
