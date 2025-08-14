import cv2
import numpy as np
import time
import glob
import os
import pygame

# ----------------------------
# CONFIG / DEPENDENCIAS
# ----------------------------
# Requiere: pip install opencv-python numpy pygame pillow
# Coloca tu archivo mp3 en la ruta SOUND_FILE (o ajusta la ruta)
SOUND_FILE = r"assets/beep2.mp3"

# Inicializar pygame mixer (sonido)
try:
    pygame.mixer.init()
    pygame.mixer.music.load(SOUND_FILE)
except Exception as e:
    print("Aviso: pygame no pudo inicializar o cargar el mp3:", e)
    # Seguimos sin sonido si falla.

# Tamaño ventana / semáforo
width, height = 200, 550  # aumenté altura para botón
center_x = width // 2
positions = (100, 250, 400)  # y positions para luces (arriba, medio, abajo)
radius = 40
housing_color = (30, 30, 30)
bg_color = (200, 200, 200)

# Colores
COLOR_RED = (0, 0, 255)
COLOR_YELLOW = (0, 255, 255)
COLOR_GREEN = (0, 255, 0)
COLOR_GRAY = (80, 80, 80)
TEXT_COLOR = (255, 255, 255)
BUTTON_COLOR = (0, 180, 255)       # botón normal
BUTTON_PRESSED_COLOR = (100, 100, 100)  # presionado (oscuro)

# Secuencia (nombre, duración por defecto)
sequence = [("green", 30), ("yellow", 5), ("red", 30)]
seq_len = len(sequence)

# Estado inicial
idx = 0
state_name, state_duration = sequence[idx]
state_start = time.time()

# Mostrar info por tecla 'i' (por defecto False)
show_info = False

# Próxima roja especial (None o número de segundos)
next_red_duration = None

# Estado del botón S (presionado)
s_pressed = False
prev_s_pressed = False

# Parámetros de braille / puntos
DOT_RADIUS = 5
# Buscamos un archivo cuyo nombre empiece por 'braille_half' en el directorio actual o 'assets'
braille_candidates = glob.glob("braille_half*") + glob.glob(os.path.join("assets", "braille_half*"))
braille_image_path = braille_candidates[0] if braille_candidates else None

