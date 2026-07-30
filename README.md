# Digest de diarios argentinos

Junta 50 notas de los 10 diarios más leídos del país, publica una página con el
listado y avisa por WhatsApp a las 14 y a las 21, de lunes a viernes.

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

## Configurar WhatsApp

WhatsApp no deja mandar mensajes libres a alguien que no te escribió en las
últimas 24 h. Un envío programado a las 14 y a las 21 cae siempre fuera de esa
ventana, así que **necesita una plantilla aprobada por Meta**. Y como los
parámetros de plantilla no admiten saltos de línea, las 50 notas no entran en el
mensaje: por eso el bot publica la página y la plantilla lleva un botón que la
abre.

### 1. Alta en Meta

1. Crear la app desde el panel: **Mis apps** →
   [Crear aplicación](https://developers.facebook.com/apps) → nombre y email →
   caso de uso **"Conectar con clientes mediante WhatsApp"** → elegir o crear un
   **portafolio comercial** → Crear aplicación.

   > No entrar por *Crea con nosotros → Plataforma de WhatsApp Business*: esa es
   > la página de producto, no el flujo de creación. Y si algún tutorial dice
   > "elegí tipo de app *Empresa*", está desactualizado: Meta lo reemplazó por la
   > selección de caso de uso.

2. En *Personalizar caso de uso → Conectar en WhatsApp → Guía de inicio rápido*,
   anotar el **Phone number ID**.
3. Generar un **token permanente**: Business Settings → Users → System Users →
   crear un system user admin → Add Assets (la app de WhatsApp) → Generate Token
   con permisos `whatsapp_business_messaging` y `whatsapp_business_management`.
   El token de prueba de 24 h no sirve para algo programado.
4. El número de ella tiene que estar en *Recipients* mientras la app esté en modo
   desarrollo.

### 2. Crear la plantilla

En *WhatsApp Manager → Message Templates → Create*:

- **Nombre**: `resumen_diarios`
- **Categoría**: Utility (se aprueba más rápido que Marketing)
- **Idioma**: Español (AR) → código `es_AR`
- **Body**:

  ```
  Hola! Listo el resumen de la {{1}}: {{2}} notas de {{3}} diarios argentinos.
  ```

- **Botón**: tipo *Visit website* → **Dynamic** → URL base la de tu GitHub Pages
  (`https://<usuario>.github.io/<repo>/`), texto del botón "Ver las notas".

La aprobación suele tardar entre minutos y unas horas.

### 3. Secrets del repo

En *Settings → Secrets and variables → Actions*:

| Secret | Qué es |
| --- | --- |
| `WHATSAPP_TOKEN` | El token permanente del system user |
| `WHATSAPP_PHONE_NUMBER_ID` | El Phone number ID del paso 1 |
| `WHATSAPP_DESTINO` | El número de ella con código de país y sin `+` (ej. `5491155551234`) |

Y como *Variables* (opcionales, tienen default):

| Variable | Default |
| --- | --- |
| `WHATSAPP_PLANTILLA` | `resumen_diarios` |
| `WHATSAPP_IDIOMA` | `es_AR` |

### 4. Activar GitHub Pages

*Settings → Pages → Source: **GitHub Actions***. La página se republica en cada
corrida con el contenido nuevo.

## Los horarios

Argentina es UTC-3 todo el año, así que los cron del workflow son:

- `0 17 * * 1-5` → 14:00 ART, lunes a viernes.
- `0 0 * * 2-6` → 21:00 ART, lunes a viernes. Va de martes a sábado **en UTC**
  porque las 21 de un lunes argentino son las 00:00 del martes UTC.

El scheduler de GitHub Actions no es puntual: suele disparar con 5 a 15 minutos
de demora, y más si la plataforma está cargada. Si necesitás precisión al
minuto, conviene un VPS con cron.

## Modo texto completo (sin plantilla)

Si ella le escribe al bot, se abre la ventana de 24 h y ahí sí se puede mandar el
digest entero como mensajes normales, sin aprobación de Meta:

```bash
MODO_ENVIO=libre python -m bot.main --modo libre
```

Son 3 o 4 mensajes (el digest ronda los 12.000 caracteres y WhatsApp corta en
4.096). Sirve para probar todo antes de que Meta apruebe la plantilla, pero no
como mecanismo permanente: si ella no escribe, el envío falla.

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
