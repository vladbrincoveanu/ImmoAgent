export function MapLegend() {
  return (
    <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow-lg px-3 py-2 text-xs z-[1000]">
      <p className="font-semibold mb-2">Legend</p>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm transform rotate-45 bg-red-500"></div>
          <span>Exact coordinates</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-sm transform rotate-45 bg-orange-500"></div>
          <span>District + landmark</span>
        </div>
      </div>
    </div>
  );
}
