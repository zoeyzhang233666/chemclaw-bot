# ChemClaw v0.3.0

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Русский](README.ru.md) | [Français](README.fr.md) | [العربية](README.ar.md) | **Español** | [Português](README.pt.md)

**En el comercio de productos químicos, lo que realmente importa es localizar compradores con necesidades reales, proveedores capaces de entregar y precios de mercado con fuentes, fechas y condiciones verificables.**

- ¿Vendes carbonato de sodio denso? Busca fábricas de vidrio que preparan nuevas líneas y podrían aumentar su consumo de materia prima.
- ¿Compras óxido de propileno? Distingue fabricantes, representantes y distribuidores con existencias, y compara precios con entrega.
- ¿Importas monoetilenglicol? Verifica las plantas de producción extranjeras y calcula el coste total puesto en fábrica.
- ¿Investigas el metanol? Combina precios físicos, futuros, inventarios, paradas y proyectos en una base de análisis verificable.

ChemClaw incluye dos vías de conexión preconfiguradas: **[Chemcloud Data Hub](https://mcp.chem-cloud.cn/)** para información especializada del sector y **[APIHub](https://apihub.chem-cloud.cn/)** para utilizar modelos de IA con opciones de precio asequibles. Solicita cada clave y pégala en la configuración de la aplicación; no necesitas programar una integración.

El conjunto de datos de Chemcloud, *High-Quality Industry-Specific Knowledge Dataset for Chemical Industry Agents*, fue seleccionado como **caso representativo de datos sectoriales de alta calidad de Shanghái en 2026** y presentado durante la **Global Data Ecosystem Conference 2026**. [Anuncio oficial](https://dt.sheitc.sh.gov.cn/cms/slddt/3123.jhtml). Esta distinción respalda el trabajo de datos sectoriales; las decisiones de compraventa requieren comprobar los documentos originales.

**50 agentes especializados, 15 grupos de colaboración y 108 habilidades del sector químico** para compraventa nacional e internacional, fundamentales energéticos y químicos, análisis físico–futuros e investigación cuantitativa. Los resultados se entregan como gráficos dentro del chat, Excel, PowerPoint, Word e informes web interactivos.

## Índice

1. [Por qué ChemClaw y no solo una IA generalista](#1-por-qué-chemclaw-y-no-solo-una-ia-generalista)
2. [Fuentes de datos y oportunidades](#2-fuentes-de-datos-y-oportunidades)
3. [Comercio físico nacional](#3-comercio-físico-nacional)
4. [Comercio internacional de productos químicos](#4-comercio-internacional-de-productos-químicos)
5. [Energía, futuros e investigación cuantitativa](#5-energía-futuros-e-investigación-cuantitativa)
6. [Gráficos dentro del chat](#6-gráficos-dentro-del-chat)
7. [Entregables](#7-entregables)
8. [Trabajar con archivos Office existentes](#8-trabajar-con-archivos-office-existentes)
9. [Navegador y control humano](#9-navegador-y-control-humano)
10. [Agentes y grupos](#10-agentes-y-grupos)
11. [Instalación y configuración](#11-instalación-y-configuración)
12. [Instrucciones prácticas para copiar](#12-instrucciones-prácticas-para-copiar)

---

## 1. Por qué ChemClaw y no solo una IA generalista

Una IA generalista puede buscar información y generar archivos. ChemClaw destaca porque **ya reúne datos del sector químico, procedimientos de comprobación, funciones profesionales y formatos de entrega**. El comercial, comprador o analista no tiene que diseñar desde cero cada consulta y cada regla.

| Trabajo real | IA web generalista | ChemClaw |
| --- | --- | --- |
| **Encontrar clientes que consumen la materia prima** | Sugiere empresas, pero hay que verificar su actividad | Relaciona producto, aplicaciones y empresas en Data Hub y comprueba materias primas en estudios ambientales, plantas y expansiones |
| **Distinguir productores de intermediarios** | Ofrece posibles proveedores | Separa fábricas, filiales comerciales y canales spot; comprueba planta, grados, licencias y documentación; señala inventario y COA pendientes |
| **Comparar una cotización física** | Los resultados pueden mezclar mercados y fechas | Prioriza el mercado físico y controla región, grado, fecha, impuestos, pago y base de entrega; nunca sustituye spot por futuros |
| **Detectar nuevas oportunidades** | Noticias y listados | Cruza datos de empresas, licencias, proyectos, licitaciones y PDF originales CNINFO para preparar una lista de seguimiento |
| **Importar y exportar con criterio** | Traducción y búsqueda | Mercado objetivo, fabricantes, importadores, verificación de empresas, términos FOB/CFR/CIF y costes aduaneros/logísticos |
| **Investigar futuros y patrones estadísticos** | Explica métodos | Base, diferenciales temporales, existencias, estacionalidad, lead–lag, eventos y backtesting con contratos negociables |
| **Entregar el trabajo al equipo** | Texto y hojas aisladas | Equipos de agentes, gráficos en el chat y Excel, PPT, Word y páginas web con fuentes |

## 2. Fuentes de datos y oportunidades

### 2.1 Chemcloud Data Hub: información química y comercial

[Solicita una clave](https://mcp.chem-cloud.cn/) y añádela en **Configuración → Conectores → Chemcloud Data Hub**. La dirección de conexión ya está preparada. El acceso a campos y registros depende de tu autorización.

| Categoría | Datos disponibles según permiso | ¿Para qué sirven? |
| --- | --- | --- |
| **Compuestos** | CAS, nombres, fichas químicas, MSDS/SDS, información de materiales y precios disponibles | Comprobar el producto exacto y evitar confundir sustancias, nombres o grados |
| **Empresas y clientes** | Búsqueda, registros corporativos, accionistas, grupos, patentes, licitaciones, perfil de cliente 360° | Identificar compradores, fabricantes, filiales, capacidad y proyectos relevantes |
| **Negociaciones y pedidos** | Solicitudes y ofertas, pedidos de venta/compra, movimientos de inventario, resúmenes de cobros | Revisar **solo datos de negocio autorizados**, detectar pedidos pendientes y analizar existencias o cobros |
| **Mercados y precios** | Puntos de mercado, históricos y tendencias disponibles | Comparar precios físicos por fecha, zona, calidad y condición comercial |

**Ejemplo de venta:**

> Vendemos óxido de propileno en Jiangsu y Zhejiang. Empieza por Chemcloud Data Hub para localizar fabricantes de polioles de poliéter y propilenglicol. Verifica plantas y consumo mediante sitios corporativos, estudios ambientales y anuncios de expansión. Entrega un Excel con empresa, fábrica, uso probado, documento fuente, grado de confianza y los diez contactos empresariales prioritarios. No inventes volúmenes de compra.

### 2.2 Proyectos gubernamentales y pruebas de consumo

Las evaluaciones de impacto ambiental (**EIA**), licencias de emisiones, registros de proyectos, anuncios de parques industriales y documentos de inversión pueden incluir **equipos, capacidad prevista y consumo anual de materias primas**. Distingue solicitud, aprobación, construcción, pruebas y producción real: una autorización no demuestra que la planta ya opere.

### 2.3 CNINFO: consulta integrada de PDF corporativos

ChemClaw incorpora consultas de divulgaciones de empresas chinas cotizadas en [CNINFO](https://www.cninfo.com.cn/) por nombre, código bursátil, palabra clave y fecha. Puede obtener el **PDF original**, extraer fragmentos legibles y localizar páginas. **No requiere una clave CNINFO aparte.**

| Documento | Qué buscar | Utilidad |
| --- | --- | --- |
| **Memorias anuales y semestrales** | Productos, plantas, ventas, activos y obras en curso | Verificar actividad industrial y cambios de capacidad |
| **Inversiones y ampliaciones** | Proyecto, sociedad, ubicación, inversión, proceso, capacidad prevista y calendario | Anticipar demanda de materias primas o nueva oferta |
| **Pruebas, arranques, paradas** | Etapa y fechas publicadas | Separar proyectos anunciados de disponibilidad efectiva |
| **Grandes contratos, folletos, respuestas regulatorias** | Contrapartes, procesos, cadenas de suministro, cifras explicadas | Reconstruir vínculos comerciales y validar información |

Los PDF escaneados pueden no ofrecer texto extraíble; cifras, tablas y páginas deben comprobarse en el original.

### 2.4 Licitaciones, productores y precios de contado

Se pueden consultar páginas accesibles de [licitaciones y recursos públicos de China](https://www.ggzy.gov.cn/), compras de grupos químicos/energéticos, portales de empresas y anuncios de proyectos. Extrae comprador, producto, especificación, volumen, lugar, cierre de presentación, enlace original y estado **abierto/cerrado/adjudicado**.

Para precios físicos, consulta primero Chemcloud Data Hub y contrasta según el producto con páginas públicas de **Longzhong, SCI99/Zhuochuang, Jinlianchuang, Baichuan, Mysteel, SunSirs y SMM**, además de avisos de fabricantes. Algunas series requieren suscripción. Distingue precio anunciado, referencia de mercado, operación real y rumor.

### 2.5 Bolsas, bases químicas y comercio internacional

- **AKShare**: datos históricos OHLC disponibles para determinados futuros y acciones, útiles para gráficos de velas; no implica acceso ilimitado en tiempo real.
- **Bolsas y finanzas**: DCE, CZCE, SHFE, INE, GFEX y páginas de Sina Finance, Eastmoney o Tencent Finance; fuentes públicas de contraste, no todas APIs integradas.
- **[PubChem](https://pubchem.ncbi.nlm.nih.gov/), [OPSIN](https://opsin.ch.cam.ac.uk/), Wikipedia y Huagongshe**: identidad de sustancias, estructura y nombres; para las especificaciones de un lote se necesitan TDS, SDS y COA.
- **UN Comtrade, WITS, aduanas y asociaciones**: comercio por país y códigos HS; la importación nacional no demuestra la compra de una empresa concreta.

### 2.6 Empresas extranjeras, LinkedIn y X

Sitios de empresas, ferias, Kompass, Thomasnet, Europages, EC21, IndiaMART, Indotrading y páginas públicas indexadas de **LinkedIn y X** pueden aportar señales de fábricas, contratación, productos y expansiones. Se consultan mediante búsqueda pública y navegador, **no mediante acceso garantizado a APIs privadas**. Algunos sitios requieren una red internacional accesible, configuración de proxy y permisos de cuenta. El usuario resuelve accesos, CAPTCHA y pagos.

## 3. Comercio físico nacional

**Para ventas**, empieza por aplicaciones y procesos industriales, verifica al usuario final mediante EIA, fábrica y proyectos, y clasifica los prospectos por evidencia. **Para compras**, separa fabricantes y distribuidores, coteja grado/calidad, fábrica, autorizaciones y prepara solicitudes de precio con cantidad, entrega, impuestos, pago y documentos.

> Necesito 300 toneladas de dióxido de titanio rutilo entregadas en Wuhu. Identifica fabricantes reales, filiales comerciales y proveedores spot con Chemcloud Data Hub y fuentes empresariales. Comprueba fichas técnicas, plantas y autorizaciones. Entrega una hoja Excel RFQ con pruebas, contactos públicos, especificaciones, COA, existencias por confirmar, precio entregado con impuestos y plazo de pago. No deduzcas la capacidad productiva del mero registro mercantil.

## 4. Comercio internacional de productos químicos

La venta exterior incluye **selección de mercados, consumidores industriales, importadores, distribuidores, identificación de contrapartes, ofertas y documentos**. Para comprar fuera, confirma fabricante, fábrica, producto, capacidad nominal, operación y entidad de ventas. El cálculo de coste debe separar FOB/CFR/CIF, divisa, seguro, aranceles, IVA, puerto y transporte terrestre.

> Exportamos TiO2 rutilo a India e Indonesia. Investiga empresas de pinturas y plásticos, importadores y distribuidores mediante comercio oficial a nivel país, sitios de fábricas, registros, asociaciones, ferias y perfiles profesionales públicos. Entrega Excel por país, con empresa, prueba de relación con el producto, nivel de evidencia, contacto corporativo público y mensaje comercial en inglés. No conviertas las importaciones de un país en compras probadas de una empresa.

> Para importar MEG desde Arabia Saudita y EAU, verifica productores reales, instalaciones, capacidad nominal, estado publicado, agentes de venta y diferencia frente a DEG. Crea un Excel de coste puesto en fábrica con tipo de cambio, FOB/CFR/CIF, arancel, seguro y transporte editables, junto con correo RFQ en inglés.

## 5. Energía, futuros e investigación cuantitativa

ChemClaw admite investigación sobre metanol, GLP, petróleo, carbonato de sodio, PVC, glicoles y otros productos, combinando **precio spot, futuros, base, diferenciales entre vencimientos, inventarios, utilización, paradas de planta, costes y nuevas capacidades**. Incluye estacionalidad, correlaciones, pruebas lead–lag, estudios de eventos y backtesting de reglas explícitas.

| Análisis | Disciplina de datos | Entrega |
| --- | --- | --- |
| **Base spot–futuros** | Series separadas y verificadas; mismas fechas, unidad, calidad y contrato identificado | Dos curvas de precios y una curva de base, Excel de cálculo |
| **Diferenciales y fundamentales** | Vencimiento, cambio de contrato, región, inventarios, mantenimiento y proyectos | Gráficos, cronología y explicación con fuentes |
| **Relaciones estadísticas** | Fecha real de publicación, tamaño muestral, corrección por múltiples contrastes y estabilidad | Excel reproducible, curvas de desfases y mapa de calor |
| **Backtest de reglas** | Contratos listados realmente, costes, ejecución, cambio de mes y muestra fuera de período | Rendimiento histórico y sensibilidad, sin promesa de rentabilidad futura |

> Analiza la base entre el metanol físico de Taicang y los futuros MA de los últimos tres meses. Consulta el spot primero en Chemcloud Data Hub y contrástalo con fuentes químicas; obtiene los OHLC reales con `chem_futures_history` y revisa los contratos de CZCE. Alinea fechas y unidades, muestra dos series de precios y un gráfico separado de base en el chat. Entrega datos y fórmulas en Excel y una presentación de 4–6 diapositivas. Nunca sustituyas datos spot faltantes por futuros.

> Comprueba si el cambio de inventarios portuarios de metanol anticipa los retornos de MA en 1–8 semanas. Usa fechas reales de publicación, analiza todos los desfases, muestra n, p/q ajustados, estabilidad por año y una prueba fuera de muestra. Entrega Excel verificable y panel de gráficos. No confundas correlación con causalidad.

## 6. Gráficos dentro del chat

Con observaciones reales, la conversación puede mostrar **líneas spot, velas OHLC, comparación de precios, base, tarjetas de indicadores, dispersión, radar, mapas de calor, treemap, Sankey y cronologías**. Una vela exige apertura, máximo, mínimo y cierre verdaderos; no se inventan puntos para completar un gráfico.

## 7. Entregables

| Formato | Uso |
| --- | --- |
| **Excel** | Clientes potenciales, fabricantes, RFQ, precios, cálculos de base, inventario y pedidos |
| **PowerPoint** | Informes para dirección, estrategia comercial, análisis de mercado y gráficos |
| **Word** | Informes, borradores comerciales, revisión documental |
| **Web interactiva** | Proyectos filtrables, mapas, cronologías y paneles de precios |

## 8. Trabajar con archivos Office existentes

ChemClaw puede inspeccionar Word, PowerPoint y Excel existentes y realizar cambios compatibles: ediciones puntuales y comentarios en Word, organización de diapositivas, verificaciones de tablas y fórmulas. Revisar el resultado en la aplicación Office cuando existan diseños complejos o cálculos importantes.

## 9. Navegador y control humano

Cada Bot de escritorio puede abrir páginas, leer contenido, hacer clic, completar formularios y ofrecer una sesión específica. **Contraseñas, pagos y CAPTCHA permanecen bajo control del usuario**; publicaciones, cargas y borrados pueden requerir autorización. Los sitios extranjeros pueden necesitar acceso de red/proxy.

## 10. Agentes y grupos

Incluye **50 Bots y 15 grupos especializados** para ventas, compras, comercio exterior, mercados físicos, análisis de futuros, cuantitativo, documentos y verificación de evidencias. El coordinador reparte tareas y puedes llamar a un especialista con `@`.

## 11. Instalación y configuración

1. Descarga el paquete **v0.3.0** para Windows, macOS Intel/Apple Silicon o Linux desde [GitHub Releases](https://github.com/zoeyzhang233666/chemclaw-bot/releases).
2. Obtén tu clave del modelo en [APIHub](https://apihub.chem-cloud.cn/) y añádela a **Configuración → Modelos → APIHub**. Consulta en el sitio las condiciones actuales de precios, vigencia y cuotas de sus paquetes.
3. Obtén una **clave de datos independiente** en [Chemcloud Data Hub](https://mcp.chem-cloud.cn/) y añádela a **Configuración → Conectores**.
4. Abre el especialista o grupo correspondiente y describe tu tarea.

También existe un [plugin ChemClaw para DeepSeek Harness](https://github.com/zoeyzhang233666/chemclaw-bot/tree/main/chemclaw-bot).

## 12. Instrucciones prácticas para copiar

**Clientes nuevos:**

> Busca fábricas de vidrio del este de China que puedan necesitar carbonato de sodio denso por nuevas líneas de producción. Empieza por Data Hub, verifica EIA y sus tablas de materias primas, PDFs CNINFO y licitaciones. Entrega Excel por fábrica con fecha prevista, fase, evidencia de consumo, fuente, fiabilidad y próxima acción; muestra una cronología.

**Licitaciones vigentes:**

> Busca en los últimos 30 días licitaciones públicas de sosa cáustica industrial para alúmina, papel y tratamiento de agua. Comprueba las páginas oficiales y separa convocatorias abiertas de adjudicaciones. Registra concentración, toneladas, lugar de entrega, fecha límite y enlace, más una tabla Excel para contactar.

---

## Antes de utilizar

ChemClaw es una herramienta de **investigación y apoyo a decisiones**, no una plataforma autónoma de ejecución de operaciones ni un sistema de control de plantas. Comprueba contratos, calidad, importación/exportación y datos críticos con fuentes originales. Usa solo información autorizada. Licencia **Apache-2.0**, basado en **DS Bot** y **DeepSeek Harness**; consulta `NOTICE`.
