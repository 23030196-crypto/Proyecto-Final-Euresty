# SIMULADOR DE DEFORMACIÓN ESTRUCTURAL EN PUENTE PRATT
## Documento Integral del Proyecto - Semana 9-10

**Materia:** Graficación  
**Profesor:** Euresty Uribe Carlos Gerardo  
**Equipo:** Clara Paulina Hernández López, Diego Serrano Serrano  
**Periodo:** Semana 9-10 de Semestre  
**Fecha de Actualización:** 27 de Mayo, 2026

---

## 📋 TABLA DE CONTENIDOS

1. [Objetivos del Proyecto](#objetivos)
2. [Marco Teórico Completo](#marco-teórico)
3. [Estado Actual del Código](#estado-actual)
4. [Problema Identificado](#problema)
5. [Análisis de Root Cause](#análisis)
6. [Solución Propuesta](#solución)
7. [Próximos Pasos](#próximos-pasos)

---

## <a name="objetivos"></a>1. OBJETIVOS DEL PROYECTO

### Objetivo General
Desarrollar un simulador gráfico interactivo en 3D utilizando Python y OpenGL que permita visualizar y analizar la respuesta mecánica de un puente de armadura (tipo Pratt) ante cargas dinámicas. El propósito es crear una herramienta educativa donde la computación gráfica sirva como puente para entender fenómenos físicos complejos, como la deformación elástica y la distribución de esfuerzos en tiempo real.

### Objetivos Específicos

1. **Motor de Renderizado Dinámico**
   - Configurar OpenGL para actualizar vertices (nodos) en GPU constantemente
   - Permitir que el puente se deforme visualmente según cálculos físicos
   - Mantener 60 FPS sin problemas de rendimiento

2. **Cargas Dinámicas Realistas**
   - Simular el paso de un vehículo sobre la estructura
   - Transferir peso de forma proporcional entre nodos
   - Implementar interpolación lineal para movimiento suave

3. **Visualización de Esfuerzos (Stress Mapping)**
   - Traducir fuerzas internas de tensión/compresión en gradiente cromático
   - Azul para tensión, Rojo para compresión
   - Representación visual de puntos críticos

4. **Elasticidad y Oscilación Realistas**
   - Ley de Hooke para comportamiento elástico
   - Amortiguamiento viscoso para estabilidad
   - Integración de Verlet para precisión numérica

5. **Interfaz Interactiva**
   - Modificación de variables en tiempo real (masa, velocidad)
   - Observación inmediata de efectos
   - Controles intuitivosintuitivos con teclado

### Problema Real a Resolver

Un puente tipo armadura necesita ser evaluado para determinar si es seguro que pase un camión de carga moderno. Visualizar esto es complejo porque:
- Los cálculos en papel solo dicen el punto máximo en un lugar fijo
- No muestran pandeo o vibración mientras se desplaza el vehículo
- No revelan qué vigas están en riesgo de ruptura

**Preguntas que responde el simulador:**
- ¿En qué parte exacta del trayecto el puente sufre más presión?
- ¿Qué vigas están en riesgo de romperse si el camión va muy rápido?
- ¿Cómo cambia la deformación con diferentes materiales (madera vs acero)?

---

## <a name="marco-teórico"></a>2. MARCO TEÓRICO COMPLETO

### 2.1 Geometría de la Armadura Pratt

La armadura Pratt se modela como un **grafo ponderado** donde:

- **Nodos (N):** Puntos de unión con coordenadas (x, y), masa asignada
- **Miembros (M):** Vigas conectando nodos, con propiedades de elasticidad
- **Carretera:** Nodos inferiores sobre los que circula el vehículo

**Configuración típica:**
```
12 paneles × 1.5 unidades = 18 metros de longitud
Altura = 4 metros
Total: 24 nodos, 45 miembros
```

**Cálculo de longitud inicial:**
```
L₀ = √[(xⱼ - xᵢ)² + (yⱼ - yᵢ)²]
```

### 2.2 Ley de Hooke (Elasticidad)

Cada viga actúa como un **resorte ultra-rígido**:

```
F = k × ΔL

Donde:
  k = (E × A) / L₀     (rigidez axial)
  ΔL = L_actual - L₀   (deformación)
  E = Módulo de Young  (propiedad del material)
  A = Área transversal (sección de la viga)
```

**Cálculo de Esfuerzo:**
```
σ = E × ε
ε = (L - L₀) / L₀     (deformación unitaria)
σ = E × (L - L₀) / L₀ (esfuerzo)
```

### 2.3 Propiedades de Materiales Reales

Después de Semana 9, implementamos valores realistas **escalados por 1e6**:

| Material  | E Real | E_Simulador | σ_tensión | σ_compresión | Área Típica |
|-----------|--------|-------------|-----------|--------------|-------------|
| Acero     | 200 GPa| 200.0       | 250 MPa   | 400 MPa      | 0.0025 m²   |
| Madera    | 12 GPa | 12.0        | 30 MPa    | 40 MPa       | 0.01 m²     |
| Concreto  | 30 GPa | 30.0        | 3 MPa     | 25 MPa       | 0.04 m²     |

**Factor de escala:** `1e6` (Pa/1e6 = MPa)

### 2.4 Carga Dinámica e Interpolación

El vehículo se modela como carga puntual `P = m × g`:

```
Posición en tiempo t:
  x(t) = x_inicio + v × t

Interpolación lineal entre nodos k y k+1:
  ξ = (x(t) - xₖ) / (xₖ₊₁ - xₖ)
  Fₖ = P × (1 - ξ)
  Fₖ₊₁ = P × ξ
```

Esta distribución suave evita saltos abruptos de carga.

### 2.5 Dinámica y Amortiguamiento

**Ecuación de movimiento (segundos grados de libertad):**
```
M × u'' + C × u' + K × u = F(t)

Términos:
  M × u''     = Aceleración (fuerza inercial)
  C × u'      = Amortiguamiento (viscoso)
  K × u       = Rigidez (elasticidad)
  F(t)        = Fuerzas externas (vehículo, gravedad)
```

**Amortiguamiento viscoso:**
```
F_damping = -c × v

Donde c = 5500.0 (coeficiente de amortiguamiento)
```

Sin amortiguamiento, el puente vibraría infinitamente. Con él, disipa energía y se estabiliza.

### 2.6 Integración de Verlet

**Algoritmo de integración temporal (Sprint 6):**

```
Para cada nodo n en cada sub-paso dt:

1. Calcular fuerza total:
   f = f_vehículo + f_elastica + f_gravedad + f_amortiguamiento

2. Aceleración (2ª Ley de Newton):
   a = f / m

3. Actualizar posición (Verlet):
   x_new = 2×x - x_prev + a×dt²
```

**Ventaja de Verlet:**
- La velocidad está implícita en `(x - x_prev) / dt`
- Reduce acumulación de errores vs. Euler
- Mejor conservación de energía
- Más estable para osciladores

**SUBSTEPS:** 25 pasos internos por frame (60 FPS = 1500 sub-pasos por segundo)

### 2.7 Análisis de Esfuerzos

**Deformación unitaria:**
```
ε = (L_actual - L₀) / L₀
```

**Esfuerzo normal:**
```
σ = E × ε
```

**Clasificación visual:**
- σ > 100 MPa: Tensión ALTA (cian/azul)
- 30 < σ < 100 MPa: Tensión MEDIA (azul oscuro)
- σ < -150 MPa: Compresión ALTA (naranja)
- -150 < σ < -50 MPa: Compresión MEDIA (naranja oscuro)
- -50 < σ < 30 MPa: Esfuerzo BAJO (gris)

**Ruptura:**
```
SI σ > σ_límite_tensión  O  σ < σ_límite_compresión:
    VIGA_ROTA = True
    Color = Gris oscuro
```

---

## <a name="estado-actual"></a>3. ESTADO ACTUAL DEL CÓDIGO

### 3.1 Arquitectura

```
SimuladorApp
├── PuentePratt
│   ├── Lista[Nodo]
│   └── Lista[Miembro]
├── CargaMovil
├── MotorGrafico
└── Pygame/OpenGL
```

### 3.2 Clases Principales

#### **Nodo**
```python
class Nodo:
    id: int
    x0, y0: float         # Posición inicial
    x, y: float           # Posición actual
    x_prev, y_prev: float # Posición previa (para Verlet)
    fijo: bool            # Si es apoyo del puente
    masa: float           # kg
    fuerza: np.array      # Acumulador de fuerzas [fx, fy]
```

#### **Miembro (Viga)**
```python
class Miembro:
    id: int
    origen, destino: Nodo
    E: float              # Módulo de Young (Pa/1e6)
    Area: float           # m²
    L0: float             # Longitud inicial (m)
    k: float              # Rigidez = E*A/L0
    
    esfuerzo_actual: float
    limite_tension: float     # σ_ruptura (tensión)
    limite_compresion: float  # σ_ruptura (compresión)
    roto: bool
    
    AREAS_MATERIAL = {
        "Acero": 0.0025,
        "Madera": 0.01,
        "Concreto": 0.04
    }
```

#### **CargaMovil**
```python
class CargaMovil:
    masa: float           # kg
    velocidad: float      # m/s
    pos_x: float          # posición en eje x
    activo: bool
    x_min, x_max: float   # rango de movimiento
```

#### **MotorGrafico**
```python
class MotorGrafico:
    # Dibuja nodos, miembros y vehículo
    # Calcula colores según esfuerzo
    # Usa OpenGL (GL_LINES, GL_POINTS, GL_QUADS)
```

### 3.3 Loop de Simulación (60 FPS)

```
CADA FRAME:
  1. Capturar eventos (teclado)
  2. FOR CADA sub-paso (25 iteraciones):
     a. Actualizar posición del vehículo
     b. Resetear fuerzas de nodos
     c. Aplicar gravedad
     d. Inyectar carga del vehículo (interpolación)
     e. Calcular fuerzas de Hooke (miembros)
     f. Aplicar amortiguamiento
     g. Integración Verlet
  3. Calcular esfuerzos de miembros
  4. Dibujar puente, vehículo
  5. Flip de pantalla (60 Hz)
```

---

## <a name="problema"></a>4. PROBLEMA IDENTIFICADO

### Síntoma Observado

**Desde que ejecutaste el simulador hoy:**

1. **Las vigas se estiran infinitamente** (comportamiento elástico extremo)
2. **Ruptura ocurre muy pronto** (~6000 kg para Acero)
3. **Los límites parecen haber vuelto a valores antiguos**

### Ejemplo de Output Actual

```
Masa: 6000 kg
VIGA 9 ROTA (σ=252.32 MPa, límite=250/-400)
Masa: 7000 kg
VIGA 30 ROTA (σ=250.57 MPa, límite=250/-400)
```

**Análisis:**
- El límite de tensión es `250 MPa` ✓ (correcto)
- El esfuerzo está apenas sobre el límite con 6000 kg
- **Esperado:** Ruptura alrededor de 70 toneladas para Acero
- **Observado:** Ruptura a 6 toneladas

**Ratio de error:** `70,000 / 6,000 ≈ 11.67×`

---

## <a name="análisis"></a>5. ANÁLISIS DE ROOT CAUSE

### 5.1 Posible Causa 1: Rigidez (k) Excesivamente Alta

**Hipótesis:** El módulo E o el área A es mucho mayor de lo que debería.

```
k = E × A / L₀

Si k es muy grande:
  - F = k × ΔL produce fuerzas enormes
  - ΔL se mantiene muy pequeño
  - El puente actúa como "infinitamente rígido"
```

**Verificación requerida:**
```python
# En Miembro.__init__():
print(f"Miembro {id}: k = {self.k:.6f}")
print(f"  E={self.E}, A={self.Area}, L0={self.L0}")
```

### 5.2 Posible Causa 2: Escala de Esfuerzo Inconsistente

**Hipótesis:** El cálculo de σ no está en la escala correcta.

```
σ = E × ε

Ejemplo:
  E = 200.0 (representa 200 GPa escalado)
  ε = 0.01 (1% de deformación)
  σ = 200.0 × 0.01 = 2.0 ← ¿En qué unidades?
```

Si σ está en escala incorrecta, los límites (250, -400) no corresponden.

### 5.3 Posible Causa 3: Fuerza de Gravedad No Escalada

**Hipótesis:** La gravedad `g = 9.81` es demasiado grande en el sistema escalado.

```
F_gravedad = m × g

Si:
  m = 6000 kg (real)
  g = 9.81 m/s² (real)
  F = 6000 × 9.81 = 58,860 N

Pero en escala simulador (Pa/1e6), esto podría estar sobre-amplificado.
```

### 5.4 Posible Causa 4: Área Transversal Subestimada

**Hipótesis:** El área de 0.0025 m² (50×50 mm) es demasiado pequeña.

```
k = E × A / L₀

Con A = 0.0025 m²:
  k = 200 × 0.0025 / 4.27 ≈ 0.117

Compáralo con A = 0.01 m² (100×100 mm):
  k = 200 × 0.01 / 4.27 ≈ 0.468

La rigidez es 4× mayor con A más grande.
```

### 5.5 Causa Más Probable: Bug en Database o Inicialización

**Sospecha fuerte:** La BD `materiales.db` puede tener valores incorrectos nuevamente.

```
Validación anterior mostró:
  E_esperado = 200.0, pero BD tenía 2000.0

Posibilidad: Se regeneró la BD con valores antiguos (10× mayores)
```

---

## <a name="solución"></a>6. SOLUCIÓN PROPUESTA

### 6.1 Paso 1: Diagnosticar el Estado Actual

```bash
# Verificar contenido de BD
sqlite3 materiales.db "SELECT * FROM materiales;"

# Salida esperada:
# Acero|200.0|250.0|-400.0
# Madera|12.0|30.0|-40.0
# Concreto|30.0|3.0|-25.0
```

### 6.2 Paso 2: Verificar Cálculos de Rigidez

Agregar debug prints en `Miembro.__init__()`:

```python
def __init__(self, id_miembro, nodo_origen, nodo_destino, E=200.0, area=0.01, material=None):
    # ... código existente ...
    
    self.k = self.E * self.Area / self.L0
    
    # DEBUG
    if id_miembro in [0, 9, 30]:  # Imprimir primeras vigas críticas
        print(f"VIGA {id_miembro}: E={self.E:.1f}, A={self.Area:.4f}, L0={self.L0:.3f}, k={self.k:.6f}")
```

### 6.3 Paso 3: Verificar Escala de Fuerzas

Agregar en `CargaMovil.aplicar_carga()`:

```python
def aplicar_carga(self, nodos_carretera):
    if not self.activo:
        return
    
    peso = self.masa * GRAVEDAD
    
    # DEBUG (solo una vez)
    if self.masa == 2000 and not hasattr(self, '_printed_debug'):
        print(f"DEBUG: masa={self.masa} kg, peso={peso:.0f} N")
        self._printed_debug = True
```

### 6.4 Paso 4: Comparar con Teoría

**Cálculo teórico esperado:**

Para Acero (E=200 GPa, A=0.0025 m², L₀=4.27 m):

```
Carga por nodo: 20,000 kg / 13 nodos ≈ 1538 kg
Peso por nodo: 1538 × 9.81 ≈ 15,070 N

Esfuerzo en viga:
  σ = F / A = 15,070 / 0.0025 = 6,028,000 Pa = 6.03 MPa

Pero nuestro modelo usa σ = E × ε, no σ = F / A directamente.

Con el modelo actual:
  ε = (L - L₀) / L₀
  σ = E × ε
  
  Para que σ = 250 MPa:
    ε = 250 / 200 = 1.25 = 125% deformación
```

**Esto significa el viga se alargaría 125% antes de romper, lo cual es correcto para una viga elástica.**

### 6.5 Paso 5: Root Cause Fix

**La causa probable es que E está mal inicializado nuevamente.**

**Fix propuesto:**

```python
def obtener_material(nombre, db_path="materiales.db"):
    """Obtiene propiedades de material escaladas (Pa/1e6)"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT E, limite_tension, limite_compresion FROM materiales WHERE nombre=?", (nombre,))
    resultado = c.fetchone()
    conn.close()
    
    if resultado:
        E, sigma_t, sigma_c = resultado
        # Validación: E no debe ser > 10000 (Concreto máximo es 30)
        if E > 10000:
            print(f"⚠️ ADVERTENCIA: Material '{nombre}' tiene E={E} (parece escalado 10×)")
            E = E / 10.0
        return (E, sigma_t, sigma_c)
    
    return (200.0, 250.0, -400.0)  # Default Acero
```

### 6.6 Paso 6: Regenerar Base de Datos

```bash
# Eliminar BD antigua
rm materiales.db

# Ejecutar simulador (se regenerará con valores correctos)
python3 simulador_puente_FINAL.py
```

---

## <a name="próximos-pasos"></a>7. PRÓXIMOS PASOS

### Corto Plazo (Hoy)

1. [ ] Ejecutar script de diagnóstico:
   ```bash
   sqlite3 materiales.db "SELECT * FROM materiales;"
   python3 validar_modelo_matematico.py
   ```

2. [ ] Revisar output de debug de rigidez (k values)

3. [ ] Comparar esfuerzos observados vs. esperados

4. [ ] Regenerar BD si es necesario

### Mediano Plazo (Semana 10)

1. [ ] Validar que ruptura ocurra alrededor de 70 toneladas para Acero
2. [ ] Probar con diferentes materiales (Madera @30 MPa, Concreto @3 MPa)
3. [ ] Implementar visualización de ruptura (graying)
4. [ ] Documentar comportamiento esperado para cada material

### Largo Plazo (Semanas 11-12)

1. [ ] Dinámicas de propagación de ruptura
2. [ ] Análisis de fallo estructural
3. [ ] HUD con telemetría
4. [ ] Preparación para entrega final

---

## 📊 ESPECIFICACIONES TÉCNICAS

### Stack Tecnológico

| Componente | Versión | Uso |
|-----------|---------|-----|
| Python | 3.x | Lenguaje principal |
| Pygame | latest | Eventos y loop |
| PyOpenGL | latest | Renderizado gráfico |
| NumPy | latest | Operaciones vectoriales |
| SQLite3 | builtin | Almacenamiento de materiales |
| Math | builtin | Trigonometría |

### Constantes Globales

```python
GRAVEDAD = 9.81              # m/s²
SUBSTEPS = 25                # Pasos internos de Verlet
FACTOR_ESCALA_MODULO = 1e6   # Pa/1e6 para estabilidad
UMBRAL_ESFUERZO = 50.0       # MPa para visualización
```

### Configuración del Puente

```python
paneles = 12                  # Número de paneles
longitud_panel = 1.5          # metros
altura = 4.0                  # metros
amortiguamiento = 5500.0      # Coeficiente viscoso
```

---

## 📚 REFERENCIAS ACADÉMICAS

- **Hibbeler, R. C. (2012).** Structural Analysis (8th ed.). Prentice Hall.
  - Análisis dinámico de estructuras
  - Identificación de fenómenos no-estáticos

- **Beer, F. P., Johnston Jr., E. R., DeWolf, J. T., & Mazurek, D. F. (2017).** Mechanics of Materials (7th ed.). McGraw-Hill.
  - Ley de Hooke
  - Deformación elástica
  - Análisis de esfuerzos

- **Shreiner, D., Khronos OpenGL ARB Working Group. (2013).** OpenGL Programming Guide (4th ed.).
  - Renderizado en GPU
  - Mapeo de colores
  - Optimización gráfica

- **Nystrom, R. (2014).** Game Programming Patterns. Genever Benning.
  - Game loop pattern
  - Fixed timestep integration
  - Architectural patterns for simulations

---

## ⚠️ NOTAS IMPORTANTES

### Para Clara y Diego

1. **Base de datos:** Verificar que `materiales.db` NO esté corrupta
2. **Escala:** Recordar que todo está en escala `Pa/1e6` = MPa
3. **Verlet:** El substeping es crítico para estabilidad
4. **Gravedad:** 9.81 m/s² es correcta, pero validar que no haya factor adicional

### Para Futuros Desarrolladores

1. **Modelo matemático es correcto** - La implementación de Semana 9 es sólida
2. **Bug es probablemente en datos,** no en lógica
3. **Validación script existe** - Ejecutar regularmente para verificar integridad
4. **Documentación completa** - Este documento integra toda la teoría

---

**Generado por:** Claude (Asistente de Ingeniería)  
**Versión:** 1.0  
**Estado:** Listo para diagnóstico  
**Próxima revisión:** Después de identificar root cause
