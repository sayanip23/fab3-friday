import { useMemo, useRef, Suspense } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import {
  Environment,
  Float,
  MeshDistortMaterial,
  MeshTransmissionMaterial,
  AdaptiveDpr,
  PerformanceMonitor,
  Preload,
} from '@react-three/drei'
import * as THREE from 'three'

import { COLOR } from '../lib/tokens'
import { useDeviceTier, usePageVisible, useReducedMotion } from '../hooks/useEnvironment'

/* ═══════════════════════════════════════════════════════════════════════
   PARTICLE FIELD

   A single THREE.Points object, not N meshes. One draw call for the whole
   field; positions are generated once into a Float32Array and never
   reallocated. Animating the parent's rotation rather than each particle
   keeps the per-frame cost at effectively zero — the GPU does the work.
   ═══════════════════════════════════════════════════════════════════════ */
function ParticleField({ count, reduced }) {
  const points = useRef()

  const positions = useMemo(() => {
    const pos = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      // Spherical shell rather than a cube: a cube reads as a box of dots at
      // the corners, a shell reads as depth.
      const r = 6 + Math.random() * 9
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.6 // flatten Y
      pos[i * 3 + 2] = r * Math.cos(phi)
    }
    return pos
  }, [count])

  useFrame((state, delta) => {
    if (reduced || !points.current) return
    // Two axes at different rates so the field never looks like a rigid
    // turntable. Delta-scaled so speed is frame-rate independent.
    points.current.rotation.y += delta * 0.035
    points.current.rotation.x =
      Math.sin(state.clock.elapsedTime * 0.12) * 0.09
  })

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        color={COLOR.accent}
        transparent
        opacity={0.55}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

/* ═══════════════════════════════════════════════════════════════════════
   MORPHING CORE

   An icosahedron with MeshDistortMaterial. The distortion is a vertex
   shader displacing along the normal by 3D simplex noise — it costs a
   uniform update per frame, not a geometry rebuild, which is why this is
   cheap enough to leave running.

   `speed` is set to 0 under reduced motion so the shape freezes in a
   readable state rather than disappearing.
   ═══════════════════════════════════════════════════════════════════════ */
function MorphingCore({ detail, reduced }) {
  const mesh = useRef()

  useFrame((state, delta) => {
    if (!mesh.current) return
    if (!reduced) mesh.current.rotation.y += delta * 0.12

    // Breathing scale, tied to elapsed time so it is continuous across
    // frame-rate changes rather than accumulating drift.
    const t = state.clock.elapsedTime
    const breathe = reduced ? 1 : 1 + Math.sin(t * 0.7) * 0.035
    mesh.current.scale.setScalar(breathe * 1.6)
  })

  return (
    <mesh ref={mesh} castShadow receiveShadow>
      <icosahedronGeometry args={[1, detail]} />
      <MeshDistortMaterial
        color={COLOR.primary}
        emissive={COLOR.primary}
        emissiveIntensity={0.35}
        roughness={0.12}
        metalness={0.85}
        distort={reduced ? 0.18 : 0.42}
        speed={reduced ? 0 : 1.6}
      />
    </mesh>
  )
}

/* ═══════════════════════════════════════════════════════════════════════
   GLASS PRIMITIVES

   MeshTransmissionMaterial does real refraction: it renders the scene to a
   buffer and samples it through the surface. That buffer is the expensive
   part, so `samples` and `resolution` are the two dials that matter, and
   both are cut hard on low-tier devices. On the lowest tier we drop
   transmission entirely for a cheap translucent standard material.
   ═══════════════════════════════════════════════════════════════════════ */
function GlassShard({ position, rotation, scale, tier, reduced }) {
  // Only the high tier pays for real refraction now. Each transmission mesh
  // re-renders the scene into its own buffer, which measured at 78 draw calls
  // per frame with five shards — and that cost lands hardest exactly when the
  // user is scrolling and the compositor is already busy with the glass UI.
  // Integrated GPUs (now graded 'mid') get the cheap material instead.
  const cheap = tier !== 'high'

  return (
    <Float
      speed={reduced ? 0 : 1.4}
      rotationIntensity={reduced ? 0 : 0.55}
      floatIntensity={reduced ? 0 : 0.9}
    >
      <mesh position={position} rotation={rotation} scale={scale} castShadow>
        <octahedronGeometry args={[1, 0]} />
        {cheap ? (
          <meshPhysicalMaterial
            color="#ffffff"
            transparent
            opacity={0.16}
            roughness={0.1}
            metalness={0.2}
            clearcoat={1}
          />
        ) : (
          <MeshTransmissionMaterial
            samples={tier === 'high' ? 6 : 3}
            resolution={tier === 'high' ? 512 : 256}
            transmission={1}
            thickness={0.9}
            roughness={0.08}
            ior={1.45}
            chromaticAberration={0.06}
            anisotropy={0.2}
            distortion={0.2}
            distortionScale={0.4}
            temporalDistortion={reduced ? 0 : 0.1}
            color="#dcd4ff"
            attenuationColor={COLOR.accent}
            attenuationDistance={2.4}
          />
        )}
      </mesh>
    </Float>
  )
}

/* ═══════════════════════════════════════════════════════════════════════
   CAMERA PARALLAX

   `state.pointer` is already normalised to [-1, 1] by R3F. We lerp toward
   the target rather than assigning it, which is what turns a twitchy
   1:1 mouse follow into something that feels weighted.

   damp() is frame-rate independent: at 144fps you get the same easing
   curve as at 60, where a naive `lerp(current, target, 0.05)` would move
   more than twice as fast.
   ═══════════════════════════════════════════════════════════════════════ */
