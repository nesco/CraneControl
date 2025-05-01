'use client';
import { useState } from 'react';
import Button from "@/components/Button";
import NumberInput from "@/components/NumberInput"

export default function CoordinatesPanel({ onSubmit }: Props) {
  const [xyz, setXYZ] = useState({ x_mm: 1000, y_mm: 1000, z_mm: 0 }); // mm

  const bind = (k: keyof typeof xyz) => ({
    value: xyz[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setXYZ(p => ({ ...p, [k]: Number(e.target.value) })),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({ xyz });           // 🚀 same WebSocket you already use :contentReference[oaicite:0]{index=0}&#8203;:contentReference[oaicite:1]{index=1}
  };

  return (
    <form onSubmit={submit} className="space-y-2 p-4">
      <h2 className="font-semibold dark:text-gray-100">Target XYZ (mm)</h2>
      <NumberInput name="x_mm" label="X (fwd)" binding={bind} />
      <NumberInput name="y_mm" label="Y (up)" binding={bind} />
      <NumberInput name="z_mm" label="Z (left)" binding={bind} />
      <Button className="mt-2">Go</Button>
    </form>
  );
}
