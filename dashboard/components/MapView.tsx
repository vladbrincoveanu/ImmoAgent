import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { MapPopup } from '@/components/MapPopup';
import { useEffect, useRef, memo } from 'react';

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const EXACT_COLOR = '#ef4444';
const LANDMARK_COLOR = '#f97316';
const DISTRICT_COLOR = '#3B82F6';
const SELECTED_COLOR = '#E07A5F';
const SELECTED_PIN_SIZE = 20;

export function createPinIcon(color: string, size: number = 14) {
  const rotation = 'rotate(45deg)';
  return L.divIcon({
    html: `<div style="background:${color};width:${size}px;height:${size}px;border-radius:50% 50% 0;transform:${rotation};border:2px solid white;box-shadow:0 3px 8px rgba(0,0,0,0.4);"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, 0],
    popupAnchor: [0, -(size / 2 + 4)],
    className: '',
  });
}

function defaultIcon(listing: MapListing): L.DivIcon {
  const isLandmark = listing.coordinate_source === 'landmark';
  const isDistrict = listing.coordinate_source === 'district';
  const color = isLandmark ? LANDMARK_COLOR : isDistrict ? DISTRICT_COLOR : EXACT_COLOR;
  return createPinIcon(color, 14);
}

interface MapViewProps {
  listings: MapListing[];
  selectedListing: MapListing | null;
  onPinClick: (listing: MapListing) => void;
  onMapClick?: () => void;
}

function MapClickHandler({ onMapClick }: { onMapClick?: () => void }) {
  const wasDragged = useRef(false);
  useMapEvents({
    mousedown: () => { wasDragged.current = false; },
    mousemove: () => { wasDragged.current = true; },
    click: () => {
      if (!wasDragged.current) onMapClick?.();
    },
  });
  return null;
}

function MapViewController({
  selectedListing,
  savedViewport,
}: {
  selectedListing: MapListing | null;
  savedViewport: React.MutableRefObject<{ lat: number; lng: number; zoom: number } | null>;
}) {
  const map = useMap();
  const prevSelectedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!map) return;

    const prevId = prevSelectedIdRef.current;
    const currentId = selectedListing?._id ?? null;

    if (currentId !== prevId) {
      prevSelectedIdRef.current = currentId;

      if (currentId === null) {
        if (savedViewport.current) {
          const { lat, lng, zoom } = savedViewport.current;
          map.stop();
          map.setView([lat, lng], zoom, { animate: true, duration: 0.3 });
          savedViewport.current = null;
        }
      } else if (selectedListing?.coordinates) {
        if (!savedViewport.current) {
          const center = map.getCenter();
          const zoom = map.getZoom();
          savedViewport.current = { lat: center.lat, lng: center.lng, zoom };
        }
        const [lat, lon] = [selectedListing.coordinates.lat, selectedListing.coordinates.lon];
        const center = map.getCenter();
        const zoom = map.getZoom();
        if (Math.abs(center.lat - lat) > 0.00001 || Math.abs(center.lng - lon) > 0.00001 || zoom !== 16) {
          map.stop();
          map.setView([lat, lon], 16, { animate: true, duration: 0.3 });
        }
      }
    }
  }, [selectedListing, map, savedViewport]);

  return null;
}

export const MapView = memo(function MapView({ listings, selectedListing, onPinClick, onMapClick }: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const savedViewport = useRef<{ lat: number; lng: number; zoom: number } | null>(null);
  const markerRefs = useRef<Map<string, L.Marker>>(new Map());
  const prevSelectedIdRef = useRef<string | null>(null);

  const selectedId = selectedListing?._id ?? null;

  const markerNodes = listings.map((listing) => {
    if (!listing.coordinates) return null;
    return (
      <Marker
        key={listing._id}
        position={[listing.coordinates.lat, listing.coordinates.lon]}
        icon={defaultIcon(listing)}
        eventHandlers={{ click: () => onPinClick(listing) }}
        ref={(marker: L.Marker | null) => {
          if (marker) {
            markerRefs.current.set(listing._id, marker);
          } else {
            markerRefs.current.delete(listing._id);
          }
        }}
      >
        <Popup>
          <MapPopup listing={listing} />
        </Popup>
      </Marker>
    );
  });

  useEffect(() => {
    const newSelectedId = selectedListing?._id ?? null;
    const prevSelectedId = prevSelectedIdRef.current;

    if (prevSelectedId && prevSelectedId !== newSelectedId) {
      const prevMarker = markerRefs.current.get(prevSelectedId);
      if (prevMarker) {
        const prevListing = listings.find((l) => l._id === prevSelectedId);
        if (prevListing) prevMarker.setIcon(defaultIcon(prevListing));
      }
    }

    if (newSelectedId) {
      const newMarker = markerRefs.current.get(newSelectedId);
      if (newMarker) {
        newMarker.setIcon(createPinIcon(SELECTED_COLOR, SELECTED_PIN_SIZE));
      }
    }

    prevSelectedIdRef.current = newSelectedId;
  }, [selectedListing, listings]);

  return (
    <MapContainer
      center={viennaCenter}
      zoom={13}
      style={{ height: '100%', width: '100%' }}
      className="rounded-lg"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <MapClickHandler onMapClick={onMapClick} />

      <MapViewController
        selectedListing={selectedListing}
        savedViewport={savedViewport}
      />

      {markerNodes}
    </MapContainer>
  );
});