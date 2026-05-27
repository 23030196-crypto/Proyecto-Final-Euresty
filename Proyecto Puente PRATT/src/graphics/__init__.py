"""
Módulo de Gráficos - Pipeline Moderno OpenGL

Componentes:
- shader_manager.py: Compilación y gestión de shaders GLSL
- vbo_manager.py: Gestión de Vertex Buffer Objects (geometría GPU)
- shader_renderer.py: Renderizador integrado (shaders + VBO)
"""

from .shader_manager import ShaderManager, ShaderProgram, Shader
from .vbo_manager import VBOManager, VBOLine
from .shader_renderer import ShaderRenderer

__all__ = [
    'ShaderManager',
    'ShaderProgram',
    'Shader',
    'VBOManager',
    'VBOLine',
    'ShaderRenderer',
]
