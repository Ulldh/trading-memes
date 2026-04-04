import { MetadataRoute } from 'next'

/**
 * Genera robots.txt dinamico.
 * Permite indexacion general pero bloquea rutas internas de API.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/', disallow: '/api/' },
    sitemap: 'https://memedetector.es/sitemap.xml',
  }
}
