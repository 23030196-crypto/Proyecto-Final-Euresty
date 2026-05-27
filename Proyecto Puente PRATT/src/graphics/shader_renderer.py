"""
Renderizador Moderno con Shaders - Pipeline OpenGL 3.3+

Responsabilidades:
- Usar Shader Manager para compilar shaders
- Usar VBO Manager para almacenar geometría
- Renderizar con stress mapping en GPU (Fragment Shader)
- Mantener performance (60 FPS)
- Interfaz simple para actualizar dinámicamente
"""

from OpenGL.GL import *
import numpy as np
import math
from .shader_manager import ShaderManager
from .vbo_manager import VBOManager


class ShaderRenderer:
    """Renderizador profesional con Shaders y VBO"""

    def __init__(self, shaders_dir: str = None):
        """
        Args:
            shaders_dir: Ruta a carpeta con shaders GLSL
        """
        # Managers
        self.shader_mgr = ShaderManager(shaders_dir)
        self.vbo_mgr = VBOManager(max_vertices=1000, max_lines=5000)

        # Cargar programa stress mapping
        self.program_stress = self.shader_mgr.load_program("stress_mapping")

        # Matrices (uniforms para shaders)
        self.projection = self._ortho_matrix()
        self.view = np.identity(4, dtype=np.float32)
        self.model = np.identity(4, dtype=np.float32)

        print("✓ ShaderRenderer inicializado - Pipeline moderno activo")

    def _ortho_matrix(self) -> np.ndarray:
        """Crea matriz ortográfica para proyección 3D"""
        left, right = -10.0, 20.0
        bottom, top = -3.0, 8.0
        near, far = 0.1, 100.0

        matrix = np.zeros((4, 4), dtype=np.float32)
        matrix[0, 0] = 2.0 / (right - left)
        matrix[1, 1] = 2.0 / (top - bottom)
        matrix[2, 2] = -2.0 / (far - near)
        matrix[0, 3] = -(right + left) / (right - left)
        matrix[1, 3] = -(top + bottom) / (top - bottom)
        matrix[2, 3] = -(far + near) / (far - near)
        matrix[3, 3] = 1.0

        return matrix

    def setup_viewport(self, width: int, height: int):
        """Configura viewport y matriz de proyección perspectiva"""
        glViewport(0, 0, width, height)

        # Usar perspectiva simple
        aspect = width / height if height > 0 else 1.0
        fov = 45.0
        near, far = 0.1, 100.0

        self.projection = self._perspective_matrix(fov, aspect, near, far)

    def _perspective_matrix(self, fov: float, aspect: float, near: float, far: float) -> np.ndarray:
        """Crea matriz perspectiva manual"""
        f = 1.0 / math.tan(math.radians(fov / 2.0))
        result = np.zeros((4, 4), dtype=np.float32)

        result[0, 0] = f / aspect
        result[1, 1] = f
        result[2, 2] = (far + near) / (near - far)
        result[2, 3] = (2.0 * far * near) / (near - far)
        result[3, 2] = -1.0

        return result

    def set_camera(self, eye_x: float, eye_y: float, eye_z: float):
        """Posiciona cámara (traslación simple)"""
        self.view = np.identity(4, dtype=np.float32)
        self.view[0, 3] = -eye_x
        self.view[1, 3] = -eye_y
        self.view[2, 3] = -eye_z

    def clear_screen(self, r: float = 0.92, g: float = 0.92, b: float = 0.95):
        """Limpia pantalla con color de fondo"""
        glClearColor(r, g, b, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

    def render_bridge(self, stress_threshold: float = 50000.0, intensity: float = 1.0):
        """
        Renderiza puente con stress mapping

        Args:
            stress_threshold: Valor donde color alcanza saturación
            intensity: Multiplicador de intensidad global
        """
        # Cargar datos a GPU
        self.vbo_mgr.upload_to_gpu()

        # Activar shader
        self.program_stress.use()

        # Pasar matrices como uniforms
        self.program_stress.set_uniform_matrix4("projection", self.projection)
        self.program_stress.set_uniform_matrix4("view", self.view)
        self.program_stress.set_uniform_matrix4("model", self.model)

        # Pasar parámetros de stress mapping
        self.program_stress.set_uniform_f("stress_threshold", stress_threshold)
        self.program_stress.set_uniform_f("intensity", intensity)

        # Renderizar líneas (miembros)
        glLineWidth(3.0)
        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
        self.vbo_mgr.render_lines()

        # Renderizar puntos (nodos)
        glPointSize(8.0)
        self._render_nodes()

    def _render_nodes(self):
        """Renderiza nodos con colores especiales (soportes en verde)"""
        # Por ahora usar renderizado simple en CPU para soportes
        # En futuro: pasar flags a VBO
        glUseProgram(0)  # Deshabilitar shaders para puntos

        glPointSize(10.0)
        glBegin(GL_POINTS)
        for i in range(self.vbo_mgr.vertex_count):
            pos = self.vbo_mgr.positions[i]
            # Puntos normales en gris
            glColor3f(0.4, 0.4, 0.4)
            glVertex3fv(pos)
        glEnd()

    def render_vehicle(self, pos_x: float, pos_y: float, width: float = 2.4, height: float = 1.0):
        """Renderiza vehículo como quad (temporal - sin shaders)"""
        glUseProgram(0)

        glColor3f(1.0, 0.65, 0.0)
        glBegin(GL_QUADS)
        glVertex3f(pos_x - width/2, pos_y, 0)
        glVertex3f(pos_x + width/2, pos_y, 0)
        glVertex3f(pos_x + width/2, pos_y + height, 0)
        glVertex3f(pos_x - width/2, pos_y + height, 0)
        glEnd()

        glLineWidth(2.0)
        glColor3f(0.0, 0.0, 0.0)
        glBegin(GL_LINE_LOOP)
        glVertex3f(pos_x - width/2, pos_y, 0)
        glVertex3f(pos_x + width/2, pos_y, 0)
        glVertex3f(pos_x + width/2, pos_y + height, 0)
        glVertex3f(pos_x - width/2, pos_y + height, 0)
        glEnd()

    def add_bridge_geometry(self, puente):
        """Carga geometría del puente al VBO"""
        # Agregar nodos
        for nodo in puente.nodos:
            self.vbo_mgr.add_node(nodo.id, nodo.x, nodo.y, 0.0)

        # Agregar líneas (miembros)
        for miembro in puente.miembros:
            self.vbo_mgr.add_line(
                miembro.id,
                miembro.origen.id,
                miembro.destino.id
            )

        print(f"✓ Geometría cargada: {len(puente.nodos)} nodos, {len(puente.miembros)} miembros")

    def update_physics_state(self, puente):
        """
        Actualiza VBO con estado físico actual del puente

        Llamar CADA FRAME después de paso_fisico()
        """
        # Actualizar posiciones
        for nodo in puente.nodos:
            self.vbo_mgr.update_node_position(nodo.id, nodo.x, nodo.y, 0.0)

        # Actualizar esfuerzos normalizados
        # Encontrar rango de esfuerzo para normalización
        stresses = [m.esfuerzo_actual for m in puente.miembros]
        if stresses:
            max_stress = max(abs(s) for s in stresses) if stresses else 1.0
            max_stress = max(max_stress, 1.0)  # Evitar división por 0

            for miembro in puente.miembros:
                # Normalizar a [-1.0, 1.0]
                stress_norm = miembro.esfuerzo_actual / max_stress if max_stress > 0 else 0.0
                stress_norm = max(-1.0, min(1.0, stress_norm))

                # Actualizar ambos nodos (promedio de sus miembros)
                # Simplificación: usar esfuerzo del miembro en ambos nodos
                self.vbo_mgr.update_node_stress(miembro.origen.id, stress_norm)
                self.vbo_mgr.update_node_stress(miembro.destino.id, stress_norm)
