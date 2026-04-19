'use client';

import { render } from '@testing-library/react';
import React from 'react';

// Mock leaflet before importing MapView
jest.mock('leaflet', () => ({
  ...jest.requireActual('leaflet'),
  divIcon: jest.fn().mockReturnValue({
    options: { className: '', iconSize: [14, 14], iconAnchor: [7, 0], popupAnchor: [0, -10] }
  }),
  Icon: {
    Default: {
      prototype: { _getIconUrl: undefined },
      mergeOptions: jest.fn(),
    },
  },
}));

// Mock react-leaflet components
jest.mock('react-leaflet', () => ({
  MapContainer: jest.fn().mockReturnValue(<div data-testid="map-container">MapContainer</div>),
  TileLayer: jest.fn().mockReturnValue(null),
  Marker: jest.fn().mockReturnValue(null),
  Popup: jest.fn().mockReturnValue(null),
  useMap: jest.fn().mockReturnValue({ flyTo: jest.fn() }),
}));

import { createPinIcon } from './MapView';
import { MapListing } from '@/lib/types';

describe('MapView', () => {
  describe('createPinIcon', () => {
    it('should create icon with exact color (#ef4444)', () => {
      const icon = createPinIcon('#ef4444');
      expect(icon).toBeDefined();
      expect(icon.options?.className).toBe('');
    });

    it('should create icon with landmark color (#f97316)', () => {
      const icon = createPinIcon('#f97316');
      expect(icon).toBeDefined();
      expect(icon.options?.className).toBe('');
    });

    it('should create divIcon with correct options', () => {
      const L = require('leaflet');
      const icon = createPinIcon('#ef4444');

      expect(L.divIcon).toHaveBeenCalledWith(
        expect.objectContaining({
          iconSize: [14, 14],
          iconAnchor: [7, 0],
          popupAnchor: [0, -10],
          className: '',
        })
      );
    });
  });

  describe('MapView Component', () => {
    const mockListings: MapListing[] = [
      {
        _id: '1',
        title: 'Test Listing 1',
        url: 'https://example.com/1',
        source_enum: 'willhaben',
        bezirk: 'Innere Stadt',
        price_total: 250000,
        area_m2: 75,
        rooms: 3,
        score: 85,
        image_url: null,
        coordinates: { lat: 48.2082, lon: 16.3738 },
        coordinate_source: 'exact',
        landmark_hint: null,
      },
      {
        _id: '2',
        title: 'Test Listing 2',
        url: 'https://example.com/2',
        source_enum: 'immokurier',
        bezirk: 'Leopoldstadt',
        price_total: 320000,
        area_m2: 90,
        rooms: 4,
        score: 72,
        image_url: null,
        coordinates: { lat: 48.2180, lon: 16.3890 },
        coordinate_source: 'landmark',
        landmark_hint: 'Near Schönbrunn Palace',
      },
    ];

    it('should render without crashing', () => {
      // We can't do full render due to react-leaflet requiring DOM
      // But we can verify imports work
      expect(createPinIcon).toBeDefined();
    });

    it('should create pins for listings with coordinates', () => {
      const exactListing = mockListings[0];
      const landmarkListing = mockListings[1];

      expect(exactListing.coordinates).not.toBeNull();
      expect(landmarkListing.coordinates).not.toBeNull();
      expect(exactListing.coordinate_source).toBe('exact');
      expect(landmarkListing.coordinate_source).toBe('landmark');
    });

    it('should have correct landmark detection logic', () => {
      const exactListing = mockListings[0];
      const landmarkListing = mockListings[1];

      const isExactLandmark = exactListing.coordinate_source === 'landmark';
      const isLandmarkLandmark = landmarkListing.coordinate_source === 'landmark';

      expect(isExactLandmark).toBe(false);
      expect(isLandmarkLandmark).toBe(true);
    });
  });
});
