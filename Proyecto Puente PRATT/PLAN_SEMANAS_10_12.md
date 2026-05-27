# Plan Detallado: Semanas 10-12 del Proyecto Puente PRATT

**Fecha de actualización:** 27 de Mayo, 2026  
**Estado actual:** Semana 9 completada ✅ — Física correcta, amplificación visual funcional

---

## Resumen Ejecutivo: Qué se ha hecho y qué falta

### ✅ Completado (Semana 9)
1. **Motor Físico Corregido**
   - E = 200 GPa (acero real) ✓
   - k calculado correctamente: k = (E × 1e9) × A / L₀ ✓
   - Esfuerzos en MPa (escala de ingeniería) ✓
   - Deformaciones realistas (milímetros, no centímetros) ✓
   - SUBSTEPS = 120, amortiguamiento = 26,800 Ns/m ✓

2. **Amplificación Visual Desacoplada**
   - Física NO afectada por factor visual ✓
   - Rendering multiplica desplazamientos por AMPLIFICACION_VISUAL (1000×) ✓
   - Deformaciones imperceptibles se ven claramente ✓
   - Compatible con ANSYS/SolidWorks standard ✓

3. **Validación Completa**
   - VALIDACION_FIX_COMPLETO.py ✓
   - FIX_ESCALA_MODULO_ELASTICO.md ✓
   - RESUMEN_FINAL_FIX_COMPLETO.md ✓

### ❌ Pendiente (Semanas 10-12)

| Semana | Componente | Estado | Deliverable |
|--------|-----------|--------|-------------|
| 10 | Visualización de Ruptura (Graying) | No iniciado | Miembros cambian color según esfuerzo |
| 10 | Sistema de Colores por Esfuerzo | No iniciado | Color rojo → ruptura inminente |
| 11 | Dinámicas de Fallo | No iniciado | Ruptura de miembros con cascada |
| 11 | Post-fallo Físico | No iniciado | Redistribución de carga post-ruptura |
| 12 | HUD Informativo | No iniciado | Panel con esfuerzos, márgenes, estado |
| 12 | Telemetría Avanzada | No iniciado | Datos en tiempo real de estructura |

---

## Semana 10: Visualización de Ruptura con Graying

### Objetivo
Mostrar el estado de stress en cada miembro usando un sistema de colores que indique:
- **Verde:** Esfuerzo bajo (< 25% del límite)
- **Amarillo:** Esfuerzo medio (25-50%)
- **Naranja:** Esfuerzo alto (50-75%)
- **Rojo oscuro:** Esfuerzo crítico (75-100%)
- **Gris (grayed out):** Miembro roto (σ ≥ límite)

### Implementación Requerida

#### 1. Función de Cálculo de Color en `Miembro` class
```python
def obtener_color_por_esfuerzo(self):
    """
    Retorna (r, g, b) basado en porcentaje de esfuerzo hasta ruptura
    
    Lógica:
    - Si miembro está roto: retornar gris (0.5, 0.5, 0.5)
    - Si no: calcular ratio = esfuerzo_actual / esfuerzo_limite
    - Interpolar color verde → amarillo → naranja → rojo según ratio
    """
    
    # Determinar esfuerzo límite (tensión o compresión según signo)
    if self.esfuerzo_actual >= 0:
        limite = self.esfuerzo_limite_tension
    else:
        limite = abs(self.esfuerzo_limite_compresion)
    
    # Si roto, devolver gris
    if abs(self.esfuerzo_actual) >= abs(limite):
        return (0.5, 0.5, 0.5)  # Gris
    
    # Calcular ratio: 0 = sin esfuerzo, 1 = ruptura
    ratio = abs(self.esfuerzo_actual) / abs(limite)
    
    # Interpolación de colores
    if ratio < 0.25:
        # Verde → Amarillo
        t = ratio / 0.25
        r = t
        g = 1.0
        b = 0.0
    elif ratio < 0.50:
        # Amarillo → Naranja
        t = (ratio - 0.25) / 0.25
        r = 1.0
        g = 1.0 - (t * 0.5)  # Reduce verde
        b = 0.0
    elif ratio < 0.75:
        # Naranja → Rojo oscuro
        t = (ratio - 0.50) / 0.25
        r = 1.0
        g = 0.5 - (t * 0.5)
        b = 0.0
    else:
        # Rojo oscuro (casi ruptura)
        r = 1.0
        g = 0.0
        b = 0.0
    
    return (r, g, b)
```

