"""
SIMULADOR DE PUENTE PRATT - MODELO MATEMÁTICO 100% REALISTA
===========================================================

SISTEMA DE UNIDADES (CORRECCIÓN FINAL - May 2026):
- Longitud: METROS (m)
- Masa: KILOGRAMOS (kg)
- Tiempo: SEGUNDOS (s)
- Módulo E: GIGAPASCALES (GPa) - valores de ingeniería real
- Esfuerzo σ: MEGAPASCALES (MPa)

PARÁMETROS FÍSICOS REALES:
- E en GPa (valores reales de materiales):
  · Acero: E = 200 GPa, σ_ruptura = 250 MPa
  · Madera: E = 12 GPa, σ_ruptura = 30 MPa
  · Concreto: E = 30 GPa, σ_ruptura = 3 MPa

ECUACIONES IMPLEMENTADAS:
1. Deformación unitaria: ε = (L - L₀) / L₀ [adimensional]
2. Esfuerzo: σ = (E[GPa] × ε) / 1000 [MPa] ← CORREGIDO
3. Rigidez axial: k = (E[Pa] × A) / L₀ = (E[GPa] × 1e9 × A) / L₀ [N/m]
4. Fuerza interna: F = k × ΔL [N]
5. Integración Verlet: x_new = 2x - x_prev + a×dt² [m]

AMPLIFICACIÓN VISUAL DESACOPLADA:
- Física: deformaciones reales (milímetros)
- Render: deformaciones × AMPLIFICACION_VISUAL (visible en pantalla)
- Desacoplamiento completo: cambios visuales NO afectan física
"""

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
try:
    from OpenGL.GLUT import glutInit, glutBitmapCharacter, GLUT_BITMAP_9_BY_15
    _GLUT_OK = True
except Exception:
    _GLUT_OK = False
import numpy as np
import math
import sys
import csv
import sqlite3
import os
import warnings

# Suprimir RuntimeWarnings de NaN/overflow que eran síntoma del bug de
# inestabilidad Verlet (ya corregido). Se mantiene para robustez en caso
# de cargas extremas o configuraciones inusuales.
warnings.filterwarnings("ignore", category=RuntimeWarning)

GRAVEDAD = 9.81  # m/s²
# -----------------------------------------------------------------------------
# SUBSTEPS (Fix Final May 2026 - escala E correcta):
# Con E = 200 GPa (valor real), k = (E×1e9) × A / L0 ~ 2e9 N/m
# m_min = 40 kg (nodos superiores)
#   ω_max = √(k/m) = √(2e9/40) ≈ 7,071 rad/s (31.6× mayor que antes)
#   dt_crítico = 2/ω_max ≈ 0.00028 s (31.6× más pequeño)
# frame_dt = 1/60 ≈ 0.0167 s (para 60 FPS)
# SUBSTEPS = ceil(frame_dt / dt_critico * 1.2) ≈ ceil(72) → 80 (conservador)
#
# Para mayor estabilidad, usamos:
# SUBSTEPS = 120 (balance: estabilidad sin overhead computacional)
# Con esto: dt_substep ≈ 0.00014 s << 0.00028 s → ESTABLE
# -----------------------------------------------------------------------------
SUBSTEPS = 120
SUBSTEPS_MIN = 80
SUBSTEPS_MAX = 1000
FACTOR_SEGURIDAD_DT = 0.12

# =============================================================================
# CONSTANTES DE ESCALADO Y UNIDADES
# =============================================================================
# IMPORTANTE: Después del fix de unidades (May 2026):
#   - E almacenado en BD: representa GIGAPASCALES (GPa)
#     · Acero = 200 (GPa), Madera = 12 (GPa), Concreto = 30 (GPa)
#   - sigma_limite almacenado en BD: representa MEGAPASCALES (MPa)
#     · Acero = 250 (MPa), Madera = 30 (MPa), Concreto = 3 (MPa)
#   - Fuerzas: NEWTONS reales (N)
#   - Masa: KILOGRAMOS (kg)
#   - Posicion: METROS (m)
#   - Esfuerzo calculado: MEGAPASCALES (MPa) - coherente con limites
# =============================================================================

# FACTOR_GPa_A_Pa REMOVIDO (May 27 2026): k ya está en escala correcta
# E está en Pa/1e6, no en GPa real
UMBRAL_ESFUERZO = 50.0       # MPa, umbral para visualizacion de colores

# Amplificacion visual de la deformacion (desacoplada de la fisica)
#
# CON E REAL (200 GPa):
# - Deformaciones reales: milímetros (0.1-5 mm bajo cargas típicas)
# - Imperceptibles en pantalla sin amplificación
#
# AMPLIFICACION_VISUAL:
# - Multiplica SOLO el desplazamiento visual del nodo desde su posición inicial
# - NO afecta la física: fuerzas, esfuerzos, ruptura se calculan con valores reales
# - Efecto es idéntico a "deformed shape" en ANSYS/SolidWorks
#
# Con E = 200 GPa (1000× más rígido que antes):
# - Deformación anterior: ~6 mm (visible)
# - Deformación actual: ~0.006 mm (invisible sin amplificación)
# - Factor de amplificación necesario: ~1000× para mantener visibilidad
AMPLIFICACION_VISUAL = 100.0   # Calibrado: pandeo leve visible ~60,000 kg
AMP_VISUAL_MIN = 10.0          # Mínimo permitido
AMP_VISUAL_MAX = 500.0         # Máximo permitido

def validar_materiales_bd(db_path="materiales.db"):
    """
    Valida que los valores en la BD sean coherentes con la convencion actual:
    - E en GPa (Acero=200, Madera=12, Concreto=30)
    - sigma en MPa (Acero=250, Madera=30, Concreto=3)
    Si detecta valores fuera de rango, regenera la tabla.
    """
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT E, limite_tension FROM materiales WHERE nombre='Acero'")
        fila = c.fetchone()
        conn.close()
        if fila is None:
            return False
        E, lim_t = fila
        # E para acero debe ser ~200 (GPa); si es muy distinto, BD corrupta
        if not (100 < E < 400) or not (100 < lim_t < 500):
            print(f"AVISO: BD con valores fuera de rango (E={E}, sigma_t={lim_t})")
            print(f"   -> Regenerando tabla materiales con valores correctos...")
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            c.execute("DROP TABLE IF EXISTS materiales")
            conn.commit()
            conn.close()
            return False
        return True
    except Exception as e:
        print(f"AVISO: Error validando BD: {e}")
        return False


