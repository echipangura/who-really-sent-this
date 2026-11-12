# ¿Quién envió esto de verdad? Guía de uso

**Sitio web:** https://who-really-sent-this.streamlit.app
**Costo:** gratis · **Idiomas:** español e inglés

> Borrador en revisión por hablantes nativos.

## ¿Qué es?

Los estafadores envían correos que fingen venir de su banco, su escuela, el
correo postal o el gobierno. Esta herramienta revisa las líneas ocultas de un
correo, llamadas **encabezados**, y le dice quién lo envió de verdad.

Úsela cuando un correo:

- le pide pagar, hacer clic en un enlace, iniciar sesión o llamar a un número;
- dice que su cuenta está bloqueada o que tiene un paquete esperando;
- parece real, pero algo no le da confianza.

## Cómo revisar un correo (4 pasos)

### Paso 1. Abra el sitio web

Vaya a **who-really-sent-this.streamlit.app** y haga clic en **Español**
arriba. Para letras más grandes, active **Letra grande** en el menú lateral.

### Paso 2. Copie los encabezados del correo

Abra el correo en su aplicación y luego:

| Aplicación | Qué hacer |
|---|---|
| **Gmail** | Tres puntos (⋮) junto a Responder → **Mostrar original** (*Show original*) → **Copiar al portapapeles** |
| **Outlook.com** | Tres puntos (…) → **Ver** → **Ver origen del mensaje** (*View message source*) → seleccione todo y cópielo |
| **Outlook en una computadora** | **Archivo** → **Propiedades** → copie el cuadro **Encabezados de Internet** (*Internet headers*) |
| **Yahoo Mail** | Tres puntos (…) → **Ver mensaje sin formato** (*View raw message*) → seleccione todo y cópielo |
| **Apple Mail (Mac)** | **Visualización** → **Mensaje** → **Fuente original** (*Raw Source*) → seleccione todo y cópielo |

Para seleccionar todo, presione **Ctrl + A** (Windows) o **Cmd + A** (Mac).
Para copiar, presione **Ctrl + C** o **Cmd + C**.

> 💡 Puede copiar el mensaje completo. La herramienta solo lee los encabezados.

### Paso 3. Pegue y revise

Haga clic en el cuadro grande, presione **Ctrl + V** (o **Cmd + V**) para
pegar y luego haga clic en **Revisar este correo**.

### Paso 4. Lea la respuesta

| Usted ve | Qué significa | Qué hacer |
|---|---|---|
| ✅ **Parece legítimo** | El correo vino de verdad de la dirección que muestra. | Probablemente está bien. Pero si le pide dinero o contraseñas, confírmelo por otro medio. |
| ⚠️ **Tenga cuidado** | Algo no está bien. | Todavía no haga lo que pide el correo. Confírmelo con quien lo envió por otro medio. |
| ⛔ **Probablemente es una estafa** | El correo no es de quien dice ser. | No haga clic, no responda y no pague. Repórtelo y bórrelo. |

Debajo de la respuesta, la página explica **por qué**, muestra **de quién es
de verdad** y le dice **qué hacer ahora**.

## Si es una estafa

1. **No** haga clic en los enlaces ni llame a los teléfonos del correo.
2. Vaya usted mismo al sitio web real. Escriba la dirección.
3. Nunca envíe contraseñas, códigos ni datos bancarios por correo.
4. ¿No está seguro? Llame a la empresa a un número que ya conoce, como el de
   su tarjeta o su factura.
5. Repórtelo:
   - en su aplicación de correo (Gmail: **Denunciar suplantación de
     identidad**; Outlook: **Notificar** → **Notificar suplantación de
     identidad**; Yahoo: **Spam**; Apple Mail: **Mover a correo no deseado**);
   - a la Comisión Federal de Comercio (FTC): **reportefraude.ftc.gov**;
   - la página de resultados también muestra dónde reportar correos falsos de
     bancos, escuelas, impuestos, inmigración y correo postal.

## Revisar varios correos a la vez

Útil para la oficina de una escuela, una biblioteca o una recepción.

1. Guarde cada correo como archivo:
   - **Gmail:** abra el correo → ⋮ → **Descargar mensaje** (*Download message*)
   - **Outlook en la web:** abra el correo → … → **Guardar como** o
     **Descargar** (*Save as* / *Download*)
   - **Apple Mail:** **Archivo** → **Guardar como** → **Fuente del mensaje sin
     procesar** (*Raw Message Source*)
2. En el sitio web, haga clic en la pestaña **Revisar varios correos**.
3. Agregue hasta 50 archivos y haga clic en **Revisar estos correos**.
4. Los correos más riesgosos aparecen primero. Haga clic en **Descargar este
   resumen (CSV)** para guardar una lista.

## Su privacidad

- Nada de lo que pegue se guarda ni se envía a ningún lugar. Cuando cierra la
  página, desaparece.
- La herramienta no abre enlaces ni archivos adjuntos, y no le sigue.
- Su propia dirección de correo está en los encabezados. Si prefiere, borre
  las líneas que empiezan con **To:** y **Delivered-To:** antes de pegar. La
  revisión sigue funcionando.
- **Nunca** pegue una contraseña ni un código. La herramienta nunca los
  necesita.

## Lo que esta herramienta no puede decirle

✅ **Parece legítimo** significa que el dueño de la dirección envió el correo.
**No** significa que el correo sea seguro:

- si una cuenta real fue hackeada, sus correos también pasan las pruebas;
- un estafador que usa una cuenta común de Gmail también pasa.

Por eso, si cualquier correo le pide dinero, contraseñas o códigos, confírmelo
con la persona o la empresa por otro medio, aunque parezca legítimo.

## Preguntas y comentarios

¿Encontró un problema o tiene una idea? Visite
https://github.com/echipangura/who-really-sent-this (en inglés) o pregunte a la
organización que le compartió esta herramienta.
