cat > docs/manuales/manual_usuario.md << 'EOF'
# Manual de Usuario – Sistema de Gestión de Cobranzas Inteligente  
**Versión 1.0 – Cumplir S.A.S.**

---

## Contenido

1. [Introducción](#1-introducción)  
2. [Acceso al Sistema](#2-acceso-al-sistema)  
3. [Pantalla Principal (Dashboard)](#3-pantalla-principal-dashboard)  
4. [Búsqueda de Clientes](#4-búsqueda-de-clientes)  
5. [Registro de Gestión (Bitácora Rápida)](#5-registro-de-gestión-bitácora-rápida)  
6. [Negociación y Cierre de Acuerdos de Pago](#6-negociación-y-cierre-de-acuerdos-de-pago)  
7. [Registro de Pagos](#7-registro-de-pagos)  
8. [Módulo de Investigación (Gestión Detallada)](#8-módulo-de-investigación-gestión-detallada)  
9. [Directorio de Teléfonos](#9-directorio-de-teléfonos)  
10. [Gestión de Acuerdos (Historial y PDF)](#10-gestión-de-acuerdos-historial-y-pdf)  
11. [Reportes y Estadísticas](#11-reportes-y-estadísticas)  
12. [Perfil del Asesor](#12-perfil-del-asesor)  
13. [Alertas Programadas](#13-alertas-programadas)  
14. [Cierre de Sesión](#14-cierre-de-sesión)  
15. [Solución de Problemas Comunes](#15-solución-de-problemas-comunes)  

---

## 1. Introducción

El **Sistema de Gestión de Cobranzas Inteligente** es una plataforma web diseñada para optimizar el recaudo de cartera, automatizar la generación de acuerdos de pago, mantener un historial detallado de gestiones y pagos, y proporcionar reportes en tiempo real. Este manual explica todas las funcionalidades disponibles para **asesores** y **administradores**.

---

## 2. Acceso al Sistema

1. Abra su navegador web (Chrome, Firefox, Edge) y escriba la dirección del servidor:  
   `http://127.0.0.1:8000` (o la IP proporcionada por el administrador).
2. Será redirigido automáticamente a la pantalla de **Inicio de Sesión**.
3. Ingrese sus credenciales:
   - **Usuario**: su nombre de usuario (ej. `angie.cuellar`).
   - **Contraseña**: la clave asignada.
4. Haga clic en **Ingresar**.
5. Si las credenciales son correctas, accederá al **Dashboard** principal.

> **Consejo:** Si olvida su contraseña, solicite al administrador que la restablezca.

---

## 3. Pantalla Principal (Dashboard)

El Dashboard muestra indicadores clave de rendimiento (KPIs):

- **Alertas Hoy**: número de compromisos de pago programados para el día actual. Al hacer clic en el botón "Alertas Hoy" se abre un modal con la lista detallada.
- **Acuerdos Cerrados**: total de dinero recuperado mediante acuerdos y cantidad de contratos generados.
- **Recuperación Global**: porcentaje de cumplimiento de la meta de recaudo sobre el total de la cartera asignada.
- **Gráfico de IA (Sentimiento)**: muestra la proporción de clientes con actitud positiva, negativa o neutra según el análisis de llamadas.

> **Nota:** Los datos se actualizan automáticamente cada vez que se registra una gestión o acuerdo.

---

## 4. Búsqueda de Clientes

Para consultar la información de un deudor:

1. En el campo de búsqueda (parte superior) escriba:
   - **Número de cédula** (ej. `1061707614`),
   - **Nombre completo** (ej. `FIGUEROA MORA`), o
   - **Número de obligación** (ej. `1904813-1061707614`).
2. Haga clic en el botón **Buscar**.
3. Los datos del cliente se desplegarán en la parte inferior, incluyendo:
   - **Datos financieros**: saldo total, días de mora, decil de contactabilidad.
   - **Historial de gestiones**: todas las interacciones registradas (bitácora).
   - **Acuerdos previos** (en la pestaña correspondiente).

---

## 5. Registro de Gestión (Bitácora Rápida)

Después de buscar un cliente, aparecerá la tarjeta **Registrar Gestión**. Para anotar una interacción:

1. **Observación**: escriba un resumen de la llamada o conversación.
2. **Canal**: seleccione `Llamada` o `WhatsApp`.
3. **Estado de la promesa**: elija una opción:
   - `Promesa de pago`
   - `Titular no contesta`
   - `Negativa de pago`
4. **Programar alerta (opcional)**: si seleccionó `Promesa de pago`, puede activar la alerta:
   - Se habilitarán los campos de fecha y hora.
   - Seleccione la **fecha** y **hora** en que desea recordar el compromiso.
5. Haga clic en **Guardar Gestión**.
6. La gestión se agregará automáticamente al **historial** (pestaña "Bitácora de Gestiones") y, si se programó alerta, se registrará en el módulo de Alertas.

> **Importante:** Las alertas se muestran en el Dashboard (botón "Alertas Hoy") y en la página independiente de Alertas.

---

## 6. Negociación y Cierre de Acuerdos de Pago

Una vez identificado el cliente, en la pestaña **Negociación Acuerdo**:

1. **Monto a Negociar**: ingrese el valor acordado.
2. **Número de Cuotas**: seleccione entre 1 y 12 cuotas.
3. **Fecha Primer Pago**: elija la fecha en que se debe realizar el primer pago.
4. **Observación del Acuerdo**: escriba un comentario (compromiso verbal, condiciones, etc.).
5. Haga clic en **CERRAR ACUERDO**.
6. El sistema:
   - Guarda el acuerdo en la base de datos.
   - Registra automáticamente un pago asociado al acuerdo (tipo `ACUERDO`).
   - Genera un **PDF legal** con los detalles del acuerdo y el nombre del asesor.
7. Se abrirá un cuadro de diálogo preguntando si desea **descargar el PDF**. Confirme para guardar el documento.

> **Consejo:** El PDF generado tiene validez paramétrica y puede ser entregado al cliente como constancia.

---

## 7. Registro de Pagos

Puede registrar pagos manualmente (cuando el cliente paga en un corresponsal bancario y usted recibe la notificación). En la sección **Registrar Pago** (debajo de las tarjetas):

1. **Cédula del cliente**: ingrese el número de documento.
2. **Monto**: valor pagado.
3. **Fecha pago**: seleccione la fecha en que se realizó el pago.
4. **Tipo**:
   - `ABONO`: pago parcial sin acuerdo formal.
   - `CUOTA`: pago correspondiente a una cuota de un acuerdo existente.
   - `ACUERDO`: pago completo de un acuerdo (también se genera automáticamente al cerrar acuerdo).
5. **Referencia** (opcional): número de transacción o comprobante.
6. **Observación** (opcional): notas adicionales.
7. Haga clic en **Registrar Pago**.
8. El pago se almacenará en el historial del cliente y en el perfil del asesor.

---

## 8. Módulo de Investigación (Gestión Detallada)

Acceda desde el menú lateral **INVESTIGACIÓN**. Este módulo permite registrar información más completa y mantener un historial de bitácoras por cliente.

### 8.1. Sincronización de cliente
- Ingrese la cédula en el campo superior y haga clic en **SINCRONIZAR**.
- Se cargarán los datos del último registro de investigación (si existe) y el historial completo de bitácoras.

### 8.2. Campos de investigación
- **Entidad Salud (EPS)**
- **Consulta de Bienes**
- **Registro RUES**
- **Observaciones de Gestión Cognitiva**
- **Teléfono de Contacto Efectivo**
- **Estado del Cliente** (Activo/Inactivo)
- **ESTADO de GESTIÓN** (Acuerdo, ilocalizado, jurídico, renuente, paz y salvo, localizado)
- **SUBESTADO** (se carga dinámicamente según el estado seleccionado)

### 8.3. Guardar investigación
- Complete los campos necesarios.
- Haga clic en **REGISTRAR GESTIÓN EN SISTEMA**.
- Se creará un **nuevo registro** en la bitácora (no sobrescribe el anterior).
- La lista de bitácoras se actualizará automáticamente, mostrando todas las interacciones previas con su fecha y estado.

---

## 9. Directorio de Teléfonos

En el menú **DIRECTORIO**:

- **Agregar teléfono**:
  1. Ingrese el número.
  2. Seleccione **Estado** (Activo/Inactivo).
  3. Seleccione **Descripción** (TITULAR, CODEUDOR, REFERENCIA).
  4. Haga clic en **+ AGREGAR**.
- **Historial de teléfonos**: se muestra una tabla con ID, número, estado, descripción y fecha de registro. Los registros son acumulativos.

> **Nota:** Los teléfonos se asocian al cliente actualmente sincronizado (campo de cédula en la cabecera).

---

## 10. Gestión de Acuerdos (Historial y PDF)

Desde el menú **ACUERDOS**:

- **Nuevo acuerdo**:
  - ROL (TITULAR/CODEUDOR)
  - NOMBRE (persona que asume el compromiso)
  - VALOR ACORDADO
  - TOTAL CUOTAS
  - FECHA PRIMER PAGO
  - OBSERVACIONES
  - Haga clic en **GRABAR ACUERDO LEGAL**.
- **Historial de acuerdos**: se listan todos los acuerdos registrados para el cliente sincronizado, con fecha, monto, cuotas y estado.

> **Nota:** Al igual que en la pantalla principal, aquí también se genera el PDF automáticamente.

---

## 11. Reportes y Estadísticas

### 11.1. Reporte de Cartera
- **Ubicación**: menú **REPORTE CARTERA**.
- **Filtros disponibles**:
  - Estado (ACTIVA, EN_ACUERDO, PAGADA, CASTIGADA)
  - Días de mora (mínimo y máximo)
  - Fechas de campaña (desde – hasta)
- **Búsqueda por texto**: por cédula o nombre.
- Los resultados se actualizan en la tabla en tiempo real.

### 11.2. Acuerdos Mensuales
- Página independiente accesible desde el menú desplegable superior (botón "Menú" → "Acuerdos Mensuales").
- **Selector de mes**: elija un año y mes.
- **Filtros adicionales**: número de operación y cédula.
- La tabla muestra: número de operación, cliente, nombre, fecha de acuerdo, valor, cuotas y asesor.

### 11.3. Reporte Mensual de Gestión
- Página independiente: "Menú" → "Reporte Mensual".
- **Generar reporte**: seleccione un mes y haga clic en "Generar y Guardar".
- **Ver reporte guardado**: elija un mes de la lista desplegable.
- El reporte muestra:
  - Totales globales: gestiones, acuerdos, pagos.
  - Ranking de asesores: por cantidad de gestiones, acuerdos y monto negociado.

---

## 12. Perfil del Asesor

1. Haga clic en **Mi Perfil** (visible en la barra superior después de iniciar sesión).
2. Se mostrarán sus datos personales:
   - Nombre, usuario, rol, email, teléfono.
3. **Editar perfil**: modifique su email y teléfono, luego haga clic en "Actualizar".
4. **Actividad de Hoy** (tres pestañas):
   - Gestiones realizadas hoy.
   - Acuerdos creados hoy.
   - Historial de pagos registrados por usted.
5. Para **cerrar sesión**, use el botón "Cerrar Sesión" dentro de esta página.

---

## 13. Alertas Programadas

- **Acceso**: botón "Alertas" en la barra superior (ícono de campana) o desde el Dashboard.
- La página de Alertas muestra una tabla con:
  - Número de operación
  - Asesor responsable
  - Fecha y hora programada
  - Mensaje de la alerta
- **Filtros**: por asesor y rango de fechas.
- Las alertas se generan automáticamente cuando un asesor programa una alerta al registrar una gestión.

> **Recomendación:** Revise sus alertas al inicio de cada jornada para no olvidar compromisos.

---

## 14. Cierre de Sesión

- Para cerrar su sesión, diríjase a **Mi Perfil** y haga clic en el botón **Cerrar Sesión**.
- Será redirigido a la pantalla de inicio de sesión.
- **No** cierre el navegador sin cerrar sesión si está en un equipo compartido.

---

## 15. Solución de Problemas Comunes

| Problema | Posible causa | Solución |
|----------|---------------|----------|
| No puedo iniciar sesión | Usuario o contraseña incorrectos | Verifique sus credenciales. Si las olvidó, contacte al administrador. |
| La página no carga | El servidor no está corriendo | Asegúrese de que los contenedores Docker estén activos (consulte al administrador). |
| El historial de gestiones no se actualiza | Error de conexión o caché del navegador | Refresque la página con Ctrl+F5. Si persiste, revise la consola de desarrollador (F12) para ver errores. |
| No se genera el PDF | ReportLab no instalado o error en los datos | Verifique que el acuerdo tenga todos los campos obligatorios. Si el error continúa, contacte al soporte técnico. |
| Las alertas no aparecen | No se programó fecha/hora al guardar gestión | Asegúrese de llenar ambos campos (fecha y hora) antes de guardar. |
| El reporte mensual no muestra datos | No hay acuerdos/gestiones en el mes seleccionado | Pruebe con otro mes o genere un nuevo reporte. |

---

## Anexos

- **Glosario de términos**: Decil, SPEI, ACID, JWT.
- **Soporte técnico**: Para incidencias no resueltas, enviar correo a `soporte@cumplirsas.com` (ejemplo).

---


EOF
