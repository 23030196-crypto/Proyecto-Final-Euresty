"""
SIMULADOR DE PUENTE PRATT - VERSIÓN FINAL VISUAL (Sprint 3)
===========================================================

ESTRUCTURA FÍSICA:
✓ 12 paneles con 5 diagonales UP + 5 DOWN (perfectamente simétrico)
✓ BUG 1: Control inteligente de gravedad
✓ BUG 2: Vehículo visible (altura ajustada a 0.8 unidades)
✓ BUG 3: Amortiguamiento optimizado (5500 Ns/m)
✓ BUG 4: Viga diagonal en punto medio (cambio en mitad)

DISEÑO VISUAL MEJORADO 🎨:
✓ Líneas dinámicas: Grosor variable según esfuerzo (2.5 a 7.0 px)
✓ Colores mejorados: Azul/Cian para tensión, Rojo/Naranja para compresión
✓ Nodos grandes: Círculos rellenos con borde (0.25-0.35 radio)
✓ Apoyos verdes: Puntos fijos destacados en verde brillante
✓ Vehículo llamativo: Naranja brillante con ventana cian y ruedas detalladas
✓ Rejilla de referencia: Contexto visual profesional
✓ Blend y antialiasing: Suavizado de líneas y transparencia

PARÁMETROS FÍSICOS:
- Paneles: 12 (longitud 1.5 u/panel)
- Amortiguamiento: 5500 Ns/m
- Amortiguamiento equilibrio: 30000 Ns/m
- Gravedad: 9.81 m/s²
- Substeps: 25

MATEMÁTICAS:
✓ Verlet Integration: x_new = 2x - x_prev + a*dt²
✓ Hooke's Law: F = k * (L - L₀)
✓ Viscous Damping: F_d = -c * v
✓ Linear Interpolation: Distribución de carga
"""

import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import sys

GRAVEDAD = 9.81
SUBSTEPS = 25
UMBRAL_ESFUERZO = 50000.0


class Nodo:
    def __init__(self, id_nodo, x, y, fijo=False, masa=80.0):
        self.id = id_nodo
        self.x0 = x
        self.y0 = y
        self.x_eq = x
        self.y_eq = y
        self.x = x
        self.y = y
        self.x_prev = x
        self.y_prev = y
        self.fijo = fijo
        self.masa = masa
        self.fuerza = np.array([0.0, 0.0])

    @property
    def pos_actual(self):
        return (self.x, self.y)

    def reset_fuerza(self):
        self.fuerza[0] = 0.0
        self.fuerza[1] = 0.0

    def aplicar_fuerza(self, fx, fy):
        self.fuerza[0] += fx
        self.fuerza[1] += fy


