'use client';
import { useEffect, useRef, useState } from "react";
import { CraneState } from '@/components/CraneCanvas';

const DEFAULT: CraneState = {
  swingDeg: 0, liftMm: 0, elbowDeg: 0, wristDeg: 0, gripMm: 70,
};

export function useCraneTelemetry(url = 'ws://localhost:8000/ws') {
  const [state, setState] = useState<CraneState>(DEFAULT);
  const wsRef = useRef<WebSocket>();

    useEffect(() =>  {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onmessage = (evt) => {
        try { setState(JSON.parse(evt.data)); } catch { /* ignore */ }
      };
      ws.onclose = () => console.warn('socket closed');

      return () => ws.close();
  }, [url])

  /**  Send control commands back to the server */
  const send = (partial: Partial<CraneState>) =>
    wsRef.current?.readyState === WebSocket.OPEN &&
    wsRef.current.send(JSON.stringify(partial));

  return { state, send };
}



