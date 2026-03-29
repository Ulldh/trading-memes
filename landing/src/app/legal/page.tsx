"use client";

import Navbar from "@/components/Navbar";
import Link from "next/link";

const sections = [
  { id: "aviso-legal", label: "Aviso Legal" },
  { id: "privacidad", label: "Privacidad" },
  { id: "cookies", label: "Cookies" },
];

export default function LegalPage() {
  return (
    <main className="min-h-screen bg-dark-900">
      {/* Header fijo */}
      <div className="fixed top-0 left-0 right-0 z-50">
        <Navbar />
      </div>

      {/* Contenido */}
      <div className="pt-[72px]">
        {/* Top bar: volver + anchor links */}
        <div className="border-b border-dark-600 bg-dark-800/80 backdrop-blur-sm sticky top-[56px] z-40">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <Link
              href="/"
              className="text-xs text-gray-400 hover:text-primary transition-colors uppercase tracking-wider flex items-center gap-1"
            >
              <span>&larr;</span> memedetector.es
            </Link>
            <div className="flex items-center gap-4">
              {sections.map((s) => (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className="text-xs text-gray-400 hover:text-primary transition-colors uppercase tracking-wider border border-dark-600 px-3 py-1 hover:border-primary/50"
                >
                  {s.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Page title */}
        <div className="max-w-4xl mx-auto px-4 sm:px-6 pt-10 pb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
            <span className="text-primary">&gt;</span> Legal
          </h1>
          <p className="text-sm text-gray-500 mt-2 font-mono">
            Aviso Legal &middot; Privacidad &middot; Cookies
          </p>
        </div>

        {/* ========== AVISO LEGAL ========== */}
        <section id="aviso-legal" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Aviso Legal
            </h2>
            <div className="space-y-8 text-gray-300 text-sm leading-relaxed">

              <div>
                <h3 className="text-white font-semibold text-base mb-3">1. Datos identificativos del responsable</h3>
                <p className="mb-4">
                  En cumplimiento del artículo 10 de la <strong>Ley 34/2002, de 11 de julio, de Servicios de la
                  Sociedad de la Información y de Comercio Electrónico (LSSI-CE)</strong>, se facilitan los
                  siguientes datos identificativos del titular del sitio web:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <tbody>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold w-44">Titular</td><td className="py-2 px-3">ULL MIDDLE MOORE S.L.</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">NIF</td><td className="py-2 px-3">B76672864</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">Domicilio</td><td className="py-2 px-3">Carretera General La Perdoma 35, La Orotava, Santa Cruz de Tenerife, España</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">Correo electrónico</td><td className="py-2 px-3">info@memedetector.es</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">Sitio web</td><td className="py-2 px-3">www.memedetector.es</td></tr>
                      <tr><td className="py-2 px-3 text-gray-400 font-semibold">Actividad</td><td className="py-2 px-3">Prestación de servicios de análisis de datos sobre criptomonedas (memecoins) mediante modelos de Machine Learning</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">2. Objeto y ámbito de aplicación</h3>
                <p className="mb-3">
                  El presente Aviso Legal regula el acceso y uso del sitio web <strong>www.memedetector.es</strong>{" "}
                  (en adelante, &quot;el Sitio Web&quot;) y del servicio <strong>MemeDetector</strong> (en adelante, &quot;el Servicio&quot;),
                  una herramienta de análisis de datos que emplea modelos de Machine Learning para evaluar
                  memecoins (tokens especulativos) en blockchains como Solana, Ethereum y Base.
                </p>
                <p className="mb-2">El Servicio proporciona:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Puntuaciones de potencial (&quot;señales&quot;) generadas por modelos estadísticos.</li>
                  <li>Dashboards de visualizacion de datos históricos y métricas de mercado.</li>
                  <li>Alertas opcionales via Telegram.</li>
                  <li>Funciones de watchlist, portfolio simulado y track record de señales pasadas.</li>
                </ul>
                <p className="mt-3">
                  El acceso al Sitio Web y al Servicio atribuye la condición de <strong>usuario</strong> e implica la
                  aceptación plena e incondicional de todas y cada una de las disposiciones incluidas en
                  este Aviso Legal, en la Política de Privacidad y en la Política de Cookies, en la version
                  publicada en el momento en que el usuario acceda al Sitio Web.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">3. Condiciones de uso</h3>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">3.1. Acceso al Servicio</h4>
                <p className="mb-3">
                  El acceso a determinadas funcionalidades del Servicio requiere el registro previo del
                  usuario mediante la creación de una cuenta con un correo electrónico valido y una contraseña.
                </p>
                <p>
                  El usuario garantiza que los datos proporcionados durante el registro son verídicos,
                  exactos, completos y actualizados, siendo responsable de cualquier daño o perjuicio
                  que pudiera derivarse de la inexactitud de los mismos.
                </p>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">3.2. Obligaciones del usuario registrado</h4>
                <p className="mb-2">El usuario se compromete a:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Mantener la confidencialidad de sus credenciales de acceso y notificar de inmediato cualquier uso no autorizado de su cuenta.</li>
                  <li>Utilizar el Servicio de conformidad con la ley, la moral, el orden público y las presentes condiciones de uso.</li>
                  <li>No utilizar el Servicio para actividades ilegales, fraudulentas o que atenten contra los derechos de terceros.</li>
                </ul>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">3.3. Usos prohibidos</h4>
                <p className="mb-2">Queda expresamente prohibido:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Intentar acceder a cuentas, datos o sistemas de otros usuarios.</li>
                  <li>Realizar scraping, ingeniería inversa, descompilacion o cualquier forma de extracción automatizada del contenido del Servicio.</li>
                  <li>Provocar una sobrecarga intencionada de los servidores o cualquier interferencia con el normal funcionamiento del Servicio.</li>
                  <li>Redistribuir las señales, análisis o datos del Servicio a terceros con fines comerciales sin autorizacion expresa del Titular.</li>
                  <li>Suplantar la identidad de otro usuario o persona.</li>
                </ul>
                <p className="mt-3">
                  El incumplimiento de estas condiciones podrá dar lugar a la suspensión o cancelación
                  inmediata de la cuenta del usuario, sin perjuicio de las acciones legales que pudieran
                  corresponder.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">4. Propiedad intelectual e industrial</h3>
                <p className="mb-3">
                  Todos los contenidos del Sitio Web y del Servicio, incluyendo a título enunciativo pero
                  no limitativo: textos, gráficos, imágenes, logotipos, iconos, código fuente, modelos de
                  Machine Learning, algoritmos, bases de datos, diseño gráfico y software, son propiedad
                  del Titular o de terceros que han autorizado su uso, y están protegidos por las normas
                  nacionales e internacionales de propiedad intelectual e industrial.
                </p>
                <p className="mb-3">
                  Queda prohibida la reproducción, distribución, comunicación pública, transformación o
                  cualquier otra forma de explotación de los contenidos del Sitio Web sin la autorizacion
                  expresa y por escrito del Titular, salvo lo dispuesto legalmente.
                </p>
                <p>
                  Los datos de mercado mostrados proceden de fuentes públicas (GeckoTerminal, DexScreener,
                  APIs de blockchain) y su redistribución esta sujeta a las condiciones de dichas fuentes.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">5. Exencion de responsabilidad financiera</h3>
                <p className="mb-4 text-gem-yellow font-semibold">
                  EL SERVICIO NO CONSTITUYE ASESORAMIENTO FINANCIERO, DE INVERSION, FISCAL NI LEGAL DE
                  NINGUN TIPO.
                </p>
                <p className="mb-2">El usuario reconoce y acepta expresamente que:</p>
                <ol className="list-[lower-alpha] list-inside space-y-2 ml-2">
                  <li>Las señales, puntuaciones y análisis generados por el Servicio son el resultado de modelos estadísticos automáticos y <strong>no representan recomendaciones de compra, venta ni mantenimiento</strong> de ningún activo digital o de cualquier otra naturaleza.</li>
                  <li>Los memecoins son activos <strong>altamente especulativos y volátiles</strong>. El usuario asume que puede perder la <strong>totalidad</strong> de su inversión. El rendimiento pasado no es indicativo de resultados futuros.</li>
                  <li>El Titular <strong>no es una entidad regulada</strong> por la Comisión Nacional del Mercado de Valores (CNMV), la Securities and Exchange Commission (SEC) ni ningún otro organismo regulador financiero nacional o internacional.</li>
                  <li>Toda decisión de inversión es <strong>responsabilidad exclusiva del usuario</strong>. El Titular no será responsable en ningún caso de las pérdidas económicas, directas o indirectas, derivadas del uso de la información proporcionada por el Servicio.</li>
                  <li>El usuario debe realizar siempre su propia investigación (<strong>DYOR — Do Your Own Research</strong>) y, en su caso, consultar a un asesor financiero profesional antes de tomar cualquier decisión de inversión.</li>
                  <li>El Servicio opera en un mercado no regulado. Los activos analizados pueden ser objeto de manipulación de mercado, rug pulls u otras prácticas fraudulentas sobre las cuales el Titular no tiene control ni responsabilidad alguna.</li>
                </ol>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">6. Suscripciones y pagos</h3>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">6.1. Planes</h4>
                <p>
                  El Servicio ofrece distintos planes (Free, Pro, Enterprise) con diferentes niveles de
                  funcionalidad. Los precios, características y condiciones específicas de cada plan se
                  detallan en la página de Pricing del Sitio Web.
                </p>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">6.2. Procesamiento de pagos</h4>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Los pagos se procesan a través de <strong>Stripe</strong>, proveedor de pagos certificado <strong>PCI DSS Nivel 1</strong>. El Titular <strong>no almacena</strong> datos de tarjetas de crédito, números de cuenta bancaria ni información financiera sensible del usuario.</li>
                  <li>Los precios indicados incluyen el IVA aplicable salvo que se indique expresamente lo contrario.</li>
                </ul>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">6.3. Renovacion y cancelación</h4>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li>Las suscripciones se renuevan <strong>automáticamente</strong> al final de cada período de facturación (mensual), salvo cancelación previa por parte del usuario.</li>
                  <li>El usuario puede cancelar su suscripción en cualquier momento desde su panel de perfil. Al cancelar, el acceso a las funciones premium se mantiene hasta el final del período ya facturado.</li>
                </ul>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">6.4. Política de reembolsos</h4>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>No se realizan reembolsos parciales</strong> por periodos no consumidos, salvo en los casos expresamente previstos por la legislacion vigente en materia de consumidores y usuarios (Real Decreto Legislativo 1/2007) o por decisión discrecional del Titular.</li>
                  <li>El usuario dispone del derecho de desistimiento previsto en la normativa de consumidores dentro de los 14 días naturales siguientes a la contratación, siempre que no haya utilizado el Servicio de forma sustancial durante dicho período.</li>
                </ul>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">7. Limitacion de responsabilidad</h3>
                <ul className="list-disc list-inside space-y-2 ml-2">
                  <li>El Servicio se proporciona <strong>&quot;tal cual&quot; (as is)</strong> y <strong>&quot;según disponibilidad&quot; (as available)</strong>, sin garantias de ningún tipo, expresas o implicitas, incluyendo pero no limitandose a garantias de comerciabilidad, idoneidad para un fin particular o no infraccion.</li>
                  <li>El Titular <strong>no garantiza</strong> la disponibilidad ininterrumpida del Servicio, la exactitud de los datos de mercado mostrados, ni la rentabilidad de las señales generadas.</li>
                  <li>El Titular <strong>no será responsable</strong> de daños directos, indirectos, incidentales, consecuentes, especiales ni punitivos derivados del uso o la imposibilidad de uso del Servicio.</li>
                  <li>En cualquier caso, la <strong>responsabilidad máxima</strong> del Titular frente al usuario se limitara al importe total efectivamente pagado por el usuario en los <strong>3 meses</strong> inmediatamente anteriores al hecho causante de la responsabilidad.</li>
                  <li>El Titular no será responsable de los fallos o interrupciones del Servicio causados por razones de fuerza mayor, fallos de la red de Internet, fallos de las APIs de terceros (GeckoTerminal, DexScreener, blockchain RPCs) o cualquier otra circunstancia fuera de su control razonable.</li>
                </ul>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">8. Modificaciones de los Términos</h3>
                <p className="mb-3">
                  El Titular se reserva el derecho de modificar el presente Aviso Legal y las condiciones
                  de uso en cualquier momento. Los cambios sustanciales se comunicaran al usuario con una
                  antelacion mínima de <strong>15 días</strong> mediante correo electrónico o aviso destacado en el
                  Servicio.
                </p>
                <p>
                  El uso continuado del Servicio tras la entrada en vigor de las modificaciones constituye
                  la aceptación de los nuevos términos. En caso de desacuerdo, el usuario podrá cancelar su
                  cuenta sin penalizacion.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">9. Legislacion aplicable y jurisdiccion</h3>
                <p className="mb-3">
                  El presente Aviso Legal se rige e interpreta conforme a la <strong>legislacion española</strong>.
                </p>
                <p className="mb-3">
                  Para la resolución de cualquier controversia que pudiera derivarse del acceso o uso del
                  Servicio, las partes se someten a los <strong>Juzgados y Tribunales de Santa Cruz de Gran
                  Canaria (España)</strong>, sin perjuicio de lo dispuesto en la normativa vigente en materia de
                  consumidores y usuarios, que podrá determinar la competencia del tribunal del domicilio
                  del consumidor.
                </p>
                <p>
                  El usuario, como consumidor residente en la Unión Europea, también puede recurrir a la{" "}
                  <strong>plataforma europea de resolución de litigios en línea (ODR)</strong>:{" "}
                  <a href="https://ec.europa.eu/consumers/odr" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    https://ec.europa.eu/consumers/odr
                  </a>
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">10. Contacto</h3>
                <p className="mb-2">Para cualquier consulta relacionada con el presente Aviso Legal:</p>
                <p><strong>Email</strong>: <a href="mailto:info@memedetector.es" className="text-primary hover:underline">info@memedetector.es</a></p>
                <p className="mt-4 text-gray-500 italic">Última actualización: marzo 2026</p>
              </div>

            </div>
          </div>
        </section>

        {/* Separator */}
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="border-t border-dark-600" />
        </div>

        {/* ========== POLITICA DE PRIVACIDAD ========== */}
        <section id="privacidad" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Política de Privacidad
            </h2>
            <div className="space-y-8 text-gray-300 text-sm leading-relaxed">

              <p>
                La presente Política de Privacidad tiene por objeto informar a los usuarios del Sitio Web
                y del Servicio <strong>MemeDetector</strong> sobre el tratamiento de sus datos personales, en cumplimiento
                del <strong>Reglamento (UE) 2016/679 del Parlamento Europeo y del Consejo, de 27 de abril de 2016</strong>{" "}
                (Reglamento General de Protección de Datos, en adelante <strong>RGPD</strong>) y de la <strong>Ley Orgánica
                3/2018, de 5 de diciembre, de Protección de Datos Personales y garantía de los derechos
                digitales (LOPD-GDD)</strong>.
              </p>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">1. Responsable del tratamiento</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <tbody>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold w-44">Responsable</td><td className="py-2 px-3">ULL MIDDLE MOORE S.L.</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">NIF</td><td className="py-2 px-3">B76672864</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">Domicilio</td><td className="py-2 px-3">Carretera General La Perdoma 35, La Orotava, Santa Cruz de Tenerife, España</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 text-gray-400 font-semibold">Correo electrónico</td><td className="py-2 px-3">info@memedetector.es</td></tr>
                      <tr><td className="py-2 px-3 text-gray-400 font-semibold">Sitio web</td><td className="py-2 px-3">www.memedetector.es</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">2. Datos personales que recopilamos</h3>
                <p className="mb-4">
                  A continuacion se detallan las categorias de datos personales que recopilamos, la finalidad
                  de su tratamiento y la base jurídica que lo legitima conforme al RGPD:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-800">
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Dato personal</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Finalidad</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Base legal (RGPD)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Correo electrónico</td><td className="py-2 px-3">Registro, autenticación, comunicaciones de servicio</td><td className="py-2 px-3">Ejecucion del contrato (art. 6.1.b)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Contraseña (hash bcrypt)</td><td className="py-2 px-3">Autenticacion segura</td><td className="py-2 px-3">Ejecucion del contrato (art. 6.1.b)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Chat ID de Telegram</td><td className="py-2 px-3">Envio de alertas y notificaciones (opcional)</td><td className="py-2 px-3">Consentimiento del interesado (art. 6.1.a)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Nombre mostrado</td><td className="py-2 px-3">Personalizacion de la interfaz</td><td className="py-2 px-3">Consentimiento del interesado (art. 6.1.a)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Datos de suscripción</td><td className="py-2 px-3">Gestión del servicio y facturación</td><td className="py-2 px-3">Ejecucion del contrato (art. 6.1.b)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">ID de cliente de Stripe</td><td className="py-2 px-3">Vinculacion con procesador de pagos</td><td className="py-2 px-3">Ejecucion del contrato (art. 6.1.b)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Datos de pago</td><td className="py-2 px-3">Procesamiento de pagos</td><td className="py-2 px-3">Ejecucion del contrato (art. 6.1.b) — gestionado exclusivamente por Stripe</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Dirección IP</td><td className="py-2 px-3">Seguridad, prevención de abuso</td><td className="py-2 px-3">Interes legitimo (art. 6.1.f)</td></tr>
                      <tr><td className="py-2 px-3">User-Agent del navegador</td><td className="py-2 px-3">Seguridad, compatibilidad técnica</td><td className="py-2 px-3">Interes legitimo (art. 6.1.f)</td></tr>
                    </tbody>
                  </table>
                </div>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">Datos que NO recopilamos</h4>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>No recopilamos</strong> datos de categorias especiales (art. 9 RGPD): datos biométricos, de salud, orientación sexual, opiniones políticas, creencias religiosas, afiliación sindical ni datos geneticos.</li>
                  <li><strong>No recopilamos</strong> direcciones de wallets de criptomonedas ni claves privadas.</li>
                  <li><strong>No recopilamos</strong> datos de menores de 16 años de forma consciente. Si detectamos que un usuario es menor de dicha edad, procederemos a eliminar su cuenta y datos asociados de forma inmediata.</li>
                </ul>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">3. Finalidad del tratamiento</h3>
                <p className="mb-2">Los datos personales son tratados para las siguientes finalidades:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>Prestación del servicio</strong>: registro, autenticación, gestión de cuenta, generación y envio de señales y alertas.</li>
                  <li><strong>Facturacion y gestión de pagos</strong>: procesamiento de suscripciones y pagos a través de Stripe.</li>
                  <li><strong>Comunicaciones de servicio</strong>: avisos sobre cambios en los Términos, interrupciones programadas, actualizaciones relevantes del Servicio.</li>
                  <li><strong>Comunicaciones comerciales</strong>: unicamente si el usuario ha otorgado su consentimiento expreso, información sobre novedades y mejoras del Servicio.</li>
                  <li><strong>Seguridad</strong>: deteccion y prevención de accesos no autorizados, fraude y uso abusivo del Servicio.</li>
                  <li><strong>Mejora del servicio</strong>: análisis agregado y anonimizado de patrones de uso para optimizar funcionalidades. Estos datos anonimizados no constituyen datos personales.</li>
                </ul>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">4. Almacenamiento y medidas de seguridad</h3>
                <p className="mb-2">Los datos personales se almacenan aplicando las siguientes medidas técnicas y organizativas:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>Ubicación de los servidores</strong>: los datos se almacenan en Supabase, con servidores ubicados en la Unión Europea (región eu-central-1, Frankfurt, Alemania), garantizando que los datos no abandonan el Espacio Económico Europeo para su almacenamiento primario.</li>
                  <li><strong>Cifrado en transito</strong>: todas las comunicaciones entre el usuario y el Servicio se cifran mediante protocolo TLS 1.2 o superior (HTTPS).</li>
                  <li><strong>Cifrado de contrasenas</strong>: las contrasenas se almacenan como hashes bcrypt con salt aleatorio. En ningún caso se almacenan en texto plano.</li>
                  <li><strong>Control de acceso</strong>: el acceso a la base de datos esta protegido mediante Row Level Security (RLS) de Supabase, garantizando que cada usuario solo puede acceder a sus propios datos.</li>
                  <li><strong>Copias de seguridad</strong>: se realizan copias de seguridad automáticas diarias con cifrado.</li>
                  <li><strong>Principio de minimizacion</strong>: solo se recopilan los datos estrictamente necesarios para la prestación del Servicio (art. 5.1.c RGPD).</li>
                </ul>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">5. Encargados de tratamiento y comparticion de datos con terceros</h3>
                <p className="mb-4">
                  Para la prestación del Servicio, los datos personales pueden ser comunicados a los siguientes
                  terceros en calidad de encargados de tratamiento (art. 28 RGPD):
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-800">
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Encargado</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Ubicación</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Datos</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Finalidad</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Supabase Inc.</td><td className="py-2 px-3">Frankfurt, Alemania (UE)</td><td className="py-2 px-3">Todos los datos de cuenta</td><td className="py-2 px-3">Base de datos y autenticación</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Stripe Inc.</td><td className="py-2 px-3">Estados Unidos</td><td className="py-2 px-3">Email, datos de pago</td><td className="py-2 px-3">Procesamiento de pagos</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Telegram Messenger Inc.</td><td className="py-2 px-3">Emiratos Arabes Unidos</td><td className="py-2 px-3">Chat ID de Telegram</td><td className="py-2 px-3">Envio de alertas</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Render Inc.</td><td className="py-2 px-3">Estados Unidos</td><td className="py-2 px-3">IP, User-Agent</td><td className="py-2 px-3">Hosting de la aplicación</td></tr>
                      <tr><td className="py-2 px-3 font-semibold">Vercel Inc.</td><td className="py-2 px-3">Estados Unidos</td><td className="py-2 px-3">IP, User-Agent</td><td className="py-2 px-3">Hosting landing page y CDN</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className="mt-4">
                  <strong>No vendemos, alquilamos ni cedemos datos personales a terceros con fines comerciales,
                  publicitarios ni de elaboracion de perfiles.</strong>
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">6. Transferencias internacionales de datos</h3>
                <p className="mb-3">
                  Algunos de los encargados de tratamiento indicados en el apartado anterior tienen su sede
                  en <strong>Estados Unidos</strong>, fuera del Espacio Económico Europeo (EEE). En concreto: Stripe Inc.,
                  Render Inc. y Vercel Inc.
                </p>
                <p className="mb-2">Estas transferencias internacionales se realizan con las siguientes garantias conforme al Capítulo V del RGPD:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>Cláusulas Contractuales Tipo (CCT)</strong> aprobadas por la Comisión Europea (art. 46.2.c RGPD), incorporadas a los contratos con dichos proveedores.</li>
                  <li><strong>Medidas complementarias</strong> de seguridad técnica (cifrado TLS, pseudonimizacion cuando es posible) conforme a las recomendaciones del Comite Europeo de Protección de Datos (CEPD).</li>
                  <li>En su caso, <strong>decisiones de adecuación</strong> de la Comisión Europea cuando existan para el país de destino.</li>
                </ul>
                <p className="mt-3">
                  El almacenamiento primario de datos personales se realiza siempre en servidores dentro de
                  la Unión Europea (Supabase, Frankfurt).
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">7. Plazos de conservacion</h3>
                <p className="mb-4">Los datos personales se conservan durante los siguientes plazos:</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-800">
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Categoria de datos</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Plazo</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Justificacion</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Datos de cuenta (email, perfil)</td><td className="py-2 px-3">Mientras la cuenta permanezca activa</td><td className="py-2 px-3">Ejecucion del contrato</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Datos de cuenta tras eliminación</td><td className="py-2 px-3 font-semibold">30 días</td><td className="py-2 px-3">Periodo de supresión efectiva</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Datos de facturación</td><td className="py-2 px-3 font-semibold">4 años</td><td className="py-2 px-3">Ley 58/2003, General Tributaria</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3">Logs de acceso (IP, User-Agent)</td><td className="py-2 px-3 font-semibold">12 meses</td><td className="py-2 px-3">Ley 25/2007, conservacion de datos</td></tr>
                      <tr><td className="py-2 px-3">Chat ID de Telegram</td><td className="py-2 px-3">Hasta revocación o eliminación de cuenta</td><td className="py-2 px-3">Consentimiento (art. 6.1.a RGPD)</td></tr>
                    </tbody>
                  </table>
                </div>
                <p className="mt-3">Transcurridos los plazos indicados, los datos seran suprimidos o anonimizados de forma irreversible.</p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">8. Derechos del interesado (ARCO+ y derechos digitales)</h3>
                <p className="mb-4">
                  De conformidad con los articulos 15 a 22 del RGPD y los articulos 12 a 18 de la LOPD-GDD,
                  el usuario tiene reconocidos los siguientes derechos:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-800">
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Derecho</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Descripción</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Acceso (art. 15)</td><td className="py-2 px-3">Obtener confirmacion de si se están tratando sus datos personales y acceder a los mismos</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Rectificacion (art. 16)</td><td className="py-2 px-3">Solicitar la correccion de datos personales inexactos o completar los que sean incompletos</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Supresion (art. 17)</td><td className="py-2 px-3">Solicitar la eliminación de sus datos personales (&quot;derecho al olvido&quot;)</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Limitacion (art. 18)</td><td className="py-2 px-3">Solicitar la restriccion del tratamiento de sus datos</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Portabilidad (art. 20)</td><td className="py-2 px-3">Recibir sus datos en formato estructurado (JSON o CSV) y transmitirlos a otro responsable</td></tr>
                      <tr className="border-b border-dark-600"><td className="py-2 px-3 font-semibold">Oposicion (art. 21)</td><td className="py-2 px-3">Oponerse al tratamiento basado en el interes legitimo del responsable</td></tr>
                      <tr><td className="py-2 px-3 font-semibold">Revocacion del consentimiento</td><td className="py-2 px-3">Retirar el consentimiento prestado en cualquier momento</td></tr>
                    </tbody>
                  </table>
                </div>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">Cómo ejercer sus derechos</h4>
                <p className="mb-2">Para ejercer cualquiera de estos derechos, el usuario deberá enviar una solicitud a <a href="mailto:info@memedetector.es" className="text-primary hover:underline">info@memedetector.es</a> indicando:</p>
                <ol className="list-decimal list-inside space-y-1 ml-2">
                  <li>Nombre completo y correo electrónico asociado a la cuenta.</li>
                  <li>El derecho que desea ejercer.</li>
                  <li>Copia de documento identificativo (DNI, NIE o pasaporte) para verificar su identidad.</li>
                </ol>
                <p className="mt-3">
                  El responsable responderá en un plazo máximo de <strong>30 días</strong> desde la recepción de la solicitud,
                  prorrogable por otros 2 meses en caso de solicitudes complejas o multiples, conforme al art. 12.3 RGPD.
                </p>
                <p className="mt-2">
                  El ejercicio de estos derechos es <strong>gratuito</strong>, salvo solicitudes manifiestamente infundadas o excesivas (art. 12.5 RGPD).
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">9. Delegado de Protección de Datos</h3>
                <p className="mb-2">
                  Dado el volumen y naturaleza de los datos tratados, no se ha designado un Delegado de
                  Protección de Datos (DPD) al no ser obligatorio conforme al art. 37 RGPD. No obstante,
                  para cualquier cuestion relativa a la protección de datos personales, el usuario puede
                  contactar directamente con el responsable:
                </p>
                <p><strong>Email</strong>: <a href="mailto:info@memedetector.es" className="text-primary hover:underline">info@memedetector.es</a></p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">10. Autoridad de control</h3>
                <p className="mb-3">
                  Si el usuario considera que sus derechos en materia de protección de datos no han sido
                  debidamente atendidos, tiene derecho a presentar una reclamación ante la autoridad de
                  control competente:
                </p>
                <div className="border border-dark-600 p-4">
                  <p className="font-semibold text-white">Agencia Española de Protección de Datos (AEPD)</p>
                  <p>Sitio web: <a href="https://www.aepd.es" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">https://www.aepd.es</a></p>
                  <p>Dirección: C/ Jorge Juan, 6 — 28001 Madrid, España</p>
                  <p>Teléfono: 901 100 099 / 91 266 35 17</p>
                </div>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">11. Modificaciones de esta política</h3>
                <p className="mb-3">
                  El responsable se reserva el derecho de actualizar la presente Política de Privacidad para
                  adaptarla a novedades legislativas, jurisprudenciales o de práctica del sector. Los cambios
                  sustanciales se comunicaran al usuario mediante correo electrónico o aviso destacado en el
                  Servicio con una antelacion mínima de 15 días.
                </p>
                <p className="text-gray-500 italic">Última actualización: marzo 2026</p>
              </div>

            </div>
          </div>
        </section>

        {/* Separator */}
        <div className="max-w-4xl mx-auto px-4 sm:px-6">
          <div className="border-t border-dark-600" />
        </div>

        {/* ========== POLITICA DE COOKIES ========== */}
        <section id="cookies" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Política de Cookies
            </h2>
            <div className="space-y-8 text-gray-300 text-sm leading-relaxed">

              <p>
                La presente Política de Cookies se establece en cumplimiento del <strong>artículo 22.2 de la
                Ley 34/2002, de 11 de julio, de Servicios de la Sociedad de la Información y de Comercio
                Electrónico (LSSI-CE)</strong> y de la <strong>Directiva 2002/58/CE del Parlamento Europeo y del Consejo</strong>{" "}
                (Directiva ePrivacy), y tiene por objeto informar al usuario de manera clara y precisa sobre
                las cookies y tecnologías similares que se utilizan en el sitio web <strong>www.memedetector.es</strong>.
              </p>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">1. Qué son las cookies</h3>
                <p className="mb-3">
                  Las cookies son pequeños archivos de texto que los sitios web almacenan en el dispositivo
                  del usuario (ordenador, tablet, teléfono móvil) cuando este los visita. Las cookies permiten
                  al sitio web recordar información sobre la visita del usuario, como sus preferencias de
                  idioma, datos de inicio de sesión u otra información, con el fin de facilitar la siguiente
                  visita y hacer que el sitio resulte más útil.
                </p>
                <p>
                  Ademas de las cookies, existen otras tecnologías similares como el almacenamiento local
                  (localStorage) del navegador, que cumplen funciones análogas.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">2. Cookies y tecnologías que utilizamos</h3>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-4">2.1. Cookies técnicas / estrictamente necesarias</h4>
                <p className="mb-4">
                  Estas cookies son imprescindibles para el correcto funcionamiento del Servicio y están
                  <strong> exentas de consentimiento</strong> conforme al artículo 22.2 de la LSSI-CE y al Considerando 66
                  de la Directiva ePrivacy.
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-800">
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Cookie / Tecnologia</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Proveedor</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Finalidad</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Duracion</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600">
                        <td className="py-2 px-3">Cookie de sesión de Streamlit</td>
                        <td className="py-2 px-3">MemeDetector (propia)</td>
                        <td className="py-2 px-3">Mantener la sesión del usuario activa y gestionar la autenticación</td>
                        <td className="py-2 px-3">Sesion</td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3">localStorage (preferencias)</td>
                        <td className="py-2 px-3">MemeDetector (propia)</td>
                        <td className="py-2 px-3">Almacenar preferencias de tema visual y configuración de la interfaz</td>
                        <td className="py-2 px-3">Persistente</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-6">2.2. Cookies de Stripe (procesamiento de pagos)</h4>
                <p className="mb-4">
                  Cuando el usuario accede a la pasarela de pago para contratar una suscripción, <strong>Stripe</strong>{" "}
                  puede instalar cookies propias necesarias para el procesamiento seguro del pago y la
                  prevención del fraude. Estas cookies son <strong>estrictamente necesarias</strong> para completar la
                  transacción de pago y están amparadas por la excepción de cookies necesarias.
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-800">
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Cookie</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Proveedor</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Finalidad</th>
                        <th className="py-2 px-3 text-left text-gray-400 font-semibold">Tipo</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="py-2 px-3 font-mono text-xs">__stripe_mid / __stripe_sid</td>
                        <td className="py-2 px-3">Stripe Inc.</td>
                        <td className="py-2 px-3">Prevención de fraude y procesamiento seguro de pagos</td>
                        <td className="py-2 px-3">Técnica, necesaria</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p className="mt-3">
                  Para más información sobre las cookies de Stripe, consulte su política de cookies:{" "}
                  <a href="https://stripe.com/es/cookie-settings" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                    https://stripe.com/es/cookie-settings
                  </a>
                </p>

                <h4 className="text-gray-200 font-semibold text-sm mb-2 mt-6">2.3. Cookies que NO utilizamos</h4>
                <p className="mb-2">Es importante destacar que el Servicio <strong>NO utiliza</strong>:</p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><strong>Cookies de analitica</strong> (Google Analytics, Matomo, Plausible ni similares).</li>
                  <li><strong>Cookies de publicidad</strong> (Google Ads, Facebook Pixel, redes publicitarias ni similares).</li>
                  <li><strong>Cookies de redes sociales</strong> (botones de compartir, widgets de terceros ni similares).</li>
                  <li><strong>Cookies de seguimiento</strong> (tracking) de terceros de ninguna clase.</li>
                  <li><strong>Cookies de elaboracion de perfiles</strong> con fines comerciales o publicitarios.</li>
                </ul>
                <p className="mt-3">
                  Por este motivo, el Servicio <strong>no requiere un banner de consentimiento de cookies</strong>, ya que
                  unicamente utiliza cookies exentas de consentimiento conforme a la normativa vigente.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">3. Cómo gestionar y eliminar cookies</h3>
                <p className="mb-3">
                  El usuario puede configurar su navegador para aceptar o rechazar cookies, asi como para
                  eliminar las cookies ya almacenadas. A continuacion se facilitan enlaces a las instrucciones
                  de los navegadores más habituales:
                </p>
                <ul className="list-disc list-inside space-y-1 ml-2">
                  <li><a href="https://support.google.com/chrome/answer/95647" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Google Chrome</a></li>
                  <li><a href="https://support.mozilla.org/es/kb/cookies-información-que-los-sitios-web-guardan-en-" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Mozilla Firefox</a></li>
                  <li><a href="https://support.apple.com/es-es/guide/safari/sfri11471/mac" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Apple Safari</a></li>
                  <li><a href="https://support.microsoft.com/es-es/microsoft-edge/eliminar-cookies-en-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Microsoft Edge</a></li>
                </ul>
                <p className="mt-3">
                  <strong>Nota importante</strong>: la desactivación de las cookies técnicas/necesarias puede impedir el
                  correcto funcionamiento del Servicio, en particular la gestión de la sesión y la
                  autenticación.
                </p>
              </div>

              <div>
                <h3 className="text-white font-semibold text-base mb-3">4. Actualizacion de esta política</h3>
                <p className="mb-3">
                  El Titular se reserva el derecho de modificar la presente Política de Cookies para adaptarla
                  a novedades legislativas, tecnologicas o cambios en el funcionamiento del Servicio. Cualquier
                  cambio sustancial será comunicado al usuario mediante aviso en el Sitio Web.
                </p>
                <p className="mb-3">
                  Se recomienda al usuario revisar periódicamente esta Política de Cookies para estar informado
                  sobre como se utilizan.
                </p>
                <p className="text-gray-500 italic">Última actualización: marzo 2026</p>
              </div>

            </div>
          </div>
        </section>

        {/* Footer: back to top + copyright */}
        <div className="border-t border-dark-600">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-500">
            <div className="flex items-center gap-2">
              <span className="text-gray-400 font-semibold">Meme Detector</span>
              <span>&copy; {new Date().getFullYear()}</span>
            </div>
            <div className="flex items-center gap-4">
              <a href="#aviso-legal" className="hover:text-primary transition-colors">&uarr; Volver arriba</a>
              <span className="text-dark-600">|</span>
              <Link href="/" className="hover:text-primary transition-colors">Inicio</Link>
              <span className="text-dark-600">|</span>
              <a href="mailto:info@memedetector.es" className="hover:text-primary transition-colors">info@memedetector.es</a>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