class Miembro:
    def __init__(self, id_miembro, nodo_origen, nodo_destino, E=1.0e9, area=0.01):
        self.id = id_miembro
        self.origen = nodo_origen
        self.destino = nodo_destino
        self.E = E
        self.Area = area
        self.esfuerzo_actual = 0.0

        dx = self.destino.x0 - self.origen.x0
        dy = self.destino.y0 - self.origen.y0
        self.L0 = math.hypot(dx, dy)
        self.k = self.E * self.Area / self.L0

    def longitud_actual(self):
        dx = self.destino.x - self.origen.x
        dy = self.destino.y - self.origen.y
        return math.hypot(dx, dy)

    def calcular_esfuerzo(self):
        L = self.longitud_actual()
        if L < 1e-9:
            self.esfuerzo_actual = 0.0
            return 0.0
        epsilon = (L - self.L0) / self.L0
        self.esfuerzo_actual = self.E * epsilon
        return self.esfuerzo_actual

    def aplicar_fuerza_hooke(self):
        L = self.longitud_actual()
        if L < 1e-9:
            return
        delta_L = L - self.L0
        F = self.k * delta_L
        ux = (self.destino.x - self.origen.x) / L
        uy = (self.destino.y - self.origen.y) / L
        fx = F * ux
        fy = F * uy
        self.origen.aplicar_fuerza(fx, fy)
        self.destino.aplicar_fuerza(-fx, -fy)

    def obtener_color_stress(self):
        """Colores dinámicos basados en esfuerzo - ¡MÁS LLAMATIVO!"""
        intensidad = min(abs(self.esfuerzo_actual) / UMBRAL_ESFUERZO, 1.0)

        if self.esfuerzo_actual > 3000:
            # Tensión FUERTE: Azul brillante → Cyan
            r = 0.0
            g = 0.5 + intensidad * 0.5  # Verde hasta 1.0
            b = 0.7 + intensidad * 0.3  # Azul hasta 1.0
        elif self.esfuerzo_actual > 1000:
            # Tensión moderada: Azul
            r = 0.0
            g = 0.3 + intensidad * 0.3
            b = 0.3 + intensidad * 0.7
        elif self.esfuerzo_actual < -3000:
            # Compresión FUERTE: Rojo brillante → Naranja
            r = 0.9 + intensidad * 0.1
            g = 0.3 + intensidad * 0.4
            b = 0.0
        elif self.esfuerzo_actual < -1000:
            # Compresión moderada: Rojo
            r = 0.6 + intensidad * 0.4
            g = 0.1 + intensidad * 0.2
            b = 0.0
        else:
            # Sin esfuerzo significativo: Gris claro
            r = 0.4
            g = 0.4
            b = 0.4

        return (r, g, b)


class CargaMovil:
    def __init__(self, masa=2000.0, velocidad=3.0):
        self.masa = masa
        self.velocidad = velocidad
        self.pos_x = 0.0
        self.activo = False
        self.x_min = 0.0
        self.x_max = 0.0
        self._idx_cache = 0

    def configurar_recorrido(self, x_min, x_max):
        self.x_min = x_min
        self.x_max = x_max
        self.pos_x = x_min

    def iniciar(self):
        self.pos_x = self.x_min
        self._idx_cache = 0  # 🌟 FIX CRÍTICO: Reiniciar la búsqueda desde el primer panel
        self.activo = True

    def detener(self):
        self.activo = False
        self.pos_x = self.x_min
        self._idx_cache = 0  # 🌟 FIX: Asegurar que quede limpio

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
                Fk = peso * (1.0 - xi)
                Fk1 = peso * xi
                nk.aplicar_fuerza(0.0, -Fk)
                nk1.aplicar_fuerza(0.0, -Fk1)
                self._idx_cache = i
                break

    def get_pos_y(self, nodos_carretera):
        if self.pos_x <= nodos_carretera[0].x0:
            return nodos_carretera[0].y
        if self.pos_x >= nodos_carretera[-1].x0:
            return nodos_carretera[-1].y

        for i in range(len(nodos_carretera) - 1):
            nk = nodos_carretera[i]
            nk1 = nodos_carretera[i + 1]
            if nk.x0 <= self.pos_x <= nk1.x0:
                xi = (self.pos_x - nk.x0) / (nk1.x0 - nk.x0)
                return nk.y * (1.0 - xi) + nk1.y * xi
        return 0.0


