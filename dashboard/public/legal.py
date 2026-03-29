"""
legal.py — Paginas legales: Aviso Legal, Política de Privacidad, Política de Cookies.

Texto legal adaptado a la legislacion espanola y europea:
- LSSI-CE (Ley 34/2002 de Servicios de la Sociedad de la Informacion)
- LOPD-GDD (Ley Organica 3/2018 de Proteccion de Datos)
- RGPD (Reglamento UE 2016/679)
- Directiva ePrivacy (2002/58/CE)

Servicio: MemeDetector — análisis de señales de criptomonedas (memecoins).
Titular: ULL MIDDLE MOORE S.L., Carretera General La Perdoma 35, La Orotava, Santa Cruz de Tenerife, España.
Contacto: info@memedetector.es
"""

import streamlit as st


# ============================================================
# TAB 1 — AVISO LEGAL (TERMINOS DE SERVICIO)
# ============================================================

_AVISO_LEGAL = """
## 1. Datos identificativos del responsable

En cumplimiento del artículo 10 de la **Ley 34/2002, de 11 de julio, de Servicios de la
Sociedad de la Informacion y de Comercio Electronico (LSSI-CE)**, se facilitan los
siguientes datos identificativos del titular del sitio web:

| | |
|---|---|
| **Titular** | ULL MIDDLE MOORE S.L. |
| **NIF** | B76672864 |
| **Domicilio** | Carretera General La Perdoma 35, La Orotava, Santa Cruz de Tenerife, España |
| **Correo electrónico** | info@memedetector.es |
| **Sitio web** | www.memedetector.es |
| **Actividad** | Prestacion de servicios de análisis de datos sobre criptomonedas (memecoins) mediante modelos de Machine Learning |

---

## 2. Objeto y ambito de aplicacion

El presente Aviso Legal regula el acceso y uso del sitio web **www.memedetector.es**
(en adelante, "el Sitio Web") y del servicio **MemeDetector** (en adelante, "el Servicio"),
una herramienta de análisis de datos que emplea modelos de Machine Learning para evaluar
memecoins (tokens especulativos) en blockchains como Solana, Ethereum y Base.

El Servicio proporciona:

- Puntuaciones de potencial ("señales") generadas por modelos estadísticos.
- Dashboards de visualizacion de datos históricos y métricas de mercado.
- Alertas opcionales via Telegram.
- Funciones de watchlist, portfolio simulado y track record de señales pasadas.

El acceso al Sitio Web y al Servicio atribuye la condicion de **usuario** e implica la
aceptacion plena e incondicional de todas y cada una de las disposiciones incluidas en
este Aviso Legal, en la Política de Privacidad y en la Política de Cookies, en la version
publicada en el momento en que el usuario acceda al Sitio Web.

---

## 3. Condiciones de uso

### 3.1. Acceso al Servicio

El acceso a determinadas funcionalidades del Servicio requiere el registro previo del
usuario mediante la creación de una cuenta con un correo electrónico valido y una contraseña.

El usuario garantiza que los datos proporcionados durante el registro son veridicos,
exactos, completos y actualizados, siendo responsable de cualquier dano o perjuicio
que pudiera derivarse de la inexactitud de los mismos.

### 3.2. Obligaciones del usuario registrado

El usuario se compromete a:

- Mantener la confidencialidad de sus credenciales de acceso y notificar de inmediato
  cualquier uso no autorizado de su cuenta.
- Utilizar el Servicio de conformidad con la ley, la moral, el orden publico y las
  presentes condiciones de uso.
- No utilizar el Servicio para actividades ilegales, fraudulentas o que atenten contra
  los derechos de terceros.

### 3.3. Usos prohibidos

Queda expresamente prohibido:

- Intentar acceder a cuentas, datos o sistemas de otros usuarios.
- Realizar scraping, ingenieria inversa, descompilacion o cualquier forma de extraccion
  automatizada del contenido del Servicio.
- Provocar una sobrecarga intencionada de los servidores o cualquier interferencia con el
  normal funcionamiento del Servicio.
- Redistribuir las señales, análisis o datos del Servicio a terceros con fines comerciales
  sin autorizacion expresa del Titular.
- Suplantar la identidad de otro usuario o persona.

El incumplimiento de estas condiciones podra dar lugar a la suspension o cancelacion
inmediata de la cuenta del usuario, sin perjuicio de las acciones legales que pudieran
corresponder.

---

## 4. Propiedad intelectual e industrial

Todos los contenidos del Sitio Web y del Servicio, incluyendo a titulo enunciativo pero
no limitativo: textos, graficos, imagenes, logotipos, iconos, codigo fuente, modelos de
Machine Learning, algoritmos, bases de datos, diseno grafico y software, son propiedad
del Titular o de terceros que han autorizado su uso, y estan protegidos por las normas
nacionales e internacionales de propiedad intelectual e industrial.

Queda prohibida la reproduccion, distribución, comunicacion publica, transformacion o
cualquier otra forma de explotacion de los contenidos del Sitio Web sin la autorizacion
expresa y por escrito del Titular, salvo lo dispuesto legalmente.

Los datos de mercado mostrados proceden de fuentes publicas (GeckoTerminal, DexScreener,
APIs de blockchain) y su redistribución esta sujeta a las condiciones de dichas fuentes.

---

## 5. Exencion de responsabilidad financiera

**EL SERVICIO NO CONSTITUYE ASESORAMIENTO FINANCIERO, DE INVERSION, FISCAL NI LEGAL DE
NINGUN TIPO.**

El usuario reconoce y acepta expresamente que:

a) Las señales, puntuaciones y análisis generados por el Servicio son el resultado de
   modelos estadísticos automaticos y **no representan recomendaciones de compra, venta ni
   mantenimiento** de ningun activo digital o de cualquier otra naturaleza.

b) Los memecoins son activos **altamente especulativos y volatiles**. El usuario asume que
   puede perder la **totalidad** de su inversion. El rendimiento pasado no es indicativo de
   resultados futuros.

c) El Titular **no es una entidad regulada** por la Comision Nacional del Mercado de Valores
   (CNMV), la Securities and Exchange Commission (SEC) ni ningun otro organismo regulador
   financiero nacional o internacional.

d) Toda decisión de inversion es **responsabilidad exclusiva del usuario**. El Titular no
   sera responsable en ningun caso de las perdidas economicas, directas o indirectas,
   derivadas del uso de la información proporcionada por el Servicio.

e) El usuario debe realizar siempre su propia investigacion (**DYOR — Do Your Own
   Research**) y, en su caso, consultar a un asesor financiero profesional antes de tomar
   cualquier decisión de inversion.

f) El Servicio opera en un mercado no regulado. Los activos analizados pueden ser objeto
   de manipulacion de mercado, rug pulls u otras prácticas fraudulentas sobre las cuales
   el Titular no tiene control ni responsabilidad alguna.

---

## 6. Suscripciones y pagos

### 6.1. Planes

El Servicio ofrece distintos planes (Free, Pro, Enterprise) con diferentes niveles de
funcionalidad. Los precios, características y condiciones especificas de cada plan se
detallan en la pagina de Pricing del Sitio Web.

### 6.2. Procesamiento de pagos

- Los pagos se procesan a traves de **Stripe**, proveedor de pagos certificado **PCI DSS
  Nivel 1**. El Titular **no almacena** datos de tarjetas de credito, números de cuenta
  bancaria ni información financiera sensible del usuario.
- Los precios indicados incluyen el IVA aplicable salvo que se indique expresamente lo
  contrario.

### 6.3. Renovacion y cancelacion

- Las suscripciones se renuevan **automáticamente** al final de cada periodo de facturación
  (mensual), salvo cancelacion previa por parte del usuario.
- El usuario puede cancelar su suscripción en cualquier momento desde su panel de perfil.
  Al cancelar, el acceso a las funciones premium se mantiene hasta el final del periodo ya
  facturado.

### 6.4. Política de reembolsos

- **No se realizan reembolsos parciales** por periodos no consumidos, salvo en los casos
  expresamente previstos por la legislacion vigente en materia de consumidores y usuarios
  (Real Decreto Legislativo 1/2007) o por decisión discrecional del Titular.
- El usuario dispone del derecho de desistimiento previsto en la normativa de consumidores
  dentro de los 14 dias naturales siguientes a la contratacion, siempre que no haya
  utilizado el Servicio de forma sustancial durante dicho periodo.

---

## 7. Limitacion de responsabilidad

- El Servicio se proporciona **"tal cual" (as is)** y **"segun disponibilidad" (as available)**,
  sin garantias de ningun tipo, expresas o implicitas, incluyendo pero no limitandose a
  garantias de comerciabilidad, idoneidad para un fin particular o no infraccion.
- El Titular **no garantiza** la disponibilidad ininterrumpida del Servicio, la exactitud
  de los datos de mercado mostrados, ni la rentabilidad de las señales generadas.
- El Titular **no sera responsable** de danos directos, indirectos, incidentales,
  consecuentes, especiales ni punitivos derivados del uso o la imposibilidad de uso del
  Servicio.
- En cualquier caso, la **responsabilidad maxima** del Titular frente al usuario se limitara
  al importe total efectivamente pagado por el usuario en los **3 meses** inmediatamente
  anteriores al hecho causante de la responsabilidad.
- El Titular no sera responsable de los fallos o interrupciones del Servicio causados por
  razones de fuerza mayor, fallos de la red de Internet, fallos de las APIs de terceros
  (GeckoTerminal, DexScreener, blockchain RPCs) o cualquier otra circunstancia fuera de
  su control razonable.

---

## 8. Modificaciones de los Terminos

El Titular se reserva el derecho de modificar el presente Aviso Legal y las condiciones
de uso en cualquier momento. Los cambios sustanciales se comunicaran al usuario con una
antelacion minima de **15 dias** mediante correo electrónico o aviso destacado en el
Servicio.

El uso continuado del Servicio tras la entrada en vigor de las modificaciones constituye
la aceptacion de los nuevos terminos. En caso de desacuerdo, el usuario podra cancelar su
cuenta sin penalizacion.

---

## 9. Legislacion aplicable y jurisdiccion

El presente Aviso Legal se rige e interpreta conforme a la **legislacion espanola**.

Para la resolución de cualquier controversia que pudiera derivarse del acceso o uso del
Servicio, las partes se someten a los **Juzgados y Tribunales de Santa Cruz de Tenerife de Gran
Canaria (España)**, sin perjuicio de lo dispuesto en la normativa vigente en materia de
consumidores y usuarios, que podra determinar la competencia del tribunal del domicilio
del consumidor.

El usuario, como consumidor residente en la Union Europea, tambien puede recurrir a la
**plataforma europea de resolución de litigios en línea (ODR)**:
https://ec.europa.eu/consumers/odr

---

## 10. Contacto

Para cualquier consulta relacionada con el presente Aviso Legal:

- **Email**: info@memedetector.es

*Ultima actualización: marzo 2026*
"""


