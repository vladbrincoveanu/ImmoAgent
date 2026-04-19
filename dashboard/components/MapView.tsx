'use client';

import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapListing } from '@/lib/types';
import { useEffect } from 'react';

// Fix default marker icon (Leaflet + webpack issue)
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

const EXACT_COLOR = '#ef4444';
const LANDMARK_COLOR = '#f97316';
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

function FlyTo({ listingId, coordinates }: { listingId: string | null; coordinates: { lat: number; lon: number } | null }) {
  const map = useMap();
  useEffect(() => {
    if (coordinates) {
      map.flyTo([coordinates.lat, coordinates.lon], 16, { duration: 0.8 });
    }
  }, [listingId, coordinates, map]);
  return null;
}

interface MapViewProps {
  listings: MapListing[];
  selectedListing: MapListing | null;
  onPinClick: (listing: MapListing) => void;
}

export function MapView({ listings, selectedListing, onPinClick }: MapViewProps) {
  const viennaCenter: [number, number] = [48.2082, 16.3738];

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

      <FlyTo
        listingId={selectedListing?._id ?? null}
        coordinates={selectedListing?.coordinates ?? null}
      />

      {listings.map((listing) => {
        if (!listing.coordinates) return null;
        const isLandmark = listing.coordinate_source === 'landmark';
        const isSelected = selectedListing?._id === listing._id;
        const pinColor = isSelected ? SELECTED_COLOR : (isLandmark ? LANDMARK_COLOR : EXACT_COLOR);
        const pinSize = isSelected ? SELECTED_PIN_SIZE : 14;
        return (
          <Marker
            key={listing._id}
            position={[listing.coordinates.lat, listing.coordinates.lon]}
            icon={createPinIcon(pinColor, pinSize)}
            eventHandlers={{ click: () => onPinClick(listing) }}
          >
            <Popup>
              <div className="text-sm min-w-[160px] font-dm-sans">
                <p className="font-bold text-heading">{listing.title}</p>
                <p className="text-accent font-bold">
                  {listing.price_total ? `€${listing.price_total.toLocaleString()}` : 'N/A'}
                </p>
                <p className="text-gray-500 text-xs">
                  {listing.area_m2}m² · {listing.rooms} rooms · Score {listing.score}
                </p>
                {isLandmark && listing.landmark_hint && (
                  <p className="text-orange-500 text-xs mt-1">~ {listing.landmark_hint}</p>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
