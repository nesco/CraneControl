/*
 * app/page.tsx – Home route hosting the CraneCanvas in a Next.js 13/14 App Router project
 * --------------------------------------------------------------------------
 * This page keeps a local `CraneState` in React state so you can see the arm
 * move without wiring up the real WebSocket yet. Replace the demo `useEffect`
 * with your telemetry hook when ready.
 */
'use client';

import CraneCanvas from "@/components/CraneCanvas";
import StatePanel from "@/components/StatePanel";
import CoordinatePanel from "@/components/CoordinatesPanel";
import { useCraneTelemetry } from '@/lib/useCraneTelemetry';


export default function Home() {
  const { state, send } = useCraneTelemetry(); 

  return (
    <main className="p-6 bg-gray-50 dark:bg-gray-800 min-h-screen flex flex-col">
      <h1 className="text-3xl font-semibold text-center mb-6 text-gray-900 dark:text-gray-100">Crane Controller</h1>
      <div className="flex flex-1 overflow-hidden h-[calc(100vh-10rem)]">
        <div className="flex flex-col overflow-y-auto border dark:border-gray-900 rounded-lg">
          <StatePanel remote={state} onSubmit={send} />
          <CoordinatePanel onSubmit={send} />
        </div>
        <div className="flex-1 border ml-1 relative">
          <CraneCanvas state={state} />
        </div>
      </div>
    </main>
  );
}