# ============================================================
# TAB 2 — POLITICA DE PRIVACIDAD
# ============================================================

_POLITICA_PRIVACIDAD = """
La presente Política de Privacidad tiene por objeto informar a los usuarios del Sitio Web
y del Servicio **MemeDetector** sobre el tratamiento de sus datos personales, en cumplimiento
del **Reglamento (UE) 2016/679 del Parlamento Europeo y del Consejo, de 27 de abril de 2016**
(Reglamento General de Proteccion de Datos, en adelante **RGPD**) y de la **Ley Organica
3/2018, de 5 de diciembre, de Proteccion de Datos Personales y garantia de los derechos
digitales (LOPD-GDD)**.

---

## 1. Responsable del tratamiento

| | |
|---|---|
| **Responsable** | ULL MIDDLE MOORE S.L. |
| **NIF** | B76672864 |
| **Domicilio** | Carretera General La Perdoma 35, La Orotava, Santa Cruz de Tenerife, España |
| **Correo electrónico** | info@memedetector.es |
| **Sitio web** | www.memedetector.es |

---

## 2. Datos personales que recopilamos

A continuacion se detallan las categorias de datos personales que recopilamos, la finalidad
de su tratamiento y la base juridica que lo legitima conforme al RGPD:

| Dato personal | Finalidad | Base legal (RGPD) |
|---|---|---|
| Correo electrónico | Registro, autenticación, comunicaciones de servicio | Ejecucion del contrato (art. 6.1.b) |
| Contraseña (almacenada como hash bcrypt) | Autenticacion segura | Ejecucion del contrato (art. 6.1.b) |
| Chat ID de Telegram | Envio de alertas y notificaciones (opcional) | Consentimiento del interesado (art. 6.1.a) |
| Nombre mostrado (display name) | Personalizacion de la interfaz | Consentimiento del interesado (art. 6.1.a) |
| Datos de suscripción (plan, fechas) | Gestión del servicio y facturación | Ejecucion del contrato (art. 6.1.b) |
| ID de cliente de Stripe | Vinculacion con procesador de pagos | Ejecucion del contrato (art. 6.1.b) |
| Datos de pago (tarjeta, cuenta bancaria) | Procesamiento de pagos | Ejecucion del contrato (art. 6.1.b) — **gestiónado exclusivamente por Stripe; el Titular NO almacena estos datos** |
| Direccion IP | Seguridad, prevencion de abuso, cumplimiento legal | Interes legitimo del responsable (art. 6.1.f) |
| User-Agent del navegador | Seguridad, compatibilidad tecnica | Interes legitimo del responsable (art. 6.1.f) |

### Datos que NO recopilamos

- **No recopilamos** datos de categorias especiales (art. 9 RGPD): datos biometricos, de salud,
  orientacion sexual, opiniones políticas, creencias religiosas, afiliacion sindical ni datos
  geneticos.
- **No recopilamos** direcciones de wallets de criptomonedas ni claves privadas.
- **No recopilamos** datos de menores de 16 anos de forma consciente. Si detectamos que un
  usuario es menor de dicha edad, procederemos a eliminar su cuenta y datos asociados de
  forma inmediata.

---

## 3. Finalidad del tratamiento

Los datos personales son tratados para las siguientes finalidades:

- **Prestacion del servicio**: registro, autenticación, gestión de cuenta, generación y envio
  de señales y alertas.
- **Facturacion y gestión de pagos**: procesamiento de suscripciones y pagos a traves de Stripe.
- **Comunicaciones de servicio**: avisos sobre cambios en los Terminos, interrupciones
  programadas, actualizaciónes relevantes del Servicio.
- **Comunicaciones comerciales**: unicamente si el usuario ha otorgado su consentimiento
  expreso, información sobre novedades y mejoras del Servicio.
- **Seguridad**: deteccion y prevencion de accesos no autorizados, fraude y uso abusivo del
  Servicio.
- **Mejora del servicio**: análisis agregado y anonimizado de patrones de uso para optimizar
  funcionalidades. Estos datos anonimizados no constituyen datos personales.

---

## 4. Almacenamiento y medidas de seguridad

Los datos personales se almacenan aplicando las siguientes medidas tecnicas y organizativas:

- **Ubicacion de los servidores**: los datos se almacenan en **Supabase**, con servidores
  ubicados en la **Union Europea** (region eu-central-1, **Frankfurt, Alemania**), garantizando
  que los datos no abandonan el Espacio Economico Europeo para su almacenamiento primario.
- **Cifrado en transito**: todas las comunicaciones entre el usuario y el Servicio se cifran
  mediante protocolo **TLS 1.2 o superior (HTTPS)**.
- **Cifrado de contraseñas**: las contraseñas se almacenan como hashes **bcrypt** con salt
  aleatorio. En ningun caso se almacenan en texto plano.
- **Control de acceso**: el acceso a la base de datos esta protegido mediante **Row Level
  Security (RLS)** de Supabase, garantizando que cada usuario solo puede acceder a sus propios
  datos.
- **Copias de seguridad**: se realizan copias de seguridad automáticas diarias con cifrado.
- **Principio de minimizacion**: solo se recopilan los datos estrictamente necesarios para la
  prestacion del Servicio (art. 5.1.c RGPD).

---

## 5. Encargados de tratamiento y comparticion de datos con terceros

Para la prestacion del Servicio, los datos personales pueden ser comunicados a los siguientes
terceros en calidad de encargados de tratamiento (art. 28 RGPD):

| Encargado de tratamiento | Ubicacion | Datos compartidos | Finalidad | Garantias |
|---|---|---|---|---|
| **Supabase Inc.** | Frankfurt, Alemania (UE) | Todos los datos de cuenta | Base de datos y autenticación | Servidores en UE; clausulas contractuales tipo (art. 28 RGPD) |
| **Stripe Inc.** | Estados Unidos | Email, datos de pago | Procesamiento de pagos | Certificacion **PCI DSS Nivel 1**; clausulas contractuales tipo UE (art. 46.2.c RGPD) |
| **Telegram Messenger Inc.** | Emiratos Arabes Unidos | Chat ID de Telegram | Envio de alertas | Solo si el usuario configura voluntariamente la integracion; consentimiento explicito |
| **Render Inc.** | Estados Unidos | Direccion IP, User-Agent (logs del servidor) | Hosting de la aplicacion | Clausulas contractuales tipo UE (art. 46.2.c RGPD) |
| **Vercel Inc.** | Estados Unidos | Direccion IP, User-Agent (logs CDN) | Hosting de la landing page y CDN | Clausulas contractuales tipo UE (art. 46.2.c RGPD) |

**No vendemos, alquilamos ni cedemos datos personales a terceros con fines comerciales,
publicitarios ni de elaboracion de perfiles.**

---

## 6. Transferencias internacionales de datos

Algunos de los encargados de tratamiento indicados en el apartado anterior tienen su sede
en **Estados Unidos**, fuera del Espacio Economico Europeo (EEE). En concreto: Stripe Inc.,
Render Inc. y Vercel Inc.

Estas transferencias internacionales se realizan con las siguientes garantias conforme al
Capítulo V del RGPD:

- **Clausulas Contractuales Tipo (CCT)** aprobadas por la Comision Europea (art. 46.2.c RGPD),
  incorporadas a los contratos con dichos proveedores.
- **Medidas complementarias** de seguridad tecnica (cifrado TLS, pseudonimizacion cuando es
  posible) conforme a las recomendaciones del Comite Europeo de Proteccion de Datos (CEPD).
- En su caso, **decisiones de adecuacion** de la Comision Europea cuando existan para el pais
  de destino.

El almacenamiento primario de datos personales se realiza siempre en servidores dentro de
la Union Europea (Supabase, Frankfurt).

---

## 7. Plazos de conservacion

Los datos personales se conservan durante los siguientes plazos:

| Categoria de datos | Plazo de conservacion | Justificacion |
|---|---|---|
| Datos de cuenta (email, perfil) | Mientras la cuenta permanezca activa | Necesarios para la ejecucion del contrato |
| Datos de cuenta tras eliminación | **30 dias** tras la solicitud de eliminación | Periodo para garantizar la supresión efectiva y permitir la recuperacion en caso de solicitud accidental |
| Datos de facturación | **4 anos** desde la ultima operacion | Obligacion legal: art. 66 de la Ley 58/2003, General Tributaria |
| Logs de acceso (IP, User-Agent) | **12 meses** | Ley 25/2007, de 18 de octubre, de conservacion de datos relativos a las comunicaciones electronicas |
| Chat ID de Telegram | Hasta que el usuario revoque su consentimiento o elimine su cuenta | Basado en consentimiento (art. 6.1.a RGPD) |

Transcurridos los plazos indicados, los datos seran suprimidos o anonimizados de forma
irreversible.

---

## 8. Derechos del interesado (ARCO+ y derechos digitales)

De conformidad con los artículos 15 a 22 del RGPD y los artículos 12 a 18 de la LOPD-GDD,
el usuario tiene reconocidos los siguientes derechos:

| Derecho | Descripcion |
|---|---|
| **Acceso** (art. 15 RGPD) | Obtener confirmacion de si se estan tratando sus datos personales y, en caso afirmativo, acceder a los mismos y a la información prevista en el art. 15.1 RGPD |
| **Rectificacion** (art. 16 RGPD) | Solicitar la correccion de datos personales inexactos o completar los que sean incompletos |
| **Supresion** (art. 17 RGPD) | Solicitar la eliminación de sus datos personales ("derecho al olvido") cuando concurra alguna de las circunstancias del art. 17.1 RGPD |
| **Limitacion del tratamiento** (art. 18 RGPD) | Solicitar la restriccion del tratamiento de sus datos en los supuestos previstos en el art. 18.1 RGPD |
| **Portabilidad** (art. 20 RGPD) | Recibir sus datos personales en un formato estructurado, de uso comun y lectura mecanica (JSON o CSV), y transmitirlos a otro responsable |
| **Oposicion** (art. 21 RGPD) | Oponerse al tratamiento de sus datos basado en el interes legitimo del responsable (art. 6.1.f), incluida la elaboracion de perfiles |
| **Revocacion del consentimiento** | Retirar el consentimiento prestado en cualquier momento, sin que ello afecte a la licitud del tratamiento basado en el consentimiento previo a su retirada |

### Como ejercer sus derechos

Para ejercer cualquiera de estos derechos, el usuario debera enviar una solicitud a
**info@memedetector.es** indicando:

1. Nombre completo y correo electrónico asociado a la cuenta.
2. El derecho que desea ejercer.
3. Copia de documento identificativo (DNI, NIE o pasaporte) para verificar su identidad.

El responsable respondera en un plazo maximo de **30 dias** desde la recepcion de la
solicitud, prorrogable por otros 2 meses en caso de solicitudes complejas o multiples,
conforme al art. 12.3 RGPD.

El ejercicio de estos derechos es **gratuito**, salvo solicitudes manifiestamente infundadas
o excesivas (art. 12.5 RGPD).

---

## 9. Delegado de Proteccion de Datos

Dado el volumen y naturaleza de los datos tratados, no se ha designado un Delegado de
Proteccion de Datos (DPD) al no ser obligatorio conforme al art. 37 RGPD. No obstante,
para cualquier cuestion relativa a la proteccion de datos personales, el usuario puede
contactar directamente con el responsable:

- **Email**: info@memedetector.es

---

## 10. Autoridad de control

Si el usuario considera que sus derechos en materia de proteccion de datos no han sido
debidamente atendidos, tiene derecho a presentar una reclamacion ante la autoridad de
control competente:

**Agencia Espanola de Proteccion de Datos (AEPD)**
- Sitio web: [https://www.aepd.es](https://www.aepd.es)
- Direccion: C/ Jorge Juan, 6 — 28001 Madrid, España
- Telefono: 901 100 099 / 91 266 35 17

---

## 11. Modificaciones de esta política

El responsable se reserva el derecho de actualizar la presente Política de Privacidad para
adaptarla a novedades legislativas, jurisprudenciales o de práctica del sector. Los cambios
sustanciales se comunicaran al usuario mediante correo electrónico o aviso destacado en el
Servicio con una antelacion minima de 15 dias.

La fecha de ultima actualización se indica al final del presente documento.

*Ultima actualización: marzo 2026*
"""


