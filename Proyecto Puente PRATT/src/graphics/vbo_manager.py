"""
Gestor de Vertex Buffer Objects (VBO) - Pipeline moderno de OpenGL

Responsabilidades:
- Crear y gestionar VAO (Vertex Array Object)
- Crear y actualizar VBO (Vertex Buffer Object) para posiciones
- Crear y actualizar VBO para esfuerzo normalizado
- Render batching eficiente
- Actualización dinámica en tiempo real (cada frame)
"""

from OpenGL.GL import *
import numpy as np
from typing import List, Tuple


class VBOLine:
    """Representa una línea (miembro del puente) para renderizado con VBO"""

    def __init__(self, vertex_indices: Tuple[int, int], stress: float = 0.0):
        """
        Args:
            vertex_indices: (índice_inicio, índice_fin) en el array de vértices
            stress: Esfuerzo actual en este miembro
        """
        self.start_idx = vertex_indices[0]
        self.end_idx = vertex_indices[1]
        self.stress_normalized = 0.0  # [-1.0, 1.0]


class VBOManager:
    """Gestor de Vertex Buffer Objects para renderizado moderno"""

    def __init__(self, max_vertices: int = 1000, max_lines: int = 5000):
        """
        Args:
            max_vertices: Máximo número de vértices (nodos)
            max_lines: Máximo número de líneas (miembros)
        """
        self.max_vertices = max_vertices
        self.max_lines = max_lines

        # Arrays de datos en CPU
        self.positions = np.zeros((max_vertices, 3), dtype=np.float32)
        self.stress_normalized = np.zeros(max_vertices, dtype=np.float32)
        self.line_indices = np.zeros((max_lines, 2), dtype=np.uint32)

        self.vertex_count = 0
        self.line_count = 0

        # IDs de OpenGL
        self.VAO = None
        self.VBO_positions = None
        self.VBO_stress = None
        self.EBO = None

        self._setup_opengl()

    def _setup_opengl(self):
        """Crea VAO, VBO y EBO"""
        # Crear VAO
        self.VAO = glGenVertexArrays(1)
        glBindVertexArray(self.VAO)

        # VBO para posiciones (attribute location 0)
        self.VBO_positions = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.VBO_positions)
        glBufferData(
            GL_ARRAY_BUFFER,
            self.positions.nbytes,
            self.positions,
            GL_DYNAMIC_DRAW  # Cambios frecuentes
        )

        # Descriptor: 3 floats por vértice
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # VBO para esfuerzo normalizado (attribute location 1)
        self.VBO_stress = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.VBO_stress)
        glBufferData(
            GL_ARRAY_BUFFER,
            self.stress_normalized.nbytes,
            self.stress_normalized,
            GL_DYNAMIC_DRAW
        )

        # Descriptor: 1 float por vértice
        glVertexAttribPointer(1, 1, GL_FLOAT, GL_FALSE, 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)

        # EBO para índices de líneas
        self.EBO = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.EBO)
        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            self.line_indices.nbytes,
            self.line_indices,
            GL_DYNAMIC_DRAW
        )

        # Desvinculaar
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        print(f"✓ VBO Manager inicializado: {self.max_vertices} verts, {self.max_lines} lines")

    def add_node(self, node_id: int, x: float, y: float, z: float = 0.0):
        """Agrega un nodo (vértice) a la geometría"""
        if node_id >= self.max_vertices:
            raise ValueError(f"Node ID {node_id} excede max_vertices {self.max_vertices}")

        self.positions[node_id] = [x, y, z]
        self.vertex_count = max(self.vertex_count, node_id + 1)

    def add_line(self, line_id: int, start_idx: int, end_idx: int):
        """Agrega una línea entre dos vértices"""
        if line_id >= self.max_lines:
            raise ValueError(f"Line ID {line_id} excede max_lines {self.max_lines}")

        self.line_indices[line_id] = [start_idx, end_idx]
        self.line_count = max(self.line_count, line_id + 1)

    def update_node_position(self, node_id: int, x: float, y: float, z: float = 0.0):
        """Actualiza posición de un nodo (para Verlet)"""
        if node_id < self.vertex_count:
            self.positions[node_id] = [x, y, z]

    def update_node_stress(self, node_id: int, stress_normalized: float):
        """
        Actualiza esfuerzo normalizado de un nodo

        Args:
            stress_normalized: Valor en rango [-1.0 (compresión) a 1.0 (tensión)]
        """
        if node_id < self.vertex_count:
            self.stress_normalized[node_id] = np.clip(stress_normalized, -1.0, 1.0)

    def upload_to_gpu(self):
        """Sube arrays actualizados a GPU (llamar una vez por frame)"""
        glBindVertexArray(self.VAO)

        # Actualizar VBO de posiciones
        glBindBuffer(GL_COPY_WRITE_BUFFER, self.VBO_positions)
        glBufferSubData(
            GL_COPY_WRITE_BUFFER,
            0,
            self.positions[:self.vertex_count].nbytes,
            self.positions[:self.vertex_count]
        )

        # Actualizar VBO de esfuerzo
        glBindBuffer(GL_COPY_WRITE_BUFFER, self.VBO_stress)
        glBufferSubData(
            GL_COPY_WRITE_BUFFER,
            0,
            self.stress_normalized[:self.vertex_count].nbytes,
            self.stress_normalized[:self.vertex_count]
        )

        # Actualizar EBO de índices
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.EBO)
        glBufferSubData(
            GL_ELEMENT_ARRAY_BUFFER,
            0,
            self.line_indices[:self.line_count].nbytes,
            self.line_indices[:self.line_count]
        )

        glBindVertexArray(0)

    def render_lines(self):
        """Renderiza todas las líneas como GL_LINES"""
        if self.line_count == 0:
            return

        glBindVertexArray(self.VAO)
        glDrawElements(GL_LINES, self.line_count * 2, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def render_points(self):
        """Renderiza todos los puntos (nodos)"""
        if self.vertex_count == 0:
            return

        glBindVertexArray(self.VAO)
        glDrawArrays(GL_POINTS, 0, self.vertex_count)
        glBindVertexArray(0)

    def clear(self):
        """Limpia todos los datos"""
        self.vertex_count = 0
        self.line_count = 0
        self.positions.fill(0.0)
        self.stress_normalized.fill(0.0)
        self.line_indices.fill(0)

    def __del__(self):
        """Limpiar recursos OpenGL"""
        try:
            if self.VAO:
                glDeleteVertexArrays(1, [self.VAO])
            if self.VBO_positions:
                glDeleteBuffers(1, [self.VBO_positions])
            if self.VBO_stress:
                glDeleteBuffers(1, [self.VBO_stress])
            if self.EBO:
                glDeleteBuffers(1, [self.EBO])
        except:
            pass


# Importar ctypes para punteros
import ctypes