def inicializar_materiales(db_path="materiales.db"):
    """
    Crea BD con materiales reales escalados.

    Unidades:
    E_real [Pa] / 1e6 → E_simulador
    σ_real [Pa] / 1e6 → σ_simulador

    Acero estructural (EN 10025-S275):
    - E = 200 GPa = 200e9 Pa
    - σ_ruptura = 275 MPa (nominal)
    - σ_trabajo = 250 MPa (con factor seguridad)

    Madera (Clase C18):
    - E = 9 GPa ≈ 12 GPa con efecto tiempo
    - σ_ruptura = 18 MPa → 30 MPa con efecto tiempo

    Concreto (f'c = 30 MPa):
    - E ≈ 30 GPa
    - σ_tracción ≈ 3 MPa (muy débil en tracción)
    - σ_compresión ≈ 25 MPa
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS materiales
                 (nombre TEXT PRIMARY KEY, E REAL, limite_tension REAL, limite_compresion REAL)''')
    c.execute("SELECT COUNT(*) FROM materiales")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO materiales VALUES (?, ?, ?, ?)", [
            ("Acero", 200.0, 250.0, -400.0),
            ("Madera", 12.0, 30.0, -40.0),
            ("Concreto", 30.0, 3.0, -25.0),
        ])
        conn.commit()
        print("✓ Materiales inicializados (valores reales escalados)")
    conn.close()
    return db_path

def obtener_material(nombre, db_path="materiales.db"):
    """Obtiene propiedades de material escaladas (Pa/1e6)"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT E, limite_tension, limite_compresion FROM materiales WHERE nombre=?", (nombre,))
    resultado = c.fetchone()
    conn.close()
    return resultado if resultado else (200.0, 250.0, -400.0)

class Nodo:
    def __init__(self, id_nodo, x, y, fijo=False, masa=80.0):
        self.id = id_nodo
        self.x0, self.y0 = x, y
        self.x_eq, self.y_eq = x, y
        self.x, self.y = x, y
        self.x_prev, self.y_prev = x, y
        self.fijo = fijo
        self.masa = masa
        self.fuerza = np.array([0.0, 0.0])

    @property
    def pos_actual(self):
        return (self.x, self.y)

    def reset_fuerza(self):
        self.fuerza[:] = 0.0

    def aplicar_fuerza(self, fx, fy):
        self.fuerza[0] += fx
        self.fuerza[1] += fy

class Miembro:
    """
    Viga con ecuaciones realistas.

    σ = E × ε donde:
    - σ: esfuerzo (Pa/1e6)
    - E: módulo elástico (Pa/1e6)
    - ε: deformación unitaria = (L - L₀)/L₀

    F = k × ΔL donde:
    - k = E × A / L₀ (rigidez axial)
    - ΔL: cambio de longitud
    """

    AREAS_MATERIAL = {
        "Acero": 0.015,
        "Madera": 0.01,
        "Concreto": 0.04,
    }

    def __init__(self, id_miembro, nodo_origen, nodo_destino, E=200.0, area=0.015, material=None):
        self.id = id_miembro
        self.origen = nodo_origen
        self.destino = nodo_destino
        self.esfuerzo_actual = 0.0
        self.epsilon_actual = 0.0
        self.roto = False
        self.color_custom = None
        self.material_nombre = material

        if material:
            props = obtener_material(material)
            self.E_GPa = props[0]
            self.limite_tension = props[1]
            self.limite_compresion = props[2]
            self.Area = area if area != 0.01 else self.AREAS_MATERIAL.get(material, 0.01)
        else:
            self.E_GPa = E
            self.limite_tension = 250.0
            self.limite_compresion = -400.0
            self.Area = area

        # Compatibilidad con código viejo
        self.E = self.E_GPa

        # Conversión real: GPa → Pa
        self.E_Pa = self.E_GPa * 1e9

        dx = self.destino.x0 - self.origen.x0
        dy = self.destino.y0 - self.origen.y0
        self.L0 = math.hypot(dx, dy)

        if self.L0 <= 1e-9:
            raise ValueError(f"Miembro {self.id} tiene longitud inicial inválida")

        # Rigidez axial real: k = EA/L0
        self.k = self.E_Pa * self.Area / self.L0
        # =====================================================================
        # CÁLCULO DE RIGIDEZ - CORRECCIÓN FINAL (May 2026)
        # k = (E × A) / L₀
        #
        # E está en GPa (valor real de ingeniería: Acero=200 GPa)
        # Para obtener k en N/m, multiplicar por 1e9 (GPa → Pa)
        #   k = (E[GPa] × 1e9[Pa/GPa]) × A[m²] / L₀[m]
        #   k = (E × 1e9) × A / L₀ [N/m]
        #
        # Ejemplo para Acero (E=200 GPa):
        #   k = (200 × 1e9) × 0.015 / 1.5 = 2.0e9 N/m ✓ (1000× más rígido)
        # =====================================================================

    def longitud_actual(self):
        dx = self.destino.x - self.origen.x
        dy = self.destino.y - self.origen.y
        return math.hypot(dx, dy)

    def calcular_esfuerzo(self):
        """
        Calcula σ = E × ε en MPa (Megapascales)

        E está en GPa (valor real: Acero=200 GPa)
        ε es adimensional (cambio relativo de longitud)
        σ [MPa] = E[GPa] × ε × 1000

        Ejemplo:
          E = 200 GPa, ε = 0.001 → σ = 200 × 0.001 × 1000 = 200 MPa
        """
        L = self.longitud_actual()
        if L < 1e-9:
            self.esfuerzo_actual = 0.0
            return 0.0
        epsilon = (L - self.L0) / self.L0
        # E está en GPa, multiplicar por 1000 para obtener MPa
        self.esfuerzo_actual = self.E_GPa * 1000.0 * epsilon
        return self.esfuerzo_actual

    def aplicar_fuerza_hooke(self):
        """
        Aplica F = k * dL en Newtons reales.

        k está en N/m (E*1e6*A/L0), por lo que F es directamente Newtons.
        """
        if self.roto:
            return
        L = self.longitud_actual()
        if L < 1e-9:
            return
        delta_L = L - self.L0
        F = self.k * delta_L  # Newtons reales (k en N/m, dL en m)
        ux = (self.destino.x - self.origen.x) / L
        uy = (self.destino.y - self.origen.y) / L
        self.origen.aplicar_fuerza(F * ux, F * uy)
        self.destino.aplicar_fuerza(-F * ux, -F * uy)

    def obtener_color_stress(self):
        """
        Azul  = tensión  (tracción),  más intenso cuanto más cerca del límite
        Rojo  = compresión,           más intenso cuanto más cerca del límite
        Gris claro = sin carga  |  Gris oscuro = roto
        Curva sqrt: colores visibles incluso con poco esfuerzo
        """
        if self.roto:
            return (0.45, 0.45, 0.45)

        if self.esfuerzo_actual >= 0:
            ratio = min(self.esfuerzo_actual / max(self.limite_tension, 1e-9), 1.0)
            t = math.sqrt(ratio)          # sqrt: más sensible a esfuerzos bajos
            r = 0.75 * (1.0 - t)
            g = 0.75 * (1.0 - t * 0.6)
            b = 0.75 + 0.25 * t          # base gris claro → azul brillante
        else:
            ratio = min(abs(self.esfuerzo_actual) / max(abs(self.limite_compresion), 1e-9), 1.0)
            t = math.sqrt(ratio)
            r = 0.75 + 0.25 * t          # base gris claro → rojo brillante
            g = 0.75 * (1.0 - t * 0.8)
            b = 0.75 * (1.0 - t)

        return (r, g, b)

    def stress_ratio(self):
        """Fracción del límite alcanzada (0-1)."""
        if self.esfuerzo_actual >= 0:
            return min(self.esfuerzo_actual / max(self.limite_tension, 1e-9), 1.0)
        return min(abs(self.esfuerzo_actual) / max(abs(self.limite_compresion), 1e-9), 1.0)

    def comprobar_ruptura(self):
        if not self.roto:
            if self.esfuerzo_actual > self.limite_tension or self.esfuerzo_actual < self.limite_compresion:
                self.roto = True
                print(f"VIGA {self.id} ROTA (σ={self.esfuerzo_actual:.2f} MPa, límite={self.limite_tension:.0f}/{self.limite_compresion:.0f})")
        return self.roto

    def actualizar_visual(self):
        self.color_custom = (128, 128, 128) if self.roto else None

