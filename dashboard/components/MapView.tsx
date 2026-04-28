'use client';

import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { MapPopup } from '@/components/MapPopup';
import { useEffect, useRef, useCallback } from 'react';

// Fix default marker icon (Leaflet + webpack issue)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const EXACT_COLOR = '#ef4444';
const LANDMARK_COLOR = '#f97316';
const DISTRICT_COLOR = '#3B82F6'; // blue — approximate district centroid
const SELECTED_COLOR = '#E07A5F'; // terracotta accent
const SELECTED_PIN_SIZE = 20;

export function createPinIcon(color: string, size: number = 14) {
  const rotation = 'rotate(45deg)';
  return L.divIcon({
    html: `<div style="
      background:${color};
      width:${size}px;height:${size}px;
      border-radius:50% 50% 0;
      transform:${rotation};
      border:2px solid white;
      box-shadow:0 3px 8px rgba(0,0,0,0.4);
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, 0],
    popupAnchor: [0, -(size / 2 + 4)],
    className: '',
  });
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
  const flyTo = useCallback((listing: MapListing) => {
    if (!listing.coordinates) return;
    const currentCenter: [number, number] = [map.getCenter().lat, map.getCenter().lng];
    const currentZoom = map.getZoom();
    previousCenter.current = currentCenter;
    previousZoom.current = currentZoom;
    map.setView([listing.coordinates.lat, listing.coordinates.lon], 16, { animate: false });
  }, [map]);

  useEffect(() => {
    if (!map) return;
    if (selectedListing?.coordinates) {
      flyTo(selectedListing);
    } else if (previousCenter.current) {
      map.setView(previousCenter.current, previousZoom.current, { animate: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedListing]);
  return null;
}

export function MapView({ listings, selectedListing, onPinClick }: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];
  const previousCenter = useRef<[number, number]>(viennaCenter);
  const previousZoom = useRef(13);

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

      {listings.map((listing) => {
        if (!listing.coordinates) return null;
        const isLandmark = listing.coordinate_source === 'landmark';
        const isDistrict = listing.coordinate_source === 'district';
        const isSelected = selectedListing?._id === listing._id;
        const pinColor = isSelected ? SELECTED_COLOR : (isLandmark ? LANDMARK_COLOR : isDistrict ? DISTRICT_COLOR : EXACT_COLOR);
        const pinSize = isSelected ? SELECTED_PIN_SIZE : 14;
        return (
          <Marker
            key={listing._id}
            position={[listing.coordinates.lat, listing.coordinates.lon]}
            icon={createPinIcon(pinColor, pinSize)}
            eventHandlers={{ click: () => onPinClick(listing) }}
          >
            <Popup>
              <MapPopup listing={listing} />
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