#### 2. Integración en `MotorGrafico.dibujar_miembros()`
```python
def dibujar_miembros(self):
    """Dibuja miembros con color según esfuerzo"""
    
    for miembro in self.puente.miembros:
        # Posiciones amplificadas (como ya está)
        x1, y1 = self._pos_amp(miembro.origen)
        x2, y2 = self._pos_amp(miembro.destino)
        
        # NUEVO: Obtener color basado en esfuerzo
        r, g, b = miembro.obtener_color_por_esfuerzo()
        
        # Dibujar con color dinámico
        glBegin(GL_LINES)
        glColor3f(r, g, b)
        glVertex3f(x1, y1, 0.0)
        glVertex3f(x2, y2, 0.0)
        glEnd()
        
        # Dibujar puntos en extremos para mejor visibilidad
        glPointSize(6.0)
        glBegin(GL_POINTS)
        glColor3f(r, g, b)
        glVertex3f(x1, y1, 0.0)
        glVertex3f(x2, y2, 0.0)
        glEnd()
```

#### 3. Telemetría de Esfuerzos
```python
def imprimir_telemetria_esfuerzos(self):
    """Imprime estado de esfuerzos en tiempo real"""
    
    print("\n" + "="*70)
    print("TELEMETRÍA DE ESFUERZOS (tiempo real)")
    print("="*70)
    
    esfuerzo_max = 0
    miembro_critico = None
    miembros_rotos = 0
    
    for i, m in enumerate(self.puente.miembros):
        ratio = abs(m.esfuerzo_actual) / abs(
            m.esfuerzo_limite_tension if m.esfuerzo_actual >= 0 
            else m.esfuerzo_limite_compresion
        )
        
        if ratio > esfuerzo_max:
            esfuerzo_max = ratio
            miembro_critico = i
        
        if ratio >= 1.0:
            miembros_rotos += 1
    
    print(f"Esfuerzo máximo: {esfuerzo_max*100:.1f}% del límite")
    if miembro_critico is not None:
        m = self.puente.miembros[miembro_critico]
        print(f"Miembro crítico: #{miembro_critico}")
        print(f"  Esfuerzo: {m.esfuerzo_actual:.2f} MPa")
        print(f"  Margen: {(1-esfuerzo_max)*100:.1f}%")
    
    if miembros_rotos > 0:
        print(f"⚠️  MIEMBROS ROTOS: {miembros_rotos}")
    else:
        print(f"✓ Estructura íntegra")
    
    print("="*70)
```

### Validación Semana 10
- [ ] Puente en reposo: todos los colores verde
- [ ] Con peso propio: colores verde a amarillo (< 50% esfuerzo)
- [ ] Con carga de 2000 kg: colores amarillo a naranja (< 75% esfuerzo)
- [ ] Con sobrecarga: colores rojo oscuro (cercano a ruptura)
- [ ] Miembros rotos muestran gris
- [ ] Telemetría imprime correctamente

---

## Semana 11: Dinámicas de Fallo Estructural

### Objetivo
Cuando un miembro se rompe, la estructura debe:
1. Marcar el miembro como "roto" (no aplica fuerzas, se vuelve gris)
2. Redistribuir carga a miembros adyacentes
3. Calcular cascada de fallos si la redistribución sobrecarga otros miembros
4. Mostrar comportamiento post-fallo físicamente correcto

### Implementación Requerida

#### 1. Sistema de Ruptura en `Miembro`
```python
class Miembro:
    def __init__(self, ...):
        ...
        self.roto = False
        self.tiempo_ruptura = None
    
    def revisar_ruptura(self):
        """Verifica si el miembro debe romperse"""
        
        if self.roto:
            return False  # Ya roto
        
        # Determinar esfuerzo límite según signo
        if self.esfuerzo_actual >= 0:
            limite = self.esfuerzo_limite_tension
        else:
            limite = abs(self.esfuerzo_limite_compresion)
        
        # Si esfuerzo supera límite
        if abs(self.esfuerzo_actual) >= abs(limite):
            self.roto = True
            self.tiempo_ruptura = tiempo_simulacion
            return True
        
        return False
    
    def aplicar_fuerza_hooke(self):
        """Aplica fuerza de Hooke SOLO si no está roto"""
        
        if self.roto:
            # Miembro roto no transmite fuerzas
            return
        
        # ... resto del código igual
```

