# Digest de diarios argentinos

Junta 50 notas de los 10 diarios más leídos del país, las manda por Telegram a
las 14 y a las 21 de lunes a viernes, y publica además una página con el listado.

Página: <https://lucianocolin.github.io/diarios-bot/>

## Lo primero que hay que saber: qué es "más leídas" acá

De los 10 diarios, **solo 3 publican su ranking real de lecturas**:

| Ranking real (lo que el diario mide) | Orden de portada (proxy) |
| --- | --- |
| La Nación, Perfil, Ámbito | Infobae, Clarín, TN, Página/12, La Voz, El Cronista, C5N |

Los otros siete no exponen sus métricas de audiencia por ningún lado: ni RSS, ni
API pública, ni un módulo en el HTML (se verificó también renderizando la home
con un navegador headless, por si lo cargaban por JavaScript). Para esos, el bot
usa **la jerarquía que el propio diario le da a cada nota en la portada**, que es
la mejor señal editorial disponible sin acceso a sus analytics.

Cada nota viaja etiquetada con su origen (`real` o `portada`), y la página lo
muestra con un cartelito por diario, así nadie confunde una cosa con la otra.

Tampoco existe un ranking cruzado entre diarios: nadie publica números absolutos
de lecturas, así que no hay forma honesta de decir que la nota #1 de Clarín fue
más leída que la #1 de Infobae. Por eso el digest son **5 notas por diario,
agrupadas por medio**, y no una lista única del 1 al 50.

## Probarlo ahora mismo

```bash
pip install -r requirements.txt
python -m bot.main --dry-run
```

Deja `out/index.html` (la página), `out/digest.txt` y `out/digest.json`. No envía
nada. Abrí el HTML en el navegador para ver cómo le va a llegar.

## Por qué Telegram y no WhatsApp

Se intentó primero con WhatsApp y no da: un envío programado a las 14 cae fuera
de la ventana de 24 h desde el último mensaje de la persona, así que tiene que
salir como plantilla aprobada por Meta, y **una plantilla topea en 1024
caracteres**. El digest ronda los 12.400: entran unas 4 notas de 50. Encima los
valores de las variables no admiten saltos de línea, así que saldrían todas
pegadas en un renglón. Acortar los links no alcanza — aun con links de 20
caracteres serían unos 6.000.

Telegram no tiene plantillas, ni aprobación, ni ventana de 24 h, y permite 4096
caracteres por mensaje. El digest entero sale en 4 mensajes con los títulos y los
links adentro, que es lo que se quería.

El código de WhatsApp quedó en `bot/whatsapp.py` y se puede usar con
`--canal whatsapp`, pero con las limitaciones de arriba.

## Configurar Telegram

### 1. Crear el bot

