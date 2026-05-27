"""
Gestor de Shaders GLSL - Compila, vincula y gestiona programas OpenGL

Responsabilidades:
- Cargar archivos .vert y .frag desde disco
- Compilar shaders individuales
- Vincular shaders en un programa ejecutable
- Manejo de errores de compilación
- Interfaz limpia para usar shaders en la aplicación
"""

from OpenGL.GL import *
import os
from pathlib import Path


class Shader:
    """Representa un shader GLSL compilado"""

    def __init__(self, source_code: str, shader_type: int):
        """
        Args:
            source_code: Código GLSL completo
            shader_type: GL_VERTEX_SHADER, GL_FRAGMENT_SHADER, etc.
        """
        self.shader_id = glCreateShader(shader_type)
        self.shader_type = shader_type

        # Compilar
        glShaderSource(self.shader_id, source_code)
        glCompileShader(self.shader_id)

        # Verificar errores de compilación
        if not glGetShaderiv(self.shader_id, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(self.shader_id).decode()
            raise RuntimeError(f"Error compilando shader: {error}")

    def __del__(self):
        """Limpiar recursos"""
        try:
            glDeleteShader(self.shader_id)
        except:
            pass


class ShaderProgram:
    """Representa un programa OpenGL completo (Vertex + Fragment + etc)"""

    def __init__(self, vertex_code: str, fragment_code: str):
        """
        Compila y vincula shaders vertex y fragment

        Args:
            vertex_code: Código GLSL del vertex shader
            fragment_code: Código GLSL del fragment shader
        """
        # Compilar shaders individuales
        vertex_shader = Shader(vertex_code, GL_VERTEX_SHADER)
        fragment_shader = Shader(fragment_code, GL_FRAGMENT_SHADER)

        # Crear programa
        self.program_id = glCreateProgram()
        glAttachShader(self.program_id, vertex_shader.shader_id)
        glAttachShader(self.program_id, fragment_shader.shader_id)

        # Vincular
        glLinkProgram(self.program_id)

        # Verificar errores de vinculación
        if not glGetProgramiv(self.program_id, GL_LINK_STATUS):
            error = glGetProgramInfoLog(self.program_id).decode()
            raise RuntimeError(f"Error vinculando programa: {error}")

        print(f"✓ Programa shader compilado exitosamente (ID: {self.program_id})")

    def use(self):
        """Activar este programa para render"""
        glUseProgram(self.program_id)

    def set_uniform_f(self, name: str, value: float):
        """Establece uniform float"""
        location = glGetUniformLocation(self.program_id, name)
        glUniform1f(location, value)

    def set_uniform_i(self, name: str, value: int):
        """Establece uniform int"""
        location = glGetUniformLocation(self.program_id, name)
        glUniform1i(location, value)

    def set_uniform_3f(self, name: str, x: float, y: float, z: float):
        """Establece uniform vec3"""
        location = glGetUniformLocation(self.program_id, name)
        glUniform3f(location, x, y, z)

    def set_uniform_matrix4(self, name: str, matrix):
        """Establece uniform mat4"""
        location = glGetUniformLocation(self.program_id, name)
        # Convertir a numpy array si es necesario
        glUniformMatrix4fv(location, 1, GL_TRUE, matrix)

    def __del__(self):
        """Limpiar programa"""
        try:
            glDeleteProgram(self.program_id)
        except:
            pass


class ShaderManager:
    """Gestor centralizado de shaders - carga desde archivos"""

    def __init__(self, shaders_dir: str = None):
        """
        Args:
            shaders_dir: Ruta a carpeta con archivos .vert y .frag
        """
        if shaders_dir is None:
            # Buscar carpeta 'shaders' relativa a este archivo
            base_dir = Path(__file__).parent.parent.parent
            shaders_dir = base_dir / "shaders"

        self.shaders_dir = Path(shaders_dir)
        self.programs = {}

        print(f"✓ ShaderManager inicializado: {self.shaders_dir}")

    def load_program(self, name: str) -> ShaderProgram:
        """
        Carga un programa shader desde archivos <name>.vert y <name>.frag

        Args:
            name: Nombre del shader (ej: 'stress_mapping')

        Returns:
            ShaderProgram compilado
        """
        # Evitar cargar dos veces
        if name in self.programs:
            return self.programs[name]

        vert_path = self.shaders_dir / f"{name}.vert"
        frag_path = self.shaders_dir / f"{name}.frag"

        # Verificar que existan
        if not vert_path.exists():
            raise FileNotFoundError(f"Vertex shader no encontrado: {vert_path}")
        if not frag_path.exists():
            raise FileNotFoundError(f"Fragment shader no encontrado: {frag_path}")

        # Cargar código
        with open(vert_path, 'r') as f:
            vert_code = f.read()
        with open(frag_path, 'r') as f:
            frag_code = f.read()

        # Compilar
        print(f"  Compilando shader: {name}")
        program = ShaderProgram(vert_code, frag_code)

        # Guardar en caché
        self.programs[name] = program

        return program

    def get_program(self, name: str) -> ShaderProgram:
        """Obtiene programa cargado (sin recargar)"""
        if name not in self.programs:
            raise KeyError(f"Shader '{name}' no cargado. Usa load_program() primero.")
        return self.programs[name]