#### 2. Cascada de Fallos en `paso_fisico()`
```python
def paso_fisico(self, dt, carga_movil=None, aplicar_gravedad=True):
    """Verifica ruptura y aplica cascada de fallos"""
    
    # ... fuerzas normales ...
    
    # NUEVO: Verificar ruptura de cada miembro
    for m in self.miembros:
        if m.revisar_ruptura():
            print(f"🔴 RUPTURA: Miembro #{self.miembros.index(m)} se rompió")
            print(f"   Esfuerzo: {m.esfuerzo_actual:.2f} MPa")
    
    # Revisar si hay cascada de fallos
    miembros_recien_rotos = [m for m in self.miembros if m.roto]
    if miembros_recien_rotos:
        self.evaluar_cascada_fallos()
```

#### 3. Evaluación de Cascada
```python
def evaluar_cascada_fallos(self):
    """
    Detecta si la ruptura de miembros causa sobrecarga en otros.
    Puede repetir hasta que el sistema se estabiliza.
    """
    
    # Aplicar fuerzas nuevamente para recalcular esfuerzos
    # (simulando redistribución)
    for n in self.nodos:
        n.reset_fuerza()
    
    if self.aplicar_gravedad:
        for n in self.nodos:
            if not n.fijo:
                n.aplicar_fuerza(0.0, -n.masa * GRAVEDAD)
    
    # Solo miembros NO rotos transmiten fuerzas
    for m in self.miembros:
        if not m.roto:
            m.aplicar_fuerza_hooke()
    
    # Verificar nuevas rupturas
    nuevas_rupturas = False
    for m in self.miembros:
        if not m.roto and m.revisar_ruptura():
            nuevas_rupturas = True
            print(f"  → Cascada: Miembro #{self.miembros.index(m)} también colapsó")
    
    # Si hay más rupturas, revisar recursivamente (max 5 iteraciones)
    if nuevas_rupturas:
        self.iteracion_cascada += 1
        if self.iteracion_cascada < 5:
            self.evaluar_cascada_fallos()
```

#### 4. Telemetría de Fallo
```python
def imprimir_estado_estructura(self):
    """Imprime resumen de integridad estructural"""
    
    miembros_rotos = [m for m in self.miembros if m.roto]
    
    print("\n" + "="*70)
    print("ESTADO ESTRUCTURAL")
    print("="*70)
    
    if not miembros_rotos:
        print("✓ Estructura íntegra")
    else:
        print(f"⚠️  DAÑO CRÍTICO: {len(miembros_rotos)} miembros rotos")
        for m in miembros_rotos:
            idx = self.miembros.index(m)
            print(f"   - Miembro #{idx}: roto en t={m.tiempo_ruptura:.2f}s")
    
    # Mostrar miembros en peligro (> 80% esfuerzo)
    en_peligro = []
    for m in self.miembros:
        if not m.roto:
            limite = (m.esfuerzo_limite_tension if m.esfuerzo_actual >= 0 
                     else abs(m.esfuerzo_limite_compresion))
            ratio = abs(m.esfuerzo_actual) / abs(limite)
            if ratio > 0.80:
                en_peligro.append((self.miembros.index(m), ratio))
    
    if en_peligro:
        print(f"\n⚠️  {len(en_peligro)} miembros en estado crítico (> 80%):")
        for idx, ratio in sorted(en_peligro, key=lambda x: x[1], reverse=True):
            print(f"   - Miembro #{idx}: {ratio*100:.1f}% del límite")
    
    print("="*70 + "\n")
```

### Validación Semana 11
- [ ] Puente soporta peso propio sin rupturas
- [ ] Con carga creciente, primer miembro se rompe a ~250 MPa
- [ ] Luego de ruptura, carga se redistribuye (telemetría muestra aumento en otros)
- [ ] Si es suficiente sobrecarga, cascada de fallos es visible
- [ ] Post-fallo, estructura se deforma más pero permanece estable
- [ ] Miembros grises no transmiten fuerzas

---

## Semana 12: HUD Informativo y Panel de Control

### Objetivo
Crear un panel visual en pantalla que muestre:
1. Esfuerzos actuales de miembros críticos
2. Margen hasta ruptura
3. Estado de la estructura (íntegra/dañada)
4. Información de carga (peso de coche, distribución)

