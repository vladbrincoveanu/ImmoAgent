import { MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { useEffect, useRef, memo, useCallback } from 'react';

const EXACT_COLOR = '#ef4444';
const LANDMARK_COLOR = '#f97316';
const DISTRICT_COLOR = '#3B82F6';
const HIGHLIGHT_COLOR = '#E07A5F';
const HOVER_COLOR = '#FBBF24';
const EXACT_SIZE = 14;
const LANDMARK_SIZE = 14;
const DISTRICT_SIZE = 14;
const HIGHLIGHT_SIZE = 20;
const HOVER_SIZE = 18;

function formatPrice(price: number): string {
  if (price >= 1000000) return `${(price / 1000000).toFixed(1)}M`;
  if (price >= 1000) return `${Math.round(price / 1000)}k`;
  return String(price);
}

function createPriceIcon(price: number, color: string, size: number): L.DivIcon {
  return L.divIcon({
    html: `<div style="background:${color};color:white;font-size:10px;font-weight:700;padding:2px 5px;border-radius:999px;white-space:nowrap;box-shadow:0 2px 6px rgba(0,0,0,0.35);border:1.5px solid white;font-family:system-ui,-apple-system,sans-serif;">€${formatPrice(price)}</div>`,
    iconSize: [size * 3, size * 1.5],
    iconAnchor: [size * 1.5, size * 0.75],
    className: '',
  });
}

type PinState = 'exact' | 'landmark' | 'district' | 'highlighted' | 'hovered';

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

function getPinSize(state: PinState): number {
  switch (state) {
    case 'highlighted': return HIGHLIGHT_SIZE;
    case 'hovered': return HOVER_SIZE;
    case 'landmark': return LANDMARK_SIZE;
    case 'district': return DISTRICT_SIZE;
    default: return EXACT_SIZE;
  }
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

export const MapView = memo(function MapView({
  listings,
  highlightedId,
  hoveredId,
  onHover,
  onHoverEnd,
  onBoundsChange,
  onPinClick,
  onMapClick,
}: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const markerLayerRef = useRef<L.LayerGroup | null>(null);
  const markerInstances = useRef<Map<string, L.Marker>>(new Map());
  const prevHoveredIdRef = useRef<string | null>(null);
  const prevHighlightedIdRef = useRef<string | null>(null);
  const mapRef = useRef<L.Map | null>(null);

  const updatePin = useCallback((listing: MapListing, marker: L.Marker) => {
    const state = getPinState(listing, highlightedId ?? null, hoveredId ?? null);
    const color = getPinColor(state);
    const size = getPinSize(state);
    const icon = createPriceIcon(listing.price_total ?? 0, color, size);
    marker.setIcon(icon);
  }, [highlightedId, hoveredId]);

  useEffect(() => {
    if (!mapRef.current) return;
    const layer = markerLayerRef.current;
    if (!layer) return;

    const prevHovered = prevHoveredIdRef.current;
    const currHovered = hoveredId ?? null;

    if (prevHovered && prevHovered !== currHovered) {
      const marker = markerInstances.current.get(prevHovered);
      const listing = listings.find((l) => l._id === prevHovered);
      if (marker && listing) updatePin(listing, marker);
    }
    if (currHovered && currHovered !== prevHovered) {
      const marker = markerInstances.current.get(currHovered);
      const listing = listings.find((l) => l._id === currHovered);
      if (marker && listing) updatePin(listing, marker);
    }
    prevHoveredIdRef.current = currHovered;
  }, [hoveredId, listings, updatePin]);

  useEffect(() => {
    if (!mapRef.current) return;
    const layer = markerLayerRef.current;
    if (!layer) return;

    const prevHighlighted = prevHighlightedIdRef.current;
    const currHighlighted = highlightedId ?? null;

    if (prevHighlighted && prevHighlighted !== currHighlighted) {
      const marker = markerInstances.current.get(prevHighlighted);
      const listing = listings.find((l) => l._id === prevHighlighted);
      if (marker && listing) updatePin(listing, marker);
    }
    if (currHighlighted && currHighlighted !== prevHighlighted) {
      const marker = markerInstances.current.get(currHighlighted);
      const listing = listings.find((l) => l._id === currHighlighted);
      if (marker && listing) updatePin(listing, marker);
    }
    prevHighlightedIdRef.current = currHighlighted;
  }, [highlightedId, listings, updatePin]);

  const handleMarkerMouseOver = useCallback((listingId: string) => {
    onHover?.(listingId);
  }, [onHover]);

  const handleMarkerMouseOut = useCallback(() => {
    onHoverEnd?.();
  }, [onHoverEnd]);

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

      <useMapEvents
        click={() => { onMapClick?.(); }}
      />

      <TileLayer /> {/* extra TileLayer for layer container */}

      <TileLayer /> {/* extra TileLayer for layer container */}

      <L.LayerGroup ref={markerLayerRef}>
        {listings.map((listing) => {
          if (!listing.coordinates) return null;

          const state = getPinState(listing, highlightedId ?? null, hoveredId ?? null);
          const color = getPinColor(state);
          const size = getPinSize(state);
          const icon = createPriceIcon(listing.price_total ?? 0, color, size);

          const marker = L.marker([listing.coordinates.lat, listing.coordinates.lon], { icon });

          marker.on('click', () => onPinClick(listing));
          marker.on('mouseover', () => handleMarkerMouseOver(listing._id));
          marker.on('mouseout', () => handleMarkerMouseOut());

          markerInstances.current.set(listing._id, marker);

          return marker;
        })}
      </L.LayerGroup>
    </MapContainer>
  );
});