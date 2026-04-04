import { MetadataRoute } from 'next'

/**
 * Genera el sitemap.xml dinamico para SEO.
 * Como el sitio usa next-intl sin prefijo de ruta (deteccion por cookie/header),
 * las URLs no llevan prefijo de locale.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const baseUrl = 'https://memedetector.es'

  const pages = [
    { path: '', changeFrequency: 'daily' as const, priority: 1.0 },
    { path: '/academia', changeFrequency: 'weekly' as const, priority: 0.8 },
    { path: '/legal', changeFrequency: 'monthly' as const, priority: 0.3 },
    { path: '/disclaimer', changeFrequency: 'monthly' as const, priority: 0.3 },
  ]

  return pages.map((page) => ({
    url: `${baseUrl}${page.path}`,
    lastModified: new Date(),
    changeFrequency: page.changeFrequency,
    priority: page.priority,
  }))
}