function CameraRig({ reduced }) {
  const { camera } = useThree()
  const target = useRef(new THREE.Vector3(0, 0, 8))

  useFrame((state, delta) => {
    if (reduced) return
    const { x, y } = state.pointer
    target.current.set(x * 1.6, y * 0.9, 8)
    camera.position.x = THREE.MathUtils.damp(camera.position.x, target.current.x, 2.2, delta)
    camera.position.y = THREE.MathUtils.damp(camera.position.y, target.current.y, 2.2, delta)
    camera.lookAt(0, 0, 0)
  })

  return null
}

/* ═══════════════════════════════════════════════════════════════════════
   LIGHTING

   Three-point rig in brand colours. The key and rim lights use the exact
   token values the CTA glow uses, so the object and the UI read as lit by
   the same source.
   ═══════════════════════════════════════════════════════════════════════ */
function Lighting({ tier }) {
  return (
    <>
      <ambientLight intensity={0.35} />
      {/* Key: violet, casts the only shadow — a second shadow-caster roughly
          doubles the shadow pass for very little visual gain. */}
      <directionalLight
        position={[4, 6, 5]}
        intensity={2.4}
        color={COLOR.primarySoft}
        castShadow={tier !== 'low'}
        shadow-mapSize={tier === 'high' ? [1024, 1024] : [512, 512]}
        shadow-bias={-0.0004}
      />
      {/* Rim: cyan from behind, separates the silhouette from the background. */}
      <pointLight position={[-5, -2, -4]} intensity={18} color={COLOR.accent} distance={18} />
      {/* Fill: dim violet, stops the shadow side going pure black. */}
      <pointLight position={[3, -3, 3]} intensity={7} color={COLOR.primary} distance={14} />
    </>
  )
}

function Scene({ tier, reduced }) {
  const particles = tier === 'high' ? 2600 : tier === 'mid' ? 1400 : 600
  const detail = tier === 'high' ? 12 : tier === 'mid' ? 8 : 4

  return (
    <>
      <color attach="background" args={[COLOR.void]} />
      <fog attach="fog" args={[COLOR.void, 9, 26]} />

      <Lighting tier={tier} />
      <CameraRig reduced={reduced} />

      <Float speed={reduced ? 0 : 1.1} rotationIntensity={reduced ? 0 : 0.3} floatIntensity={reduced ? 0 : 0.6}>
        <MorphingCore detail={detail} reduced={reduced} />
      </Float>

      <ParticleField count={particles} reduced={reduced} />

      {/* Glass shards are the most expensive objects on screen. Only the high
          tier gets five with real refraction; everything else gets three with a
          cheap translucent material that costs a single ordinary draw call. */}
      <GlassShard position={[-3.4, 1.5, -1]} rotation={[0.6, 0.3, 0]} scale={0.75} tier={tier} reduced={reduced} />
      <GlassShard position={[3.6, -1.2, -0.5]} rotation={[0.2, 0.9, 0.4]} scale={0.95} tier={tier} reduced={reduced} />
      <GlassShard position={[2.6, 2.3, -2.6]} rotation={[1.1, 0.2, 0.7]} scale={0.55} tier={tier} reduced={reduced} />
      {tier === 'high' && (
        <>
          <GlassShard position={[-4.1, -2.1, -2]} rotation={[0.4, 1.4, 0.2]} scale={0.65} tier={tier} reduced={reduced} />
          <GlassShard position={[0.4, 3.1, -3.4]} rotation={[0.9, 0.5, 1.1]} scale={0.45} tier={tier} reduced={reduced} />
        </>
      )}

      {/* Image-based lighting gives the metal and glass something to reflect.
          Without it, MeshTransmissionMaterial refracts a flat void and reads
          as grey plastic. "city" is dim and neutral so it does not fight the
          brand lights. */}
      <Environment preset="city" environmentIntensity={0.5} />
      <Preload all />
    </>
  )
}

export default function CanvasScene() {
  const tier = useDeviceTier()
  const reduced = useReducedMotion()
  const visible = usePageVisible()

  // Under reduced motion nothing animates, so after the first paint there is
  // nothing left to draw — "demand" renders once and then idles at 0% GPU.
  // Hidden tab stops the loop entirely.
  const frameloop = !visible ? 'never' : reduced ? 'demand' : 'always'

  return (
    <div className="fixed inset-0 z-0" aria-hidden="true">
      <Canvas
        frameloop={frameloop}
        shadows={tier !== 'low'}
        // Clamping DPR is the single highest-impact mobile optimisation:
        // a 3x retina phone would otherwise render 9x the pixels.
        dpr={tier === 'high' ? [1, 2] : [1, 1.5]}
        camera={{ position: [0, 0, 8], fov: 45, near: 0.1, far: 100 }}
        gl={{
          antialias: tier === 'high',
          alpha: false,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
        }}
      >
        {/* PerformanceMonitor watches the real frame rate and lets
            AdaptiveDpr drop resolution when the device struggles, so a weak
            GPU degrades to a softer image instead of a stuttering one. */}
        <PerformanceMonitor>
          <AdaptiveDpr pixelated />
          <Suspense fallback={null}>
            <Scene tier={tier} reduced={reduced} />
          </Suspense>
        </PerformanceMonitor>
      </Canvas>
    </div>
  )
}
