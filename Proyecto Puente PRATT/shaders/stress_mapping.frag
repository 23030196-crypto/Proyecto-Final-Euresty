#version 330 core

/**
 * FRAGMENT SHADER - Stress Mapping Heatmap
 *
 * Mapeo cromático continuo:
 * Esfuerzo negativo (Compresión) → Rojo/Naranja
 * Esfuerzo neutral             → Gris claro
 * Esfuerzo positivo (Tensión)  → Azul/Cian
 *
 * Entrada: stress_normalized ∈ [-1.0, 1.0]
 * Salida: Color RGB con saturación proporcional a |stress|
 */

// Entrada del Vertex Shader
in VS_OUT {
    vec3 position_world;
    float stress;             // [-1.0 (compresión máx) a 1.0 (tensión máx)]
} fs_in;

// Uniforms para ajuste en tiempo real
uniform float stress_threshold;  // Valor donde color alcanza saturación máxima
uniform float intensity;         // Multiplicador global de intensidad

// Salida
out vec4 FragColor;

/**
 * Mapea esfuerzo normalizado a color continuo
 * Entrada: stress ∈ [-1.0, 1.0]
 * Salida: RGB con heatmap suave
 */
vec3 stress_to_color(float stress)
{
    vec3 color = vec3(0.4, 0.4, 0.4); // Gris neutro por defecto

    if (stress > 0.01) {
        // TENSIÓN: Azul → Cian
        // stress = 0.1 → azul tenue
        // stress = 1.0 → cian brillante
        float t = min(stress / stress_threshold, 1.0);
        color = vec3(
            0.0,                           // R: sin rojo
            0.3 + t * 0.7,                 // G: azul+cian (0.3 → 1.0)
            0.4 + t * 0.6                  // B: azul brillante (0.4 → 1.0)
        );
    }
    else if (stress < -0.01) {
        // COMPRESIÓN: Rojo → Naranja
        // stress = -0.1 → rojo tenue
        // stress = -1.0 → naranja brillante
        float t = min(-stress / stress_threshold, 1.0);
        color = vec3(
            0.6 + t * 0.4,                 // R: rojo intenso (0.6 → 1.0)
            0.1 + t * 0.5,                 // G: naranja (0.1 → 0.6)
            0.0                            // B: sin azul
        );
    }

    return color;
}

void main()
{
    // Obtener color basado en esfuerzo normalizado
    vec3 base_color = stress_to_color(fs_in.stress);

    // Aplicar intensidad global
    vec3 final_color = base_color * intensity;

    // Clamp para evitar overflow
    final_color = clamp(final_color, 0.0, 1.0);

    // Salida: RGB + Alpha=1.0 (opaco)
    FragColor = vec4(final_color, 1.0);
}
