"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { HeroFallbackArt } from "./HeroFallbackArt";

const BRAND_BLUE = new THREE.Color("#2563EB");
const BRAND_TEAL = new THREE.Color("#00BFA6");

const POINT_COUNT = 260;
const RADIUS = 2.15;
const NEIGHBOURS = 2;
const MAX_LINK_DISTANCE = 0.62;
const PULSE_SECONDS = 2.6;

/**
 * Points spread evenly over a sphere (Fibonacci lattice) with a little jitter, each
 * linked to its nearest neighbours: a calm "connected care" network around the cross.
 * Built once; a fixed seed keeps the shape identical between visits.
 */
function useNetworkGeometry() {
  return useMemo(() => {
    let seed = 7;
    const random = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    const positions = new Float32Array(POINT_COUNT * 3);
    const colors = new Float32Array(POINT_COUNT * 3);
    const golden = Math.PI * (3 - Math.sqrt(5));
    const color = new THREE.Color();

    for (let i = 0; i < POINT_COUNT; i++) {
      const y = 1 - (i / (POINT_COUNT - 1)) * 2;
      const ring = Math.sqrt(1 - y * y);
      const theta = golden * i;
      const r = RADIUS * (0.92 + random() * 0.16);
      positions.set([Math.cos(theta) * ring * r, y * r, Math.sin(theta) * ring * r], i * 3);
      color.copy(BRAND_BLUE).lerp(BRAND_TEAL, (y + 1) / 2);
      colors.set([color.r, color.g, color.b], i * 3);
    }

    const segments: number[] = [];
    const a = new THREE.Vector3();
    const b = new THREE.Vector3();
    for (let i = 0; i < POINT_COUNT; i++) {
      a.fromArray(positions, i * 3);
      const nearest: Array<{ j: number; d: number }> = [];
      for (let j = 0; j < POINT_COUNT; j++) {
        if (j === i) continue;
        const d = a.distanceTo(b.fromArray(positions, j * 3));
        if (d < MAX_LINK_DISTANCE) nearest.push({ j, d });
      }
      nearest.sort((x, y) => x.d - y.d);
      for (const { j } of nearest.slice(0, NEIGHBOURS)) {
        if (j > i) segments.push(...positions.slice(i * 3, i * 3 + 3), ...positions.slice(j * 3, j * 3 + 3));
      }
    }

    const points = new THREE.BufferGeometry();
    points.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    points.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const lines = new THREE.BufferGeometry();
    lines.setAttribute("position", new THREE.Float32BufferAttribute(segments, 3));
    return { points, lines };
  }, []);
}

/**
 * The logo's medical cross as a solid: a plus with rounded arm ends (same proportions as
 * NoraLogo: arm 1, bar 0.357), extruded with a soft bevel, and coloured with the brand
 * gradient from blue (top left) to teal (bottom right) through vertex colours.
 */
function useCrossGeometry() {
  return useMemo(() => {
    const arm = 1.25;
    const bar = arm * 0.357;
    const h = arm / 2;
    const w = bar / 2;
    const r = w; // fully rounded ends
    const shape = new THREE.Shape();
    shape.moveTo(-w, h - r);
    shape.absarc(0, h - r, r, Math.PI, 0, true); // top end
    shape.lineTo(w, w);
    shape.lineTo(h - r, w);
    shape.absarc(h - r, 0, r, Math.PI / 2, -Math.PI / 2, true); // right end
    shape.lineTo(w, -w);
    shape.lineTo(w, -(h - r));
    shape.absarc(0, -(h - r), r, 0, -Math.PI, true); // bottom end
    shape.lineTo(-w, -w);
    shape.lineTo(-(h - r), -w);
    shape.absarc(-(h - r), 0, r, -Math.PI / 2, Math.PI / 2, true); // left end
    shape.lineTo(-w, w);
    shape.lineTo(-w, h - r);

    const geometry = new THREE.ExtrudeGeometry(shape, {
      depth: 0.22,
      bevelEnabled: true,
      bevelThickness: 0.06,
      bevelSize: 0.05,
      bevelSegments: 6,
      curveSegments: 24,
    });
    geometry.center();

    const position = geometry.getAttribute("position");
    const colors = new Float32Array(position.count * 3);
    const color = new THREE.Color();
    for (let i = 0; i < position.count; i++) {
      const t = THREE.MathUtils.clamp((position.getX(i) - position.getY(i)) / arm + 0.5, 0, 1);
      color.copy(BRAND_BLUE).lerp(BRAND_TEAL, t);
      colors.set([color.r, color.g, color.b], i * 3);
    }
    geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return geometry;
  }, []);
}

function Network() {
  const group = useRef<THREE.Group>(null);
  const pulse = useRef<THREE.Mesh>(null);
  const pulseMaterial = useRef<THREE.MeshBasicMaterial>(null);
  const { points, lines } = useNetworkGeometry();
  const cross = useCrossGeometry();

  useFrame((state, delta) => {
    const g = group.current;
    if (g) {
      g.rotation.y += delta * 0.07;
      // Gentle parallax towards the pointer.
      g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, state.pointer.y * 0.18, 0.04);
      g.rotation.z = THREE.MathUtils.lerp(g.rotation.z, -state.pointer.x * 0.08, 0.04);
    }
    // A slow "heartbeat" ring expanding from the cross.
    const t = (state.clock.elapsedTime % PULSE_SECONDS) / PULSE_SECONDS;
    if (pulse.current && pulseMaterial.current) {
      pulse.current.scale.setScalar(0.6 + t * 2.4);
      pulseMaterial.current.opacity = 0.35 * (1 - t);
    }
  });

  return (
    <group ref={group}>
      <points geometry={points}>
        <pointsMaterial vertexColors size={0.05} sizeAttenuation transparent opacity={0.9} depthWrite={false} />
      </points>
      <lineSegments geometry={lines}>
        <lineBasicMaterial color={BRAND_BLUE} transparent opacity={0.16} depthWrite={false} />
      </lineSegments>

      <mesh geometry={cross}>
        <meshStandardMaterial vertexColors roughness={0.32} metalness={0.08} emissive="#0b3a8c" emissiveIntensity={0.12} />
      </mesh>

      {/* Faces the camera, so it reads as a ring rather than a line. */}
      <mesh ref={pulse}>
        <torusGeometry args={[0.9, 0.012, 8, 96]} />
        <meshBasicMaterial ref={pulseMaterial} color={BRAND_TEAL} transparent opacity={0.3} depthWrite={false} />
      </mesh>
    </group>
  );
}

/**
 * The landing-page hero scene. `animate` false renders a single still frame (used for
 * reduced motion and while the hero is scrolled out of view).
 */
export default function HeroScene({ animate }: { animate: boolean }) {
  return (
    <Canvas
      frameloop={animate ? "always" : "demand"}
      dpr={[1, 1.75]}
      camera={{ position: [0, 0, 6.2], fov: 42 }}
      gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}
      fallback={<HeroFallbackArt />}
      aria-hidden
    >
      <ambientLight intensity={1.15} />
      <directionalLight position={[3, 4, 5]} intensity={1.4} color="#ffffff" />
      <directionalLight position={[-4, -2, 3]} intensity={0.5} color="#ccfbf1" />
      <Network />
    </Canvas>
  );
}
