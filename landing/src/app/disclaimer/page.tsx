"use client";

import Navbar from "@/components/Navbar";
import Link from "next/link";

const sections = [
  { id: "que-somos", label: "Que somos" },
  { id: "que-no-somos", label: "Que NO somos" },
  { id: "marco-regulatorio", label: "Regulatorio" },
  { id: "senales", label: "Senales" },
  { id: "riesgos", label: "Riesgos" },
  { id: "responsabilidad", label: "Tu responsabilidad" },
  { id: "contacto", label: "Contacto" },
];

export default function DisclaimerPage() {
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
            <div className="flex items-center gap-2 flex-wrap">
              {sections.map((s) => (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className="text-[10px] sm:text-xs text-gray-400 hover:text-primary transition-colors uppercase tracking-wider border border-dark-600 px-2 sm:px-3 py-1 hover:border-primary/50"
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
            <span className="text-primary">&gt;</span> Que somos y que NO somos
          </h1>
          <p className="text-sm text-gray-500 mt-2 font-mono">
            Disclaimer &middot; Exencion de responsabilidad &middot; Marco regulatorio
          </p>
        </div>

        {/* ========== SECCION 1: QUE ES MEME DETECTOR ========== */}
        <section id="que-somos" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              1. Que es Meme Detector
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">
              <div className="border border-primary/30 bg-primary/5 p-6">
                <ul className="space-y-4">
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold mt-0.5">$</span>
                    <span>
                      Somos una <strong className="text-white">herramienta de software de analisis automatizado de datos</strong>.
                      Nuestro producto es tecnologia, no asesoramiento financiero.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold mt-0.5">$</span>
                    <span>
                      Utilizamos <strong className="text-white">Machine Learning</strong> para analizar caracteristicas publicas
                      de tokens en blockchains como Solana, Ethereum y Base. Los modelos identifican patrones
                      estadisticos en datos historicos.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold mt-0.5">$</span>
                    <span>
                      Proporcionamos <strong className="text-white">informacion estadistica y analisis de datos</strong>,
                      NO recomendaciones de inversion. La interpretacion y las decisiones corresponden
                      exclusivamente al usuario.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold mt-0.5">$</span>
                    <span>
                      Somos una <strong className="text-white">empresa tecnologica espanola</strong>:{" "}
                      <strong className="text-white">ULL MIDDLE MOORE S.L.</strong>, NIF B76672864,
                      con domicilio en Carretera General La Perdoma 35, La Orotava, Santa Cruz de Tenerife, Espana.
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ========== SECCION 2: QUE NO SOMOS ========== */}
        <section id="que-no-somos" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-gem-red mb-8 border-b border-gem-red/40 pb-3 uppercase tracking-wider">
              2. Que NO somos
            </h2>
            <div className="border-2 border-gem-red/50 bg-gem-red/5 p-6 md:p-8">
              <p className="text-gem-yellow font-semibold text-sm mb-6 uppercase tracking-wider">
                Es fundamental que entiendas lo que Meme Detector NO es:
              </p>
              <ul className="space-y-4 text-sm text-gray-300">
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO somos una empresa de asesoramiento financiero.</strong>{" "}
                    No proporcionamos recomendaciones personalizadas basadas en tus circunstancias individuales.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO estamos registrados ni autorizados por la CNMV, SEC, FCA ni ningun regulador financiero.</strong>{" "}
                    No somos una Empresa de Servicios de Inversion (ESI).
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO proporcionamos recomendaciones de compra, venta o mantenimiento de ningun activo.</strong>{" "}
                    Las puntuaciones son indicadores estadisticos, no instrucciones operativas.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO somos un broker, exchange, ni intermediario financiero.</strong>{" "}
                    No intermediamos en la compra o venta de ningún criptoactivo.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO gestionamos carteras ni fondos de inversion.</strong>{" "}
                    No tenemos acceso a tus fondos ni a tus wallets.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO garantizamos rentabilidad ni resultados de ningun tipo.</strong>{" "}
                    Los rendimientos pasados no garantizan resultados futuros.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold text-base shrink-0">X</span>
                  <span>
                    <strong className="text-white">NO somos responsables de las decisiones de inversion de nuestros usuarios.</strong>{" "}
                    Cada usuario asume la total responsabilidad de sus operaciones.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ========== SECCION 3: MARCO REGULATORIO ========== */}
        <section id="marco-regulatorio" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              3. Marco regulatorio
            </h2>
            <div className="space-y-8 text-gray-300 text-sm leading-relaxed">

              {/* MiFID II */}
              <div className="border border-dark-600 p-6">
                <h3 className="text-white font-semibold text-base mb-3 flex items-center gap-2">
                  <span className="text-primary font-mono text-xs">01</span>
                  MiFID II — Directiva 2014/65/UE
                </h3>
                <p>
                  Nuestro servicio <strong className="text-gem-yellow">NO constituye &quot;asesoramiento en materia de inversion&quot;</strong>{" "}
                  segun el articulo 4(1)(4) de la Directiva 2014/65/UE, ya que no proporcionamos recomendaciones
                  personalizadas basadas en las circunstancias individuales del cliente. Meme Detector es una
                  herramienta de analisis automatizado que genera indicadores estadisticos genericos, sin
                  considerar la situacion financiera, objetivos de inversion ni perfil de riesgo de ningun
                  usuario concreto.
                </p>
              </div>

              {/* MiCA */}
              <div className="border border-dark-600 p-6">
                <h3 className="text-white font-semibold text-base mb-3 flex items-center gap-2">
                  <span className="text-primary font-mono text-xs">02</span>
                  MiCA — Reglamento UE 2023/1114
                </h3>
                <p>
                  Los criptoactivos tipo memecoins <strong className="text-gem-yellow">NO estan clasificados como tokens referenciados
                  a activos (ART) ni tokens de dinero electronico (EMT)</strong> bajo el Reglamento de Mercados de
                  Criptoactivos. Son criptoactivos que quedan fuera del ambito regulatorio especifico de MiCA.
                  Meme Detector no emite, ofrece al publico ni solicita la admision a negociacion de ningun
                  criptoactivo. Somos exclusivamente un proveedor de herramientas de analisis de datos.
                </p>
              </div>

              {/* CNMV */}
              <div className="border border-dark-600 p-6">
                <h3 className="text-white font-semibold text-base mb-3 flex items-center gap-2">
                  <span className="text-primary font-mono text-xs">03</span>
                  CNMV — Comision Nacional del Mercado de Valores
                </h3>
                <p>
                  <strong className="text-gem-yellow">No estamos registrados como empresa de servicios de inversion (ESI)</strong> en la CNMV.
                  No necesitamos estarlo porque NO proporcionamos asesoramiento financiero, gestion de carteras,
                  ni intermediacion en la compraventa de valores o criptoactivos. Nuestro servicio es analisis
                  de datos automatizado: un software que procesa informacion publica de blockchains y genera
                  metricas estadisticas.
                </p>
              </div>

              {/* Ley 10/2010 */}
              <div className="border border-dark-600 p-6">
                <h3 className="text-white font-semibold text-base mb-3 flex items-center gap-2">
                  <span className="text-primary font-mono text-xs">04</span>
                  Ley 10/2010 — Prevencion de blanqueo de capitales
                </h3>
                <p>
                  <strong className="text-gem-yellow">No intermediamos con fondos de clientes.</strong>{" "}
                  No custodiamos, transferimos ni gestionamos criptoactivos o dinero fiat de nuestros usuarios.
                  Los pagos de suscripcion se procesan exclusivamente mediante <strong className="text-white">Stripe</strong>{" "}
                  (certificado PCI DSS Level 1), un procesador de pagos regulado. En ningun momento tenemos
                  acceso a los datos de pago completos del usuario.
                </p>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 4: NATURALEZA DE LAS SENALES ========== */}
        <section id="senales" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-gem-yellow mb-8 border-b border-gem-yellow/40 pb-3 uppercase tracking-wider">
              4. Naturaleza de las &quot;senales&quot;
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">
              <div className="border border-gem-yellow/30 bg-gem-yellow/5 p-6 md:p-8">
                <ul className="space-y-5">
                  <li className="flex items-start gap-3">
                    <span className="text-gem-yellow font-bold shrink-0">!</span>
                    <span>
                      Las &quot;senales&quot; que genera Meme Detector son el resultado de un{" "}
                      <strong className="text-white">algoritmo de Machine Learning</strong> (Random Forest + XGBoost).
                      Son calculos matematicos, no opiniones ni recomendaciones.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-gem-yellow font-bold shrink-0">!</span>
                    <span>
                      Son <strong className="text-white">indicadores estadisticos basados en datos publicos</strong> de
                      blockchain (precios, volumenes, liquidez, holders, etc.),{" "}
                      <strong className="text-gem-red">NO recomendaciones de inversion</strong>.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-gem-yellow font-bold shrink-0">!</span>
                    <span>
                      Un &quot;score alto&quot; significa que el algoritmo ha detectado{" "}
                      <strong className="text-white">patrones similares a tokens que historicamente tuvieron revalorizacion</strong>.{" "}
                      <strong className="text-gem-red">NO significa que el token vaya a subir.</strong>{" "}
                      Correlacion no implica causalidad.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-gem-yellow font-bold shrink-0">!</span>
                    <span>
                      El modelo tiene una tasa de acierto del{" "}
                      <strong className="text-white">~67% (F1-score)</strong>. Esto implica que aproximadamente{" "}
                      <strong className="text-gem-red">~33% de las senales NO se materializan</strong>.
                      Ningun modelo de Machine Learning es perfecto.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-gem-yellow font-bold shrink-0">!</span>
                    <span>
                      <strong className="text-gem-red">Rendimientos pasados NO garantizan resultados futuros.</strong>{" "}
                      El mercado de memecoins es altamente impredecible y los patrones historicos pueden
                      dejar de funcionar en cualquier momento.
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ========== SECCION 5: RIESGOS DE LOS MEMECOINS ========== */}
        <section id="riesgos" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-gem-red mb-8 border-b border-gem-red/40 pb-3 uppercase tracking-wider">
              5. Riesgos de los memecoins
            </h2>
            <div className="border-2 border-gem-red/50 bg-gem-red/5 p-6 md:p-8">
              <p className="text-gem-red font-semibold text-sm mb-6 uppercase tracking-wider">
                Advertencia de riesgo — Lectura obligatoria
              </p>
              <ul className="space-y-4 text-sm text-gray-300">
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold shrink-0">&gt;</span>
                  <span>
                    Los memecoins son activos <strong className="text-white">altamente especulativos y volatiles</strong>.
                    Pueden perder el 90-100% de su valor en minutos.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold shrink-0">&gt;</span>
                  <span>
                    <strong className="text-white">Puedes perder el 100% de tu inversion.</strong>{" "}
                    Este escenario no es improbable, es estadisticamente frecuente en memecoins.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold shrink-0">&gt;</span>
                  <span>
                    Los memecoins <strong className="text-white">no tienen valor intrinseco ni respaldo de activos</strong>.
                    Su precio depende exclusivamente de la especulacion y el sentimiento del mercado.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold shrink-0">&gt;</span>
                  <span>
                    Son susceptibles a <strong className="text-white">manipulacion de mercado</strong>: pump &amp; dump,
                    rug pulls, wash trading, insider trading y otras practicas fraudulentas.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold shrink-0">&gt;</span>
                  <span>
                    La <strong className="text-white">liquidez puede desaparecer en segundos</strong>.
                    Es posible que no puedas vender tu posicion cuando lo desees.
                  </span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-gem-red font-bold shrink-0">&gt;</span>
                  <span>
                    <strong className="text-white">No estan protegidos por ningun fondo de garantia</strong> de
                    depositos ni de inversiones. Si pierdes tu dinero, nadie te lo devolvera.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ========== SECCION 6: TU RESPONSABILIDAD ========== */}
        <section id="responsabilidad" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              6. Tu responsabilidad
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">
              <div className="border border-dark-600 p-6 md:p-8">
                <ul className="space-y-4">
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold shrink-0">&gt;</span>
                    <span>
                      El usuario es el <strong className="text-white">unico responsable de sus decisiones de inversion</strong>.
                      Meme Detector no tiene ningun control ni influencia sobre las operaciones que realices.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold shrink-0">&gt;</span>
                    <span>
                      Debes realizar tu propia investigacion (<strong className="text-white">DYOR — Do Your Own Research</strong>)
                      antes de cualquier operacion. Las senales de Meme Detector son un punto de partida
                      para tu analisis, no una conclusion.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold shrink-0">&gt;</span>
                    <span>
                      <strong className="text-gem-red">No inviertas dinero que no puedas permitirte perder.</strong>{" "}
                      Los memecoins deben representar solo una fraccion marginal de tu patrimonio,
                      y solo si comprendes y aceptas los riesgos.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold shrink-0">&gt;</span>
                    <span>
                      <strong className="text-white">Consulta con un asesor financiero registrado</strong> si
                      necesitas asesoramiento personalizado. Los profesionales registrados en la CNMV
                      estan cualificados para evaluar tu situacion individual.
                    </span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-bold shrink-0">&gt;</span>
                    <span>
                      Al usar Meme Detector, <strong className="text-white">aceptas estos terminos y la exencion de
                      responsabilidad</strong> en su totalidad. Si no estas de acuerdo, no utilices el servicio.
                    </span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* ========== SECCION 7: CONTACTO REGULATORIO ========== */}
        <section id="contacto" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              7. Contacto regulatorio
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">
              <div className="border border-dark-600 p-6">
                <p className="mb-6">
                  Si consideras que nuestro servicio incumple alguna normativa aplicable, puedes dirigirte a:
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm border border-dark-600">
                    <tbody>
                      <tr className="border-b border-dark-600">
                        <td className="py-3 px-4 text-gray-400 font-semibold w-40">Meme Detector</td>
                        <td className="py-3 px-4">
                          <a href="mailto:legal@memedetector.es" className="text-primary hover:underline">
                            legal@memedetector.es
                          </a>
                        </td>
                      </tr>
                      <tr className="border-b border-dark-600">
                        <td className="py-3 px-4 text-gray-400 font-semibold">CNMV</td>
                        <td className="py-3 px-4">
                          <a href="https://www.cnmv.es" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                            www.cnmv.es
                          </a>
                          <span className="text-gray-500 mx-2">|</span>
                          <span>Tel: 900 535 015</span>
                        </td>
                      </tr>
                      <tr>
                        <td className="py-3 px-4 text-gray-400 font-semibold">AEPD</td>
                        <td className="py-3 px-4">
                          <a href="https://www.aepd.es" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                            www.aepd.es
                          </a>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Bottom disclaimer bar */}
        <div className="border-t border-dark-600 bg-dark-800/50">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 text-center">
            <p className="text-xs text-gray-500">
              Ultima actualizacion: marzo 2026 &middot; ULL MIDDLE MOORE S.L. &middot; NIF B76672864
            </p>
            <div className="mt-3 flex items-center justify-center gap-4 text-xs">
              <Link href="/legal" className="text-gray-400 hover:text-primary transition-colors">
                Aviso Legal
              </Link>
              <span className="text-dark-600">|</span>
              <Link href="/legal#privacidad" className="text-gray-400 hover:text-primary transition-colors">
                Privacidad
              </Link>
              <span className="text-dark-600">|</span>
              <Link href="/" className="text-gray-400 hover:text-primary transition-colors">
                Volver al inicio
              </Link>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
