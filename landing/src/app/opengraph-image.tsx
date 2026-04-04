import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const alt = 'MemeDetector - AI Gem Detector'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

/**
 * Genera imagen OG dinamica con stats reales de la API.
 * Se regenera cada hora (revalidate: 3600).
 */
export default async function Image() {
  // Valores por defecto (fallback si la API no responde)
  let stats = { tokens: '11,000+', hitRate: '52%', gems: '260+' }

  try {
    const res = await fetch('https://memedetector.es/api/stats', {
      next: { revalidate: 3600 },
    })
    if (res.ok) {
      const data = await res.json()
      stats = {
        tokens: data.tokens?.toLocaleString() || '11,000+',
        hitRate: `${Math.round((data.hit_rate || 0.52) * 100)}%`,
        gems: data.gems?.toLocaleString() || '260+',
      }
    }
  } catch {
    // Usar fallback si hay error de red
  }

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'linear-gradient(135deg, #0a0a0a 0%, #0d1117 100%)',
          fontFamily: 'monospace',
          color: '#e0e0e0',
        }}
      >
        {/* Logo / Titulo */}
        <div
          style={{
            fontSize: 64,
            fontWeight: 800,
            color: '#00ff41',
            marginBottom: 20,
            display: 'flex',
          }}
        >
          MEME DETECTOR
        </div>

        {/* Subtitulo */}
        <div
          style={{
            fontSize: 28,
            color: '#888',
            marginBottom: 40,
            display: 'flex',
          }}
        >
          AI-Powered Memecoin Gem Detector
        </div>

        {/* Stats */}
        <div style={{ display: 'flex', gap: 60 }}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                fontSize: 48,
                fontWeight: 700,
                color: '#00ff41',
                display: 'flex',
              }}
            >
              {stats.tokens}
            </div>
            <div style={{ fontSize: 18, color: '#666', display: 'flex' }}>
              tokens analyzed
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                fontSize: 48,
                fontWeight: 700,
                color: '#fbbf24',
                display: 'flex',
              }}
            >
              {stats.hitRate}
            </div>
            <div style={{ fontSize: 18, color: '#666', display: 'flex' }}>
              hit rate
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                fontSize: 48,
                fontWeight: 700,
                color: '#00ff41',
                display: 'flex',
              }}
            >
              {stats.gems}
            </div>
            <div style={{ fontSize: 18, color: '#666', display: 'flex' }}>
              gems found
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size }
  )
}
