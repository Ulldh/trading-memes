"""
legal.py — Paginas legales: Terminos de Servicio y Politica de Privacidad.

Texto legal adaptado a la legislacion espanola (LOPD, LSSI-CE) y
al Reglamento General de Proteccion de Datos (RGPD/GDPR) de la UE.

Servicio: MemeDetector — analisis de senales de criptomonedas (memecoins).
Prestador: persona fisica con domicilio fiscal en Espana.
Contacto: info@memedetector.es
"""

import streamlit as st


# ============================================================
# TEXTOS LEGALES
# ============================================================

_TERMINOS_DE_SERVICIO = """
## 1. Informacion general

El presente documento regula las condiciones de uso del servicio web
**MemeDetector** (en adelante, "el Servicio"), accesible a traves de
la direccion https://memedetector.es y sus subdominios.

El Servicio es ofrecido por **Ulises Diaz Hernandez**, con domicilio fiscal
en Espana (en adelante, "el Prestador"), y correo electronico de contacto
**info@memedetector.es**.

Al registrarse o utilizar el Servicio, el usuario acepta integramente
estos Terminos de Servicio. Si no esta de acuerdo, debe abstenerse de
utilizar el Servicio.

---

## 2. Descripcion del Servicio

MemeDetector es una herramienta de analisis de datos que emplea modelos
de Machine Learning para evaluar memecoins (tokens especulativos) en
blockchains como Solana, Ethereum y Base. El Servicio proporciona:

- Puntuaciones de potencial ("senales") generadas por modelos estadisticos.
- Dashboards de visualizacion de datos historicos y metricas.
- Alertas opcionales via Telegram.
- Funciones de watchlist, portfolio simulado y track record de senales
  pasadas.

---

## 3. Exencion de responsabilidad financiera

**EL SERVICIO NO CONSTITUYE ASESORAMIENTO FINANCIERO, DE INVERSION NI
FISCAL DE NINGUN TIPO.**

El usuario reconoce y acepta que:

a) Las senales, puntuaciones y analisis generados por el Servicio son
   el resultado de modelos estadisticos automaticos y **no representan
   recomendaciones de compra, venta ni mantenimiento** de ningun activo.

b) Los memecoins son activos altamente especulativos y volatiles. El usuario
   puede perder la totalidad de su inversion.

c) El Prestador **no es una entidad regulada** por la Comision Nacional del
   Mercado de Valores (CNMV), la SEC ni ningun organismo regulador financiero.

d) Toda decision de inversion es responsabilidad exclusiva del usuario.
   El Prestador no sera responsable en ningun caso de las perdidas
   economicas derivadas del uso de la informacion proporcionada.

e) El usuario debe realizar siempre su propia investigacion (DYOR — Do
   Your Own Research) antes de tomar cualquier decision financiera.

---

## 4. Registro y cuenta de usuario

- Para acceder al Servicio es necesario crear una cuenta con un email
  valido y una contrasena.
- El usuario es responsable de mantener la confidencialidad de sus
  credenciales.
- El Prestador se reserva el derecho de suspender o eliminar cuentas que
  incumplan estos Terminos, que realicen un uso abusivo del Servicio, o
  que intenten acceder a datos de otros usuarios.

---

## 5. Planes y suscripciones

El Servicio ofrece distintos planes (Free, Pro, Enterprise) con diferentes
niveles de funcionalidad. Los precios y caracteristicas de cada plan se
detallan en la pagina de Pricing.

- Los pagos se procesan a traves de **Stripe**, un proveedor de pagos
  certificado PCI DSS Nivel 1. El Prestador no almacena datos de tarjetas
  de credito ni informacion bancaria.
- Las suscripciones se renuevan automaticamente al final de cada periodo
  de facturacion (mensual), salvo cancelacion previa.
- El usuario puede cancelar su suscripcion en cualquier momento desde su
  panel de perfil. Al cancelar, el acceso a las funciones premium se
  mantiene hasta el final del periodo ya facturado.
- No se realizan reembolsos parciales por periodos no consumidos, salvo
  en los casos previstos por la legislacion vigente o por decision
  discrecional del Prestador.

---

## 6. Propiedad intelectual

- Todo el contenido del Servicio (codigo, modelos, textos, graficos,
  logotipos) es propiedad del Prestador o se utiliza bajo licencia.
- El usuario no puede copiar, distribuir, modificar ni realizar ingenieria
  inversa de ningun componente del Servicio.
- Los datos de mercado mostrados proceden de fuentes publicas (GeckoTerminal,
  DexScreener, APIs de blockchain) y su redistribucion esta sujeta a las
  condiciones de dichas fuentes.

---

## 7. Limitacion de responsabilidad

- El Servicio se proporciona "tal cual" (*as is*) sin garantias de ningun
  tipo, expresas o implicitas.
- El Prestador no garantiza la disponibilidad ininterrumpida del Servicio,
  la exactitud de los datos ni la rentabilidad de las senales.
- El Prestador no sera responsable de danos directos, indirectos,
  incidentales, consecuentes ni punitivos derivados del uso del Servicio.
- En cualquier caso, la responsabilidad maxima del Prestador se limitara
  al importe total pagado por el usuario en los ultimos 3 meses.

---

## 8. Uso aceptable

El usuario se compromete a:

- No utilizar el Servicio para actividades ilegales.
- No intentar acceder a cuentas o datos de otros usuarios.
- No realizar scraping, ingenieria inversa ni sobrecarga intencionada
  de los servidores.
- No redistribuir las senales del Servicio a terceros con fines
  comerciales.

---

## 9. Modificaciones

El Prestador se reserva el derecho de modificar estos Terminos en
cualquier momento. Los cambios se comunicaran al usuario por email o
mediante aviso en el Servicio. El uso continuado tras la notificacion
constituye aceptacion de los nuevos Terminos.

---

## 10. Legislacion aplicable y jurisdiccion

Estos Terminos se rigen por la legislacion espanola. Para la resolucion
de cualquier controversia, las partes se someten a los Juzgados y
Tribunales de Las Palmas de Gran Canaria (Espana), salvo que la normativa
de consumidores establezca un fuero distinto.

---

## 11. Contacto

Para cualquier consulta relacionada con estos Terminos:

- **Email**: info@memedetector.es

*Ultima actualizacion: marzo 2026*
"""