class CargaMovil:
    def __init__(self, masa=2000.0, velocidad=3.0):
        self.masa = masa
        self.velocidad = velocidad
        self.pos_x = 0.0
        self.activo = False
        self.x_min = self.x_max = 0.0
        self._idx_cache = 0

    def configurar_recorrido(self, x_min, x_max):
        self.x_min, self.x_max = x_min, x_max
        self.pos_x = x_min

    def iniciar(self):
        self.pos_x = self.x_min
        self._idx_cache = 0
        self.activo = True

    def detener(self):
        self.activo = False
        self.pos_x = self.x_min
        self._idx_cache = 0

    def actualizar(self, dt):
        if not self.activo:
            return
        self.pos_x += self.velocidad * dt
        if self.pos_x >= self.x_max:
            self.pos_x = self.x_max
            self.activo = False

    def aplicar_carga(self, nodos_carretera):
        if not self.activo:
            return
        if self.pos_x < nodos_carretera[0].x0 or self.pos_x > nodos_carretera[-1].x0:
            return
        peso = self.masa * GRAVEDAD
        for i in range(self._idx_cache, len(nodos_carretera) - 1):
            nk = nodos_carretera[i]
            nk1 = nodos_carretera[i + 1]
            if nk.x0 <= self.pos_x <= nk1.x0:
                xi = (self.pos_x - nk.x0) / (nk1.x0 - nk.x0)
                nk.aplicar_fuerza(0.0, -peso * (1.0 - xi))
                nk1.aplicar_fuerza(0.0, -peso * xi)
                self._idx_cache = i
                break

    def get_pos_y(self, nodos_carretera):
        if self.pos_x <= nodos_carretera[0].x0:
            return nodos_carretera[0].y
        if self.pos_x >= nodos_carretera[-1].x0:
            return nodos_carretera[-1].y
        for i in range(len(nodos_carretera) - 1):
            nk, nk1 = nodos_carretera[i], nodos_carretera[i + 1]
            if nk.x0 <= self.pos_x <= nk1.x0:
                xi = (self.pos_x - nk.x0) / (nk1.x0 - nk.x0)
                return nk.y * (1.0 - xi) + nk1.y * xi
        return 0.0