### Implementación Requerida

#### 1. Clase HUD en `MotorGrafico`
```python
class HUD:
    def __init__(self, puente):
        self.puente = puente
        self.mostrar = True
    
    def calcular_estadisticas(self):
        """Calcula datos para mostrar"""
        
        esfuerzo_max = 0
        miembro_critico = None
        miembros_rotos = len([m for m in self.puente.miembros if m.roto])
        
        for i, m in enumerate(self.puente.miembros):
            if not m.roto:
                limite = (m.esfuerzo_limite_tension if m.esfuerzo_actual >= 0 
                         else abs(m.esfuerzo_limite_compresion))
                ratio = abs(m.esfuerzo_actual) / abs(limite)
                
                if ratio > esfuerzo_max:
                    esfuerzo_max = ratio
                    miembro_critico = i
        
        return {
            'esfuerzo_max_ratio': esfuerzo_max,
            'miembro_critico': miembro_critico,
            'miembros_rotos': miembros_rotos,
            'margen': max(0, 1.0 - esfuerzo_max)
        }
    
    def dibujar_texto_2d(self, x, y, texto, escala=0.15):
        """
        Dibuja texto en pantalla (posición 2D)
        Requiere rendertext_rendertext o similar
        """
        # Usar GLUT para renderizar texto
        glRasterPos2f(x, y)
        for caracter in texto:
            glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(caracter))
    
    def renderizar(self):
        """Dibuja el HUD completo"""
        
        if not self.mostrar:
            return
        
        # Cambiar a modo 2D (ortográfico)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.ancho_pantalla, 0, self.alto_pantalla, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Desactivar iluminación para HUD
        glDisable(GL_LIGHTING)
        
        stats = self.calcular_estadisticas()
        
        # Panel de fondo (rectángulo semi-transparente)
        glColor4f(0.0, 0.0, 0.0, 0.7)
        glBegin(GL_QUADS)
        glVertex2f(10, self.alto_pantalla - 10)
        glVertex2f(350, self.alto_pantalla - 10)
        glVertex2f(350, self.alto_pantalla - 200)
        glVertex2f(10, self.alto_pantalla - 200)
        glEnd()
        
        # Textos
        glColor3f(1.0, 1.0, 1.0)  # Blanco
        y_pos = self.alto_pantalla - 30
        
        self.dibujar_texto_2d(20, y_pos, "=== PUENTE PRATT ===")
        y_pos -= 20
        
        # Esfuerzo máximo
        ratio_pct = stats['esfuerzo_max_ratio'] * 100
        color = self._color_por_ratio(stats['esfuerzo_max_ratio'])
        glColor3f(*color)
        self.dibujar_texto_2d(20, y_pos, 
            f"Esfuerzo máx: {ratio_pct:.1f}%")
        y_pos -= 20
        
        # Miembro crítico
        if stats['miembro_critico'] is not None:
            glColor3f(1.0, 1.0, 0.0)  # Amarillo
            self.dibujar_texto_2d(20, y_pos,
                f"Crítico: Miembro #{stats['miembro_critico']}")
            y_pos -= 20
        
        # Estado de integridad
        glColor3f(1.0, 1.0, 1.0)
        if stats['miembros_rotos'] > 0:
            glColor3f(1.0, 0.0, 0.0)  # Rojo
            self.dibujar_texto_2d(20, y_pos,
                f"⚠️ {stats['miembros_rotos']} miembros ROTOS")
        else:
            glColor3f(0.0, 1.0, 0.0)  # Verde
            self.dibujar_texto_2d(20, y_pos,
                f"✓ Estructura íntegra")
        y_pos -= 20
        
        # Margen de seguridad
        margen_pct = stats['margen'] * 100
        glColor3f(*self._color_por_ratio(1 - stats['margen']))
        self.dibujar_texto_2d(20, y_pos,
            f"Margen: {margen_pct:.1f}%")
        
        # Restaurar estado 3D
        glEnable(GL_LIGHTING)
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
    
    def _color_por_ratio(self, ratio):
        """Retorna color (r,g,b) según ratio de esfuerzo"""
        if ratio < 0.25:
            return (0.0, 1.0, 0.0)  # Verde
        elif ratio < 0.50:
            return (1.0, 1.0, 0.0)  # Amarillo
        elif ratio < 0.75:
            return (1.0, 0.5, 0.0)  # Naranja
        else:
            return (1.0, 0.0, 0.0)  # Rojo
```

