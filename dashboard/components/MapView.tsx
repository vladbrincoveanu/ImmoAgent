'use client';

import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { useEffect, useRef, useState, memo, useCallback } from 'react';

const EXACT_COLOR = '#ef4444';
const LANDMARK_COLOR = '#f97316';
const DISTRICT_COLOR = '#3B82F6';
const HIGHLIGHT_COLOR = '#E07A5F';
const UBAHN_COLOR = '#1d4ed8';
const SCHOOL_COLOR = '#16a34a';
const HOVER_COLOR = '#FBBF24';

type PinState = 'exact' | 'landmark' | 'district' | 'highlighted' | 'hovered';
type MarkerTier = 'default' | 'hovered' | 'highlighted';

const TIER_STYLES: Record<MarkerTier, { fontSize: string; padding: string; border: string; shadow: string; h: number }> = {
  default:     { fontSize: '9px',  padding: '1px 4px', border: '1px solid white',   shadow: '0 1px 3px rgba(0,0,0,0.3)',  h: 16 },
  hovered:     { fontSize: '10px', padding: '2px 5px', border: '1.5px solid white', shadow: '0 2px 6px rgba(0,0,0,0.35)', h: 20 },
  highlighted: { fontSize: '12px', padding: '3px 7px', border: '2px solid white',   shadow: '0 3px 8px rgba(0,0,0,0.45)', h: 24 },
};

function formatPrice(price: number): string {
  if (price >= 1000000) return `${(price / 1000000).toFixed(1)}M`;
  if (price >= 1000) return `${Math.round(price / 1000)}k`;
  return String(price);
}

function getPinState(listing: MapListing, highlightedId: string | null, hoveredId: string | null): PinState {
  if (hoveredId === listing._id) return 'hovered';
  if (highlightedId === listing._id) return 'highlighted';
  if (listing.coordinate_source === 'landmark') return 'landmark';
  if (listing.coordinate_source === 'district') return 'district';
  return 'exact';
}

function getPinColor(state: PinState): string {
  switch (state) {
    case 'highlighted': return HIGHLIGHT_COLOR;
    case 'hovered': return HOVER_COLOR;
    case 'landmark': return LANDMARK_COLOR;
    case 'district': return DISTRICT_COLOR;
    default: return EXACT_COLOR;
  }
}

function getTier(state: PinState): MarkerTier {
  if (state === 'highlighted') return 'highlighted';
  if (state === 'hovered') return 'hovered';
  return 'default';
}

function createPriceIcon(price: number, color: string, tier: MarkerTier): L.DivIcon {
  const s = TIER_STYLES[tier];
  const label = `€${formatPrice(price)}`;
  return L.divIcon({
    html: `<div style="background:${color};color:white;font-size:${s.fontSize};font-weight:700;padding:${s.padding};border-radius:999px;white-space:nowrap;box-shadow:${s.shadow};border:${s.border};font-family:system-ui,-apple-system,sans-serif;">${label}</div>`,
    iconSize: [Math.max(40, label.length * 7 + 8), s.h],
    iconAnchor: [Math.max(40, label.length * 7 + 8) / 2, s.h / 2],
    className: '',
  });
}

interface MapViewProps {
  listings: MapListing[];
  highlightedId: string | null;
  hoveredId?: string | null;
  onHover?: (id: string | null) => void;
  onHoverEnd?: () => void;
  onBoundsChange?: (bounds: ViewportBounds) => void;
  onPinClick: (listing: MapListing) => void;
  onMapClick?: () => void;
}

export interface ViewportBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

function MapClickHandler({ onMapClick }: { onMapClick?: () => void }) {
  useMapEvents({ click: () => { onMapClick?.(); } });
  return null;
}

function BoundsTracker({ onBoundsChange }: { onBoundsChange?: (bounds: ViewportBounds) => void }) {
  const map = useMap();

  const emit = useCallback(() => {
    if (!onBoundsChange) return;
    const b = map.getBounds();
    onBoundsChange({
      north: b.getNorth(),
      south: b.getSouth(),
      east: b.getEast(),
      west: b.getWest(),
    });
  }, [map, onBoundsChange]);

  useEffect(() => {
    emit();
    map.on('moveend', emit);
    map.on('zoomend', emit);
    return () => {
      map.off('moveend', emit);
      map.off('zoomend', emit);
    };
  }, [map, emit]);

  return null;
}