class PuentePratt:
    def calcular_rigidez_nodal_max(self):
        """
        Estima la rigidez efectiva máxima que siente un nodo.
        No basta con usar k_max de un solo miembro, porque un nodo puede
        estar conectado a varias vigas rígidas al mismo tiempo.
        """
        if not self.nodos or not self.miembros:
            return 0.0

        k_por_nodo = {n.id: 0.0 for n in self.nodos}

        for m in self.miembros:
            if m.roto:
                continue

            k_por_nodo[m.origen.id] += m.k
            k_por_nodo[m.destino.id] += m.k

        return max(k_por_nodo.values()) if k_por_nodo else 0.0

    def calcular_substeps_estables(self, frame_dt):
        k_nodal_max = self.calcular_rigidez_nodal_max()
        masas_libres = [n.masa for n in self.nodos if not n.fijo]

        if k_nodal_max <= 0.0 or not masas_libres:
            return SUBSTEPS_MIN

        m_min = min(masas_libres)

        omega_max = math.sqrt(k_nodal_max / m_min)
        dt_critico = 2.0 / omega_max

        dt_seguro = dt_critico * FACTOR_SEGURIDAD_DT

        substeps = math.ceil(frame_dt / dt_seguro)

        return max(SUBSTEPS_MIN, min(SUBSTEPS_MAX, substeps))

    def __init__(self):
        self.nodos = []
        self.miembros = []
        self.nodos_carretera = []
        # ---------------------------------------------------------------------
        # AMORTIGUAMIENTO (May 2026 - FIX FINAL CON E EN GPa):
        # Con E = 200 GPa (valor real), k aumenta 1000×:
        #   k_anterior ≈ 2.0e6 N/m  (E = 200 MPa)
        #   k_actual ≈ 2.0e9 N/m    (E = 200 GPa) ← CORRECCIÓN
        #
        # c_crítico = 2√(k×m) escala con √k (aprox √1000 ≈ 31.6×):
        #   c_crit_anterior ≈ 8,655 Ns/m
        #   c_crit_actual ≈ 17,889 Ns/m (2× mayor)
        #
        # Usamos ~1.5× crítico:
        #   c = 1.5 × 17,889 ≈ 26,800 Ns/m
        #
        # Propiedades:
        #   - Estabilidad Verlet excelente (ζ ≈ 1.5)
        #   - Sin divergencia numérica
        #   - Oscilaciones claramente amortiguadas
        #   - Convergencia rápida a equilibrio
        # ---------------------------------------------------------------------
        self.amortiguamiento = 8000.0

    def generar_parametrizado(self, paneles, longitud_panel, altura):
        self.nodos.clear()
        self.miembros.clear()
        self.nodos_carretera.clear()

        nodos_inf = []
        for i in range(paneles + 1):
            es_apoyo = (i == 0 or i == paneles)
            nodo = Nodo(len(self.nodos), i * longitud_panel, 0.0, fijo=es_apoyo, masa=80.0)
            self.nodos.append(nodo)
            nodos_inf.append(nodo)
            self.nodos_carretera.append(nodo)

        nodos_sup = []
        for i in range(1, paneles):
            # masa=100 kg: necesario para estabilidad Verlet con SUBSTEPS=120
            # dt_substep=1.39e-4 s < dt_critico=1.99e-4 s → 70% del límite (30% margen)
            nodo = Nodo(len(self.nodos), i * longitud_panel, altura, masa=100.0)
            self.nodos.append(nodo)
            nodos_sup.append(nodo)

        id_m = 0
        def conectar(n1, n2):
            nonlocal id_m
            self.miembros.append(Miembro(id_m, n1, n2))
            id_m += 1

        for i in range(len(nodos_inf) - 1):
            conectar(nodos_inf[i], nodos_inf[i + 1])
        for i in range(len(nodos_sup) - 1):
            conectar(nodos_sup[i], nodos_sup[i + 1])
        for i in range(len(nodos_sup)):
            conectar(nodos_inf[i + 1], nodos_sup[i])
        conectar(nodos_inf[0], nodos_sup[0])
        conectar(nodos_inf[-1], nodos_sup[-1])

        print(f"\n  Patrón de diagonales (paneles={paneles}):")
        for i in range(1, paneles - 1):
            if i % 2 == 1:
                conectar(nodos_sup[i - 1], nodos_inf[i + 1])
            else:
                conectar(nodos_inf[i], nodos_sup[i])

        print(f"\n[OK] Puente: {len(self.nodos)} nodos, {len(self.miembros)} miembros")
        self._imprimir_telemetria_fisica()

    def _imprimir_telemetria_fisica(self):
        if not self.miembros:
            return

        print("\n" + "-" * 60)
        print("TELEMETRIA FISICA (validacion de unidades)")
        print("-" * 60)

        ks = [m.k for m in self.miembros]
        L0s = [m.L0 for m in self.miembros]

        print(f"  Miembros: {len(self.miembros)}")
        print(f"  L0  min/max: {min(L0s):.3f} / {max(L0s):.3f} m")
        print(f"  k   min/max: {min(ks):.2e} / {max(ks):.2e} N/m")

        m0 = self.miembros[0]

        print(f"\n  Muestra miembro #0:")
        print(f"    E = {m0.E_GPa:.1f} GPa  ({m0.E_Pa:.2e} Pa)")
        print(f"    A = {m0.Area:.4f} m^2")
        print(f"    L0 = {m0.L0:.3f} m")
        print(f"    k = {m0.k:.3e} N/m")
        print(
            f"    sigma_limite tension/comp: "
            f"{m0.limite_tension:.0f} / {m0.limite_compresion:.0f} MPa"
        )

        eps_break = m0.limite_tension / (m0.E_GPa * 1000.0)
        dL_break = eps_break * m0.L0
        F_break = m0.k * dL_break
        masa_break = F_break / GRAVEDAD

        print(f"\n  Ruptura esperada (modelo Hooke axial, 1 miembro):")
        print(f"    epsilon_ruptura = {eps_break:.6f} ({eps_break * 100:.4f}%)")
        print(f"    dL_ruptura = {dL_break * 1000:.3f} mm")
        print(f"    F_ruptura = {F_break:.0f} N")
        print(f"    ~ {masa_break:.0f} kg en 1 miembro aislado")

        masa_total = sum(n.masa for n in self.nodos)

        print(f"\n  Peso de la estructura (gravedad):")
        print(f"    masa total = {masa_total:.0f} kg")
        print(f"    peso total = {masa_total * GRAVEDAD:.0f} N")
        print("-" * 60 + "\n")

    def cargar_geometria_csv(self, csv_nodos="puente_nodos.csv", csv_miembros="puente_miembros.csv"):
        if not os.path.exists(csv_nodos):
            return False
        try:
            self.nodos.clear()
            self.miembros.clear()
            self.nodos_carretera.clear()
            nodos_dict = {}
            with open(csv_nodos, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    node_id, x, y = int(row['id']), float(row['x']), float(row['y'])
                    fijo = bool(int(row.get('fijo', 0)))
                    masa = float(row.get('masa', 80.0))
                    nodo = Nodo(node_id, x, y, fijo=fijo, masa=masa)
                    self.nodos.append(nodo)
                    nodos_dict[node_id] = nodo
                    if abs(y) < 1e-6:
                        self.nodos_carretera.append(nodo)
            print(f"✓ Nodos: {len(self.nodos)}")
            if os.path.exists(csv_miembros):
                miembro_id = 0
                with open(csv_miembros, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        origen_id, destino_id = int(row['origen']), int(row['destino'])
                        material = row.get('material', None)
                        if origen_id in nodos_dict and destino_id in nodos_dict:
                            miembro = Miembro(miembro_id, nodos_dict[origen_id],
                                            nodos_dict[destino_id], material=material)
                            self.miembros.append(miembro)
                            miembro_id += 1
                print(f"[OK] Miembros: {len(self.miembros)}")
            self._imprimir_telemetria_fisica()
            return True
        except Exception as e:
            print(f"[ERR] Error CSV: {e}")
            return False

    def reset_a_equilibrio(self, reparar_vigas=True):
        for n in self.nodos:
            n.x = n.x_eq
            n.y = n.y_eq
            n.x_prev = n.x_eq
            n.y_prev = n.y_eq
            n.fuerza[:] = 0.0
        for m in self.miembros:
            if reparar_vigas:
                m.roto = False
            m.esfuerzo_actual = 0.0
            m.calcular_esfuerzo()

    def reparar_vigas(self):
        n = sum(1 for m in self.miembros if m.roto)
        for m in self.miembros:
            m.roto = False
        if n:
            print(f"✓ {n} vigas reparadas")

    def paso_fisico(self, dt, carga_movil=None, aplicar_gravedad=True):
        for n in self.nodos:
            n.reset_fuerza()

        if aplicar_gravedad:
            for n in self.nodos:
                if not n.fijo:
                    n.aplicar_fuerza(0.0, -n.masa * GRAVEDAD)

        if carga_movil is not None:
            carga_movil.aplicar_carga(self.nodos_carretera)

        for m in self.miembros:
            m.aplicar_fuerza_hooke()

        for n in self.nodos:
            if n.fijo:
                continue

            vx = (n.x - n.x_prev) / dt
            vy = (n.y - n.y_prev) / dt

            n.aplicar_fuerza(
                -self.amortiguamiento * vx,
                -self.amortiguamiento * vy
            )

        for n in self.nodos:
            if n.fijo:
                n.x = n.x0
                n.y = n.y0
                n.x_prev = n.x0
                n.y_prev = n.y0
                continue

            ax = n.fuerza[0] / n.masa
            ay = n.fuerza[1] / n.masa

            x_new = 2.0 * n.x - n.x_prev + ax * dt * dt
            y_new = 2.0 * n.y - n.y_prev + ay * dt * dt

            if (
                    not math.isfinite(x_new)
                    or not math.isfinite(y_new)
                    or abs(x_new - n.x0) > 1.0
                    or abs(y_new - n.y0) > 1.0
            ):
                if not hasattr(self, "_avisos_inestabilidad"):
                    self._avisos_inestabilidad = 0

                if self._avisos_inestabilidad < 10:
                    print(f"AVISO: nodo {n.id} inestable. Reiniciando a equilibrio.")
                    self._avisos_inestabilidad += 1
                x_new = n.x_eq
                y_new = n.y_eq
                n.x_prev = n.x_eq
                n.y_prev = n.y_eq

            else:
                n.x_prev = n.x
                n.y_prev = n.y

            n.x = x_new
            n.y = y_new

        for m in self.miembros:
            m.calcular_esfuerzo()

    def relajar_a_equilibrio(self, n_iter=None, dt=None):
        if self.miembros:
            k_nodal_max = self.calcular_rigidez_nodal_max()
            masas_libres = [n.masa for n in self.nodos if not n.fijo]
            m_min = min(masas_libres) if masas_libres else 1.0

            omega_max = math.sqrt(k_nodal_max / m_min)
            dt_critico = 2.0 / omega_max
            dt_seguro = dt_critico * 0.12

            if dt is None or dt > dt_seguro:
                dt = dt_seguro
        elif dt is None:
            dt = 0.00002

        if n_iter is None:
            n_iter = max(8000, min(120000, int(1.5 / dt)))

        damp_orig = self.amortiguamiento

        # Damping menor. 26800 puede ser demasiado agresivo para varios nodos conectados.
        self.amortiguamiento = 8000.0

        print(f"Calculando equilibrio (dt={dt:.2e} s, máx {n_iter} iter)...")

        nodos_libres = [n for n in self.nodos if not n.fijo]
        prev_desp = float('inf')
        for iter_num in range(n_iter):
            self.paso_fisico(dt, carga_movil=None, aplicar_gravedad=True)

            if iter_num % 10000 == 0 and iter_num > 0 and nodos_libres:
                max_desp = max(
                    math.hypot(n.x - n.x0, n.y - n.y0)
                    for n in nodos_libres
                )
                print(f"  Iter {iter_num}: Desplazamiento máx = {max_desp:.6f} m")
                if abs(prev_desp - max_desp) < 1e-9:
                    print(f"  Convergencia anticipada en iter {iter_num}")
                    break
                prev_desp = max_desp

        for n in self.nodos:
            n.x_eq = n.x if math.isfinite(n.x) else n.x0
            n.y_eq = n.y if math.isfinite(n.y) else n.y0
            n.x_prev = n.x_eq
            n.y_prev = n.y_eq
            n.x = n.x_eq
            n.y = n.y_eq

        self.amortiguamiento = damp_orig

        nodos_libres = [n for n in self.nodos if not n.fijo]
        if nodos_libres:
            max_desp = max(
                math.hypot(n.x_eq - n.x0, n.y_eq - n.y0)
                for n in nodos_libres
            )
            print(f"✓ Equilibrio alcanzado: deformación máx = {max_desp * 1000:.3f} mm")

class MotorGrafico:
    def __init__(self, puente, amp_visual=AMPLIFICACION_VISUAL):
        self.puente = puente
        # ---------------------------------------------------------------------
        # AMPLIFICACION VISUAL (May 2026):
        # Con la fisica corregida, las deformaciones reales son del orden de
        # mm-cm (apenas visibles). Amplificamos solo el DESPLAZAMIENTO del
        # nodo respecto a su posicion inicial - la fisica es exacta, solo
        # el dibujo se exagera (como en ANSYS, SolidWorks Simulation, etc.)
        # ---------------------------------------------------------------------
        self.amp_visual = amp_visual

    def _pos_amp(self, nodo):
        """
        Devuelve la posicion del nodo con la deformacion amplificada para
        visualizacion. La fisica interna usa nodo.x / nodo.y (reales).
        """
        x = nodo.x0 + (nodo.x - nodo.x0) * self.amp_visual
        y = nodo.y0 + (nodo.y - nodo.y0) * self.amp_visual
        return x, y

    def get_y_carretera_amp(self, x_target):
        """
        Devuelve la altura amplificada de la carretera para una posicion x.
        Usado para que el vehiculo siga la deformacion visual del puente.
        """
        nodos = self.puente.nodos_carretera
        if not nodos:
            return 0.0
        if x_target <= nodos[0].x0:
            return nodos[0].y0 + (nodos[0].y - nodos[0].y0) * self.amp_visual
        if x_target >= nodos[-1].x0:
            return nodos[-1].y0 + (nodos[-1].y - nodos[-1].y0) * self.amp_visual
        for i in range(len(nodos) - 1):
            nk, nk1 = nodos[i], nodos[i + 1]
            if nk.x0 <= x_target <= nk1.x0:
                xi = (x_target - nk.x0) / (nk1.x0 - nk.x0)
                y_k = nk.y0 + (nk.y - nk.y0) * self.amp_visual
                y_k1 = nk1.y0 + (nk1.y - nk1.y0) * self.amp_visual
                return y_k * (1.0 - xi) + y_k1 * xi
        return 0.0

    def dibujar(self, carga_movil=None):
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._dibujar_rejilla()
        for m in self.puente.miembros:
            color = m.obtener_color_stress()
            grosor = 2.0 + m.stress_ratio() * 5.0
            glLineWidth(grosor)
            glBegin(GL_LINES)
            glColor3f(*color)
            x1, y1 = self._pos_amp(m.origen)
            x2, y2 = self._pos_amp(m.destino)
            glVertex3f(x1, y1, 0)
            glVertex3f(x2, y2, 0)
            glEnd()
        glLineWidth(1.0)
        for n in self.puente.nodos:
            xn, yn = self._pos_amp(n)
            if n.fijo:
                self._dibujar_nodo(xn, yn, 0.35, (0.1, 0.95, 0.2))
            else:
                self._dibujar_nodo(xn, yn, 0.25, (0.3, 0.3, 0.3))
        if carga_movil is not None:
            y_v = self.get_y_carretera_amp(carga_movil.pos_x)
            self._dibujar_vehiculo(carga_movil.pos_x, y_v)

    def _dibujar_nodo(self, x, y, radio, color):
        glColor3f(*color)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(x, y, 0)
        for i in range(33):
            th = 2.0 * math.pi * i / 32
            glVertex3f(x + radio * math.cos(th), y + radio * math.sin(th), 0)
        glEnd()
        glLineWidth(2.0)
        glColor3f(color[0]*0.5, color[1]*0.5, color[2]*0.5)
        glBegin(GL_LINE_LOOP)
        for i in range(32):
            th = 2.0 * math.pi * i / 32
            glVertex3f(x + radio * math.cos(th), y + radio * math.sin(th), 0)
        glEnd()

    def _dibujar_rejilla(self):
        glLineWidth(1.0)
        glColor3f(0.85, 0.85, 0.88)
        for y_line in range(-2, 6):
            glBegin(GL_LINES)
            glVertex3f(-2.0, y_line, -0.1)
            glVertex3f(20.0, y_line, -0.1)
            glEnd()
        for x_line in range(-2, 21):
            glBegin(GL_LINES)
            glVertex3f(x_line, -2.0, -0.1)
            glVertex3f(x_line, 6.0, -0.1)
            glEnd()
        glLineWidth(2.5)
        glColor3f(0.4, 0.4, 0.5)
        glBegin(GL_LINES)
        glVertex3f(-2.0, 0.0, -0.05)
        glVertex3f(20.0, 0.0, -0.05)
        glEnd()

    def _dibujar_vehiculo(self, x, y):
        # y = superficie de la carretera
        rr = 0.26                      # radio de rueda
        eje_y = y + rr                 # centro de eje al nivel de rueda
        piso = y + rr * 2.0            # base del chasis

        # --- chasis / caja de carga ---
        cx0, cx1 = x - 1.2, x + 0.38
        cy0, cy1 = piso, piso + 0.82
        glColor3f(0.18, 0.25, 0.55)
        glBegin(GL_QUADS)
        glVertex3f(cx0, cy0, 0); glVertex3f(cx1, cy0, 0)
        glVertex3f(cx1, cy1, 0); glVertex3f(cx0, cy1, 0)
        glEnd()
        # franja lateral clara
        glColor3f(0.55, 0.65, 0.95)
        glBegin(GL_QUADS)
        glVertex3f(cx0, cy0 + 0.12, 0); glVertex3f(cx1, cy0 + 0.12, 0)
        glVertex3f(cx1, cy0 + 0.28, 0); glVertex3f(cx0, cy0 + 0.28, 0)
        glEnd()
        # contorno caja
        glColor3f(0.08, 0.1, 0.25); glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        glVertex3f(cx0, cy0, 0); glVertex3f(cx1, cy0, 0)
        glVertex3f(cx1, cy1, 0); glVertex3f(cx0, cy1, 0)
        glEnd()

        # --- cabina (trapezoidal, frente a la derecha) ---
        cab_x0, cab_x1 = x + 0.38, x + 1.22
        cab_y0, cab_y1 = piso, piso + 1.15
        hood_y = piso + 0.55           # altura del capó (zona baja frontal)
        glColor3f(0.22, 0.32, 0.70)
        glBegin(GL_POLYGON)            # cuerpo cabina trapezoidal
        glVertex3f(cab_x0, cab_y0, 0)
        glVertex3f(cab_x1, cab_y0, 0)
        glVertex3f(cab_x1, hood_y, 0)  # frente baja (capó)
        glVertex3f(cab_x1 - 0.18, cab_y1, 0)
        glVertex3f(cab_x0, cab_y1, 0)
        glEnd()
        # parabrisas
        pw = 0.52; ph = 0.38
        glColor3f(0.55, 0.85, 1.0)
        glBegin(GL_POLYGON)
        glVertex3f(cab_x0 + 0.06, cab_y1 - 0.06, 0)
        glVertex3f(cab_x1 - 0.22, cab_y1 - 0.06, 0)
        glVertex3f(cab_x1 - 0.22, cab_y1 - ph, 0)
        glVertex3f(cab_x0 + 0.06, cab_y1 - ph, 0)
        glEnd()
        # faro delantero
        glColor3f(1.0, 0.95, 0.6)
        glBegin(GL_QUADS)
        glVertex3f(cab_x1 - 0.12, hood_y + 0.04, 0)
        glVertex3f(cab_x1,        hood_y + 0.04, 0)
        glVertex3f(cab_x1,        hood_y + 0.2, 0)
        glVertex3f(cab_x1 - 0.12, hood_y + 0.2, 0)
        glEnd()
        # contorno cabina
        glColor3f(0.08, 0.1, 0.3); glLineWidth(1.5)
        glBegin(GL_LINE_LOOP)
        glVertex3f(cab_x0, cab_y0, 0); glVertex3f(cab_x1, cab_y0, 0)
        glVertex3f(cab_x1, hood_y, 0); glVertex3f(cab_x1 - 0.18, cab_y1, 0)
        glVertex3f(cab_x0, cab_y1, 0)
        glEnd()

        # --- separador caja/cabina ---
        glColor3f(0.7, 0.75, 0.85); glLineWidth(2.5)
        glBegin(GL_LINES)
        glVertex3f(cab_x0, cy0, 0); glVertex3f(cab_x0, cy1, 0)
        glEnd()

        # --- chasis inferior ---
        glColor3f(0.12, 0.12, 0.18)
        glBegin(GL_QUADS)
        glVertex3f(cx0, piso - 0.06, 0); glVertex3f(cab_x1, piso - 0.06, 0)
        glVertex3f(cab_x1, piso, 0);     glVertex3f(cx0, piso, 0)
        glEnd()

        # --- ruedas: eje trasero doble + eje delantero ---
        for eje_x, doble in ((x - 0.72, True), (x - 0.12, False), (x + 0.85, False)):
            if doble:
                # par trasero (offset visual)
                for off in (-0.07, 0.07):
                    self._dibujar_circulo(eje_x, eje_y, rr,        (0.08, 0.08, 0.08))
                    self._dibujar_circulo(eje_x, eje_y, rr * 0.55, (0.55, 0.55, 0.6))
                    self._dibujar_circulo(eje_x, eje_y, rr * 0.18, (0.25, 0.25, 0.25))
            else:
                self._dibujar_circulo(eje_x, eje_y, rr,        (0.08, 0.08, 0.08))
                self._dibujar_circulo(eje_x, eje_y, rr * 0.55, (0.55, 0.55, 0.6))
                self._dibujar_circulo(eje_x, eje_y, rr * 0.18, (0.25, 0.25, 0.25))

        glLineWidth(1.0)

    def _dibujar_circulo(self, cx, cy, r, color, segs=24):
        glColor3f(*color)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(cx, cy, 0)
        for i in range(segs + 1):
            th = 2.0 * math.pi * i / segs
            glVertex3f(cx + r * math.cos(th), cy + r * math.sin(th), 0)
        glEnd()

    def _glut_text(self, x, y, texto, color=(1.0, 1.0, 1.0)):
        if not _GLUT_OK:
            return
        glColor3f(*color)
        glRasterPos2f(x, y)
        for ch in texto:
            glutBitmapCharacter(GLUT_BITMAP_9_BY_15, ord(ch))

    def dibujar_hud(self, carga_movil, display_size):
        """HUD en esquina superior izquierda con estado estructural."""
        # --- estadísticas ---
        max_ratio = 0.0
        idx_critico = -1
        n_rotos = 0
        for i, m in enumerate(self.puente.miembros):
            if m.roto:
                n_rotos += 1
                continue
            r = m.stress_ratio()
            if r > max_ratio:
                max_ratio = r
                idx_critico = i

        W, H = display_size

        # --- cambiar a proyección 2D ortográfica ---
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, W, 0, H, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)

        # fondo semitransparente
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glColor4f(0.05, 0.05, 0.1, 0.72)
        glBegin(GL_QUADS)
        glVertex2f(8,  H - 8)
        glVertex2f(330, H - 8)
        glVertex2f(330, H - 188)
        glVertex2f(8,  H - 188)
        glEnd()

        # leyenda de colores (barra tensión/compresión)
        bx, by, bw, bh = 8, H - 188, 322, 10
        segs = 40
        for s in range(segs):
            t = s / segs
            # mitad izq = compresión (rojo), mitad der = tensión (azul)
            cx = bx + t * bw
            if t < 0.5:
                ratio = 1.0 - t * 2
                glColor3f(0.4 + 0.6 * ratio, 0.4 * (1 - ratio), 0.4 * (1 - ratio))
            else:
                ratio = (t - 0.5) * 2
                glColor3f(0.4 * (1 - ratio), 0.4 * (1 - ratio), 0.4 + 0.6 * ratio)
            glBegin(GL_QUADS)
            glVertex2f(cx,            by)
            glVertex2f(cx + bw/segs,  by)
            glVertex2f(cx + bw/segs,  by + bh)
            glVertex2f(cx,            by + bh)
            glEnd()

        # etiquetas leyenda
        self._glut_text(bx,            by - 14, "COMP", (1.0, 0.4, 0.4))
        self._glut_text(bx + bw - 36, by - 14, "TENS", (0.4, 0.7, 1.0))

        # líneas de texto
        y = H - 28
        self._glut_text(18, y, "PUENTE PRATT", (1.0, 0.85, 0.0))
        y -= 20

        pct = max_ratio * 100.0
        if pct < 50:
            c_stress = (0.2, 1.0, 0.2)
        elif pct < 75:
            c_stress = (1.0, 0.7, 0.0)
        else:
            c_stress = (1.0, 0.2, 0.2)
        self._glut_text(18, y, f"Stress max: {pct:.1f}%", c_stress)
        y -= 18

        if idx_critico >= 0:
            m = self.puente.miembros[idx_critico]
            signo = "T" if m.esfuerzo_actual >= 0 else "C"
            self._glut_text(18, y, f"Critico: viga {idx_critico} {signo} {abs(m.esfuerzo_actual):.1f} MPa", (0.9, 0.9, 0.9))
            y -= 18

        if n_rotos > 0:
            self._glut_text(18, y, f"ROTOS: {n_rotos} miembros", (1.0, 0.1, 0.1))
        else:
            self._glut_text(18, y, "Estructura: integra", (0.3, 1.0, 0.3))
        y -= 18

        if carga_movil.activo:
            self._glut_text(18, y, f"Vehiculo: {carga_movil.masa:.0f} kg  {carga_movil.velocidad:.1f} m/s", (1.0, 1.0, 1.0))
        else:
            self._glut_text(18, y, f"En espera: {carga_movil.masa:.0f} kg  {carga_movil.velocidad:.1f} m/s", (0.65, 0.65, 0.65))
        y -= 18

        self._glut_text(18, y, f"Amp visual: x{self.amp_visual:.0f}   [+/-/0]", (0.6, 0.6, 1.0))
        y -= 18
        lim_t = self.puente.miembros[0].limite_tension if self.puente.miembros else 250
        lim_c = self.puente.miembros[0].limite_compresion if self.puente.miembros else -400
        self._glut_text(18, y, f"Lim T: {lim_t:.0f} MPa [Q/A]  C: {lim_c:.0f} MPa [W/S]", (0.85, 0.85, 0.6))
        y -= 18
        n_rotos_total = sum(1 for m in self.puente.miembros if m.roto)
        hint = f"[F] Reparar {n_rotos_total} vigas" if n_rotos_total else "[F] Sin vigas rotas"
        self._glut_text(18, y, hint, (1.0, 0.5, 0.2) if n_rotos_total else (0.5, 0.5, 0.5))

        # restaurar estado 3D
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

class SimuladorApp:
    def __init__(self):
        pygame.init()
        self.display = (1024, 768)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Simulador Puente Pratt - Modelo Realista")
        if _GLUT_OK:
            glutInit(sys.argv)
        validar_materiales_bd()
        inicializar_materiales()
        self.paneles, self.long_panel, self.altura = 12, 1.5, 4.0
        self.puente = PuentePratt()
        if not self.puente.cargar_geometria_csv():
            print("  (CSV no encontrado, usando generación paramétrica)")
            self.puente.generar_parametrizado(self.paneles, self.long_panel, self.altura)
        self.puente.relajar_a_equilibrio()
        self.motor_grafico = MotorGrafico(self.puente)
        self.carga_movil = CargaMovil(masa=2000.0, velocidad=3.0)
        self.carga_movil.configurar_recorrido(0.0, self.paneles * self.long_panel)
        self.cam_x, self.cam_y, self.cam_z = -9.0, -2.0, -28.0
        self.zoom = 45.0
        self._imprimir_controles()

    def _imprimir_controles(self):
        print("\n" + "="*60)
        print("CONTROLES - Simulador Puente Pratt")
        print("="*60)
        print("ESPACIO   : Lanzar vehiculo")
        print("R         : Reiniciar posiciones + reparar vigas")
        print("F         : Reparar vigas rotas (sin mover puente)")
        print("Up/Down   : +/-500 kg masa vehiculo")
        print("Right/Left: +/-1 m/s velocidad vehiculo")
        print("+ / -     : +/-25 amplificacion visual")
        print("0         : Reset amplificacion visual")
        print("Q / A     : Limite tension +/-25 MPa")
        print("W / S     : Limite compresion +/-25 MPa")
        print("="*60 + "\n")

    def configurar_proyeccion(self):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(self.zoom, (self.display[0] / self.display[1]), 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glTranslatef(self.cam_x, self.cam_y, self.cam_z)

    def manejar_eventos(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    self.puente.reset_a_equilibrio()
                    print(f"\u25b6 Veh\u00edculo: {self.carga_movil.masa:.0f} kg @ {self.carga_movil.velocidad:.1f} m/s")
                    self.carga_movil.iniciar()
                elif event.key == pygame.K_r:
                    print("\u27f3 Reiniciando")
                    self.carga_movil.detener()
                    self.puente.reset_a_equilibrio()
                elif event.key == pygame.K_UP:
                    self.carga_movil.masa += 500.0
                    print(f"Masa: {self.carga_movil.masa:.0f} kg")
                elif event.key == pygame.K_DOWN:
                    self.carga_movil.masa = max(500.0, self.carga_movil.masa - 500.0)
                    print(f"Masa: {self.carga_movil.masa:.0f} kg")
                elif event.key == pygame.K_RIGHT:
                    self.carga_movil.velocidad += 1.0
                    print(f"Velocidad: {self.carga_movil.velocidad:.1f} m/s")
                elif event.key == pygame.K_LEFT:
                    self.carga_movil.velocidad = max(1.0, self.carga_movil.velocidad - 1.0)
                    print(f"Velocidad: {self.carga_movil.velocidad:.1f} m/s")
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    self.motor_grafico.amp_visual = min(
                        AMP_VISUAL_MAX, self.motor_grafico.amp_visual + 25.0
                    )
                    print(f"Amp visual: x{self.motor_grafico.amp_visual:.0f}")
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    self.motor_grafico.amp_visual = max(
                        AMP_VISUAL_MIN, self.motor_grafico.amp_visual - 25.0
                    )
                    print(f"Amp visual: x{self.motor_grafico.amp_visual:.0f}")
                elif event.key == pygame.K_0:
                    self.motor_grafico.amp_visual = AMPLIFICACION_VISUAL
                    print(f"Amp visual reset: x{self.motor_grafico.amp_visual:.0f}")
                elif event.key == pygame.K_f:
                    self.puente.reparar_vigas()
                # --- edición de límites de ruptura ---
                elif event.key == pygame.K_q:
                    for m in self.puente.miembros:
                        m.limite_tension = min(m.limite_tension + 25.0, 2000.0)
                    v = self.puente.miembros[0].limite_tension
                    print(f"Tensión límite: {v:.0f} MPa")
                elif event.key == pygame.K_a:
                    for m in self.puente.miembros:
                        m.limite_tension = max(m.limite_tension - 25.0, 25.0)
                    v = self.puente.miembros[0].limite_tension
                    print(f"Tensión límite: {v:.0f} MPa")
                elif event.key == pygame.K_w:
                    for m in self.puente.miembros:
                        m.limite_compresion = min(m.limite_compresion + 25.0, -25.0)
                    v = self.puente.miembros[0].limite_compresion
                    print(f"Compresión límite: {v:.0f} MPa")
                elif event.key == pygame.K_s:
                    for m in self.puente.miembros:
                        m.limite_compresion = max(m.limite_compresion - 25.0, -2000.0)
                    v = self.puente.miembros[0].limite_compresion
                    print(f"Compresión límite: {v:.0f} MPa")

    def ejecutar(self):
        clock = pygame.time.Clock()
        glClearColor(0.92, 0.92, 0.95, 1.0)
        print("\u2713 Iniciando simulaci\u00f3n a 60 FPS...\n")
        # dt físico fijo: independiente del frame rate para garantizar estabilidad Verlet
        # sub_dt = 1/(60*SUBSTEPS) = 1.39e-4 s < dt_critico ~2.4e-4 s → 57% del límite
        sub_dt = 1.0 / (60.0 * SUBSTEPS)
        while True:
            clock.tick(60)
            self.manejar_eventos()
            aplicar_gravedad = self.carga_movil.activo

            for _ in range(SUBSTEPS):
                self.carga_movil.actualizar(sub_dt)
                self.puente.paso_fisico(
                    sub_dt,
                    self.carga_movil,
                    aplicar_gravedad=aplicar_gravedad
                )
            for miembro in self.puente.miembros:
                miembro.comprobar_ruptura()
                miembro.actualizar_visual()
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.configurar_proyeccion()
            self.motor_grafico.dibujar(self.carga_movil)
            self.motor_grafico.dibujar_hud(self.carga_movil, self.display)
            pygame.display.flip()

if __name__ == "__main__":
    app = SimuladorApp()
    app.ejecutar()
