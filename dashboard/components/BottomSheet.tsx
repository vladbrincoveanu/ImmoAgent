'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';

export type SheetState = 'collapsed' | 'half' | 'full';

interface BottomSheetProps {
  children: React.ReactNode;
  snapPoints: [collapsed: number, half: number, full: number];
  defaultState?: SheetState;
  onStateChange?: (state: SheetState) => void;
  count?: number;
}

const STATE_KEYS: SheetState[] = ['collapsed', 'half', 'full'];

export function BottomSheet({
  children,
  snapPoints,
  defaultState = 'half',
  onStateChange,
  count,
}: BottomSheetProps) {
  const [state, setState] = useState<SheetState>(defaultState);
  const [translateY, setTranslateY] = useState(0);
  const sheetRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef(0);
  const dragStartTranslate = useRef(0);
  const isDragging = useRef(false);

  const defaultHeights: Record<SheetState, number> = {
    collapsed: snapPoints[0],
    half: snapPoints[1],
    full: snapPoints[2],
  };

  useEffect(() => {
    const height = defaultHeights[defaultState];
    setTranslateY(window.innerHeight - height);
  }, [defaultState]);

  const snapToNearest = useCallback((currentY: number) => {
    const windowH = window.innerHeight;
    const heights = [snapPoints[0], snapPoints[1], snapPoints[2]].map((h) => windowH - h);
    let nearestIdx = 0;
    let nearestDist = Infinity;
    heights.forEach((targetY, idx) => {
      const dist = Math.abs(currentY - targetY);
      if (dist < nearestDist) {
        nearestDist = dist;
        nearestIdx = idx;
      }
    });
    const newState: SheetState = STATE_KEYS[nearestIdx];
    setState(newState);
    setTranslateY(heights[nearestIdx]);
    onStateChange?.(newState);
  }, [snapPoints, onStateChange]);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    isDragging.current = true;
    dragStartY.current = e.clientY;
    dragStartTranslate.current = translateY;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [translateY]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging.current) return;
    const delta = dragStartY.current - e.clientY;
    const newTranslate = Math.max(
      window.innerHeight - snapPoints[2],
      Math.min(window.innerHeight - snapPoints[0], dragStartTranslate.current + delta)
    );
    setTranslateY(newTranslate);
  }, [snapPoints]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!isDragging.current) return;
    isDragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    snapToNearest(translateY);
  }, [translateY, snapToNearest]);

  const handleBackdropClick = useCallback(() => {
    setState('collapsed');
    setTranslateY(window.innerHeight - snapPoints[0]);
    onStateChange?.('collapsed');
  }, [snapPoints, onStateChange]);

  const sheetStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    height: snapPoints[2],
    transform: `translateY(${translateY}px)`,
    transition: isDragging.current ? 'none' : 'transform 200ms ease-out',
    zIndex: 1000,
    display: 'flex',
    flexDirection: 'column',
  };

  return (
    <>
      {state !== 'collapsed' && (
        <div
          className="fixed inset-0 bg-black/10 z-50 md:hidden"
          onClick={handleBackdropClick}
        />
      )}

      <div
        ref={sheetRef}
        className="bg-white rounded-t-2xl shadow-[0_-4px_20px_rgba(0,0,0,0.08)] flex flex-col overflow-hidden"
        style={sheetStyle}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <div className="shrink-0 flex flex-col items-center pt-3 pb-2 cursor-grab active:cursor-grabbing select-none">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
          <div className="flex items-center gap-2 mt-2">
            {count !== undefined && (
              <span className="text-xs font-medium text-muted">
                {count} listings
              </span>
            )}
            {state === 'collapsed' ? (
              <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
              </svg>
            ) : state === 'full' ? (
              <svg className="w-4 h-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            ) : (
              <div className="w-4" />
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  );
}
