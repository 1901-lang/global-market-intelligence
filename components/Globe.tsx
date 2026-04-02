'use client'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import { useRef, useState } from 'react'
import * as THREE from 'three'

interface MarketData {
  name: string
  data: string[]
  x: number
  y: number
}

interface MarkerProps {
  position: [number, number, number]
  marketData: MarketData
  onHover: (data: MarketData | null, x: number, y: number) => void
}

const marketHubs = [
  {
    name: 'New York',
    lat: 40.7,
    lng: -74.0,
    data: ['S&P 500: 5,123 ▲0.8%', 'Oil WTI: $85.20 ▲2.3%', 'Gold: $2,150 ▲0.8%', 'BTC: $67,420 ▲3.2%'],
  },
  {
    name: 'London',
    lat: 51.5,
    lng: -0.1,
    data: ['FTSE 100: 8,012 ▲0.4%', 'Brent: $88.60 ▲1.9%', 'GBP/USD: 1.2650 ▼0.1%', 'Natural Gas: $2.85 ▲4.1%'],
  },
  {
    name: 'Tokyo',
    lat: 35.7,
    lng: 139.7,
    data: ['Nikkei: 38,720 ▲1.2%', 'USD/JPY: 149.8 ▲0.3%', 'Silver: $24.80 ▲1.5%', 'ETH: $3,580 ▲2.8%'],
  },
  {
    name: 'Dubai',
    lat: 25.2,
    lng: 55.3,
    data: ['Dubai Oil: $86.40 ▲2.1%', 'Gold (spot): $2,148 ▲0.7%', 'AED/USD: 0.272 stable', 'SOL: $142 ▲5.2%'],
  },
  {
    name: 'Singapore',
    lat: 1.3,
    lng: 103.8,
    data: ['STI: 3,280 ▲0.6%', 'Palm Oil: $920 ▼0.4%', 'SGD/USD: 0.745 ▲0.1%', 'XRP: $0.582 ▲1.8%'],
  },
  {
    name: 'Sydney',
    lat: -33.9,
    lng: 151.2,
    data: ['ASX 200: 7,890 ▲0.9%', 'Iron Ore: $128 ▼1.2%', 'AUD/USD: 0.652 ▲0.2%', 'BNB: $412 ▲2.4%'],
  },
]

function latLngToVector3(lat: number, lng: number, radius: number): [number, number, number] {
  const phi = (90 - lat) * (Math.PI / 180)
  const theta = (lng + 180) * (Math.PI / 180)
  const x = -(radius * Math.sin(phi) * Math.cos(theta))
  const z = radius * Math.sin(phi) * Math.sin(theta)
  const y = radius * Math.cos(phi)
  return [x, y, z]
}

function Marker({ position, marketData, onHover }: MarkerProps) {
  const meshRef = useRef<THREE.Mesh>(null)
  const [hovered, setHovered] = useState(false)

  useFrame((state) => {
    if (meshRef.current) {
      const scale = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.3
      meshRef.current.scale.setScalar(hovered ? scale * 1.5 : scale)
    }
  })

  return (
    <mesh
      ref={meshRef}
      position={position}
      onPointerOver={(e) => {
        e.stopPropagation()
        setHovered(true)
        onHover(marketData, e.nativeEvent.clientX, e.nativeEvent.clientY)
      }}
      onPointerOut={() => {
        setHovered(false)
        onHover(null, 0, 0)
      }}
    >
      <sphereGeometry args={[0.025, 8, 8]} />
      <meshStandardMaterial
        color={hovered ? '#00FF88' : '#00D4FF'}
        emissive={hovered ? '#00FF88' : '#00D4FF'}
        emissiveIntensity={2}
      />
    </mesh>
  )
}

function GlobeScene({ onMarkerHover }: { onMarkerHover: (data: MarketData | null, x: number, y: number) => void }) {
  const globeRef = useRef<THREE.Mesh>(null)

  useFrame(() => {
    // OrbitControls handles rotation; ref retained for future effects
  })

  return (
    <>
      {/* Main globe sphere */}
      <mesh ref={globeRef}>
        <sphereGeometry args={[1, 64, 64]} />
        <meshPhongMaterial
          color="#0A1628"
          emissive="#0A1628"
          emissiveIntensity={0.1}
          specular="#00D4FF"
          shininess={20}
          wireframe={false}
        />
      </mesh>

      {/* Wireframe overlay */}
      <mesh>
        <sphereGeometry args={[1.001, 32, 32]} />
        <meshBasicMaterial
          color="#00D4FF"
          wireframe={true}
          transparent={true}
          opacity={0.06}
        />
      </mesh>

      {/* Atmosphere glow */}
      <mesh>
        <sphereGeometry args={[1.15, 64, 64]} />
        <meshBasicMaterial
          color="#00D4FF"
          transparent={true}
          opacity={0.04}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Second atmosphere layer */}
      <mesh>
        <sphereGeometry args={[1.08, 64, 64]} />
        <meshBasicMaterial
          color="#7B2FBE"
          transparent={true}
          opacity={0.05}
          side={THREE.BackSide}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Market hub markers */}
      {marketHubs.map((hub) => {
        const position = latLngToVector3(hub.lat, hub.lng, 1.02)
        return (
          <Marker
            key={hub.name}
            position={position}
            marketData={{ name: hub.name, data: hub.data, x: 0, y: 0 }}
            onHover={onMarkerHover}
          />
        )
      })}

      {/* Lighting */}
      <ambientLight intensity={0.15} />
      <pointLight position={[10, 10, 10]} intensity={1.5} color="#00D4FF" />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#7B2FBE" />
      <directionalLight position={[5, 5, 5]} intensity={0.8} />
    </>
  )
}

export default function Globe() {
  const [tooltip, setTooltip] = useState<{ data: MarketData; x: number; y: number } | null>(null)

  const handleMarkerHover = (data: MarketData | null, x: number, y: number) => {
    if (data) {
      setTooltip({ data: { ...data, x, y }, x, y })
    } else {
      setTooltip(null)
    }
  }

  return (
    <div style={{ width: '100%', height: '500px', position: 'relative' }}>
      <Canvas camera={{ position: [0, 0, 2.8], fov: 45 }}>
        <GlobeScene onMarkerHover={handleMarkerHover} />
        <OrbitControls
          enableZoom={false}
          autoRotate
          autoRotateSpeed={0.4}
          enablePan={false}
          minPolarAngle={Math.PI / 4}
          maxPolarAngle={(Math.PI * 3) / 4}
        />
      </Canvas>

      {tooltip && (
        <div
          className="absolute z-10 glass-card rounded-lg p-3 pointer-events-none"
          style={{
            left: Math.min(tooltip.x - 10, typeof window !== 'undefined' ? window.innerWidth - 200 : 800),
            top: tooltip.y - 10,
            transform: 'translate(-50%, -110%)',
            minWidth: '180px',
          }}
        >
          <div className="text-accent-blue font-bold text-sm mb-2">{tooltip.data.name}</div>
          {tooltip.data.data.map((item, i) => (
            <div key={i} className="text-xs text-gray-300 py-0.5">
              {item}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