# ============================================================
# TAB 3 — POLITICA DE COOKIES
# ============================================================

_POLITICA_COOKIES = """
La presente Política de Cookies se establece en cumplimiento del **artículo 22.2 de la
Ley 34/2002, de 11 de julio, de Servicios de la Sociedad de la Informacion y de Comercio
Electronico (LSSI-CE)** y de la **Directiva 2002/58/CE del Parlamento Europeo y del Consejo**
(Directiva ePrivacy), y tiene por objeto informar al usuario de manera clara y precisa sobre
las cookies y tecnologías similares que se utilizan en el sitio web **www.memedetector.es**.

---

## 1. Que son las cookies

Las cookies son pequenos archivos de texto que los sitios web almacenan en el dispositivo
del usuario (ordenador, tablet, telefono movil) cuando este los visita. Las cookies permiten
al sitio web recordar información sobre la visita del usuario, como sus preferencias de
idioma, datos de inicio de sesión u otra información, con el fin de facilitar la siguiente
visita y hacer que el sitio resulte mas util.

Ademas de las cookies, existen otras tecnologías similares como el almacenamiento local
(localStorage) del navegador, que cumplen funciones analogas.

---

## 2. Cookies y tecnologías que utilizamos

### 2.1. Cookies tecnicas / estrictamente necesarias

Estas cookies son imprescindibles para el correcto funcionamiento del Servicio y estan
**exentas de consentimiento** conforme al artículo 22.2 de la LSSI-CE y al Considerando 66
de la Directiva ePrivacy.

| Cookie / Tecnologia | Proveedor | Finalidad | Duracion | Tipo |
|---|---|---|---|---|
| Cookie de sesion de Streamlit | MemeDetector (propia) | Mantener la sesión del usuario activa y gestionar la autenticación | Sesion (se elimina al cerrar el navegador o tras periodo de inactividad) | Tecnica, necesaria |
| localStorage (preferencias de interfaz) | MemeDetector (propia) | Almacenar preferencias de tema visual y configuración de la interfaz | Persistente hasta eliminación manual | Tecnica, necesaria |

### 2.2. Cookies de Stripe (procesamiento de pagos)

Cuando el usuario accede a la pasarela de pago para contratar una suscripción, **Stripe**
puede instalar cookies propias necesarias para el procesamiento seguro del pago y la
prevencion del fraude. Estas cookies son **estrictamente necesarias** para completar la
transaccion de pago y estan amparadas por la excepcion de cookies necesarias.

| Cookie | Proveedor | Finalidad | Tipo |
|---|---|---|---|
| __stripe_mid / __stripe_sid | Stripe Inc. | Prevencion de fraude y procesamiento seguro de pagos | Tecnica, necesaria |

Para mas información sobre las cookies de Stripe, consulte su política de cookies:
[https://stripe.com/es/cookie-settings](https://stripe.com/es/cookie-settings)

### 2.3. Cookies que NO utilizamos

Es importante destacar que el Servicio **NO utiliza**:

- **Cookies de analitica** (Google Analytics, Matomo, Plausible ni similares).
- **Cookies de publicidad** (Google Ads, Facebook Pixel, redes publicitarias ni similares).
- **Cookies de redes sociales** (botones de compartir, widgets de terceros ni similares).
- **Cookies de seguimiento** (tracking) de terceros de ninguna clase.
- **Cookies de elaboracion de perfiles** con fines comerciales o publicitarios.

Por este motivo, el Servicio **no requiere un banner de consentimiento de cookies**, ya que
unicamente utiliza cookies exentas de consentimiento conforme a la normativa vigente.

---

## 3. Como gestionar y eliminar cookies

El usuario puede configurar su navegador para aceptar o rechazar cookies, asi como para
eliminar las cookies ya almacenadas. A continuacion se facilitan enlaces a las instrucciones
de los navegadores mas habituales:

- **Google Chrome**: [Gestiónar cookies en Chrome](https://support.google.com/chrome/answer/95647)
- **Mozilla Firefox**: [Gestiónar cookies en Firefox](https://support.mozilla.org/es/kb/cookies-información-que-los-sitios-web-guardan-en-)
- **Apple Safari**: [Gestiónar cookies en Safari](https://support.apple.com/es-es/guide/safari/sfri11471/mac)
- **Microsoft Edge**: [Gestiónar cookies en Edge](https://support.microsoft.com/es-es/microsoft-edge/eliminar-cookies-en-microsoft-edge-63947406-40ac-c3b8-57b9-2a946a29ae09)

**Nota importante**: la desactivacion de las cookies tecnicas/necesarias puede impedir el
correcto funcionamiento del Servicio, en particular la gestión de la sesión y la
autenticación.

---

## 4. Actualizacion de esta política

El Titular se reserva el derecho de modificar la presente Política de Cookies para adaptarla
a novedades legislativas, tecnologicas o cambios en el funcionamiento del Servicio. Cualquier
cambio sustancial sera comunicado al usuario mediante aviso en el Sitio Web.

Se recomienda al usuario revisar periodicamente esta Política de Cookies para estar informado
sobre como se utilizan.

*Ultima actualización: marzo 2026*
"""


# ============================================================
# RENDER
# ============================================================

def render():
    """Paginas legales — Aviso Legal, Política de Privacidad y Política de Cookies."""
    st.header(":material/gavel: Legal")

    tab_aviso, tab_privacy, tab_cookies = st.tabs([
        "Aviso Legal",
        "Política de Privacidad",
        "Política de Cookies",
    ])

    with tab_aviso:
        st.markdown(_AVISO_LEGAL)

    with tab_privacy:
        st.markdown(_POLITICA_PRIVACIDAD)

    with tab_cookies:
        st.markdown(_POLITICA_COOKIES)