class PuentePratt:
    def __init__(self):
        self.nodos = []
        self.miembros = []
        self.nodos_carretera = []
        self.amortiguamiento = 5500.0  # ✓ Ajustado para oscilaciones controladas

    def generar_parametrizado(self, paneles, longitud_panel, altura):
        """
        Genera armadura Pratt con todas las vigas correctas.

        Patrón de diagonales (revisado):
        - Lado izquierdo (i <= mitad): nodos_sup[i-1] a nodos_inf[i+1]
        - Lado derecho (i > mitad): nodos_inf[i] a nodos_sup[i]
        """
        self.nodos.clear()
        self.miembros.clear()
        self.nodos_carretera.clear()

        # Nodos inferiores (carretera)
        nodos_inf = []
        for i in range(paneles + 1):
            es_apoyo = (i == 0 or i == paneles)
            nodo = Nodo(len(self.nodos), i * longitud_panel, 0.0,
                       fijo=es_apoyo, masa=80.0)
            self.nodos.append(nodo)
            nodos_inf.append(nodo)
            self.nodos_carretera.append(nodo)

        # Nodos superiores
        nodos_sup = []
        for i in range(1, paneles):
            nodo = Nodo(len(self.nodos), i * longitud_panel, altura, masa=40.0)
            self.nodos.append(nodo)
            nodos_sup.append(nodo)

        # Conectar miembros
        id_m = 0
        def conectar(n1, n2):
            nonlocal id_m
            self.miembros.append(Miembro(id_m, n1, n2))
            id_m += 1

        # Miembro inferior
        for i in range(len(nodos_inf) - 1):
            conectar(nodos_inf[i], nodos_inf[i + 1])

        # Miembro superior
        for i in range(len(nodos_sup) - 1):
            conectar(nodos_sup[i], nodos_sup[i + 1])

        # Verticales
        for i in range(len(nodos_sup)):
            conectar(nodos_inf[i + 1], nodos_sup[i])

        # Verticales de extremos
        conectar(nodos_inf[0], nodos_sup[0])
        conectar(nodos_inf[-1], nodos_sup[-1])

        # ✓ DIAGONALES CORRECTAS - Patrón ALTERNADO para distribución uniforme
        # Alternancia: UP, DOWN, UP, DOWN... para rigidez balanceada
        diagonales_creadas = 0

        print(f"\n  Patrón de diagonales (paneles={paneles}, ALTERNADO):")
        for i in range(1, paneles - 1):
            # Alternancia basada en si i es par o impar
            if i % 2 == 1:  # Paneles impares: Diagonal UP
                conectar(nodos_sup[i - 1], nodos_inf[i + 1])
                print(f"    Panel {i}: Diagonal UP   (sup[{i-1}] → inf[{i+1}])")
                diagonales_creadas += 1
            else:  # Paneles pares: Diagonal DOWN
                conectar(nodos_inf[i], nodos_sup[i])
                print(f"    Panel {i}: Diagonal DOWN (inf[{i}] → sup[{i}])")
                diagonales_creadas += 1

        # Debug: mostrar cantidad de vigas
        print(f"\n✓ Puente generado: {len(self.nodos)} nodos, {len(self.miembros)} miembros")
        print(f"  - Diagonales creadas: {diagonales_creadas}")
        print(f"  - Tamaño total: {paneles * longitud_panel:.1f} unidades")
        print(f"  - Patrón: ALTERNADO (distribución uniforme de rigidez)")

    def reset_a_equilibrio(self):
        """Reinicia al equilibrio calculado y recalcula esfuerzos"""
        for n in self.nodos:
            n.x = n.x_eq
            n.y = n.y_eq
            n.x_prev = n.x_eq
            n.y_prev = n.y_eq
            n.fuerza[:] = 0.0

        # ✓ CRÍTICO: Forzar recálculo de esfuerzos
        for m in self.miembros:
            m.esfuerzo_actual = 0.0  # Reset
            m.calcular_esfuerzo()    # Recalcular

    def paso_fisico(self, dt, carga_movil=None, aplicar_gravedad=True):
        """Ejecuta paso de simulación"""
        for n in self.nodos:
            n.reset_fuerza()

        if aplicar_gravedad:
            for n in self.nodos:
                if not n.fijo:
                    n.aplicar_fuerza(0.0, -n.masa * GRAVEDAD)

        if carga_movil:
            carga_movil.aplicar_carga(self.nodos_carretera)

        for m in self.miembros:
            m.aplicar_fuerza_hooke()

        # ✓ Amortiguamiento mejorado
        for n in self.nodos:
            if not n.fijo:
                vx = (n.x - n.x_prev) / dt
                vy = (n.y - n.y_prev) / dt
                n.aplicar_fuerza(-self.amortiguamiento * vx,
                               -self.amortiguamiento * vy)

        # Verlet integration
        for n in self.nodos:
            if n.fijo:
                continue

            ax = n.fuerza[0] / n.masa
            ay = n.fuerza[1] / n.masa

            x_new = 2.0 * n.x - n.x_prev + ax * dt * dt
            y_new = 2.0 * n.y - n.y_prev + ay * dt * dt

            n.x_prev = n.x
            n.y_prev = n.y
            n.x = x_new
            n.y = y_new

        # Recalcular esfuerzos
        for m in self.miembros:
            m.calcular_esfuerzo()

    def relajar_a_equilibrio(self, n_iter=6000, dt=0.0015):
        """Precalcula equilibrio con damping fuerte"""
        damp_orig = self.amortiguamiento
        self.amortiguamiento = 30000.0  # ✓ AUMENTADO para convergencia más fuerte

        print("Calculando equilibrio...")
        for iter_num in range(n_iter):
            self.paso_fisico(dt, carga_movil=None, aplicar_gravedad=True)

            # Mostrar progreso cada 1000 iteraciones
            if iter_num % 1000 == 0 and iter_num > 0:
                max_desp = max(abs(n.y - n.y_eq) for n in self.nodos if not n.fijo)
                print(f"  Iter {iter_num}: Desplazamiento máximo = {max_desp:.6f}")

        # Guardar equilibrio
        for n in self.nodos:
            n.x_eq = n.x
            n.y_eq = n.y
            n.x_prev = n.x
            n.y_prev = n.y

        # Restaurar damping normal
        self.amortiguamiento = damp_orig

        # Debug: mostrar desplazamientos finales
        max_desp = max(abs(n.y - n.y0) for n in self.nodos)
        print(f"✓ Equilibrio alcanzado. Desplazamiento máximo: {max_desp:.6f} m")


