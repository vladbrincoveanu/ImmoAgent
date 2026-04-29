import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { MapPopup } from '@/components/MapPopup';
import { useEffect, useRef, useCallback, memo } from 'react';

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
}

function MapViewController({
  selectedListing,
  previousCenter,
  previousZoom,
}: {
  selectedListing: MapListing | null;
  previousCenter: React.MutableRefObject<[number, number]>;
  previousZoom: React.MutableRefObject<number>;
}) {
  const map = useMap();
  const prevSelectedIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!map) return;

    const currentId = selectedListing?._id ?? null;
    if (currentId === prevSelectedIdRef.current) return;
    prevSelectedIdRef.current = currentId;

    if (selectedListing?.coordinates) {
      const [lat, lon] = [selectedListing.coordinates.lat, selectedListing.coordinates.lon];
      const currCenter = map.getCenter();
      const currZoom = map.getZoom();
      if (currCenter.lat !== lat || currCenter.lng !== lon || currZoom !== 16) {
        previousCenter.current = [currCenter.lat, currCenter.lng];
        previousZoom.current = currZoom;
        map.setView([lat, lon], 16, { animate: false });
      }
    } else if (previousCenter.current) {
      map.setView(previousCenter.current, previousZoom.current, { animate: false });
    }
  }, [selectedListing, map, previousCenter, previousZoom]);

  return null;
}

export const MapView = memo(function MapView({ listings, selectedListing, onPinClick }: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const previousCenter = useRef<[number, number]>(viennaCenter);
  const previousZoom = useRef(13);
  const markerRefs = useRef<Map<string, L.Marker>>(new Map());
  const prevSelectedIdRef = useRef<string | null>(null);

  const selectedId = selectedListing?._id ?? null;

  // Stable marker rendering — ONLY recreated when listings or onPinClick change.
  // selectedListing is NOT a dep — icons are updated imperatively via setIcon.
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

  // Imperatively update marker icons when selection changes.
  // This avoids recreating all marker DOM elements on every pin click.
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

      <MapViewController
        selectedListing={selectedListing}
        previousCenter={previousCenter}
        previousZoom={previousZoom}
      />

      {markerNodes}
    </MapContainer>
  );
});