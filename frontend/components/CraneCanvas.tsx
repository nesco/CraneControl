/*
 * CraneCanvas.tsx – v2  ·  R‑P‑R‑R chain matching Monumental’s schematic
 * --------------------------------------------------------------------------
 *  J1  swingDeg  – swing rotation (deg)
 *  J2  liftMm    – prismatic lift (mm)
 *  J3  elbowDeg  – elbow pitch (deg)
 *  J4  wristDeg  – wrist pitch (deg)
 *  g   gripMm    – gripper opening (mm)
 * --------------------------------------------------------------------------
 *  Dependencies:
 *    npm i three @react-three/fiber @react-three/drei
 */
'use client';

import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { useRef } from 'react';
import { Sky } from '@react-three/drei';
import { MathUtils, GridHelper, AxesHelper, Group } from 'three';

// ─────────────────────────────────────────────────────────────────────────────
// Types
export interface CraneState {
  swingDeg:   number; // J1 – base rotation about Z
  liftMm:   number; // J2 – vertical slide
  elbowDeg: number; // J3 – elbow pitch
  wristDeg: number; // J4 – wrist pitch
  gripMm?:  number; // gripper opening (mm)
}
 type Props = {
  state: CraneState
}

// ─────────────────────────────────────────────────────────────────────────────
export default function CraneCanvas({state}: Props ) {
  return (
    <div className="relative w-full h-full">
      <Canvas camera={{ position: [6, 4, 8], fov: 45 }} className="!absolute inset-0">
        <Sky
          distance={450000}     // camera distance
          sunPosition={[5, 1, 8]} 
          inclination={0.49}    // elevation / azimuth
          azimuth={0.25}
        />
        <primitive object={new GridHelper(10, 20, "#444", "#222")} />
        <primitive object={new AxesHelper(2)} />
        <ambientLight intensity={0.6} />
        <directionalLight position={[5, 10, 2]} intensity={0.8} />
        <OrbitControls makeDefault />
        <CraneModel state={state} />
        {/* ground */}
        <mesh rotation-x={-Math.PI / 2}>
          <planeGeometry args={[10, 10]} />
          <meshStandardMaterial color="#555" />
        </mesh>
      </Canvas>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Internal constants
const COLUMN_H = 3;
const CHASSIS_H = 0.3;

const ELBOW_LEN = COLUMN_H/4; // metres
const WRIST_LEN = ELBOW_LEN*3/4;
const CHASSIS_W = 1.2;
const PIVOT_W = 0.15;
const COLUMN_W = 0.2;
const ELBOW_W = PIVOT_W*4/5;
const WRIST_W = ELBOW_W*4/5;

const DROP_BOX_H  = 0.12;   // how far we hang below the wrist beam
const JAW_LEN     = 0.04;   // length of each finger
const JAW_THICK   = 0.02;   // thickness of the finger plates

/** Two opposing jaws whose inner faces are `gripMm` apart */
function Gripper({innerRef, gripMm = 60 }: { ref: Ref, gripMm?: number }) {
  const gap      = gripMm / 1000;
  const halfGap  = gap / 2;

  return (
    /* keep cylinder-style rotation so beam still points forward (world +X) */
    <group ref={innerRef} rotation={[0, 0, Math.PI / 2]}>
      {/* ── drop-down mounting box ── */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[WRIST_W, DROP_BOX_H, WRIST_W]} />
        <meshStandardMaterial color="#c0c0c0" />
      </mesh>

      {/* ── jaws ── */}
      <group position={[0, DROP_BOX_H/2, 0]}>
        {/* upper jaw */}
        <mesh
          position={[0, 0,  halfGap + JAW_THICK / 2]}
          rotation={[0,  Math.PI / 2, 0]}
        >
          <boxGeometry args={[JAW_THICK, JAW_LEN, WRIST_W]} />
          <meshStandardMaterial color="#cf2e2e" />
        </mesh>

        {/* lower jaw */}
        <mesh
          position={[0, 0, -halfGap - JAW_THICK / 2]}
          rotation={[0, -Math.PI / 2, 0]}
        >
          <boxGeometry args={[JAW_THICK, JAW_LEN, WRIST_W]} />
          <meshStandardMaterial color="#cf2e2e" />
        </mesh>
      </group>
    </group>
  );
}


function CraneModel({ state }: { state: CraneState }) {
  // joint pivots
  const root = useRef<Group>(null!);   // swing
  const lift = useRef<Group>(null!);   // prismatic slide
  const elbow = useRef<Group>(null!); 
  const wrist = useRef<Group>(null!);  // elbow pitch
  const gripper = useRef<Group>(null!);  // wrist pitch

  useFrame(() => {
    const { swingDeg, liftMm, elbowDeg, wristDeg } = state;
    root.current.rotation.y = MathUtils.degToRad(swingDeg);
    lift.current.position.y = liftMm / 1000;
    wrist.current.rotation.y = MathUtils.degToRad(elbowDeg);
    gripper.current.rotation.x = MathUtils.degToRad(wristDeg);
  });

  return (
    <group ref={root}>
      {/* base / chassis */}
      <mesh position={[0, PIVOT_W, 0]}>
        <boxGeometry args={[CHASSIS_W, CHASSIS_H, CHASSIS_W]} />
        <meshStandardMaterial color="#404040" />
      </mesh>

      {/* column */}
      <group>
        <mesh position={[0, COLUMN_H/2, 0]}> {/* centre of tall box */}
          <boxGeometry args={[COLUMN_W, COLUMN_H, COLUMN_W]} />
          <meshStandardMaterial color="#c0c0c0" />
        </mesh>

        {/* lift carriage */}
        <group ref={lift} position={[0, 0, 0]}>
          <mesh position={[0, 0, 0]}> {/* centred on pivot */}
            <boxGeometry args={[0.3, PIVOT_W, 0.3]} />
            <meshStandardMaterial color="#e0b700" /> {/* yellow */}
          </mesh>

          {/* elbow joint */}
          <group ref={elbow} position={[PIVOT_W, 0, 0]}> {/* pivot at front face */}
            {/* elbow beam */}
            <mesh position={[ELBOW_LEN / 2, 0, 0]}>
              <boxGeometry args={[ELBOW_LEN, ELBOW_W, ELBOW_W]} />
              <meshStandardMaterial color="#c0c0c0" />
            </mesh>

            {/* wrist joint */}
            <group ref={wrist} position={[ELBOW_LEN-ELBOW_W/2, -ELBOW_W/1.3, 0]}>
              {/* wrist beam */}
              <mesh position={[WRIST_LEN / 2, 0, 0]}>
                <boxGeometry args={[WRIST_LEN, WRIST_W, WRIST_W]} />
                <meshStandardMaterial color="#c0c0c0" />
              </mesh>

              {/* gripper */}
              <group position={[WRIST_LEN - WRIST_W/2, -WRIST_W, 0]} rotation={[0, 0, Math.PI / 2]}>
                <Gripper innerRef={gripper} gripMm={state.gripMm} />
              </group>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}

