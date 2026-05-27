import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import sys
import csv
import sqlite3

GRAVEDAD = 9.81
SUBSTEPS = 25
UMBRAL_ESFUERZO = 50000.0

class BaseMateriales:
    def __init__(self, db_path="materiales.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self._crear_tabla()
        self._insertar_materiales_default()
        print(f"Base de materiales inicializada: {db_path}")

    def _crear_tabla(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS materiales (
                nombre TEXT PRIMARY KEY,
                E REAL,
                limite_compresion REAL,
                limite_tension REAL,
                densidad REAL
            )
        ''')
        self.conn.commit()

    def _insertar_materiales_default(self):
        self.cursor.execute("SELECT COUNT(*) FROM materiales")
        if self.cursor.fetchone()[0] == 0:
            materiales = [
                ("Acero",    2000.0,  -3000.0,  2500.0, 7850),
                ("Madera",    120.0,   -400.0,   150.0,  600),
                ("Concreto",  300.0,   -300.0,    50.0, 2400),
            ]
            self.cursor.executemany("INSERT INTO materiales VALUES (?, ?, ?, ?, ?)", materiales)
            self.conn.commit()
            print("Materiales insertados")

    def obtener_material(self, nombre):
        self.cursor.execute("SELECT E, limite_compresion, limite_tension FROM materiales WHERE nombre=?", (nombre,))
        return self.cursor.fetchone()

    def listar_materiales(self):
        self.cursor.execute("SELECT nombre FROM materiales")
        return [row[0] for row in self.cursor.fetchall()]

    def cerrar(self):
        self.conn.close()

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
    def __init__(self, id_miembro, nodo_origen, nodo_destino, E=1.0e9, area=0.0005, material=None, db_materiales=None):
        self.id = id_miembro
        self.origen = nodo_origen
        self.destino = nodo_destino
        self.Area = area
        self.material = material
        self.esfuerzo_actual = 0.0
        self.roto = False
        self.color_custom = None

        if db_materiales and material:
            props = db_materiales.obtener_material(material)
            if props:
                self.E = props[0]
                self.limite_compresion = props[1]
                self.limite_tension = props[2]
            else:
                self.E = E
                self.limite_compresion = -1e9
                self.limite_tension = 1e9
        else:
            self.E = E
            self.limite_compresion = -1e9
            self.limite_tension = 1e9

        dx = self.destino.x0 - self.origen.x0
        dy = self.destino.y0 - self.origen.y0
        self.L0 = math.hypot(dx, dy)
        self.k = (self.E * self.Area / self.L0)

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
        intensidad = min(abs(self.esfuerzo_actual) / UMBRAL_ESFUERZO, 1.0)
        if self.esfuerzo_actual > 3000:
            r, g, b = 0.0, 0.5 + intensidad * 0.5, 0.7 + intensidad * 0.3
        elif self.esfuerzo_actual > 1000:
            r, g, b = 0.0, 0.3 + intensidad * 0.3, 0.3 + intensidad * 0.7
        elif self.esfuerzo_actual < -3000:
            r, g, b = 0.9 + intensidad * 0.1, 0.3 + intensidad * 0.4, 0.0
        elif self.esfuerzo_actual < -1000:
            r, g, b = 0.6 + intensidad * 0.4, 0.1 + intensidad * 0.2, 0.0
        else:
            r, g, b = 0.4, 0.4, 0.4
        return (r, g, b)

    def comprobar_ruptura(self):
        if not self.roto:
            if self.esfuerzo_actual > self.limite_tension:
                self.roto = True
                print(f"VIGA {self.id} ROTA (Tension)")
                return True
            elif self.esfuerzo_actual < self.limite_compresion:
                self.roto = True
                print(f"VIGA {self.id} ROTA (Compresion)")
                return True
        return False

    def actualizar_visual(self):
        if self.roto:
            self.color_custom = (128, 128, 128)
        else:
            self.color_custom = None

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
        self.amortiguamiento = 5500.0

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
            nodo = Nodo(len(self.nodos), i * longitud_panel, altura, masa=40.0)
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
        for i in range(1, paneles - 1):
            if i % 2 == 1:
                conectar(nodos_sup[i - 1], nodos_inf[i + 1])
            else:
                conectar(nodos_inf[i], nodos_sup[i])
        if paneles >= 2:
            conectar(nodos_inf[paneles - 1], nodos_sup[paneles - 2])
        print(f"Puente: {len(self.nodos)} nodos, {len(self.miembros)} miembros")

    def reset_a_equilibrio(self):
        for n in self.nodos:
            n.x = n.x_eq
            n.y = n.y_eq
            n.x_prev = n.x_eq
            n.y_prev = n.y_eq
            n.fuerza[:] = 0.0
        for m in self.miembros:
            m.esfuerzo_actual = 0.0
            m.calcular_esfuerzo()

    def paso_fisico(self, dt, carga_movil=None, aplicar_gravedad=True):
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
        for n in self.nodos:
            if not n.fijo:
                vx = (n.x - n.x_prev) / dt
                vy = (n.y - n.y_prev) / dt
                n.aplicar_fuerza(-self.amortiguamiento * vx, -self.amortiguamiento * vy)
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
        for m in self.miembros:
            m.calcular_esfuerzo()

    def relajar_a_equilibrio(self, n_iter=6000, dt=0.0015):
        damp_orig = self.amortiguamiento
        self.amortiguamiento = 30000.0
        print("Calculando equilibrio...")
        for iter_num in range(n_iter):
            self.paso_fisico(dt, carga_movil=None, aplicar_gravedad=True)
            if iter_num % 1000 == 0 and iter_num > 0:
                max_desp = max(abs(n.y - n.y_eq) for n in self.nodos if not n.fijo)
                print(f"  Iter {iter_num}: {max_desp:.6f}")
        for n in self.nodos:
            n.x_eq = n.x
            n.y_eq = n.y
            n.x_prev = n.x
            n.y_prev = n.y
        self.amortiguamiento = damp_orig
        max_desp = max(abs(n.y - n.y0) for n in self.nodos)
        print(f"Equilibrio alcanzado: {max_desp:.6f}")

    def cargar_geometria_csv(self, filename, db_materiales=None, material_default="Acero"):
        self.nodos.clear()
        self.miembros.clear()
        self.nodos_carretera.clear()
        nodos_file = f"{filename}_nodos.csv"
        try:
            with open(nodos_file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    nodo = Nodo(int(row['id']), float(row['x']), float(row['y']), fijo=row['fijo'].lower() == 'true', masa=float(row['masa']))
                    self.nodos.append(nodo)
                    if float(row['y']) == 0.0:
                        self.nodos_carretera.append(nodo)
            print(f"Nodos: {len(self.nodos)}")
        except FileNotFoundError:
            print(f"Error: {nodos_file} no encontrado")
            return False
        miembros_file = f"{filename}_miembros.csv"
        try:
            with open(miembros_file, 'r') as f:
                reader = csv.DictReader(f)
                id_m = 0
                for row in reader:
                    nodo1 = self.nodos[int(row['nodo_origen'])]
                    nodo2 = self.nodos[int(row['nodo_destino'])]
                    area = float(row['area']) if 'area' in row else 0.01
                    miembro = Miembro(id_m, nodo1, nodo2, area=area, material=material_default, db_materiales=db_materiales)
                    self.miembros.append(miembro)
                    id_m += 1
            print(f"Miembros: {len(self.miembros)}")
        except FileNotFoundError:
            print(f"Error: {miembros_file} no encontrado")
            return False
        return True

class HUD:
    def __init__(self):
        self.lineas = []
        self.activo = True

    def agregar_linea(self, texto, x=10, y=None):
        self.lineas.append({"texto": texto, "x": x, "y": y})

    def limpiar(self):
        self.lineas = []

class MotorGrafico:
    def __init__(self, puente):
        self.puente = puente

    def dibujar(self, carga_movil=None):
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self._dibujar_rejilla()
        for m in self.puente.miembros:
            if m.color_custom:
                r, g, b = m.color_custom
                color = (r/255.0, g/255.0, b/255.0)
            else:
                color = m.obtener_color_stress()
            esfuerzo_norm = min(abs(m.esfuerzo_actual) / UMBRAL_ESFUERZO, 1.0)
            grosor = 2.5 + esfuerzo_norm * 4.5
            glLineWidth(grosor)
            glBegin(GL_LINES)
            glColor3f(*color)
            x1, y1 = m.origen.pos_actual
            x2, y2 = m.destino.pos_actual
            glVertex3f(x1, y1, 0)
            glVertex3f(x2, y2, 0)
            glEnd()
        glLineWidth(1.0)
        for n in self.puente.nodos:
            if n.fijo:
                self._dibujar_nodo(n.x, n.y, 0.35, (0.1, 0.95, 0.2))
            else:
                self._dibujar_nodo(n.x, n.y, 0.25, (0.3, 0.3, 0.3))
        if carga_movil is not None:
            y_v = carga_movil.get_pos_y(self.puente.nodos_carretera)
            self._dibujar_vehiculo(carga_movil.pos_x, y_v + 0.8)

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
        ancho, alto = 2.4, 1.0
        glColor3f(1.0, 0.65, 0.0)
        glBegin(GL_QUADS)
        glVertex3f(x - ancho/2, y, 0)
        glVertex3f(x + ancho/2, y, 0)
        glVertex3f(x + ancho/2, y + alto, 0)
        glVertex3f(x - ancho/2, y + alto, 0)
        glEnd()
        glColor3f(0.8, 0.4, 0.0)
        glBegin(GL_QUADS)
        glVertex3f(x + ancho/2 - 0.3, y, 0)
        glVertex3f(x + ancho/2, y, 0)
        glVertex3f(x + ancho/2, y + alto, 0)
        glVertex3f(x + ancho/2 - 0.3, y + alto, 0)
        glEnd()
        cab_w, cab_h = ancho * 0.55, alto * 0.55
        glColor3f(1.0, 0.8, 0.2)
        glBegin(GL_QUADS)
        glVertex3f(x - cab_w/2 - 0.2, y + alto, 0)
        glVertex3f(x + cab_w/2 - 0.2, y + alto, 0)
        glVertex3f(x + cab_w/2 - 0.2, y + alto + cab_h, 0)
        glVertex3f(x - cab_w/2 - 0.2, y + alto + cab_h, 0)
        glEnd()
        ventana_w, ventana_h = cab_w * 0.7, cab_h * 0.6
        glColor3f(0.0, 0.8, 1.0)
        glBegin(GL_QUADS)
        glVertex3f(x - ventana_w/2 - 0.2, y + alto + 0.1, 0)
        glVertex3f(x + ventana_w/2 - 0.2, y + alto + 0.1, 0)
        glVertex3f(x + ventana_w/2 - 0.2, y + alto + ventana_h, 0)
        glVertex3f(x - ventana_w/2 - 0.2, y + alto + ventana_h, 0)
        glEnd()
        glColor3f(0.0, 0.0, 0.0)
        glLineWidth(3.0)
        glBegin(GL_LINE_LOOP)
        glVertex3f(x - ancho/2, y, 0)
        glVertex3f(x + ancho/2, y, 0)
        glVertex3f(x + ancho/2, y + alto, 0)
        glVertex3f(x - ancho/2, y + alto, 0)
        glEnd()
        rueda_r = 0.32
        rueda_y = y - rueda_r * 0.4
        for cx in (x - ancho/2 * 0.65, x + ancho/2 * 0.65):
            self._dibujar_circulo(cx, rueda_y, rueda_r, (0.05, 0.05, 0.05))
            self._dibujar_circulo(cx, rueda_y, rueda_r * 0.5, (0.6, 0.6, 0.65))
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
        pygame.display.set_caption("Simulador Puente Pratt - SEMANA 10")
        print("Inicializando...")
        self.db_materiales = BaseMateriales()
        self.material_actual = "Acero"
        self.puente = PuentePratt()
        exito = self.puente.cargar_geometria_csv("puente", self.db_materiales, self.material_actual)
        if not exito:
            print("Usando fallback parametrico")
            self.puente.generar_parametrizado(12, 1.5, 4.0)
        self.puente.relajar_a_equilibrio()
        self.motor_grafico = MotorGrafico(self.puente)
        self.hud = HUD()
        self.carga_movil = CargaMovil(masa=2000.0, velocidad=3.0)
        if self.puente.nodos_carretera:
            x_min = self.puente.nodos_carretera[0].x0
            x_max = self.puente.nodos_carretera[-1].x0
            self.carga_movil.configurar_recorrido(x_min, x_max)
        self.cam_x = -9.0
        self.cam_y = -2.0
        self.cam_z = -28.0
        self.zoom = 45.0
        print("CONTROLES: SPACE=Lanzar, R=Reset, ESC=Salir")

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
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                elif event.key == pygame.K_SPACE:
                    self.puente.reset_a_equilibrio()
                    print(f"Lanzado: {self.carga_movil.masa:.0f}kg")
                    self.carga_movil.iniciar()
                elif event.key == pygame.K_r:
                    self.carga_movil.detener()
                    self.puente.reset_a_equilibrio()
                elif event.key == pygame.K_UP:
                    self.carga_movil.masa += 500.0
                elif event.key == pygame.K_DOWN:
                    self.carga_movil.masa = max(500.0, self.carga_movil.masa - 500.0)

    def ejecutar(self):
        clock = pygame.time.Clock()
        glClearColor(0.92, 0.92, 0.95, 1.0)
        print("Iniciando simulacion a 60 FPS")
        while True:
            frame_dt = clock.tick(60) / 1000.0
            frame_dt = min(frame_dt, 1.0 / 30.0)
            self.manejar_eventos()
            aplicar_gravedad = self.carga_movil.activo
            sub_dt = frame_dt / SUBSTEPS
            for _ in range(SUBSTEPS):
                self.carga_movil.actualizar(sub_dt)
                self.puente.paso_fisico(sub_dt, self.carga_movil, aplicar_gravedad=aplicar_gravedad)
            for miembro in self.puente.miembros:
                miembro.comprobar_ruptura()
                miembro.actualizar_visual()
            num_rotos = sum(1 for m in self.puente.miembros if m.roto)
            if self.carga_movil.activo:
                if int(clock.get_time()) % 1000 < 50:
                    print(f"Rotos: {num_rotos}")
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            self.configurar_proyeccion()
            self.motor_grafico.dibujar(self.carga_movil)
            pygame.display.flip()

if __name__ == "__main__":
    app = SimuladorApp()
    app.ejecutar()
