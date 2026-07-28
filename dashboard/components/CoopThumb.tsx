'use client';

import { useState } from 'react';

/** Thumbnail for one co-op row.
 *
 * A plain <img>, not next/image: the sources are ~30 different Bauträger
 * domains, each of which would need its own next.config remote-pattern entry
 * (ListingCard makes the same call). Builder images are hotlinked, so a 403 or
 * a hotlink-protected host is expected — onError swaps in the placeholder
 * rather than leaving a broken-image glyph.
 *
 * Client component because /coop is a Server Component and onError needs a
 * client boundary. */
export function CoopThumb({ src, bezirk }: { src: string | null; bezirk: string | null }) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        data-testid="coop-thumb-fallback"
        aria-hidden="true"
        className="flex h-[72px] w-24 shrink-0 flex-col items-center justify-center rounded-lg bg-[#F2EFEC] text-[#6B6B6B]"
      >
        <span className="text-lg leading-none">🏘️</span>
        {bezirk && <span className="mt-1 text-[10px] font-medium">{bezirk}</span>}
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      data-testid="coop-thumb"
      src={src}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-[72px] w-24 shrink-0 rounded-lg object-cover"
    />
  );
}