1. Escribirle a [@BotFather](https://t.me/BotFather) en Telegram: `/newbot`,
   nombre y username (tiene que terminar en `bot`).
2. Anota el **token** que te devuelve, con forma `123456789:AAE...`.

### 2. Averiguar el chat_id

La persona que va a recibir el digest tiene que **darle `/start` al bot una vez**
(si no, Telegram no deja escribirle). Después:

```bash
TELEGRAM_TOKEN=<el token> python -c "
from bot import telegram
for c in telegram.chats_recientes():
    print(c['id'], c.get('first_name') or c.get('title'))"
```

Ese número es el `chat_id`. Es estable, se saca una sola vez.

### 3. Secrets del repo

En *Settings → Secrets and variables → Actions*:

| Secret | Qué es |
| --- | --- |
| `TELEGRAM_TOKEN` | El token de BotFather |
| `TELEGRAM_CHAT_ID` | El chat_id del paso 2. Admite varios separados por coma |

Con varios destinatarios, si uno bloqueó al bot los demás igual reciben el
digest; la corrida termina en error para que se note en el historial.

### 4. Activar GitHub Pages

*Settings → Pages → Source: **GitHub Actions***. La página se republica en cada
corrida. Es opcional: el digest llega completo por Telegram igual.

## Configurar WhatsApp (alternativa limitada)

Solo llegan ~4 notas por mensaje, por el tope de 1024 caracteres. Se corre con
`--canal whatsapp`.

### 1. Alta en Meta

1. Crear la app desde el panel: **Mis apps** →
   [Crear aplicación](https://developers.facebook.com/apps) → nombre y email →
   caso de uso **"Conectar con clientes mediante WhatsApp"** → elegir o crear un
   **portafolio comercial** → Crear aplicación.

   > No entrar por *Crea con nosotros → Plataforma de WhatsApp Business*: esa es
   > la página de producto, no el flujo de creación. Y si algún tutorial dice
   > "elegí tipo de app *Empresa*", está desactualizado: Meta lo reemplazó por la
   > selección de caso de uso.

2. Pasar el mouse por **Casos de uso** en el menú izquierdo → **ícono de lápiz** →
   botón **Personalizar** del caso de uso de WhatsApp → **Configuración de la
   API**. Ahí está el **Phone number ID**, debajo del desplegable del número.

   > Meta movió esto: antes estaba en *Guía de inicio rápido*. Si la app se creó
   > con otro caso de uso, el lápiz no ofrece WhatsApp; en ese caso hay que ir al
   > Panel → *Agregar productos* → **WhatsApp** → Configurar.
3. Generar un **token permanente**: Business Settings → Users → System Users →
   crear un system user admin → Add Assets → Generate Token con permisos
   `whatsapp_business_messaging` y `whatsapp_business_management`. El token de
   prueba de 24 h no sirve para algo programado.

   > En *Add Assets* hay que asignarle **la cuenta de WhatsApp Business (WABA),
   > no solo la app**, con control total. Si no, el token se genera igual pero
   > los envíos vuelven con `403 / object does not exist`.
4. El número de ella tiene que estar en *Recipients* mientras la app esté en modo
   desarrollo.

### 2. Crear la plantilla

En *WhatsApp Manager → Message Templates → Create*:

- **Nombre**: `resumen_diarios`
- **Categoría**: Utility (se aprueba más rápido que Marketing)
- **Idioma**: Español (AR) → código `es_AR`
- **Body** (con variables **numeradas**, no con nombre: el código manda
  parámetros posicionales y con variables nombradas falla con error 132000):

  ```
  Hola! Listo el resumen de la {{1}}: {{2}} notas de {{3}} diarios argentinos.
  ```

  Meta pide valores de ejemplo para revisar la plantilla. Son solo para eso, no
  se mandan: `{{1}}` → `mediodía`, `{{2}}` → `50`, `{{3}}` → `10`.

- **Botón**: tipo *Visit website* → **Static** → la URL de la página. Static y no
  Dynamic: una URL dinámica exige mandar el parámetro del botón en cada envío, y
  `PAGINA_SUFIJO` no está definida, así que el envío fallaría con "number of
  parameters does not match". La página vive siempre en la misma dirección.

La aprobación suele tardar entre minutos y unas horas.

### 3. Secrets

| Secret | Qué es |
| --- | --- |
| `WHATSAPP_TOKEN` | El token permanente del system user |
| `WHATSAPP_PHONE_NUMBER_ID` | El Phone number ID del paso 1 |
| `WHATSAPP_DESTINO` | El número con código de país y sin `+`. Argentina lleva el `9` de celular: `5493815165415`, no `543815165415` |

Y como *Variables* (opcionales, tienen default):

| Variable | Default |
| --- | --- |
| `WHATSAPP_PLANTILLA` | `resumen_diarios` |
| `WHATSAPP_IDIOMA` | `es_AR` |

## Los horarios

Argentina es UTC-3 todo el año, así que los cron del workflow son:

- `0 17 * * *` → 14:00 ART, todos los días.
- `0 0 * * *` → 21:00 ART, todos los días. En UTC cae a las 00:00 del día
  siguiente, pero al correr los 7 días el corrimiento no cambia nada.

El scheduler de GitHub Actions no es puntual: suele disparar con 5 a 15 minutos
de demora, y más si la plataforma está cargada. Si necesitás precisión al
minuto, conviene un VPS con cron.

## Por qué hay un workflow de keepalive

GitHub **deshabilita los workflows programados de un repo público cuando pasan
60 días sin commits nuevos**, y avisa solo por mail. Las corridas del propio
cron, los deploys de Pages y los issues no cuentan como actividad: solo cuentan
los commits. Como este bot no commitea nada (publica la página desde un
artefacto), sin esto el digest se apagaría solo a los dos meses.

`.github/workflows/keepalive.yml` pushea un commit vacío el día 1 de cada mes y
resetea ese contador. No toca ningún archivo.

## WhatsApp en modo texto completo

Si ella le escribe al bot, se abre la ventana de 24 h y ahí sí se puede mandar el
digest entero por WhatsApp, sin plantilla ni aprobación:

```bash
python -m bot.main --canal whatsapp --modo libre
```

Son 4 mensajes. No sirve como mecanismo permanente: si ella no escribe, falla.
Es justamente el problema que resuelve Telegram.

## Cuando un diario cambie el HTML

Los extractores están en `bot/sources.py`, uno por diario. Si un medio rediseña
la portada, ese extractor tira `SinResultados`, el bot lo registra en `fallidos`
y **completa las 50 notas pidiéndole más a los otros diarios**, así el envío no
se cae por un solo medio. La página muestra abajo cuáles quedaron sin datos.

Para probar uno solo:

```bash
python -c "from bot import sources; [print(a.titulo) for a in sources.clarin(5)]"
```

## Nota legal

El bot lee portadas públicas y manda titular + link, que es lo que hace cualquier
lector de RSS. No copia el cuerpo de las notas ni saltea paywalls. Si la idea
después es republicar esto en algún lado, ahí sí conviene revisar los términos de
cada medio.