_POLITICA_PRIVACIDAD = """
## 1. Responsable del tratamiento

- **Responsable**: Ulises Diaz Hernandez
- **Correo electronico**: info@memedetector.es
- **Domicilio fiscal**: Espana

---

## 2. Datos personales que recopilamos

| Dato | Finalidad | Base legal |
|------|-----------|------------|
| Email | Registro, comunicaciones | Ejecucion de contrato (art. 6.1.b RGPD) |
| Contrasena (hash) | Autenticacion | Ejecucion de contrato |
| Chat ID de Telegram | Envio de alertas (opcional) | Consentimiento (art. 6.1.a RGPD) |
| Nombre mostrado (display name) | Personalizacion | Consentimiento |
| Direccion IP y User-Agent | Seguridad, prevencion de abuso | Interes legitimo (art. 6.1.f RGPD) |
| Datos de suscripcion (plan, fecha inicio/fin) | Gestion del servicio | Ejecucion de contrato |
| ID de cliente de Stripe | Gestion de pagos | Ejecucion de contrato |

**No recopilamos** datos biometricos, de salud, orientacion sexual,
opiniones politicas, ni ninguna categoria especial de datos personales.

**No recopilamos** direcciones de wallets de criptomonedas ni claves
privadas.

---

## 3. Como utilizamos tus datos

- **Prestacion del servicio**: autenticacion, gestion de cuenta, envio de
  senales y alertas.
- **Facturacion**: procesamiento de pagos a traves de Stripe. No
  almacenamos datos de tarjetas de credito; estos se gestionan
  exclusivamente por Stripe (certificado PCI DSS Nivel 1).
- **Comunicaciones**: avisos de servicio, cambios en los Terminos y, si
  el usuario lo consiente, novedades del producto.
- **Mejora del servicio**: analisis agregado y anonimizado del uso para
  mejorar funcionalidades.
- **Seguridad**: deteccion de accesos no autorizados y prevencion de
  fraude.

---

## 4. Almacenamiento y seguridad

- Los datos se almacenan en **Supabase**, con servidores ubicados en la
  **Union Europea** (region eu-central, Frankfurt, Alemania).
- Las contrasenas se almacenan como hashes bcrypt (nunca en texto plano).
- Las comunicaciones se cifran mediante TLS/HTTPS.
- El acceso a la base de datos esta protegido mediante Row Level Security
  (RLS) de Supabase, de forma que cada usuario solo puede acceder a sus
  propios datos.
- Se realizan copias de seguridad automaticas diarias.

---

## 5. Comparticion de datos con terceros

| Tercero | Dato compartido | Finalidad |
|---------|----------------|-----------|
| **Supabase** (Viena, AT / Frankfurt, DE) | Todos los datos de cuenta | Hosting y base de datos |
| **Stripe** (EE.UU., con clausulas contractuales tipo) | Email, datos de pago | Procesamiento de pagos |
| **Telegram** (Emiratos Arabes Unidos) | Chat ID | Envio de alertas (solo si el usuario lo configura) |
| **Render** (EE.UU.) | Logs del servidor (IP, User-Agent) | Hosting de la aplicacion |
| **GitHub Actions** | Ninguno personal | CI/CD automatizado |

**No vendemos, alquilamos ni cedemos datos personales a terceros con
fines comerciales.**

Las transferencias internacionales a paises fuera del EEE se amparan en
Clausulas Contractuales Tipo de la Comision Europea (art. 46.2.c RGPD) o
en decisiones de adecuacion cuando existan.

---

## 6. Cookies y tecnologias similares

El Servicio utiliza:

- **Cookies de sesion** (estrictamente necesarias): mantienen la sesion
  del usuario activa. Se eliminan al cerrar el navegador o tras el
  tiempo de inactividad configurado.
- **Almacenamiento local (localStorage)**: para preferencias de interfaz
  (tema, idioma).

**No utilizamos** cookies de terceros para publicidad, tracking ni
analytics. No usamos Google Analytics, Facebook Pixel ni herramientas
similares.

---

## 7. Derechos del usuario (RGPD / LOPD-GDD)

De acuerdo con el Reglamento (UE) 2016/679 y la Ley Organica 3/2018
(LOPD-GDD), el usuario tiene derecho a:

- **Acceso**: obtener confirmacion de si se tratan sus datos y acceder
  a ellos.
- **Rectificacion**: corregir datos inexactos o incompletos.
- **Supresion** ("derecho al olvido"): solicitar la eliminacion de sus
  datos cuando ya no sean necesarios.
- **Limitacion del tratamiento**: solicitar que se restrinja el
  tratamiento en determinadas circunstancias.
- **Portabilidad**: recibir sus datos en un formato estructurado, de uso
  comun y lectura mecanica (JSON/CSV).
- **Oposicion**: oponerse al tratamiento basado en interes legitimo.
- **Revocacion del consentimiento**: retirar el consentimiento en
  cualquier momento sin que afecte a la licitud del tratamiento previo.

Para ejercer cualquiera de estos derechos, contacta con nosotros en
**info@memedetector.es** indicando tu email de registro y el derecho
que deseas ejercer. Responderemos en un plazo maximo de **30 dias**.

Si consideras que tus derechos no han sido atendidos, puedes presentar
una reclamacion ante la **Agencia Espanola de Proteccion de Datos (AEPD)**
en https://www.aepd.es.

---

## 8. Conservacion de datos

- **Datos de cuenta**: se conservan mientras la cuenta este activa. Tras
  la eliminacion de la cuenta, se suprimen en un plazo de 30 dias,
  salvo obligacion legal de conservacion.
- **Datos de facturacion**: se conservan durante el plazo legal exigido
  por la normativa fiscal espanola (4 anos, art. 66 Ley General
  Tributaria).
- **Logs de acceso**: se conservan 12 meses conforme a la Ley 25/2007
  de conservacion de datos.

---

## 9. Menores de edad

El Servicio no esta dirigido a menores de 16 anos. No recopilamos
conscientemente datos de menores. Si detectamos que un usuario es menor
de 16 anos, eliminaremos su cuenta y datos asociados.

---

## 10. Modificaciones de esta politica

Nos reservamos el derecho de actualizar esta Politica de Privacidad.
Los cambios se comunicaran por email o mediante aviso en el Servicio.
La fecha de ultima actualizacion se indica al final del documento.

---

## 11. Contacto y Delegado de Proteccion de Datos

Para consultas sobre proteccion de datos:

- **Email**: info@memedetector.es
- **Autoridad de control**: Agencia Espanola de Proteccion de Datos
  (AEPD) — https://www.aepd.es

*Ultima actualizacion: marzo 2026*
"""


# ============================================================
# RENDER
# ============================================================

def render():
    """Paginas legales — Terminos de servicio y Politica de privacidad."""
    st.header(":material/gavel: Legal")

    tab_tos, tab_privacy = st.tabs([
        "Terminos de Servicio",
        "Politica de Privacidad",
    ])

    with tab_tos:
        st.markdown(_TERMINOS_DE_SERVICIO)

    with tab_privacy:
        st.markdown(_POLITICA_PRIVACIDAD)
