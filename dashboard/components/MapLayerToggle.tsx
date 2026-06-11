'use client';

export type MapLayer = 'ubahn' | 'schools' | 'pins';

interface MapLayerToggleProps {
  layers: Record<MapLayer, boolean>;
  onToggle: (layer: MapLayer) => void;
}

const LABELS: Record<MapLayer, { label: string; color: string }> = {
  ubahn: { label: 'U-Bahn', color: '#1d4ed8' },
  schools: { label: 'Schools', color: '#16a34a' },
  pins: { label: 'Price pins', color: '#ef4444' },
};

export function MapLayerToggle({ layers, onToggle }: MapLayerToggleProps) {
  return (
    <div
      className="absolute top-4 left-4 z-[1100] bg-white rounded-lg shadow-lg p-2 flex flex-col gap-1.5 text-xs"
      data-testid="map-layer-toggle"
    >
      <p className="text-[10px] uppercase tracking-wide text-muted font-semibold px-1 pb-1 border-b border-gray-100">Layers</p>
      {(Object.keys(LABELS) as MapLayer[]).map((layer) => (
        <label key={layer} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 px-1 py-0.5 rounded">
          <input
            type="checkbox"
            checked={layers[layer]}
            onChange={() => onToggle(layer)}
            className="w-3.5 h-3.5 rounded"
            data-testid={`layer-toggle-${layer}`}
          />
          <span className="w-2.5 h-2.5 rounded-full" style={{ background: LABELS[layer].color }} />
          <span className="text-gray-700">{LABELS[layer].label}</span>
        </label>
      ))}
    </div>
  );
}
