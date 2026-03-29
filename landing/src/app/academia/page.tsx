"use client";

import Navbar from "@/components/Navbar";
import Link from "next/link";

/* Secciones de la academia con sus anchor links */
const sections = [
  { id: "criptomonedas", label: "Criptomonedas" },
  { id: "memecoins", label: "Memecoins" },
  { id: "conceptos", label: "Conceptos" },
  { id: "riesgo", label: "Riesgo" },
  { id: "como-comprar", label: "Como comprar" },
  { id: "red-flags", label: "Red Flags" },
];

export default function AcademiaPage() {
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
                  className="text-xs text-gray-400 hover:text-primary transition-colors uppercase tracking-wider border border-dark-600 px-2 py-1 hover:border-primary/50"
                >
                  {s.label}
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Titulo de la pagina */}
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
              Que son las criptomonedas
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Moneda digital descentralizada</h3>
                <p>
                  Una criptomoneda es una <strong className="text-primary">moneda digital</strong> que funciona sin
                  bancos ni gobiernos. En lugar de depender de una entidad central (como el Banco de Espana),
                  las transacciones se verifican y registran en una red de ordenadores distribuida por todo el mundo.
                </p>
                <p className="mt-3">
                  Esto significa que <strong>nadie puede congelar tu cuenta</strong>, <strong>nadie puede
                  imprimir mas moneda</strong> arbitrariamente, y las transacciones son publicas y verificables por cualquiera.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Blockchain = Libro contable publico</h3>
                <p>
                  La <strong className="text-primary">blockchain</strong> es la tecnologia detras de las criptomonedas.
                  Piensa en ella como un <strong>libro contable gigante</strong> donde se registran todas las
                  transacciones, y ese libro esta copiado en miles de ordenadores al mismo tiempo.
                </p>
                <p className="mt-3">
                  Cada &quot;pagina&quot; del libro se llama <strong>bloque</strong>, y cada bloque esta
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
                        <th className="py-2 px-3 text-left text-primary font-semibold">Descripcion</th>
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
              Que es un memecoin
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Tokens inspirados en memes</h3>
                <p>
                  Un memecoin es un <strong className="text-primary">token de criptomoneda</strong> cuyo valor no
                  proviene de una tecnologia innovadora o un servicio util, sino de la{" "}
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
                    <p className="text-gray-500 text-xs mt-1">El original. Creado como broma, llego a top 10 por market cap.</p>
                  </div>
                  <div className="border border-dark-600 p-3 text-center">
                    <p className="text-white font-bold text-lg">PEPE</p>
                    <p className="text-gray-500 text-xs mt-1">Basado en la rana Pepe. Ethereum. Exploto en 2023.</p>
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
                  Un <strong>utility token</strong> (como ETH o SOL) tiene una funcion real: pagar gas fees,
                  participar en gobernanza, acceder a servicios. Un <strong className="text-gem-yellow">memecoin no
                  tiene utilidad intrinseca</strong> &mdash; su valor depende exclusivamente de la percepcion,
                  el hype y la comunidad.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Por que suben y bajan</h3>
                <ul className="list-disc list-inside space-y-2 ml-2">
                  <li><strong className="text-white">Hype y viralidad:</strong> Un tweet de un influencer puede multiplicar el precio en minutos.</li>
                  <li><strong className="text-white">Comunidad:</strong> Cuanto mas grande y activa la comunidad, mas demanda.</li>
                  <li><strong className="text-white">Narrativa:</strong> Los memecoins que enganchan con la tendencia del momento suben mas rapido.</li>
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
              Conceptos basicos
            </h2>
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">

              {/* Wallet */}
              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-primary font-mono text-lg">$</span>
                  <h3 className="text-white font-semibold text-base">Wallet (billetera digital)</h3>
                </div>
                <p>
                  Es tu &quot;cuenta bancaria&quot; en el mundo crypto. Almacena tus criptomonedas y te permite
                  enviar y recibir tokens. Cada wallet tiene una <strong>direccion publica</strong> (como un IBAN) y
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
                    <p>Plataformas como Binance, Coinbase o Kraken. Tu depositas tu dinero y ellos lo custodian. Facil de usar, pero tienes que confiar en la empresa.</p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">DEX (Exchange Descentralizado)</p>
                    <p>Plataformas como Jupiter (Solana) o Uniswap (Ethereum). Conectas tu wallet directamente. Tu controlas tus fondos siempre. Aqui se compran los memecoins.</p>
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
                  sin que el precio se mueva drasticamente. Un token con alta liquidez (ej: $1M+) es mas seguro
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
                    <p>Precio actual x tokens en circulacion. Es el &quot;tamano real&quot; del token ahora mismo.</p>
                  </div>
                  <div className="border border-dark-600 p-3">
                    <p className="text-primary font-semibold mb-1">FDV (Fully Diluted Valuation)</p>
                    <p>Precio actual x TODOS los tokens que existiran. Si hay mucha diferencia con Market Cap, significa que van a salir muchos tokens nuevos al mercado (dilucion).</p>
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
                  compradores con tokens que ya no valen nada. Es la estafa mas comun en memecoins.
                </p>
                <p className="mt-2">
                  Senales de alerta: liquidez no bloqueada, creador con historial de rug pulls,
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
                  &quot;Haz tu propia investigacion&quot;. Antes de comprar cualquier token, investiga: quien lo creo,
                  que problema resuelve, como esta la liquidez, quienes son los holders principales,
                  y si el contrato esta verificado. <strong>Nunca compres solo porque alguien te lo recomendo.</strong>
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
            <div className="space-y-6 text-gray-300 text-sm leading-relaxed">

              {/* Aviso destacado */}
              <div className="border-2 border-gem-red bg-gem-red/5 p-5">
                <p className="text-gem-red font-bold text-base mb-2">AVISO IMPORTANTE</p>
                <p>
                  Esta informacion es <strong>educativa</strong>, no constituye asesoramiento financiero.
                  Las criptomonedas, y especialmente los memecoins, son activos <strong>altamente
                  especulativos</strong>. Puedes perder la totalidad de tu inversion.
                </p>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">La realidad de los numeros</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="border border-gem-red/30 p-4 text-center">
                    <p className="text-gem-red text-4xl font-bold">99%</p>
                    <p className="text-gray-400 mt-2">de los memecoins van a cero</p>
                  </div>
                  <div className="border border-primary/30 p-4 text-center">
                    <p className="text-primary text-4xl font-bold">1%</p>
                    <p className="text-gray-400 mt-2">puede hacer 10x, 100x o mas</p>
                  </div>
                </div>
              </div>

              <div className="border border-dark-600 bg-dark-800/50 p-5">
                <h3 className="text-white font-semibold text-base mb-3">Reglas de gestion de riesgo</h3>
                <ul className="space-y-3">
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[1]</span>
                    <span><strong className="text-white">Nunca inviertas mas de lo que puedas perder.</strong> Si pierdes ese dinero, tu vida debe seguir exactamente igual.</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[2]</span>
                    <span><strong className="text-white">Maximo 1-5% del portfolio por token.</strong> Si tienes 1000 EUR para memecoins, maximo 10-50 EUR por cada token individual.</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[3]</span>
                    <span><strong className="text-white">Diversifica.</strong> Es mejor tener 20 posiciones pequenas que 1 posicion grande. Si 19 van a cero y 1 hace 100x, sales ganando.</span>
                  </li>
                  <li className="flex items-start gap-3">
                    <span className="text-primary font-mono shrink-0">[4]</span>
                    <span><strong className="text-gem-yellow">Si suena demasiado bien para ser verdad, probablemente lo es.</strong> Desconfia de &quot;ganancias garantizadas&quot;, grupos VIP de senales, y promesas de rentabilidad fija.</span>
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
              Como comprar un memecoin (paso a paso)
            </h2>
            <div className="space-y-4 text-gray-300 text-sm leading-relaxed">

              {/* Paso 1 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">1</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Crear una wallet</h3>
                  <p>
                    Descarga <strong>Phantom</strong> (para Solana) o <strong>MetaMask</strong> (para Ethereum/Base)
                    desde sus paginas oficiales. Al crearla, te dara una <strong>frase semilla de 12-24
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
                    Desde el exchange, retira tus SOL/ETH a la direccion de tu wallet personal.
                    Copia la direccion de tu wallet con cuidado (verifica los primeros y ultimos caracteres).
                    La primera vez, envia una cantidad pequena de prueba.
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
                  <h3 className="text-white font-semibold text-base mb-2">Buscar el token por direccion de contrato</h3>
                  <p>
                    <span className="text-gem-red font-semibold">IMPORTANTE:</span> Busca siempre por la{" "}
                    <strong>direccion del contrato (contract address)</strong>, nunca por nombre. Hay muchos tokens
                    falsos con el mismo nombre. La direccion la encuentras en DexScreener, GeckoTerminal o
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
                    El <strong>slippage</strong> es la diferencia maxima de precio que aceptas entre cuando
                    envias la transaccion y cuando se ejecuta. Para memecoins con baja liquidez,
                    puede ser necesario subir el slippage al 1-5%. Si es mucho mayor, desconfia.
                  </p>
                </div>
              </div>

              {/* Paso 7 */}
              <div className="border border-dark-600 bg-dark-800/50 p-5 flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 border border-primary text-primary flex items-center justify-center font-bold text-lg">7</div>
                <div>
                  <h3 className="text-white font-semibold text-base mb-2">Confirmar transaccion</h3>
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
              Senales de alerta (Red Flags)
            </h2>
            <div className="space-y-4 text-gray-300 text-sm leading-relaxed">

              <p className="text-gray-400 mb-4">
                Si un token presenta una o mas de estas senales, <strong className="text-gem-red">aumenta
                significativamente el riesgo</strong> de perder tu inversion:
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Equipo anonimo sin historial</p>
                  <p className="text-gray-400 text-xs">
                    Si no puedes verificar quien esta detras del proyecto, no hay responsabilidad.
                    Los mejores proyectos tienen fundadores publicos con reputacion.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Liquidez no bloqueada</p>
                  <p className="text-gray-400 text-xs">
                    Si la liquidez no esta &quot;lockeada&quot; (bloqueada en un smart contract con tiempo),
                    el creador puede retirarla en cualquier momento = rug pull.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Concentracion de holders</p>
                  <p className="text-gray-400 text-xs">
                    Si una sola wallet tiene mas del 50% del supply, esa persona puede vender
                    todo y destruir el precio. Usa BubbleMaps para verificar.
                  </p>
                </div>

                <div className="border border-gem-red/30 bg-gem-red/5 p-4">
                  <p className="text-gem-red font-semibold mb-2">Contrato no verificado</p>
                  <p className="text-gray-400 text-xs">
                    Un contrato no verificado significa que no puedes ver el codigo. Podria
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

        {/* ========== CTA FINAL ========== */}
        <section className="border-t border-dark-600">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 py-16 text-center">
            <p className="text-gray-500 text-xs uppercase tracking-wider mb-3">Siguiente paso</p>
            <h2 className="text-xl md:text-2xl font-bold text-white mb-4">
              Aprende mas con <span className="text-primary">Meme Detector Pro</span>
            </h2>
            <p className="text-gray-400 text-sm max-w-xl mx-auto mb-8">
              Contenido avanzado: analisis de blockchains, narrativas de mercado, gestion de riesgo profesional,
              herramientas del trader y como interpretar las senales de nuestra IA.
            </p>
            <a
              href="https://app.memedetector.es"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block border-2 border-primary text-primary px-8 py-3 text-sm font-bold uppercase tracking-wider hover:bg-primary hover:text-dark-900 transition-all duration-300"
            >
              Aprende mas con Meme Detector Pro &rarr;
            </a>
          </div>
        </section>

        {/* Footer minimo */}
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
