"use client";

import { useState, useEffect } from "react";
import Navbar from "@/components/Navbar";
import Link from "next/link";

/* Secciones de la academia con sus anchor links */
const sections = [
  { id: "criptomonedas", label: "Criptomonedas" },
  { id: "memecoins", label: "Memecoins" },
  { id: "conceptos", label: "Conceptos" },
  { id: "riesgo", label: "Riesgo" },
  { id: "como-comprar", label: "Cómo comprar" },
  { id: "red-flags", label: "Red Flags" },
  { id: "anatomia-pump", label: "Anatomía Pump" },
  { id: "narrativas", label: "Narrativas" },
  { id: "donde-nacen", label: "Dónde nacen" },
  { id: "smart-money", label: "Smart Money" },
  { id: "suma-negativa", label: "Suma negativa" },
  { id: "gestión-emocional", label: "Emociones" },
  { id: "métricas-clave", label: "Métricas" },
];

export default function AcademiaPage() {
  const [activeSection, setActiveSection] = useState<string>("");

  /* IntersectionObserver: detecta la seccion visible al hacer scroll */
  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    const visibleSections = new Map<string, number>();

    sections.forEach((s) => {
      const el = document.getElementById(s.id);
      if (!el) return;

      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              visibleSections.set(s.id, entry.intersectionRatio);
            } else {
              visibleSections.delete(s.id);
            }

            /* De las secciones visibles, activar la que aparece primero en el DOM */
            if (visibleSections.size > 0) {
              const first = sections.find((sec) => visibleSections.has(sec.id));
              if (first) setActiveSection(first.id);
            }
          });
        },
        { rootMargin: "-120px 0px -40% 0px", threshold: [0, 0.1, 0.3] }
      );

      observer.observe(el);
      observers.push(observer);
    });

    return () => observers.forEach((o) => o.disconnect());
  }, []);

  return (
    <main className="min-h-screen bg-dark-900">
      {/* Header fijo */}
      <div className="fixed top-0 left-0 right-0 z-50">
        <Navbar />
      </div>

      {/* Contenido */}
      <div className="pt-[72px]">
        {/* Barra superior: volver + anchor links */}
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
                  className={`text-xs uppercase tracking-wider border px-2 py-1 transition-all duration-300 ${
                    activeSection === s.id
                      ? "text-primary border-primary/60 bg-primary/10 shadow-[0_0_8px_rgba(0,212,170,0.3),0_0_16px_rgba(0,212,170,0.15)]"
                      : "text-gray-400 border-dark-600 hover:text-primary hover:border-primary/50"
                  }`}
                >
                  {s.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Título de la página */}
        <div className="max-w-4xl mx-auto px-4 sm:px-6 pt-10 pb-6">
          <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
            <span className="text-primary">&gt;</span> Academia
          </h1>
          <p className="text-sm text-gray-500 mt-2 font-mono">
            Aprende los fundamentos de criptomonedas y memecoins desde cero.
          </p>
        </div>

        {/* ========== SECCION 1: QUE SON LAS CRIPTOMONEDAS ========== */}
        <section id="criptomonedas" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Qué son las criptomonedas
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Moneda digital descentralizada</h3>
                <p>
                  Una criptomoneda es una <strong className="text-primary">moneda digital</strong> que funciona sin
                  bancos ni gobiernos. En lugar de depender de una entidad central (como el Banco de España),
                  las transacciones se verifican y registran en una red de ordenadores distribuida por todo el mundo.
                </p>
                <p className="mt-3">
                  Esto significa que <strong>nadie puede congelar tu cuenta</strong>, <strong>nadie puede
                  imprimir más moneda</strong> arbitrariamente, y las transacciones son públicas y verificables por cualquiera.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Blockchain = Libro contable público</h3>
                <p>
                  La <strong className="text-primary">blockchain</strong> es la tecnología detrás de las criptomonedas.
                  Piensa en ella como un <strong>libro contable gigante</strong> donde se registran todas las
                  transacciones, y ese libro está copiado en miles de ordenadores al mismo tiempo.
                </p>
                <p className="mt-3">
                  Cada &quot;página&quot; del libro se llama <strong>bloque</strong>, y cada bloque está
                  enlazado al anterior formando una cadena. Una vez que algo se escribe, <strong>no se puede borrar ni
                  modificar</strong>. Por eso se dice que la blockchain es &quot;inmutable&quot;.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Bitcoin vs Altcoins vs Memecoins</h3>
                <div className="overflow-x-auto mt-3">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-700">
                        <th className="py-2 px-3 text-left text-primary font-semibold">Tipo</th>
                        <th className="py-2 px-3 text-left text-primary font-semibold">Descripción</th>
                        <th className="py-2 px-3 text-left text-primary font-semibold">Ejemplos</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600">
                        <td className="py-2 px-3 text-white font-semibold">Bitcoin (BTC)</td>
                        <td className="py-2 px-3">La primera criptomoneda. Reserva de valor digital, &quot;oro digital&quot;.</td>
                        <td className="py-2 px-3">Bitcoin</td>
                      </tr>
                      <tr className="border-b border-dark-600">
                        <td className="py-2 px-3 text-white font-semibold">Altcoins</td>
                        <td className="py-2 px-3">Todas las criptomonedas que NO son Bitcoin. Muchas tienen utilidad real.</td>
                        <td className="py-2 px-3">Ethereum, Solana, Cardano</td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-white font-semibold">Memecoins</td>
                        <td className="py-2 px-3">Tokens basados en memes o cultura de internet. Sin utilidad clara, valor especulativo.</td>
                        <td className="py-2 px-3">Dogecoin, Pepe, Bonk</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 2: QUE ES UN MEMECOIN ========== */}
        <section id="memecoins" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Qué es un memecoin
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Tokens inspirados en memes</h3>
                <p>
                  Un memecoin es un <strong className="text-primary">token de criptomoneda</strong> cuyo valor no
                  proviene de una tecnología innovadora o un servicio útil, sino de la{" "}
                  <strong>cultura de internet, memes y la comunidad</strong> que se forma a su alrededor.
                </p>
                <p className="mt-3">
                  El primer memecoin fue <strong>Dogecoin (DOGE)</strong>, creado en 2013 como una broma basada
                  en el meme del perro Shiba Inu. Hoy existen miles de memecoins en diferentes blockchains.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Ejemplos conocidos</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
                  <div className="border border-dark-600 p-3 text-center">
                    <p className="text-white font-bold text-lg">DOGE</p>
                    <p className="text-gray-500 text-xs mt-1">El original. Creado como broma, llegó a top 10 por market cap.</p>
                  </div>
                  <div className="border border-dark-600 p-3 text-center">
                    <p className="text-white font-bold text-lg">PEPE</p>
                    <p className="text-gray-500 text-xs mt-1">Basado en la rana Pepe. Ethereum. Explotó en 2023.</p>
                  </div>
                  <div className="border border-dark-600 p-3 text-center">
                    <p className="text-white font-bold text-lg">BONK</p>
                    <p className="text-gray-500 text-xs mt-1">El primer gran memecoin de Solana. Airdrop masivo.</p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Diferencia con utility tokens</h3>
                <p>
                  Un <strong>utility token</strong> (como ETH o SOL) tiene una función real: pagar gas fees,
                  participar en gobernanza, acceder a servicios. Un <strong className="text-gem-yellow">memecoin no
                  tiene utilidad intrínseca</strong> &mdash; su valor depende exclusivamente de la percepción,
                  el hype y la comunidad.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Por que suben y bajan</h3>
                <ul className="list-disc list-inside space-y-2 ml-2">
                  <li><strong className="text-white">Hype y viralidad:</strong> Un tweet de un influencer puede multiplicar el precio en minutos.</li>
                  <li><strong className="text-white">Comunidad:</strong> Cuanto más grande y activa la comunidad, más demanda.</li>
                  <li><strong className="text-white">Narrativa:</strong> Los memecoins que enganchan con la tendencia del momento suben más rápido.</li>
                  <li><strong className="text-white">Liquidez:</strong> Con poca liquidez, cualquier compra o venta mueve mucho el precio.</li>
                </ul>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 3: CONCEPTOS BASICOS ========== */}
        <section id="conceptos" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Conceptos básicos
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              {/* Wallet */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Wallet (billetera digital)</h3>
                </div>
                <p>
                  Es tu &quot;cuenta bancaria&quot; en el mundo crypto. Almacena tus criptomonedas y te permite
                  enviar y recibir tokens. Cada wallet tiene una <strong>dirección pública</strong> (como un IBAN) y
                  una <strong>clave privada</strong> (como tu PIN &mdash; <span className="text-gem-red">NUNCA la compartas</span>).
                </p>
                <p className="mt-2 text-gray-500">
                  Ejemplos: Phantom (Solana), MetaMask (Ethereum/Base), Ledger (hardware wallet).
                </p>
              </div>

              {/* DEX vs CEX */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">DEX vs CEX</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">CEX (Exchange Centralizado)</p>
                    <p>Plataformas como Binance, Coinbase o Kraken. Tú depositas tu dinero y ellos lo custodian. Fácil de usar, pero tienes que confiar en la empresa.</p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">DEX (Exchange Descentralizado)</p>
                    <p>Plataformas como Jupiter (Solana) o Uniswap (Ethereum). Conectas tu wallet directamente. Tú controlas tus fondos siempre. Aquí se compran los memecoins.</p>
                  </div>
                </div>
              </div>

              {/* Liquidez */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Liquidez</h3>
                </div>
                <p>
                  La liquidez indica <strong>cuanto dinero hay disponible</strong> para comprar y vender un token
                  sin que el precio se mueva drásticamente. Un token con alta liquidez (ej: $1M+) es más seguro
                  de operar. Un token con baja liquidez (ej: $5K) puede tener movimientos de precio extremos.
                </p>
                <p className="mt-2 text-gem-yellow">
                  Regla de oro: nunca inviertas en un token con menos liquidez que la cantidad que quieres invertir.
                </p>
              </div>

              {/* Market Cap vs FDV */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Market Cap vs FDV</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">Market Cap</p>
                    <p>Precio actual x tokens en circulación. Es el &quot;tamaño real&quot; del token ahora mismo.</p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">FDV (Fully Diluted Valuation)</p>
                    <p>Precio actual x TODOS los tokens que existiran. Si hay mucha diferencia con Market Cap, significa que van a salir muchos tokens nuevos al mercado (dilución).</p>
                  </div>
                </div>
              </div>

              {/* Rug Pull */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-gem-red font-mono text-lg">!</span>
                  <h3 className="text-white font-semibold text-base">Rug Pull</h3>
                </div>
                <p>
                  Un <strong className="text-gem-red">rug pull</strong> (&quot;tirar de la alfombra&quot;) ocurre cuando
                  los creadores de un token <strong>retiran toda la liquidez</strong> de repente, dejando a los
                  compradores con tokens que ya no valen nada. Es la estafa más común en memecoins.
                </p>
                <p className="mt-2">
                  Señales de alerta: liquidez no bloqueada, creador con historial de rug pulls,
                  promesas exageradas de rentabilidad.
                </p>
              </div>

              {/* DYOR */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">DYOR (Do Your Own Research)</h3>
                </div>
                <p>
                  &quot;Haz tu propia investigación&quot;. Antes de comprar cualquier token, investiga: quien lo creó,
                  que problema resuelve, como esta la liquidez, quienes son los holders principales,
                  y si el contrato esta verificado. <strong>Nunca compres solo porque alguien te lo recomendó.</strong>
                </p>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 4: RIESGO / RECOMPENSA ========== */}
        <section id="riesgo" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Riesgo / Recompensa en memecoins
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              {/* Aviso destacado */}
              <div className="border-2 border-gem-red bg-gem-red/5 p-5">
                <p className="text-gem-red font-bold text-base mb-2">AVISO IMPORTANTE</p>
                <p>
                  Esta información es <strong>educativa</strong>, no constituye asesoramiento financiero.
                  Las criptomonedas, y especialmente los memecoins, son activos <strong>altamente
                  especulativos</strong>. Puedes perder la totalidad de tu inversión.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">La realidad de los números</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-gem-red/30 p-4 text-center">
                    <p className="text-gem-red text-4xl font-bold">99%</p>
                    <p className="text-gray-400 mt-2">de los memecoins van a cero</p>
                  </div>
                  <div className="border border-primary/30 p-4 text-center">
                    <p className="text-primary text-4xl font-bold">1%</p>
                    <p className="text-gray-400 mt-2">puede hacer 10x, 100x o más</p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Reglas de gestión de riesgo</h3>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[1]</span>
                    <span><strong className="text-white">Nunca inviertas más de lo que puedas perder.</strong> Si pierdes ese dinero, tu vida debe seguir exactamente igual.</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[2]</span>
                    <span><strong className="text-white">Maximo 1-5% del portfolio por token.</strong> Si tienes 1000 EUR para memecoins, máximo 10-50 EUR por cada token individual.</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[3]</span>
                    <span><strong className="text-white">Diversifica.</strong> Es mejor tener 20 posiciones pequeñas que 1 posición grande. Si 19 van a cero y 1 hace 100x, sales ganando.</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[4]</span>
                    <span><strong className="text-gem-yellow">Si suena demasiado bien para ser verdad, probablemente lo es.</strong> Desconfía de &quot;ganancias garantizadas&quot;, grupos VIP de señales, y promesas de rentabilidad fija.</span>
                  </li>
                </ul>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 5: COMO COMPRAR UN MEMECOIN ========== */}
        <section id="como-comprar" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Cómo comprar un memecoin (paso a paso)
            </h2>
            <div className="space-y-4 text-gray-300 text-sm leading-relaxed text-justify">

              {/* Paso 1 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">1</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Crear una wallet</h3>
                  <p>
                    Descarga <strong>Phantom</strong> (para Solana) o <strong>MetaMask</strong> (para Ethereum/Base)
                    desde sus páginas oficiales. Al crearla, te dara una <strong>frase semilla de 12-24
                    palabras</strong>. Guardala en un lugar seguro offline.{" "}
                    <span className="text-gem-red font-semibold">NUNCA la compartas con nadie.</span>
                  </p>
                </div>
              </div>

              {/* Paso 2 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">2</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Comprar SOL o ETH en un exchange</h3>
                  <p>
                    Registrate en un exchange centralizado como <strong>Binance</strong>, <strong>Coinbase</strong> o{" "}
                    <strong>Kraken</strong>. Compra SOL (si quieres memecoins de Solana) o ETH (para Ethereum/Base)
                    con tu tarjeta o transferencia bancaria.
                  </p>
                </div>
              </div>

              {/* Paso 3 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">3</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Enviar a tu wallet</h3>
                  <p>
                    Desde el exchange, retira tus SOL/ETH a la dirección de tu wallet personal.
                    Copia la dirección de tu wallet con cuidado (verifica los primeros y últimos caracteres).
                    La primera vez, envía una cantidad pequeña de prueba.
                  </p>
                </div>
              </div>

              {/* Paso 4 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">4</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Conectar a un DEX</h3>
                  <p>
                    Ve a <strong>Jupiter</strong> (jup.ag, para Solana) o <strong>Uniswap</strong> (uniswap.org,
                    para Ethereum). Haz clic en &quot;Connect Wallet&quot; y selecciona tu wallet (Phantom o MetaMask).
                  </p>
                </div>
              </div>

              {/* Paso 5 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">5</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Buscar el token por dirección de contrato</h3>
                  <p>
                    <span className="text-gem-red font-semibold">IMPORTANTE:</span> Busca siempre por la{" "}
                    <strong>dirección del contrato (contract address)</strong>, nunca por nombre. Hay muchos tokens
                    falsos con el mismo nombre. La dirección la encuentras en DexScreener, GeckoTerminal o
                    la web oficial del proyecto.
                  </p>
                </div>
              </div>

              {/* Paso 6 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">6</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Ajustar slippage</h3>
                  <p>
                    El <strong>slippage</strong> es la diferencia máxima de precio que aceptas entre cuando
                    envías la transacción y cuando se ejecuta. Para memecoins con baja liquidez,
                    puede ser necesario subir el slippage al 1-5%. Si es mucho mayor, desconfía.
                  </p>
                </div>
              </div>

              {/* Paso 7 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">7</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Confirmar transacción</h3>
                  <p>
                    Revisa los detalles del swap (cantidad, precio, gas fees) y confirma en tu wallet.
                    En Solana las transacciones tardan 1-2 segundos. En Ethereum pueden tardar
                    30 segundos a varios minutos dependiendo del gas.
                  </p>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 6: RED FLAGS ========== */}
        <section id="red-flags" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Señales de alerta (Red Flags)
            </h2>
            <div className="space-y-4 text-gray-300 text-sm leading-relaxed text-justify">

              <p className="text-gray-400 mb-4">
                Si un token presenta una o más de estas señales, <strong className="text-gem-red">aumenta
                significativamente el riesgo</strong> de perder tu inversión:
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Equipo anónimo sin historial</p>
                  <p className="text-gray-400 text-xs">
                    Si no puedes verificar quién está detrás del proyecto, no hay responsabilidad.
                    Los mejores proyectos tienen fundadores públicos con reputación.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Liquidez no bloqueada</p>
                  <p className="text-gray-400 text-xs">
                    Si la liquidez no está &quot;lockeada&quot; (bloqueada en un smart contract con tiempo),
                    el creador puede retirarla en cualquier momento = rug pull.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Concentracion de holders</p>
                  <p className="text-gray-400 text-xs">
                    Si una sola wallet tiene más del 50% del supply, esa persona puede vender
                    todo y destruir el precio. Usa BubbleMaps para verificar.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Contrato no verificado</p>
                  <p className="text-gray-400 text-xs">
                    Un contrato no verificado significa que no puedes ver el código. Podría
                    contener funciones maliciosas (impuestos ocultos, honeypot, mint infinito).
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Promesas de rentabilidad garantizada</p>
                  <p className="text-gray-400 text-xs">
                    Nadie puede garantizar ganancias en crypto. Si alguien te promete
                    &quot;100% seguro&quot; o &quot;sin riesgo&quot;, es una estafa. Siempre.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Web/redes sociales copiadas</p>
                  <p className="text-gray-400 text-xs">
                    Webs clonadas, cuentas de Twitter recien creadas, Discord sin actividad real.
                    Verifica siempre los enlaces oficiales desde fuentes confiables.
                  </p>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 7: ANATOMIA DE UN PUMP ========== */}
        <section id="anatomia-pump" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Anatomía de un pump
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Las 5 fases de un pump</h3>
                <p className="mb-4">
                  Casi todos los pumps de memecoins siguen un patrón predecible. Entender estas fases te permite
                  identificar <strong className="text-primary">donde estas</strong> en el ciclo y tomar mejores decisiones.
                </p>
                <div className="space-y-4">
                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-primary font-mono font-bold">FASE 1</span>
                      <span className="text-white font-semibold">Acumulación silenciosa</span>
                    </div>
                    <p className="text-gray-400">
                      Los &quot;insiders&quot; o wallets informadas compran grandes cantidades cuando nadie esta mirando.
                      El precio apenas se mueve. El volumen es bajo pero constante. Las redes sociales están en silencio.
                      <strong className="text-primary"> Es el mejor momento para entrar, pero el más difícil de detectar.</strong>
                    </p>
                    <p className="text-gray-500 text-xs mt-2">
                      Señales: Volumen bajo pero creciente, holders aumentando gradualmente, compras grandes sin movimiento de precio.
                    </p>
                  </div>

                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-primary font-mono font-bold">FASE 2</span>
                      <span className="text-white font-semibold">Primer pump</span>
                    </div>
                    <p className="text-gray-400">
                      El precio explota entre un 200% y un 1000% en horas. El volumen se multiplica por 5x-20x.
                      Twitter y Telegram se llenan de posts. Los influencers empiezan a mencionarlo.
                      <strong className="text-gem-yellow"> Si no entraste en la Fase 1, aun hay oportunidad, pero con más riesgo.</strong>
                    </p>
                    <p className="text-gray-500 text-xs mt-2">
                      Señales: Volumen explosivo, trending en DexScreener, menciones organicas en redes sociales.
                    </p>
                  </div>

                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-primary font-mono font-bold">FASE 3</span>
                      <span className="text-white font-semibold">Consolidación</span>
                    </div>
                    <p className="text-gray-400">
                      El precio corrige un 30-60% desde el máximo. Los &quot;manos débiles&quot; venden en pánico.
                      Pero los holders comprometidos mantienen. El volumen baja pero se estabiliza. Se forma un{" "}
                      <strong className="text-primary">soporte claro</strong>. Es una segunda ventana de entrada más segura que la Fase 2.
                    </p>
                    <p className="text-gray-500 text-xs mt-2">
                      Señales: Precio formando rango lateral, soporte respetado 2-3 veces, volumen estable, comunidad activa.
                    </p>
                  </div>

                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-primary font-mono font-bold">FASE 4</span>
                      <span className="text-white font-semibold">Segundo pump (si ocurre)</span>
                    </div>
                    <p className="text-gray-400">
                      Si la comunidad sobrevive la consolidacion, puede haber un segundo rally. A menudo
                      impulsado por un <strong>catalizador</strong>: listing en un exchange centralizado (CEX),
                      mencion de un influencer grande, o una narrativa renovada.
                      El precio puede superar el máximo anterior.
                    </p>
                    <p className="text-gray-500 text-xs mt-2">
                      Señales: Breakout del rango con volumen alto, nuevo ATH, noticias de CEX listing.
                    </p>
                  </div>

                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-gem-red font-mono font-bold">FASE 5</span>
                      <span className="text-white font-semibold">Distribución</span>
                    </div>
                    <p className="text-gem-red/80">
                      Las ballenas y los primeros inversores venden gradualmente mientras los compradores tardios entran
                      por FOMO. El volumen de venta supera al de compra. Las redes sociales están en máxima euforia
                      (irónicamente, la señal más peligrosa). <strong>Si entras aquí, probablemente estás comprando
                      la bolsa de alguien más.</strong>
                    </p>
                    <p className="text-gray-500 text-xs mt-2">
                      Señales: Precio estancado con volumen alto, grandes ventas on-chain, &quot;compra ahora o nunca&quot; en redes,
                      divergencia bajista en RSI.
                    </p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Patrones de precio típicos en memecoins</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-dark-600 p-4">
                    <p className="text-primary font-semibold mb-2">V-Shape (recuperación en V)</p>
                    <p className="text-gray-400 text-xs">
                      Caída fuerte seguida de recuperación igual de fuerte. Ocurre cuando una venta de pánico es
                      absorbida rápidamente por compradores. Típico en memecoins con comunidad sólida.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <p className="text-primary font-semibold mb-2">Staircase (escalera)</p>
                    <p className="text-gray-400 text-xs">
                      Subidas escalonadas con consolidaciones entre cada escalón. Es el patrón más saludable: indica
                      acumulación orgánica y demanda sostenida. Los soportes se forman en cada &quot;escalón&quot;.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <p className="text-gem-red font-semibold mb-2">Pump &amp; Dump</p>
                    <p className="text-gray-400 text-xs">
                      Subida vertical sin consolidación seguida de caída total. El precio nunca se recupera.
                      Es el patrón de las estafas y tokens sin comunidad real. Sube un 1000%, cae un 99%.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <p className="text-gem-yellow font-semibold mb-2">Slow Bleed (sangrado lento)</p>
                    <p className="text-gray-400 text-xs">
                      Caída gradual durante días o semanas. El volumen desaparece, los holders se cansan y venden.
                      No hay un crash dramático, sino una muerte lenta. La mayoría de memecoins terminan así.
                    </p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Timeframes: la velocidad del juego</h3>
                <p>
                  A diferencia de acciones o incluso Bitcoin, los memecoins se mueven <strong className="text-primary">extremadamente
                  rápido</strong>. La mayoría de los pumps significativos ocurren en una ventana de{" "}
                  <strong className="text-white">24 a 72 horas</strong>.
                </p>
                <ul className="list-disc list-inside space-y-2 ml-2 mt-3">
                  <li>
                    <strong className="text-white">Primeras 1-6 horas:</strong> El pump inicial. Los que entran
                    aquí tienen el mayor potencial de ganancia (y riesgo).
                  </li>
                  <li>
                    <strong className="text-white">6-24 horas:</strong> La consolidacion. El mercado digiere el
                    movimiento. Se define si el token tiene fuerza para continuar.
                  </li>
                  <li>
                    <strong className="text-white">24-72 horas:</strong> El segundo intento. Si supera el máximo
                    anterior, puede ser un token con longevidad. Si no, empieza el declive.
                  </li>
                  <li>
                    <strong className="text-gem-yellow">Después de 72 horas:</strong> Si no ha habido segundo pump,
                    la probabilidad de que ocurra cae drásticamente. Los memecoins tienen una vida media muy corta.
                  </li>
                </ul>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 8: TIPOS DE MEMECOINS POR NARRATIVA ========== */}
        <section id="narrativas" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Tipos de memecoins por narrativa
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Las narrativas mueven el mercado</h3>
                <p>
                  En el mundo de los memecoins, la <strong className="text-primary">narrativa</strong> lo es todo.
                  No importa la tecnología (no la hay), importa la <strong>historia que se cuenta</strong> y si
                  esa historia conecta con el momento cultural. Cada narrativa tiene su propio ciclo de vida:
                  nace, explota, se satura y muere. Entender en que fase esta una narrativa es tan importante
                  como analizar el token individual.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="border border-dark-600 bg-dark-800/50 p-5">
                  <p className="text-primary font-bold text-lg mb-1">Dog Tokens</p>
                  <p className="text-gray-500 text-xs mb-3">DOGE, SHIB, BONK, WIF, FLOKI</p>
                  <p>
                    La narrativa original de los memecoins. Tokens con temática de perros. Tienen
                    las <strong className="text-white">comunidades más grandes y leales</strong> del espacio.
                    DOGE fue el primero, SHIB demostró que podía replicarse el éxito, y cada blockchain
                    busca su propio &quot;dog token&quot; insignia.
                  </p>
                  <p className="text-gray-500 text-xs mt-2">
                    Ciclo: maduro. Los nuevos dog tokens compiten con gigantes establecidos.
                  </p>
                </div>

                <div className="border border-dark-600 bg-dark-800/50 p-5">
                  <p className="text-primary font-bold text-lg mb-1">Cultura / Meme Puro</p>
                  <p className="text-gray-500 text-xs mb-3">PEPE, WOJAK, BRETT, GIGACHAD</p>
                  <p>
                    Tokens basados en memes iconicos de internet. Su valor reside en el{" "}
                    <strong className="text-white">reconocimiento cultural universal</strong>. PEPE es
                    el ejemplo perfecto: la rana Pepe es uno de los memes más reconocidos del mundo,
                    y eso se tradujo en una comunidad masiva desde el dia 1.
                  </p>
                  <p className="text-gray-500 text-xs mt-2">
                    Ciclo: ciclico. Resurgen con cada bull market, especialmente los memes &quot;evergreen&quot;.
                  </p>
                </div>

                <div className="border border-dark-600 bg-dark-800/50 p-5">
                  <p className="text-gem-red font-bold text-lg mb-1">Celebrity / Influencer</p>
                  <p className="text-gray-500 text-xs mb-3">Tokens de famosos, streamers, politicos</p>
                  <p>
                    Tokens lanzados por o asociados con celebridades. Generan un{" "}
                    <strong className="text-gem-red">hype inicial explosivo</strong> pero
                    históricamente tienen una tasa de supervivencia muy baja. El famoso lanza,
                    los fans compran, el famoso pierde interes, el precio colapsa.
                  </p>
                  <p className="text-gem-red text-xs mt-2">
                    Riesgo: extremo. La mayoría pierden 90%+ tras el hype inicial.
                  </p>
                </div>

                <div className="border border-dark-600 bg-dark-800/50 p-5">
                  <p className="text-primary font-bold text-lg mb-1">AI + Meme</p>
                  <p className="text-gray-500 text-xs mb-3">Tokens que combinan IA con cultura meme</p>
                  <p>
                    La tendencia de 2025-2026. Tokens que integran narrativa de inteligencia artificial
                    con elementos meme. Algunos tienen <strong className="text-white">utilidad parcial</strong>{" "}
                    (chatbots, agentes IA), lo que les da un argumento adicional, aunque la realidad
                    tecnológica suele estar muy por debajo del marketing.
                  </p>
                  <p className="text-gray-500 text-xs mt-2">
                    Ciclo: en expansion. Mientras la IA sea tendencia global, estos tokens tendran traccion.
                  </p>
                </div>

                <div className="border border-dark-600 bg-dark-800/50 p-5">
                  <p className="text-gem-yellow font-bold text-lg mb-1">Political Memecoins</p>
                  <p className="text-gray-500 text-xs mb-3">Tokens de figuras políticas o eventos politicos</p>
                  <p>
                    Tokens creados alrededor de figuras políticas, elecciones o eventos geopoliticos.
                    Tienen <strong className="text-gem-yellow">volatilidad extrema</strong> porque
                    dependen de noticias impredecibles. Un tweet, un discurso o un resultado
                    electoral puede mover el precio un 500% en minutos.
                  </p>
                  <p className="text-gem-yellow text-xs mt-2">
                    Riesgo: muy alto. Imposible predecir los catalizadores politicos.
                  </p>
                </div>

                <div className="border border-dark-600 bg-dark-800/50 p-5">
                  <p className="text-primary font-bold text-lg mb-1">Cat Tokens</p>
                  <p className="text-gray-500 text-xs mb-3">MEW, POPCAT, CATIZEN</p>
                  <p>
                    La &quot;anti-dog&quot; narrativa. Surgen como contraparte a los dog tokens,
                    capitalizando en la eterna rivalidad gatos vs perros de internet. Han demostrado
                    que pueden generar comunidades fuertes, especialmente en <strong className="text-white">Solana</strong>,
                    donde POPCAT y MEW alcanzaron market caps de cientos de millones.
                  </p>
                  <p className="text-gray-500 text-xs mt-2">
                    Ciclo: en crecimiento. Aun no tan saturado como los dog tokens.
                  </p>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Ciclo de vida de una narrativa</h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="border border-primary/30 p-3 text-center">
                    <p className="text-primary font-bold text-sm">1. Nacimiento</p>
                    <p className="text-gray-500 text-xs mt-1">Un token pionero demuestra que la narrativa funciona. Pocos lo notan.</p>
                  </div>
                  <div className="border border-primary/30 p-3 text-center">
                    <p className="text-primary font-bold text-sm">2. Explosión</p>
                    <p className="text-gray-500 text-xs mt-1">Docenas de imitadores. Los que llegan pronto pueden ganar mucho.</p>
                  </div>
                  <div className="border border-gem-yellow/30 p-3 text-center">
                    <p className="text-gem-yellow font-bold text-sm">3. Saturación</p>
                    <p className="text-gray-500 text-xs mt-1">Cientos de copias. La atencion se fragmenta. Rendimientos decrecientes.</p>
                  </div>
                  <div className="border border-gem-red/30 p-3 text-center">
                    <p className="text-gem-red font-bold text-sm">4. Muerte</p>
                    <p className="text-gray-500 text-xs mt-1">La narrativa se agota. Solo sobreviven 2-3 tokens de los cientos lanzados.</p>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 9: DONDE NACEN LOS MEMECOINS ========== */}
        <section id="donde-nacen" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Dónde nacen los memecoins
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Pump.fun (Solana)</h3>
                <p>
                  La <strong className="text-primary">fábrica de memecoins más grande del mundo</strong>.
                  Lanzada en 2024, permite a cualquier persona crear un token en segundos sin necesidad
                  de conocimientos técnicos. Cada dia se lanzan más de <strong className="text-white">10,000
                  tokens nuevos</strong> en Pump.fun.
                </p>
                <div className="mt-3 border border-gem-red/30 bg-gem-red/5 p-3">
                  <p className="text-gem-red font-semibold text-xs">
                    Realidad: el 99.9% de los tokens lanzados en Pump.fun mueren en las primeras horas.
                    Solo un punado llega a &quot;graduarse&quot; (alcanzar suficiente liquidez para migrar a Raydium).
                    De los que se gradúan, la mayoría también mueren.
                  </p>
                </div>
                <p className="mt-3 text-gray-400">
                  <strong className="text-white">Cómo funciona:</strong> Pump.fun usa un sistema de{" "}
                  <strong className="text-primary">bonding curve</strong> (curva de vinculacion). El precio
                  empieza casi en cero y sube automáticamente con cada compra. Cuando se alcanza un threshold
                  de liquidez (~85 SOL), el token se &quot;gradua&quot; y migra automáticamente a Raydium con
                  un pool de liquidez propio.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Blockchains principales para memecoins</h3>
                <div className="overflow-x-auto mt-3">
                  <table className="w-full text-sm border border-dark-600">
                    <thead>
                      <tr className="border-b border-dark-600 bg-dark-700">
                        <th className="py-2 px-3 text-left text-primary font-semibold">Blockchain</th>
                        <th className="py-2 px-3 text-left text-primary font-semibold">Ventajas</th>
                        <th className="py-2 px-3 text-left text-primary font-semibold">Desventajas</th>
                        <th className="py-2 px-3 text-left text-primary font-semibold">DEXs principales</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-dark-600">
                        <td className="py-2 px-3 text-white font-semibold">Solana</td>
                        <td className="py-2 px-3">Fees &lt;$0.01, transacciones en 1-2s, ecosistema de memecoins más activo</td>
                        <td className="py-2 px-3">Menor descentralización, caídas de red ocasionales</td>
                        <td className="py-2 px-3">Jupiter, Raydium, Pump.fun</td>
                      </tr>
                      <tr className="border-b border-dark-600">
                        <td className="py-2 px-3 text-white font-semibold">Ethereum</td>
                        <td className="py-2 px-3">Mayor liquidez, red más segura y descentralizada, los OG memecoins (PEPE, SHIB)</td>
                        <td className="py-2 px-3">Gas fees $5-50+ por transacción, hace inviable operar con cantidades pequeñas</td>
                        <td className="py-2 px-3">Uniswap, SushiSwap</td>
                      </tr>
                      <tr>
                        <td className="py-2 px-3 text-white font-semibold">Base</td>
                        <td className="py-2 px-3">Fees muy bajas (L2 de Ethereum), respaldada por Coinbase, seguridad de Ethereum</td>
                        <td className="py-2 px-3">Ecosistema más joven, menos liquidez que Solana/Ethereum</td>
                        <td className="py-2 px-3">Aerodrome, BaseSwap</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Cómo se lanza un memecoin</h3>
                <div className="space-y-3">
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">Bonding Curve (Pump.fun y similares)</p>
                    <p className="text-gray-400 text-xs">
                      El precio empieza cercano a cero y sube automáticamente con cada compra según una fórmula matemática.
                      No hay liquidez previa &mdash; los compradores SON la liquidez. Ventaja: no hay presale ni insiders.
                      Desventaja: el primero que vende en grande puede vaciar el pool.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">Fair Launch</p>
                    <p className="text-gray-400 text-xs">
                      El creador anade liquidez a un DEX (ej: Raydium, Uniswap) y renuncia al control del contrato.
                      Todos tienen la misma oportunidad de comprar al mismo precio. Es el modelo más &quot;justo&quot;, pero
                      los bots suelen snipear los primeros bloques.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-gem-red font-semibold mb-1">Presale / Private Sale</p>
                    <p className="text-gray-400 text-xs">
                      Los insiders compran antes del lanzamiento público a un precio mucho más bajo.
                      Cuando el token se lanza, los compradores de presale ya tienen ganancias y pueden vender sobre ti.
                      <strong className="text-gem-red"> Aumenta significativamente el riesgo de dump temprano.</strong>
                    </p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">El ciclo de vida completo</h3>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                  <div className="border border-primary/30 p-2 text-center">
                    <p className="text-primary font-bold text-xs">LAUNCH</p>
                    <p className="text-gray-500 text-xs mt-1">Token creado. Primeros compradores.</p>
                  </div>
                  <div className="border border-primary/30 p-2 text-center">
                    <p className="text-primary font-bold text-xs">HYPE</p>
                    <p className="text-gray-500 text-xs mt-1">Viralidad. Social media explota.</p>
                  </div>
                  <div className="border border-gem-yellow/30 p-2 text-center">
                    <p className="text-gem-yellow font-bold text-xs">PEAK</p>
                    <p className="text-gray-500 text-xs mt-1">Maximo precio. Maxima euforia.</p>
                  </div>
                  <div className="border border-gem-red/30 p-2 text-center">
                    <p className="text-gem-red font-bold text-xs">DUMP</p>
                    <p className="text-gray-500 text-xs mt-1">Ventas masivas. Panico.</p>
                  </div>
                  <div className="border border-dark-600 p-2 text-center">
                    <p className="text-gray-400 font-bold text-xs">SURVIVE?</p>
                    <p className="text-gray-500 text-xs mt-1">Solo el 1% construye comunidad y sobrevive.</p>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 10: SMART MONEY VS DUMB MONEY ========== */}
        <section id="smart-money" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Smart Money vs Dumb Money
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Qué es el &quot;Smart Money&quot;</h3>
                <p>
                  En crypto, <strong className="text-primary">smart money</strong> se refiere a wallets que
                  tienen un <strong>historial demostrable de operaciones rentables</strong>. Son traders
                  profesionales, fondos de inversión, o individuos con acceso a información privilegiada
                  o herramientas avanzadas de análisis. Cuando estas wallets compran un memecoin antes de
                  que explote, no es casualidad &mdash; tienen un edge (ventaja).
                </p>
                <p className="mt-3">
                  <strong className="text-white">&quot;Dumb money&quot;</strong> se refiere al dinero que entra por
                  FOMO, sin análisis, normalmente tarde en el ciclo. Es el comprador que ve que un token
                  ya subió un 500% y piensa &quot;todavía puede subir más&quot;.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Herramientas para rastrear smart money</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-dark-600 p-4">
                    <p className="text-primary font-semibold mb-1">Arkham Intelligence</p>
                    <p className="text-gray-400 text-xs">
                      Plataforma que identifica y etiqueta wallets de entidades conocidas (fondos, exchanges, ballenas).
                      Permite ver que están comprando los grandes jugadores en tiempo real.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <p className="text-primary font-semibold mb-1">Nansen</p>
                    <p className="text-gray-400 text-xs">
                      Análisis on-chain avanzado. Clasifica wallets por su historial de rentabilidad
                      (&quot;Smart Money&quot; label). Permite crear alertas cuando wallets inteligentes mueven fondos.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <p className="text-primary font-semibold mb-1">DeBank</p>
                    <p className="text-gray-400 text-xs">
                      Portfolio tracker que permite ver las posiciones completas de cualquier wallet pública.
                      Util para seguir a traders específicos y ver sus movimientos históricos.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <p className="text-primary font-semibold mb-1">BubbleMaps</p>
                    <p className="text-gray-400 text-xs">
                      Visualiza la distribución de holders de un token como burbujas. Detecta wallets
                      conectadas (cluster analysis) y concentración sospechosa de supply.
                    </p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Señales de smart money</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-primary/30 p-4">
                    <p className="text-primary font-semibold mb-2">Entrando (bullish)</p>
                    <ul className="list-disc list-inside space-y-1 text-gray-400 text-xs">
                      <li>Compras grandes sin mover el precio (ordenes OTC o divididas en multiples transacciones)</li>
                      <li>Wallets con historial de 5x+ entrando en un token antes de que sea trending</li>
                      <li>Acumulación durante periodos de bajo volumen y caidas de precio</li>
                      <li>Multiples wallets inteligentes comprando el mismo token en un período corto</li>
                    </ul>
                  </div>
                  <div className="border border-gem-red/30 p-4">
                    <p className="text-gem-red font-semibold mb-2">Saliendo (bearish)</p>
                    <ul className="list-disc list-inside space-y-1 text-gray-400 text-xs">
                      <li>Ventas graduales y escalonadas (no de golpe, para no mover el precio)</li>
                      <li>Transferencias de tokens a exchanges centralizados (paso previo a venta)</li>
                      <li>Reduccion de posicion mientras el precio sigue subiendo</li>
                      <li>Retirada de liquidez del pool (si son los creadores/LP providers)</li>
                    </ul>
                  </div>
                </div>
              </div>

              <div className="border border-gem-yellow/30 bg-gem-yellow/5 p-5">
                <h3 className="text-gem-yellow font-semibold text-base mb-3">Cuando seguir smart money NO funciona</h3>
                <ul className="list-disc list-inside space-y-2 text-gray-400 text-xs">
                  <li>
                    <strong className="text-white">Latencia:</strong> Cuando tu ves la transacción, el smart money ya compró.
                    Si el precio ya subió un 100% desde su compra, el riesgo/recompensa cambia drásticamente.
                  </li>
                  <li>
                    <strong className="text-white">Fake wallets:</strong> Algunos crean wallets con &quot;historial perfecto&quot;
                    operando consigo mismos para manipular a los seguidores.
                  </li>
                  <li>
                    <strong className="text-white">Tamaño diferente:</strong> Un fondo que compra $500K puede
                    permitirse perder $500K. Tu no. Su gestión de riesgo es diferente a la tuya.
                  </li>
                  <li>
                    <strong className="text-white">Diversificacion oculta:</strong> Ves que una wallet inteligente
                    compro un token, pero no ves que también compro otros 49 tokens. Solo necesita que 1 de 50 funcione.
                  </li>
                </ul>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 11: EL JUEGO DE SUMA NEGATIVA ========== */}
        <section id="suma-negativa" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              El juego de suma negativa
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border-2 border-gem-red bg-gem-red/5 p-5">
                <p className="text-gem-red font-bold text-base mb-2">LA VERDAD INCOMODA</p>
                <p>
                  El trading de memecoins no es un juego de suma cero (donde lo que uno gana, otro pierde).
                  Es un <strong className="text-gem-red">juego de suma negativa</strong>: las fees, el gas,
                  el slippage y los impuestos hacen que, en conjunto, <strong>se pierda más dinero del que
                  se gana</strong>. Por cada persona que hace 10x, hay 9 que pierden su inversión.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Donde se va tu dinero (costes ocultos)</h3>
                <div className="space-y-3">
                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-gem-red font-mono text-lg">!</span>
                      <p className="text-white font-semibold">Fees del DEX</p>
                    </div>
                    <p className="text-gray-400 text-xs">
                      Cada swap tiene una comision. En Uniswap es 0.3%, en Raydium 0.25%.
                      Si compras y vendes, pagas fee dos veces. Con 10 operaciones al dia durante un mes,
                      las fees pueden comerse un 15-20% de tu capital aunque no pierdas en ningún trade.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-gem-red font-mono text-lg">!</span>
                      <p className="text-white font-semibold">Gas fees</p>
                    </div>
                    <p className="text-gray-400 text-xs">
                      El coste de procesar tu transacción en la blockchain. En Ethereum puede ser $5-50+ por transacción.
                      En Solana es &lt;$0.01 normalmente, pero en momentos de alta congestión puede subir.
                      Si operas con cantidades pequeñas en Ethereum, el gas puede ser mayor que tu ganancia.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-gem-red font-mono text-lg">!</span>
                      <p className="text-white font-semibold">Slippage</p>
                    </div>
                    <p className="text-gray-400 text-xs">
                      La diferencia entre el precio esperado y el precio real de ejecucion. En tokens con baja liquidez,
                      el slippage puede ser del 5-10%. Si compras un token y el precio &quot;real&quot; que pagas es un 5% más alto,
                      ya empiezas perdiendo. Y al vender, pierdes otro 5%.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-gem-red font-mono text-lg">!</span>
                      <p className="text-white font-semibold">MEV (Bots de front-running)</p>
                    </div>
                    <p className="text-gray-400 text-xs">
                      Bots sofisticados que detectan tu orden pendiente y ejecutan una compra justo antes que tu,
                      subiendo el precio. Luego venden justo después. Te pagaste un precio más alto sin saberlo.
                      En Ethereum esto es especialmente agresivo. En Solana, Jupiter ofrece protección parcial contra MEV.
                    </p>
                  </div>
                  <div className="border border-dark-600 p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-gem-yellow font-mono text-lg">!</span>
                      <p className="text-white font-semibold">Impuestos (España)</p>
                    </div>
                    <p className="text-gray-400 text-xs">
                      En España, las ganancias por criptomonedas tributan en el IRPF como ganancias patrimoniales:
                      <strong className="text-white"> 19% hasta 6.000 EUR, 21% de 6.000 a 50.000 EUR, 23% de 50.000 a 200.000 EUR,
                      27% de 200.000 a 300.000 EUR, y 28% a partir de 300.000 EUR</strong>.
                      Esto aplica a cada operación con ganancia, no solo al retirar a tu banco.
                    </p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Tu edge: la ventaja que necesitas</h3>
                <p className="mb-4">
                  Para ganar consistentemente en un juego de suma negativa, necesitas una{" "}
                  <strong className="text-primary">ventaja (edge)</strong> que te ponga por delante del 90% de participantes.
                  Hay tres tipos de edge:
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="border border-primary/30 p-3">
                    <p className="text-primary font-semibold text-sm mb-1">Edge informacional</p>
                    <p className="text-gray-400 text-xs">
                      Saber algo que otros no saben. Estar en el grupo de Telegram correcto, seguir a los
                      insiders correctos, detectar tendencias antes que la masa. Es el edge más común pero
                      también el más frágil.
                    </p>
                  </div>
                  <div className="border border-primary/30 p-3">
                    <p className="text-primary font-semibold text-sm mb-1">Edge temporal</p>
                    <p className="text-gray-400 text-xs">
                      Ser más rápido que otros. Tener bots de trading, alertas automatizadas, o simplemente
                      estar despierto en el momento correcto. En memecoins, 30 minutos de diferencia pueden
                      significar un 500% de diferencia en precio de entrada.
                    </p>
                  </div>
                  <div className="border border-primary/30 p-3">
                    <p className="text-primary font-semibold text-sm mb-1">Edge analitico</p>
                    <p className="text-gray-400 text-xs">
                      Analizar datos que otros no analizan. Esto es exactamente lo que hace{" "}
                      <strong className="text-primary">Meme Detector</strong>: nuestro ML analiza 94 features
                      por token (liquidez, holders, volumen, precio, contrato) que un humano no puede procesar
                      manualmente.
                    </p>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 12: GESTION EMOCIONAL ========== */}
        <section id="gestión-emocional" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Gestión emocional del trader
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Las emociones son tu peor enemigo</h3>
                <p>
                  El mercado de memecoins está diseñado para explotar tus emociones. La volatilidad extrema,
                  las ganancias rápidas de otros, los gráficos verdes en redes sociales... todo está pensado
                  para que <strong className="text-gem-red">actúes impulsivamente</strong>.
                  Los traders profesionales no son los que mejor predicen el mercado, sino los que mejor
                  controlan sus emociones.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="border border-gem-red/30 bg-gem-red/5 p-5">
                  <p className="text-gem-red font-bold text-base mb-2">FOMO</p>
                  <p className="text-gray-400 text-xs mb-2">Fear Of Missing Out (Miedo a perderte la oportunidad)</p>
                  <p className="text-gray-300 text-xs">
                    &quot;Si no compro ahora, perdera la oportunidad.&quot; El FOMO te hace comprar en el peor momento
                    posible: cuando el precio ya subió, todos están eufricos y las ballenas están vendiendo.
                    <strong className="text-white"> Si sientes FOMO intenso, esa ES la señal de NO entrar.</strong>
                  </p>
                  <p className="text-primary text-xs mt-2">
                    Antidoto: siempre habra otra oportunidad. El mercado genera oportunidades todos los días.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-5">
                  <p className="text-gem-red font-bold text-base mb-2">FUD</p>
                  <p className="text-gray-400 text-xs mb-2">Fear, Uncertainty, Doubt (Miedo, Incertidumbre, Duda)</p>
                  <p className="text-gray-300 text-xs">
                    &quot;Esto va a caer, vendo todo antes de perder más.&quot; El FUD te hace vender en el peor momento:
                    justo antes de que el precio se recupere. Las ballenas generan FUD intencionalmente para
                    comprar tus tokens más baratos.
                  </p>
                  <p className="text-primary text-xs mt-2">
                    Antidoto: si tu tesis de inversión original sigue intacta, mantener. Si se invalidó, vender sin emociones.
                  </p>
                </div>

                <div className="border border-gem-yellow/30 bg-gem-yellow/5 p-5">
                  <p className="text-gem-yellow font-bold text-base mb-2">Bag Holding</p>
                  <p className="text-gray-400 text-xs mb-2">Aguantar un token en pérdidas por esperanza</p>
                  <p className="text-gray-300 text-xs">
                    &quot;Ya bajará de perder, no vendo.&quot; Te niegas a aceptar la pérdida y sigues aguantando
                    un token que cayo un 80%, esperando que vuelva a tu precio de compra.
                    En memecoins, un token que cae un 80% rara vez se recupera. Es mejor aceptar la pérdida
                    y mover el capital a una mejor oportunidad.
                  </p>
                  <p className="text-primary text-xs mt-2">
                    Antidoto: define tu stop-loss ANTES de comprar y respetalo siempre.
                  </p>
                </div>

                <div className="border border-gem-yellow/30 bg-gem-yellow/5 p-5">
                  <p className="text-gem-yellow font-bold text-base mb-2">Revenge Trading</p>
                  <p className="text-gray-400 text-xs mb-2">Intentar recuperar pérdidas con trades impulsivos</p>
                  <p className="text-gray-300 text-xs">
                    &quot;Perdí $200, voy a meter $400 en este otro token para recuperar rápido.&quot;
                    El revenge trading es la espiral descendente más común en memecoins.
                    Cada trade impulsivo pierde más, lo que genera más frustración y más trades impulsivos.
                  </p>
                  <p className="text-primary text-xs mt-2">
                    Antídoto: tras una pérdida significativa, NO operes durante 24 horas. Las decisiones emocionales son las más costosas.
                  </p>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">La regla del plan</h3>
                <p className="mb-4">
                  Antes de comprar <strong className="text-primary">cualquier</strong> memecoin, define por escrito estos 4 elementos.
                  Si no puedes completar los 4, <strong className="text-gem-red">no entres al trade</strong>:
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="border border-primary/30 p-3 text-center">
                    <p className="text-primary font-bold text-sm">ENTRY</p>
                    <p className="text-gray-500 text-xs mt-1">Precio exacto o condición para comprar. &quot;Compro si baja a $X.&quot;</p>
                  </div>
                  <div className="border border-primary/30 p-3 text-center">
                    <p className="text-primary font-bold text-sm">TARGET</p>
                    <p className="text-gray-500 text-xs mt-1">Donde tomas ganancias. Al menos 2 niveles de salida parcial.</p>
                  </div>
                  <div className="border border-gem-red/30 p-3 text-center">
                    <p className="text-gem-red font-bold text-sm">STOP-LOSS</p>
                    <p className="text-gray-500 text-xs mt-1">Precio máximo de pérdida. Si llega aquí, vendes sin dudar.</p>
                  </div>
                  <div className="border border-gem-yellow/30 p-3 text-center">
                    <p className="text-gem-yellow font-bold text-sm">SIZE</p>
                    <p className="text-gray-500 text-xs mt-1">Cuanto dinero. Nunca más del 1-5% de tu capital por trade.</p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Journaling: tu herramienta secreta</h3>
                <p>
                  Los traders profesionales llevan un <strong className="text-primary">diario de trading</strong>.
                  Por cada operación, registra:
                </p>
                <ul className="list-disc list-inside space-y-2 ml-2 mt-3 text-gray-400">
                  <li><strong className="text-white">Fecha y token:</strong> Qué compraste y cuándo.</li>
                  <li><strong className="text-white">Razón de entrada:</strong> Por qué compraste. Debe ser una razón analítica, no &quot;porque todos lo compraban&quot;.</li>
                  <li><strong className="text-white">Emoción al entrar:</strong> ¿Estabas tranquilo y confiado? ¿O ansioso y con FOMO? Esto es clave.</li>
                  <li><strong className="text-white">Plan (entry/target/stop/size):</strong> Lo que definiste antes de entrar.</li>
                  <li><strong className="text-white">Resultado:</strong> Ganancia o pérdida. ¿Seguiste el plan?</li>
                  <li><strong className="text-white">Lección aprendida:</strong> Qué harías diferente la próxima vez.</li>
                </ul>
                <p className="mt-3 text-gray-500">
                  Después de 20-30 trades registrados, empezarás a ver patrones en tu comportamiento.
                  Esos patrones son la clave para mejorar como trader.
                </p>
              </div>

            </div>
          </div>
        </section>

        {/* ========== SECCION 13: METRICAS CLAVE ========== */}
        <section id="métricas-clave" className="scroll-mt-28">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-16">
            <h2 className="text-xl md:text-2xl font-bold text-primary mb-8 border-b border-dark-600 pb-3 uppercase tracking-wider">
              Métricas clave que debes conocer
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed text-justify">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Entiende los números antes de invertir</h3>
                <p>
                  Los memecoins se mueven por narrativa y emocion, pero las <strong className="text-primary">métricas
                  cuantitativas</strong> te permiten separar los que tienen potencial de los que son puro ruido.
                  Cada métrica te dice algo diferente sobre la salud y el potencial de un token.
                </p>
              </div>

              {/* Market Cap */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Market Cap (Capitalizacion de mercado)</h3>
                </div>
                <p className="mb-3">
                  <strong className="text-primary">Formula:</strong> Precio actual x Tokens en circulación.
                </p>
                <div className="border border-dark-600 bg-dark-700/50 p-3 text-xs font-mono text-gray-400">
                  <p>Ejemplo: Token XYZ tiene precio = $0.001 y supply = 1 billn de tokens</p>
                  <p>Market Cap = $0.001 x 1,000,000,000 = <span className="text-primary">$1,000,000 ($1M)</span></p>
                  <p className="mt-2">Si compras $1,000 de este token, necesitas que el Market Cap suba de $1M a $10M para hacer <span className="text-primary">10x</span>.</p>
                  <p>Es posible? Un token de $1M puede llegar a $10M. Pero un token de $100M llegar a $1B es mucho más difícil.</p>
                </div>
                <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-center">
                  <div className="border border-dark-600 p-2">
                    <p className="text-primary font-bold">&lt;$100K</p>
                    <p className="text-gray-500">Micro cap. Altisimo riesgo, alto potencial.</p>
                  </div>
                  <div className="border border-dark-600 p-2">
                    <p className="text-primary font-bold">$100K-$1M</p>
                    <p className="text-gray-500">Small cap. Donde están las &quot;gems&quot;.</p>
                  </div>
                  <div className="border border-dark-600 p-2">
                    <p className="text-gem-yellow font-bold">$1M-$50M</p>
                    <p className="text-gray-500">Mid cap. Mas seguro, menor multiplicador.</p>
                  </div>
                  <div className="border border-dark-600 p-2">
                    <p className="text-white font-bold">&gt;$50M</p>
                    <p className="text-gray-500">Large cap meme. DOGE, PEPE, SHIB.</p>
                  </div>
                </div>
              </div>

              {/* Volumen 24h */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Volumen 24h</h3>
                </div>
                <p>
                  El total de dinero que se ha movido (compras + ventas) en las últimas 24 horas.
                  Te indica <strong className="text-primary">cuanto interes real hay</strong> en el token.
                </p>
                <div className="border border-dark-600 bg-dark-700/50 p-3 text-xs font-mono text-gray-400 mt-3">
                  <p>Regla rápida: <span className="text-primary">Volumen 24h / Market Cap = ratio de actividad</span></p>
                  <p className="mt-1">Si ratio &gt; 0.5 (50%): Token muy activo, mucho trading.</p>
                  <p>Si ratio 0.1-0.5 (10-50%): Actividad normal.</p>
                  <p>Si ratio &lt; 0.1 (10%): <span className="text-gem-red">Token &quot;muerto&quot;. Poca actividad, difícil vender.</span></p>
                </div>
                <p className="mt-3 text-gray-500 text-xs">
                  Atención: un volumen artificialmente alto puede indicar wash trading (compras y ventas entre las mismas wallets para simular actividad).
                </p>
              </div>

              {/* Holders */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Holders (número de wallets)</h3>
                </div>
                <p>
                  El número de wallets únicas que poseen el token. Mas holders generalmente
                  significa una <strong className="text-primary">distribución más saludable</strong> y menor riesgo de manipulación.
                </p>
                <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-center">
                  <div className="border border-gem-red/30 p-2">
                    <p className="text-gem-red font-bold">&lt;100</p>
                    <p className="text-gray-500">Extremadamente arriesgado. Probablemente una trampa.</p>
                  </div>
                  <div className="border border-gem-yellow/30 p-2">
                    <p className="text-gem-yellow font-bold">100-500</p>
                    <p className="text-gray-500">Muy temprano. Alto riesgo pero también alto potencial.</p>
                  </div>
                  <div className="border border-primary/30 p-2">
                    <p className="text-primary font-bold">500-5,000</p>
                    <p className="text-gray-500">Comunidad establecida. Token con traccion.</p>
                  </div>
                  <div className="border border-primary/30 p-2">
                    <p className="text-primary font-bold">&gt;5,000</p>
                    <p className="text-gray-500">Gran comunidad. Mas resistente a rug pulls.</p>
                  </div>
                </div>
              </div>

              {/* Liquidez */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Liquidez (Liquidity Pool)</h3>
                </div>
                <p>
                  La cantidad de dinero depositada en el pool de trading del DEX.
                  <strong className="text-primary"> Determina cuanto puedes comprar o vender sin mover el precio</strong>.
                </p>
                <div className="border border-dark-600 bg-dark-700/50 p-3 text-xs font-mono text-gray-400 mt-3">
                  <p>Ejemplo: Pool con $10K de liquidez</p>
                  <p>- Compras $100 -&gt; precio se mueve ~1% (aceptable)</p>
                  <p>- Compras $1,000 -&gt; precio se mueve ~10% (caro)</p>
                  <p>- Compras $5,000 -&gt; precio se mueve ~50% (<span className="text-gem-red">inviable</span>)</p>
                  <p className="mt-2 text-gem-yellow">Regla: nunca compres más del 2% de la liquidez total del pool.</p>
                </div>
              </div>

              {/* Top Holders % */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-gem-red font-mono text-lg">!</span>
                  <h3 className="text-white font-semibold text-base">Top Holders % (concentración)</h3>
                </div>
                <p>
                  El porcentaje del supply total que poseen las wallets más grandes.
                  <strong className="text-gem-red"> Si una sola wallet tiene más del 30% del supply, puede destruir el precio
                  vendiendo</strong>. Cuanto más distribuido este el supply, más seguro.
                </p>
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
                  <div className="border border-primary/30 p-3 text-center">
                    <p className="text-primary font-bold">Top 10 &lt; 30%</p>
                    <p className="text-gray-500 mt-1">Buena distribución. Las 10 wallets más grandes tienen menos del 30%. Saludable.</p>
                  </div>
                  <div className="border border-gem-yellow/30 p-3 text-center">
                    <p className="text-gem-yellow font-bold">Top 10 = 30-50%</p>
                    <p className="text-gray-500 mt-1">Concentrado. Riesgo moderado de manipulación. Precaucion.</p>
                  </div>
                  <div className="border border-gem-red/30 p-3 text-center">
                    <p className="text-gem-red font-bold">Top 10 &gt; 50%</p>
                    <p className="text-gray-500 mt-1">Muy concentrado. Alto riesgo de rug pull o dump masivo.</p>
                  </div>
                </div>
                <p className="mt-3 text-gray-500 text-xs">
                  Herramientas: Usa BubbleMaps para visualizar la distribución y detectar wallets conectadas
                  (cluster analysis). A veces una &quot;ballena&quot; tiene su supply repartido en 20 wallets para parecer más distribuido.
                </p>
              </div>

              {/* Buyer/Seller Ratio */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Buyer/Seller Ratio (ratio compradores/vendedores)</h3>
                </div>
                <p>
                  El número de transacciones de compra dividido entre el de venta en un período dado (normalmente 24h).
                </p>
                <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-center">
                  <div className="border border-primary/30 p-3">
                    <p className="text-primary font-bold text-lg">&gt;1.0</p>
                    <p className="text-gray-400">Mas compradores que vendedores. Presion alcista. Demanda creciente.</p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-white font-bold text-lg">=1.0</p>
                    <p className="text-gray-400">Equilibrio. Ni alcista ni bajista. Consolidación.</p>
                  </div>
                  <div className="border border-gem-red/30 p-3">
                    <p className="text-gem-red font-bold text-lg">&lt;1.0</p>
                    <p className="text-gray-400">Más vendedores que compradores. Presión bajista. Cuidado.</p>
                  </div>
                </div>
                <p className="mt-3 text-gray-500 text-xs">
                  Atención: mira también el VOLUMEN de compra vs venta, no solo el número de transacciones.
                  100 compras pequeñas vs 1 venta enorme = bajista a pesar de que el ratio diga lo contrario.
                </p>
              </div>

            </div>
          </div>
        </section>

        {/* ========== CTA FINAL ========== */}
        <section className="border-t border-dark-600">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16 text-center">
            <p className="text-gray-500 text-xs uppercase tracking-wider mb-3">Siguiente paso</p>
            <h2 className="text-xl md:text-2xl font-bold text-white mb-4">
              Aprende más con <span className="text-primary">Meme Detector Pro</span>
            </h2>
            <p className="text-gray-400 text-sm max-w-xl mx-auto mb-8">
              Contenido avanzado: análisis de blockchains, narrativas de mercado, gestión de riesgo profesional,
              herramientas del trader y cómo interpretar las señales de nuestra IA.
            </p>
            <a
              href="https://app.memedetector.es"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block border-2 border-primary text-primary px-8 py-3 text-sm font-bold uppercase tracking-wider hover:bg-primary hover:text-dark-900 transition-all duration-300"
            >
              Aprende más con Meme Detector Pro &rarr;
            </a>
          </div>
        </section>

        {/* Footer mínimo */}
        <footer className="border-t border-dark-600 py-6">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
            <p className="text-xs text-gray-600">
              &copy; {new Date().getFullYear()} Meme Detector &mdash;{" "}
              <Link href="/legal" className="text-gray-500 hover:text-primary transition-colors">Legal</Link>
            </p>
          </div>
        </footer>
      </div>
    </main>
  );
}