class MotorGrafico:
    def __init__(self, puente):
        self.puente = puente

    def dibujar(self, carga_movil=None):
        """Renderiza puente con EFECTOS VISUALES mejorados"""
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # 📐 REJILLA DE REFERENCIA
        self._dibujar_rejilla()

        # ✨ MIEMBROS - Con grosor dinámico basado en esfuerzo
        for m in self.puente.miembros:
            color = m.obtener_color_stress()
            esfuerzo_norm = min(abs(m.esfuerzo_actual) / UMBRAL_ESFUERZO, 1.0)
            # Grosor entre 2.5 y 7.0 según esfuerzo
            grosor = 2.5 + esfuerzo_norm * 4.5
            glLineWidth(grosor)

            glBegin(GL_LINES)
            glColor3f(*color)
            x1, y1 = m.origen.pos_actual
            x2, y2 = m.destino.pos_actual
            glVertex3f(x1, y1, 0)
            glVertex3f(x2, y2, 0)
            glEnd()

        # 🔵 NODOS - Más grandes y coloridos
        glLineWidth(1.0)
        for n in self.puente.nodos:
            if n.fijo:
                # Apoyos: Verde brillante
                self._dibujar_nodo(n.x, n.y, 0.35, (0.1, 0.95, 0.2))
            else:
                # Nodos normales: Gris oscuro
                self._dibujar_nodo(n.x, n.y, 0.25, (0.3, 0.3, 0.3))

        # 🚛 VEHÍCULO
        if carga_movil is not None:
            y_v = carga_movil.get_pos_y(self.puente.nodos_carretera)
            self._dibujar_vehiculo(carga_movil.pos_x, y_v + 0.8)  # ✓ Altura ajustada

    def _dibujar_nodo(self, x, y, radio, color):
        """Dibuja un nodo circular con borde"""
        # Relleno
        glColor3f(*color)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(x, y, 0)
        for i in range(33):
            th = 2.0 * math.pi * i / 32
            glVertex3f(x + radio * math.cos(th), y + radio * math.sin(th), 0)
        glEnd()

        # Borde
        glLineWidth(2.0)
        glColor3f(color[0]*0.5, color[1]*0.5, color[2]*0.5)
        glBegin(GL_LINE_LOOP)
        for i in range(32):
            th = 2.0 * math.pi * i / 32
            glVertex3f(x + radio * math.cos(th), y + radio * math.sin(th), 0)
        glEnd()

    def _dibujar_rejilla(self):
        """Dibuja rejilla de referencia para mejor contexto visual"""
        glLineWidth(1.0)
        glColor3f(0.85, 0.85, 0.88)  # Gris muy claro

        # Líneas horizontales
        for y_line in range(-2, 6):
            glBegin(GL_LINES)
            glVertex3f(-2.0, y_line, -0.1)
            glVertex3f(20.0, y_line, -0.1)
            glEnd()

        # Líneas verticales
        for x_line in range(-2, 21):
            glBegin(GL_LINES)
            glVertex3f(x_line, -2.0, -0.1)
            glVertex3f(x_line, 6.0, -0.1)
            glEnd()

        # Línea de referencia principal (suelo)
        glLineWidth(2.5)
        glColor3f(0.4, 0.4, 0.5)
        glBegin(GL_LINES)
        glVertex3f(-2.0, 0.0, -0.05)
        glVertex3f(20.0, 0.0, -0.05)
        glEnd()

    def _dibujar_vehiculo(self, x, y):
        """Vehículo con diseño mejorado y COLORES LLAMATIVOS"""
        ancho, alto = 2.4, 1.0

        # 🟠 CARROCERÍA - Naranja brillante degradado
        # Parte principal - Naranja vibrante
        glColor3f(1.0, 0.65, 0.0)  # Naranja brillante
        glBegin(GL_QUADS)
        glVertex3f(x - ancho/2, y, 0)
        glVertex3f(x + ancho/2, y, 0)
        glVertex3f(x + ancho/2, y + alto, 0)
        glVertex3f(x - ancho/2, y + alto, 0)
        glEnd()

        # Sombra en carrocería - Naranja oscuro
        glColor3f(0.8, 0.4, 0.0)
        glBegin(GL_QUADS)
        glVertex3f(x + ancho/2 - 0.3, y, 0)
        glVertex3f(x + ancho/2, y, 0)
        glVertex3f(x + ancho/2, y + alto, 0)
        glVertex3f(x + ancho/2 - 0.3, y + alto, 0)
        glEnd()

        # 🟡 CABINA - Naranja aún más brillante
        cab_w = ancho * 0.55
        cab_h = alto * 0.55
        glColor3f(1.0, 0.8, 0.2)  # Amarillo-Naranja
        glBegin(GL_QUADS)
        glVertex3f(x - cab_w/2 - 0.2, y + alto, 0)
        glVertex3f(x + cab_w/2 - 0.2, y + alto, 0)
        glVertex3f(x + cab_w/2 - 0.2, y + alto + cab_h, 0)
        glVertex3f(x - cab_w/2 - 0.2, y + alto + cab_h, 0)
        glEnd()

        # 🪟 VENTANA - Cian translúcido
        ventana_w = cab_w * 0.7
        ventana_h = cab_h * 0.6
        glColor3f(0.0, 0.8, 1.0)
        glBegin(GL_QUADS)
        glVertex3f(x - ventana_w/2 - 0.2, y + alto + 0.1, 0)
        glVertex3f(x + ventana_w/2 - 0.2, y + alto + 0.1, 0)
        glVertex3f(x + ventana_w/2 - 0.2, y + alto + ventana_h, 0)
        glVertex3f(x - ventana_w/2 - 0.2, y + alto + ventana_h, 0)
        glEnd()

        # ⬛ BORDE - Negro definido
        glColor3f(0.0, 0.0, 0.0)
        glLineWidth(3.0)
        glBegin(GL_LINE_LOOP)
        glVertex3f(x - ancho/2, y, 0)
        glVertex3f(x + ancho/2, y, 0)
        glVertex3f(x + ancho/2, y + alto, 0)
        glVertex3f(x - ancho/2, y + alto, 0)
        glEnd()

        # 🛞 RUEDAS - Negro y gris metálico
        rueda_r = 0.32
        rueda_y = y - rueda_r * 0.4
        for cx in (x - ancho/2 * 0.65, x + ancho/2 * 0.65):
            # Rueda externa - Negro
            self._dibujar_circulo(cx, rueda_y, rueda_r, (0.05, 0.05, 0.05))
            # Rueda interna - Gris metálico
            self._dibujar_circulo(cx, rueda_y, rueda_r * 0.5, (0.6, 0.6, 0.65))
            # Eje central
            self._dibujar_circulo(cx, rueda_y, rueda_r * 0.2, (0.3, 0.3, 0.3))

    def _dibujar_circulo(self, cx, cy, r, color, segs=24):
        glColor3f(*color)
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(cx, cy, 0)
        for i in range(segs + 1):
            th = 2.0 * math.pi * i / segs
            glVertex3f(cx + r * math.cos(th), cy + r * math.sin(th), 0)
        glEnd()


