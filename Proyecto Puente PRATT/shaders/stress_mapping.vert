#version 330 core

/**
 * VERTEX SHADER - Stress Mapping Moderno
 *
 * Responsabilidades:
 * - Recibir posiciones actualizadas del VBO
 * - Recibir esfuerzo normalizado como atributo por vértice
 * - Transformar coordenadas a espacio clip
 * - Pasar esfuerzo normalizado al Fragment Shader
 */

// Atributos de entrada (desde VBO)
layout(location = 0) in vec3 position;        // Posición 3D del vértice
layout(location = 1) in float stress_normalized; // Esfuerzo normalizado [-1.0, 1.0]

// Uniforms (constantes para todos los vértices en un frame)
uniform mat4 projection;
uniform mat4 view;
uniform mat4 model;

// Salida hacia Fragment Shader
out VS_OUT {
    vec3 position_world;     // Posición en espacio mundial
    float stress;            // Esfuerzo normalizado para interpolación
} vs_out;

void main()
{
    // Transformar posición a espacio clip
    vec4 pos_world = model * vec4(position, 1.0);
    gl_Position = projection * view * pos_world;

    // Pasar datos al Fragment Shader
    vs_out.position_world = pos_world.xyz;
    vs_out.stress = stress_normalized;  // [-1.0 (compresión) a 1.0 (tensión)]
}
