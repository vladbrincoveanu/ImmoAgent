'use client';

import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip, GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Feature, GeoJsonObject } from 'geojson';
import { MapListing } from '@/lib/types';
import { priceToColor } from '@/lib/heatmap-color';
import { useEffect, useRef, useState, memo, useCallback, ReactNode } from 'react';

const PIN_COLOR_DEFAULT = '#16243a';
const PIN_COLOR_SELECTED = '#2456e6';
const STATION_COLOR = '#1d4ed8';
const SCHOOL_COLOR = '#16a34a';

export interface LayerState {
  listings: boolean;
  stations: boolean;
  schools: boolean;
  heatmap: boolean;
}

function formatPrice(price: number): string {
  if (price >= 1000000) return `${(price / 1000000).toFixed(1)}M`;
  if (price >= 1000) return `${Math.round(price / 1000)}k`;
  return String(price);
}

function createPriceIcon(price: number, selected: boolean): L.DivIcon {
  const label = `€${formatPrice(price)}`;
  const color = selected ? PIN_COLOR_SELECTED : PIN_COLOR_DEFAULT;
  const fontSize = selected ? '10px' : '9px';
  const padding = selected ? '2px 5px' : '1px 4px';
  const border = selected ? '1.5px solid white' : '1px solid white';
  const shadow = selected ? '0 2px 6px rgba(0,0,0,0.35)' : '0 1px 3px rgba(0,0,0,0.3)';
  const h = selected ? 20 : 16;
  return L.divIcon({
    html: `<div style="background:${color};color:white;font-size:${fontSize};font-weight:700;padding:${padding};border-radius:999px;white-space:nowrap;box-shadow:${shadow};border:${border};font-family:system-ui,-apple-system,sans-serif;">${label}</div>`,
    iconSize: [Math.max(40, label.length * 7 + 8), h],
    iconAnchor: [Math.max(40, label.length * 7 + 8) / 2, h / 2],
    className: '',
  });
}

export interface ViewportBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

export interface StationFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: { kind: 'ubahn'; name: string; district?: string };
}

export interface SchoolFeature {
  type: 'Feature';
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: { kind: 'school'; name: string; type?: string };
}

interface MapViewProps {
  listings: MapListing[];
  selectedListingId: string | null;
  layers: LayerState;
  layersPopoverSlot?: ReactNode;
  stationData?: StationFeature[] | null;
  schoolData?: SchoolFeature[] | null;
  onPinClick: (listing: MapListing) => void;
  onMapClick?: () => void;
  onHover?: (id: string) => void;
  onHoverEnd?: () => void;
  onBoundsChange?: (bounds: ViewportBounds) => void;
}

function MapClickHandler({ onMapClick }: { onMapClick?: () => void }) {
  useMapEvents({ click: () => { onMapClick?.(); } });
  return null;
}