class SimuladorApp:
    def __init__(self):
        pygame.init()
        self.display = (1024, 768)
        pygame.display.set_mode(self.display, DOUBLEBUF | OPENGL)
        pygame.display.set_caption("Simulador Puente Pratt - Sprint 3 MEJORADO")

        self.paneles = 12  # ✓ 12 paneles para 5 y 5 diagonales exactos
        self.long_panel = 1.5  # ✓ 18.0 / 12 = 1.5 unidades por panel
        self.altura = 4.0

        self.puente = PuentePratt()
        self.puente.generar_parametrizado(self.paneles, self.long_panel, self.altura)

        self.puente.relajar_a_equilibrio()

        self.motor_grafico = MotorGrafico(self.puente)
        self.carga_movil = CargaMovil(masa=2000.0, velocidad=3.0)
        self.carga_movil.configurar_recorrido(0.0, self.paneles * self.long_panel)

        self.cam_x = -9.0
        self.cam_y = -2.0
        self.cam_z = -28.0
        self.zoom = 45.0

        self._imprimir_controles()

    def _imprimir_controles(self):
        print("\n" + "="*50)
        print("CONTROLES - Simulador Puente Pratt")
        print("="*50)
        print("ESPACIO  : Lanzar vehículo")
        print("R        : Reiniciar al equilibrio")
        print("↑ / ↓    : ±500 kg masa vehículo")
        print("→ / ←    : ±1 m/s velocidad vehículo")
        print("="*50 + "\n")

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
                    print(f"▶ Vehículo lanzado: {self.carga_movil.masa:.0f} kg @ {self.carga_movil.velocidad:.1f} m/s")
                    self.carga_movil.iniciar()

                elif event.key == pygame.K_r:
                    print("⟳ Reiniciando al equilibrio")
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

    def ejecutar(self):
        """Game loop con control inteligente de gravedad"""
        clock = pygame.time.Clock()
        # Fondo más oscuro para mejor contraste
        glClearColor(0.92, 0.92, 0.95, 1.0)

        print("✓ Iniciando simulación a 60 FPS...\n")

        while True:
            frame_dt = clock.tick(60) / 1000.0
            frame_dt = min(frame_dt, 1.0 / 30.0)

            self.manejar_eventos()

            # ✓ CRÍTICO: Aplicar gravedad SOLO cuando vehículo está activo
            aplicar_gravedad = self.carga_movil.activo

            sub_dt = frame_dt / SUBSTEPS
            for _ in range(SUBSTEPS):
                self.carga_movil.actualizar(sub_dt)
                self.puente.paso_fisico(sub_dt, self.carga_movil,
                                       aplicar_gravedad=aplicar_gravedad)

            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.configurar_proyeccion()
            self.motor_grafico.dibujar(self.carga_movil)
            pygame.display.flip()


if __name__ == "__main__":
    app = SimuladorApp()
    app.ejecutar()
 