def load_or_generate_braille_norm_centroids(path):
    """
    Si existe una imagen 'path', extrae los "puntos" (blobs) y devuelve
    una lista de centroides normalizados (nx, ny) en rango [0,1].
    Si no hay imagen o no se detectan puntos, devuelve patrón 2x3 centrado.
    """
    if path is None:
        # fallback grid 2x3
        cols = 2; rows = 3
        pts = []
        for r in range(rows):
            for c in range(cols):
                nx = (c + 0.5) / cols
                ny = (r + 0.5) / rows
                pts.append((nx, ny))
        return pts

    import cv2 as _cv
    import numpy as _np
    try:
        img = _cv.imread(path, _cv.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("No se pudo leer imagen")
        # Convertir a gris robustamente
        if img.ndim == 2:
            gray = img.copy()
        elif img.shape[2] == 4:
            gray = _cv.cvtColor(img[:,:,:3], _cv.COLOR_BGR2GRAY)
        else:
            gray = _cv.cvtColor(img, _cv.COLOR_BGR2GRAY)

        blur = _cv.GaussianBlur(gray, (5,5), 0)
        _, thresh = _cv.threshold(blur, 0, 255, _cv.THRESH_BINARY + _cv.THRESH_OTSU)
        # asegurar que los puntos quedan blancos para detectar contornos
        if _np.mean(blur) > 127:
            thresh = 255 - thresh

        contours, _ = _cv.findContours(thresh, _cv.RETR_EXTERNAL, _cv.CHAIN_APPROX_SIMPLE)
        centroids = []
        for cnt in contours:
            area = _cv.contourArea(cnt)
            if area < 8:
                continue
            M = _cv.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            centroids.append((cx, cy))

        # ordenar y normalizar
        if len(centroids) == 0:
            raise RuntimeError("No se detectaron contornos válidos")
        centroids = sorted(centroids, key=lambda c: (c[1], c[0]))
        h, w = gray.shape
        norm = [ (cx / w, cy / h) for (cx, cy) in centroids ]
        return norm
    except Exception as e:
        # fallback 2x3
        print("Aviso: no se pudieron extraer puntos braille de la imagen:", e)
        cols = 2; rows = 3
        pts = []
        for r in range(rows):
            for c in range(cols):
                nx = (c + 0.5) / cols
                ny = (r + 0.5) / rows
                pts.append((nx, ny))
        return pts

# Cargar o generar puntos normalizados
norm_centroids = load_or_generate_braille_norm_centroids(braille_image_path)

# ----------------------------
# DIBUJO Y LÓGICA
# ----------------------------
cv2.namedWindow("Semaforo", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Semaforo", width*2, height*2)

def draw_frame(active, blink_on, show_info_flag, remaining_seconds, s_button_state):
    """
    Devuelve la imagen (numpy array) del semáforo con botón.
    s_button_state: bool → si True, dibuja el botón 'presionado' (oscurecido y hundido)
    """
    img = np.full((height, width, 3), bg_color, dtype=np.uint8)

    # Caja semáforo
    cv2.rectangle(img, (40, 40), (width-40, height-40), housing_color, -1, cv2.LINE_AA)

    # Colores de luces
    colors = {
        "red": COLOR_RED if active == "red" else COLOR_GRAY,
        "yellow": COLOR_YELLOW if active == "yellow" else COLOR_GRAY,
        "green": COLOR_GREEN if active == "green" and blink_on else COLOR_GRAY
    }

    # Luces
    cv2.circle(img, (center_x, positions[0]), radius, colors["red"], -1, cv2.LINE_AA)
    cv2.circle(img, (center_x, positions[1]), radius, colors["yellow"], -1, cv2.LINE_AA)
    cv2.circle(img, (center_x, positions[2]), radius, colors["green"], -1, cv2.LINE_AA)

    # Botón (con "hundimiento" visual si s_button_state)
    btn_top = positions[2] + 70
    btn_height = 60
    btn_x1 = 60
    btn_x2 = width - 60
    # hundimiento: desplazamiento vertical mientras presionado
    press_offset = 4 if s_button_state else 0
    btn_y1 = btn_top + press_offset
    btn_y2 = btn_top + btn_height + press_offset

    btn_color = BUTTON_PRESSED_COLOR if s_button_state else BUTTON_COLOR
    cv2.rectangle(img, (btn_x1, btn_y1), (btn_x2, btn_y2), btn_color, -1, cv2.LINE_AA)

    # Draw "PUSH" centrado (OpenCV)
    text = "PUSH"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.6
    thickness = 2
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    text_x = (btn_x1 + btn_x2) // 2 - tw // 2
    text_y = btn_y1 + (btn_height // 2) + th // 2 - 2 + press_offset
    cv2.putText(img, text, (text_x, text_y), font, scale, (0,0,0), thickness, cv2.LINE_AA)

    # Áreas para puntos braille (arriba y abajo de la palabra PUSH)
    pad_x = 10
    upper_area = (btn_x1 + pad_x, btn_y1 + 6, btn_x2 - pad_x, text_y - 6)
    lower_area = (btn_x1 + pad_x, text_y + 6, btn_x2 - pad_x, btn_y2 - 6)

    # Dibujar puntos normalizados y su versión volteada (180°) abajo
    for (nx, ny) in norm_centroids:
        ux = int(upper_area[0] + nx * (upper_area[2] - upper_area[0]))
        uy = int(upper_area[1] + ny * (upper_area[3] - upper_area[1]))
        cv2.circle(img, (ux, uy), DOT_RADIUS, (0,0,0), -1)

        # Volteado 180°: invertir ambas coordenadas (1-nx, 1-ny)
        fx = int(lower_area[0] + (1 - nx) * (lower_area[2] - lower_area[0]))
        fy = int(lower_area[1] + (1 - ny) * (lower_area[3] - lower_area[1]))
        cv2.circle(img, (fx, fy), DOT_RADIUS, (0,0,0), -1)

    # Info texto opcional (estado + remaining)
    if show_info_flag:
        remaining = max(0, int(remaining_seconds + 0.999))
        label = f"{active.upper()}  {remaining}s"
        cv2.putText(img, label, (10, height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, TEXT_COLOR, 2, cv2.LINE_AA)

    return img

def play_sound_on_release():
    """Reproducir sonido con pygame (no bloqueante)."""
    try:
        # Si la música está sonando, detenerla y volver a reproducir
        if pygame.mixer.get_init() is None:
            print("pygame mixer no inicializado; no se reproduce sonido.")
            return
        pygame.mixer.music.stop()
        pygame.mixer.music.play()
    except Exception as e:
        print("Error reproduciendo sonido con pygame:", e)

# ----------------------------
# Bucle principal
# ----------------------------
while True:
    img = np.full((height, width, 3), bg_color, dtype=np.uint8)

    now = time.time()
    # Cambio de fase si se agotó el tiempo
    if now - state_start >= state_duration:
        idx = (idx + 1) % seq_len
        state_name, state_duration = sequence[idx]

        # Aplicar duración especial si entramos en rojo
        if state_name == "red" and next_red_duration is not None:
            state_duration = next_red_duration
            next_red_duration = None

        state_start = now
        now = time.time()

    elapsed = now - state_start
    remaining = state_duration - elapsed

    # Blink para verde últimos 5s (0.5s on/off)
    if state_name == "green" and remaining <= 5:
        blink_on = int(now * 2) % 2 == 0
    else:
        blink_on = (state_name == "green")

    # Dibuja frame
    frame = draw_frame(state_name, blink_on, show_info, remaining, s_pressed)
    cv2.imshow("Semaforo", frame)

    # Espera y captura key (100 ms)
    key = cv2.waitKey(100) & 0xFF

    # Actualizar estados de tecla S
    prev_s_pressed = s_pressed
    # Nota: cv2.waitKey detecta tecla solo cuando ocurre dentro del intervalo de espera.
    # Esto funciona razonablemente para uso interactivo simple.
    s_pressed = (key == ord('s') or key == ord('S'))

    # Eventos globales
    if key == ord('q') or key == 27:  # 'q' o ESC
        break
    elif key == ord('i') or key == ord('I'):  # toggle info
        show_info = not show_info

    # Comportamiento al mantener presionada S
    if s_pressed:
        # Si estamos en verde y faltan >5s, acortar a 5s restantes (sin cambiar duración base)
        if state_name == "green" and remaining > 5:
            state_start = now - (state_duration - 5)
        # Si no estamos en rojo, programar próxima roja a 60s
        if state_name != "red":
            next_red_duration = 60

    # Detectar soltado de S (antes presionado y ahora no) -> reproducir sonido
    if prev_s_pressed and not s_pressed:
        play_sound_on_release()

# Cleanup
cv2.destroyAllWindows()
pygame.mixer.quit()