function BoundsTracker({ onBoundsChange }: { onBoundsChange?: (bounds: ViewportBounds) => void }) {
  const map = useMap();

  const emit = useCallback(() => {
    if (!onBoundsChange) return;
    // A hidden map (e.g. the mobile instance at desktop width, which is
    // display:none and 0x0) reports degenerate bounds. Both the desktop and
    // mobile MapView instances share one onBoundsChange handler, so letting an
    // unsized map emit would clobber the visible map's bounds and filter every
    // listing out of view. Only a map with real dimensions may report bounds.
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;
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

function SelectionAnimator({
  selectedListingId,
  listings,
}: {
  selectedListingId: string | null;
  listings: MapListing[];
}) {
  const map = useMap();

  // Test hook: expose the live Leaflet map on its container element so E2E
  // tests can read map.getCenter(). Harmless in production.
  useEffect(() => {
    (map.getContainer() as unknown as { __map?: L.Map }).__map = map;
  }, [map]);

  useEffect(() => {
    if (!selectedListingId) return;
    const target = listings.find((l) => l._id === selectedListingId);
    if (!target || !target.coordinates) return;
    // A hidden map (the mobile instance at desktop width, 0x0 / display:none)
    // must never hijack focus — same guard as BoundsTracker (commit 2f32f06).
    const size = map.getSize();
    if (size.x === 0 || size.y === 0) return;
    map.flyTo([target.coordinates.lat, target.coordinates.lon], 16, {
      duration: 1.2,
      easeLinearity: 0.25,
    });
  }, [map, selectedListingId, listings]);

  return null;
}

function MarkerLayer({
  listings,
  selectedListingId,
  showPins,
  onPinClick,
  onHover,
  onHoverEnd,
}: {
  listings: MapListing[];
  selectedListingId: string | null;
  showPins: boolean;
  onPinClick: (listing: MapListing) => void;
  onHover?: (id: string) => void;
  onHoverEnd?: () => void;
}) {
  const map = useMap();
  const markerInstances = useRef<Map<string, L.Marker>>(new Map());
  const layerGroupRef = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    if (!showPins) {
      if (layerGroupRef.current) {
        layerGroupRef.current.clearLayers();
      }
      markerInstances.current.clear();
      return;
    }
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

      const selected = listing._id === selectedListingId;
      const icon = createPriceIcon(listing.price_total ?? 0, selected);

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
  }, [map, listings, selectedListingId, onPinClick, onHover, onHoverEnd, showPins]);

  return null;
}

function StationsLayer({ stations }: { stations: StationFeature[] }) {
  if (!stations || stations.length === 0) return null;
  return (
    <>
      {stations.map((f, i) => {
        const [lon, lat] = f.geometry.coordinates;
        return (
          <CircleMarker
            key={`station-${i}`}
            center={[lat, lon]}
            radius={7}
            pathOptions={{ color: STATION_COLOR, fillColor: STATION_COLOR, fillOpacity: 0.7, weight: 2 }}
            data-testid={`infra-station-${i}`}
            data-infra-kind="ubahn"
            data-infra-name={f.properties.name}
          >
            <Tooltip
              direction="right"
              offset={[6, 0]}
              className="leaflet-infra-label"
              opacity={1}
            >
              <span className="text-[10px] font-semibold" style={{ color: STATION_COLOR }}>
                {f.properties.name}
              </span>
            </Tooltip>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{f.properties.name}</div>
                <div className="text-gray-500 text-xs">
                  U-Bahn station
                  {f.properties.district ? ` · ${f.properties.district}` : ''}
                </div>
                <div className="text-xs text-gray-400 mt-1">transit</div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

function SchoolsLayer({ schools }: { schools: SchoolFeature[] }) {
  if (!schools || schools.length === 0) return null;
  return (
    <>
      {schools.map((f, i) => {
        const [lon, lat] = f.geometry.coordinates;
        return (
          <CircleMarker
            key={`school-${i}`}
            center={[lat, lon]}
            radius={5}
            pathOptions={{ color: SCHOOL_COLOR, fillColor: SCHOOL_COLOR, fillOpacity: 0.7, weight: 2 }}
            data-testid={`infra-school-${i}`}
            data-infra-kind="school"
            data-infra-name={f.properties.name}
          >
            <Tooltip direction="top" offset={[0, -4]} opacity={1}>
              <span className="text-[10px] font-medium">
                {f.properties.name}
                {f.properties.type ? ` · ${f.properties.type}` : ''}
              </span>
            </Tooltip>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{f.properties.name}</div>
                <div className="text-gray-500 text-xs">
                  School
                  {f.properties.type ? ` · ${f.properties.type}` : ''}
                </div>
                <div className="text-xs text-gray-400 mt-1">education</div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

type DistrictStats = Record<string, { avg_price_per_m2: number; count: number }>;

function DistrictHeatmapLayer({ visible }: { visible: boolean }) {
  const [geojson, setGeojson] = useState<GeoJsonObject | null>(null);
  const [stats, setStats] = useState<DistrictStats>({});

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    Promise.all([
      fetch('/vienna-districts.geojson').then((r) => r.json()),
      fetch('/api/district-heatmap').then((r) => r.json()),
    ])
      .then(([gj, s]) => {
        if (cancelled) return;
        setGeojson(gj as GeoJsonObject);
        setStats((s?.districts ?? {}) as DistrictStats);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [visible]);

  if (!visible || !geojson) return null;

  const styleFn = (feature?: Feature): L.PathOptions => {
    const bezirk = feature?.properties?.bezirk as string | undefined;
    const stat = bezirk ? stats[bezirk] : undefined;
    if (!stat) return { fillOpacity: 0, weight: 0, opacity: 0 };
    return { fillColor: priceToColor(stat.avg_price_per_m2), fillOpacity: 0.45, color: '#ffffff', weight: 1 };
  };

  const onEachFeature = (feature: Feature, layer: L.Layer) => {
    const bezirk = feature.properties?.bezirk as string | undefined;
    const stat = bezirk ? stats[bezirk] : undefined;
    if (bezirk && stat) {
      layer.bindTooltip(
        `${bezirk} · Ø €${stat.avg_price_per_m2.toLocaleString('de-AT')}/m² · ${stat.count} listings`,
        { sticky: true, direction: 'top' },
      );
    }
  };

  // key forces GeoJSON to re-apply styles once async stats arrive (it snapshots
  // style/onEachFeature at mount).
  return <GeoJSON key={Object.keys(stats).length} data={geojson} style={styleFn} onEachFeature={onEachFeature} />;
}

export const MapView = memo(function MapView({
  listings,
  selectedListingId,
  layers,
  layersPopoverSlot,
  stationData = null,
  schoolData = null,
  onPinClick,
  onMapClick,
  onHover,
  onHoverEnd,
  onBoundsChange,
}: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const mapRef = useRef<L.Map | null>(null);

  return (
    <div className="relative h-full w-full">
      <MapContainer
        center={viennaCenter}
        zoom={13}
        style={{ height: '100%', width: '100%' }}
        className="rounded-lg"
        ref={mapRef}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
        />

        {layers.heatmap && <DistrictHeatmapLayer visible={layers.heatmap} />}

        <BoundsTracker onBoundsChange={onBoundsChange} />
        <SelectionAnimator selectedListingId={selectedListingId} listings={listings} />
        <MapClickHandler onMapClick={onMapClick} />
        {layers.stations && <StationsLayer stations={stationData ?? []} />}
        {layers.schools && <SchoolsLayer schools={schoolData ?? []} />}
        {layers.listings && (
          <MarkerLayer
            listings={listings}
            selectedListingId={selectedListingId}
            onPinClick={onPinClick}
            onHover={onHover}
            onHoverEnd={onHoverEnd}
            showPins={true}
          />
        )}
      </MapContainer>

      {layersPopoverSlot && (
        <div className="absolute top-3 right-3 z-[1000] pointer-events-none">
          <div className="pointer-events-auto">{layersPopoverSlot}</div>
        </div>
      )}

      {layers.heatmap && (
        <div
          data-testid="heatmap-legend"
          className="absolute bottom-4 left-3 z-[1000] bg-white/95 rounded-lg shadow px-3 py-2 text-[11px]"
        >
          <div className="font-semibold mb-1">Ø €/m²</div>
          <div
            className="h-2 w-32 rounded"
            style={{ background: 'linear-gradient(to right, rgb(26,152,80), rgb(255,221,100), rgb(215,48,39))' }}
          />
          <div className="flex justify-between w-32 mt-0.5">
            <span>3.5k</span>
            <span>8k+</span>
          </div>
        </div>
      )}
    </div>
  );
});