#### 2. Integración en Loop Principal
```python
def display():
    """Loop de renderizado"""
    
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    
    # Dibujar estructura 3D
    motor_grafico.dibujar()
    
    # NUEVO: Dibujar HUD
    motor_grafico.hud.renderizar()
    
    glutSwapBuffers()
```

#### 3. Telemetría a Archivo
```python
class RegistroTelemetria:
    def __init__(self, nombre_archivo="telemetria_simulacion.csv"):
        self.archivo = open(nombre_archivo, 'w')
        self.archivo.write("tiempo,esfuerzo_max,margen,miembros_rotos,carga_movil\n")
    
    def registrar(self, tiempo, stats, carga_movil):
        """Escribe línea de telemetría"""
        self.archivo.write(
            f"{tiempo:.3f},"
            f"{stats['esfuerzo_max_ratio']:.4f},"
            f"{stats['margen']:.4f},"
            f"{stats['miembros_rotos']},"
            f"{carga_movil.peso if carga_movil else 0}\n"
        )
    
    def cerrar(self):
        self.archivo.close()

# En main loop:
telemetria = RegistroTelemetria()
# ... en cada frame ...
telemetria.registrar(tiempo_actual, stats, carga_movil)
# ... al terminar ...
telemetria.cerrar()
```

### Validación Semana 12
- [ ] HUD visible en esquina superior izquierda
- [ ] Esfuerzo máximo actualiza en tiempo real
- [ ] Color de esfuerzo cambia según nivel (verde/amarillo/naranja/rojo)
- [ ] Miembro crítico se identifica correctamente
- [ ] Estado de integridad muestra "íntegra" o "X miembros rotos"
- [ ] Margen de seguridad es 100% - esfuerzo_máximo
- [ ] Archivo de telemetría se genera correctamente
- [ ] Datos del CSV coinciden con HUD en pantalla

---

## Integración Final y Testing

### Checklist de Testing Completo

```
SEMANA 10:
  [ ] Colores visuales correctos
  [ ] Telemetría de esfuerzos funciona
  [ ] Transición de colores es suave
  [ ] Miembros grises cuando alcanzan ruptura

SEMANA 11:
  [ ] Ruptura física ocurre a ~250 MPa
  [ ] Cascada de fallos detecta rupturas múltiples
  [ ] Post-fallo, cargas se redistribuyen
  [ ] Telemetría de cascada es clara
  [ ] Sistema es estable después de fallo

SEMANA 12:
  [ ] HUD renderiza sin lag
  [ ] Texto es legible en todo tipo de carga
  [ ] CSV se genera y contiene datos válidos
  [ ] HUD y telemetría están sincronizados
  [ ] Se puede exportar análisis post-simulación

INTEGRACIÓN:
  [ ] Las 3 semanas funcionan conjuntamente
  [ ] Sin conflictos de código
  [ ] Memoria no se filtra
  [ ] Rendimiento > 30 FPS en carga normal
  [ ] Sin artefactos visuales
```

### Entregables Finales

1. **`simulador_puente_FINAL.py`** (versión actualizada)
   - Semana 10 features (colores + telemetría)
   - Semana 11 features (ruptura + cascada)
   - Semana 12 features (HUD + CSV)

2. **`DOCUMENTACION_SPRINTS_10_12.md`**
   - Explicación de cada feature
   - Decisiones de diseño
   - Validación de resultados

3. **`VALIDACION_FINAL_SEMANAS_10_12.py`**
   - Tests de colores según esfuerzo
   - Tests de cascada de fallos
   - Tests de HUD y telemetría

4. **Ejemplos de salida**
   - `telemetria_ejemplo.csv` (archivo de ejemplo)
   - `screenshots/` (imágenes de HUD en diferentes estados)

---

## Próximos Pasos Inmediatos

1. **Revisar este plan** con profesor/equipo
2. **Priorizar** si hay cambios de scope
3. **Iniciar Semana 10** con sistema de colores
4. **Testing incremental** cada semana
5. **Documentar decisiones** conforme avances

**Estimado:** ~40 horas de desarrollo (~2 semanas a tiempo completo)

---

**Preparado por:** Claude  
**Fecha:** 27 de Mayo, 2026  
**Siguiente revisión:** Post-Semana 10