function MarkerLayer({
  listings,
  highlightedId,
  hoveredId,
  onPinClick,
  onHover,
  onHoverEnd,
}: {
  listings: MapListing[];
  highlightedId: string | null;
  hoveredId?: string | null;
  onPinClick: (listing: MapListing) => void;
  onHover?: (id: string) => void;
  onHoverEnd?: () => void;
}) {
  const map = useMap();
  const markerInstances = useRef<Map<string, L.Marker>>(new Map());
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!layerGroupRef.current) {
      layerGroupRef.current = L.layerGroup().addTo(map);
    }
    const layer = layerGroupRef.current;

    const toRemove: string[] = [];
    markerInstances.current.forEach((_, id) => {
      if (!listings.find((l) => l._id === id)) {
        toRemove.push(id);
      }
    });
    toRemove.forEach((id) => {
      const marker = markerInstances.current.get(id);
      if (marker) {
        layer.removeLayer(marker);
        markerInstances.current.delete(id);
      }
    });

    listings.forEach((listing) => {
      if (!listing.coordinates) return;

      const state = getPinState(listing, highlightedId ?? null, hoveredId ?? null);
      const color = getPinColor(state);
      const tier = getTier(state);
      const icon = createPriceIcon(listing.price_total ?? 0, color, tier);

      let marker = markerInstances.current.get(listing._id);
      if (marker) {
        marker.setLatLng([listing.coordinates.lat, listing.coordinates.lon]);
        marker.setIcon(icon);
      } else {
        marker = L.marker([listing.coordinates.lat, listing.coordinates.lon], { icon });
        marker.on('click', () => onPinClick(listing));
        marker.on('mouseover', () => onHover?.(listing._id));
        marker.on('mouseout', () => onHoverEnd?.());
        layer.addLayer(marker);
        markerInstances.current.set(listing._id, marker);
      }
    });
  }, [map, listings, highlightedId, hoveredId, onPinClick, onHover, onHoverEnd]);

  return null;
}

interface InfraFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: { kind: 'ubahn' | 'school'; name: string; type?: string; district?: string };
}

function InfrastructureLayer({ show }: { show: boolean }) {
  const [features, setFeatures] = useState<InfraFeature[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!show) {
      setFeatures([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetch('/api/geo/infrastructure')
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled && d?.features) setFeatures(d.features);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [show]);

  if (!show || loading || features.length === 0) return null;

  return (
    <>
      {features.map((f, i) => {
        const [lon, lat] = f.geometry.coordinates;
        const color = f.properties.kind === 'ubahn' ? UBAHN_COLOR : SCHOOL_COLOR;
        const radius = f.properties.kind === 'ubahn' ? 7 : 5;
        const isUbahn = f.properties.kind === 'ubahn';
        const tooltipText = isUbahn
          ? `U-Bahn ${f.properties.name}${f.properties.district ? ` (${f.properties.district})` : ''}`
          : `School: ${f.properties.name}`;
        return (
          <CircleMarker
            key={`${f.properties.kind}-${i}`}
            center={[lat, lon]}
            radius={radius}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.7, weight: 2 }}
            data-testid={`infra-${f.properties.kind}-${i}`}
            data-infra-kind={f.properties.kind}
            data-infra-name={f.properties.name}
          >
            {isUbahn && (
              <Tooltip
                permanent
                direction="right"
                offset={[6, 0]}
                className="leaflet-infra-label"
                opacity={1}
                sticky
              >
                <span className="text-[10px] font-semibold text-[#1d4ed8]">
                  {f.properties.name}
                </span>
              </Tooltip>
            )}
            {!isUbahn && (
              <Tooltip direction="top" offset={[0, -4]} opacity={1}>
                <span className="text-[10px] font-medium">
                  {f.properties.name}
                  {f.properties.type ? ` · ${f.properties.type}` : ''}
                </span>
              </Tooltip>
            )}
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{f.properties.name}</div>
                <div className="text-gray-500 text-xs">
                  {f.properties.kind === 'ubahn' ? 'U-Bahn station' : 'School'}
                  {f.properties.district ? ` · ${f.properties.district}` : ''}
                  {f.properties.type ? ` · ${f.properties.type}` : ''}
                </div>
                <div className="text-xs text-gray-400 mt-1">
                  {f.properties.kind === 'ubahn' ? '🚇 transit' : '🏫 education'}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

export const MapView = memo(function MapView({
  listings,
  highlightedId,
  hoveredId,
  onHover,
  onHoverEnd,
  onPinClick,
  onMapClick,
  onBoundsChange,
  showInfrastructure = true,
}: {
  listings: MapListing[];
  highlightedId?: string | null;
  hoveredId?: string | null;
  onHover?: (id: string) => void;
  onHoverEnd?: () => void;
  onPinClick?: (id: string) => void;
  onMapClick?: () => void;
  onBoundsChange?: (bounds: { north: number; south: number; east: number; west: number }) => void;
  showInfrastructure?: boolean;
}) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const mapRef = useRef<L.Map | null>(null);

  return (
    <MapContainer
      center={viennaCenter}
      zoom={13}
      style={{ height: '100%', width: '100%' }}
      className="rounded-lg"
      ref={mapRef}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <BoundsTracker onBoundsChange={onBoundsChange} />
      <MapClickHandler onMapClick={onMapClick} />
      <InfrastructureLayer show={showInfrastructure} />
      <MarkerLayer
        listings={listings}
        highlightedId={highlightedId ?? null}
        hoveredId={hoveredId ?? null}
        onPinClick={(l) => onPinClick?.(l._id)}
        onHover={onHover}
        onHoverEnd={onHoverEnd}
      />
    </MapContainer>
  );
});