import { useState, useEffect } from 'react';
import { CraneState } from '@/components/CraneCanvas';
import Button from "@/components/Button";
import NumberInput from "@/components/NumberInput"

type Props = {
  remote: CraneStae,
  onSubmit: (cmd: Partial<CraneState>) => void;
}

type Joint = keyof CraneState;
const EPS = 0.5;

export default function StatePanel({remote, onSubmit}: Props) {
  const [local, setLocal] = useState(remote);
  const [editing, setEditing] = useState<Record<Joint, boolean>>(
    {} as Record<Joint, boolean>,
  );
  const [pending, setPending] = useState<Record<Joint, boolean>>({} as any);


  const bind = (name: Joint) => ({
    name,
    value: local[name],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setLocal(p => ({ ...p, [name]: Number(e.target.value) })),
    onFocus: () => setEditing(p => ({ ...p, [name]: true })),
    onBlur : () => setEditing(p => ({ ...p, [name]: false })),
  });

  useEffect(() => {
    setLocal(prev => {
      const next = { ...prev };

      (Object.keys(remote) as Joint[]).forEach(k => {
        const busy = editing[k] || pending[k];
        const reached = pending[k] && Math.abs(remote[k] - prev[k]) < EPS;

        if (reached)                             // backend caught up ➜ unlock
          setPending(p => ({ ...p, [k]: false }));

        if (!busy) next[k] = remote[k];          // ordinary copy-over
      });
      return next;
    });
  }, [remote, editing, pending]);
  

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const diff: Partial<CraneState> = {};

    (Object.keys(local) as Joint[]).forEach(k => {
      if (local[k] !== remote[k]) {
        diff[k] = local[k];
      }
    });

    if (!Object.keys(diff).length) return;

    onSubmit(diff);                           // ship it 🚀
    setPending(p => ({ ...p, ...Object.fromEntries(
      Object.keys(diff).map(k => [k as Joint, true]),
    )}));
    };

  return (
    <form className="p-4 rounded-lg max-w-md mx-auto" id="state-panel" onSubmit={submit}>
      <h2 className="text-lg font-semibold text-gray-800 mb-4 dark:text-gray-100">Crane Control Panel</h2>
      <NumberInput name="swingDeg" label="Swing (deg)" binding={bind} min={-360} max={360}/>
      <NumberInput name="elbowDeg" label="Elbow (deg)" binding={bind} min={-360} max={360}/>
      <NumberInput name="wristDeg" label="Wrist (deg)" binding={bind} min={-360} max={360}/>
      <NumberInput name="liftMm" label="Lift (mm)" binding={bind} min={0} max={3000}/>
      <NumberInput name="gripMm" label="Grip (mm)" binding={bind} min={0} max={70}/>
      <Button onMouseDown={e => e.preventDefault()} className="mt-2">Send</Button>
    </form>
  );
}

