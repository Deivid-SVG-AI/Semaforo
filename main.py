import cv2
import numpy as np
import time
import pygame

# ----------------------------
# CONFIG
# ----------------------------
SOUND_FILE = r"assets/beep2.mp3"  # Ajusta la ruta a tu mp3

# Inicializar pygame mixer (sonido)
try:
    pygame.mixer.init()
    pygame.mixer.music.load(SOUND_FILE)
except Exception as e:
    print("Aviso: pygame no pudo inicializar o cargar el mp3:", e)
    # Seguimos sin sonido si falla.

# Tamaño ventana / semáforo
width, height = 200, 550
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
BUTTON_COLOR = (0, 180, 255)
BUTTON_PRESSED_COLOR = (100, 100, 100)

# Secuencia (nombre, duración por defecto)
sequence = [("green", 30), ("yellow", 4), ("red", 45)]
seq_len = len(sequence)

# Estado inicial
idx = 0
state_name, state_duration = sequence[idx]
state_start = time.time()

# Mostrar info por tecla 'i'
show_info = False

# Próxima roja especial
next_red_duration = None

# Estado del botón S
s_pressed = False
prev_s_pressed = False

# Braille: mapping de letras (Grade-1 uncontracted) usando puntos 1..6
# Representación en sets de números {dots}
BRAILLE_MAP = {
    "P": {1,2,3,4},
    "U": {1,3,6},
    "S": {2,3,4},
    "H": {1,2,5}
}

# El texto que queremos escribir en braille (debe corresponder a BRAILLE_MAP keys)
BRAILLE_TEXT = "PUSH"

# Parámetros visuales de braille
DOT_RADIUS = 2
CELL_SPACING = 8  # espacio entre celdas de braille

# ----------------------------
# DIBUJO Y LÓGICA
# ----------------------------
cv2.namedWindow("Semaforo", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Semaforo", width*2, height*2)

def draw_frame(active, blink_on, show_info_flag, remaining_seconds, s_button_state):
    """
    Devuelve la imagen (numpy array) del semáforo con botón.
    Dibuja las celdas braille que representan la palabra PUSH arriba de la palabra.
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
    press_offset = 4 if s_button_state else 0
    btn_y1 = btn_top + press_offset
    btn_y2 = btn_top + btn_height + press_offset

    btn_color = BUTTON_PRESSED_COLOR if s_button_state else BUTTON_COLOR
    cv2.rectangle(img, (btn_x1, btn_y1 - 5), (btn_x2, btn_y2), btn_color, -1, cv2.LINE_AA)

    # Draw "PUSH" centrado (OpenCV)
    text = "PUSH"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.6
    thickness = 2
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    text_x = (btn_x1 + btn_x2) // 2 - tw // 2
    text_y = btn_y1 + (btn_height // 2) + th // 2 - 2 + press_offset
    cv2.putText(img, text, (text_x, text_y), font, scale, (0,0,0), thickness, cv2.LINE_AA)

    # Área para dibujar las celdas braille ARRIBA de PUSH (dentro del botón)
    pad_x = 8
    upper_area = (btn_x1 + pad_x, btn_y1 + 6, btn_x2 - pad_x, text_y - 6)
    ua_x1, ua_y1, ua_x2, ua_y2 = upper_area
    ua_w = ua_x2 - ua_x1
    ua_h = ua_y2 - ua_y1

    # Cantidad de celdas = numero de caracteres en BRAILLE_TEXT
    n_cells = len(BRAILLE_TEXT)
    # ancho disponible por celda considerando espacios
    total_spacing = CELL_SPACING * (n_cells - 1)
    cell_w = (ua_w - total_spacing) / n_cells
    cell_h = ua_h  # usar toda la altura del área

    # Para cada celda (letra), calcular coordenadas de los 6 puntos
    for i, ch in enumerate(BRAILLE_TEXT):
        ch = ch.upper()
        cell_x1 = int(ua_x1 + i * (cell_w + CELL_SPACING))
        cell_y1 = int(ua_y1)
        cell_x2 = int(cell_x1 + cell_w)
        cell_y2 = int(cell_y1 + cell_h)

        # Posiciones relativas para los 6 puntos dentro de la celda:
        # Columna izquierda (col=0), columna derecha (col=1)
        # Filas: 3 (top, mid, bottom)
        # calculamos coordenadas concretas:
        left_x = int(cell_x1 + 0.25 * (cell_x2 - cell_x1))
        right_x = int(cell_x1 + 0.75 * (cell_x2 - cell_x1))
        top_y = int(cell_y1 + 0.18 * (cell_y2 - cell_y1))
        mid_y = int(cell_y1 + 0.5 * (cell_y2 - cell_y1))
        bot_y = int(cell_y1 + 0.82 * (cell_y2 - cell_y1))

        # mapa de índices a coords
        coords = {
            1: (left_x, top_y-8),
            2: (left_x, mid_y-8),
            3: (left_x, bot_y-8),
            4: (right_x, top_y-8),
            5: (right_x, mid_y-8),
            6: (right_x, bot_y-8)
        }

        dots = BRAILLE_MAP.get(ch, set())
        for d in range(1,7):
            if d in dots:
                cv2.circle(img, coords[d], DOT_RADIUS, (0,0,0), -1)
            else:
                # opcional: dibujar puntos no-relieve como círculos pequeños grises (comentar si no se desea)
                pass

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

    # Dibuja frame y muestra
    frame = draw_frame(state_name, blink_on, show_info, remaining, s_pressed)
    cv2.imshow("Semaforo", frame)

    # Espera y captura key (100 ms)
    key = cv2.waitKey(100) & 0xFF

    # Actualizar estados de tecla S
    prev_s_pressed = s_pressed
    s_pressed = (key == ord('s') or key == ord('S'))

    # Eventos globales
    if key == ord('q') or key == 27:  # 'q' o ESC
        break
    elif key == ord('i') or key == ord('I'):  # toggle info
        show_info = not show_info

    # Comportamiento al mantener presionada S
    if s_pressed:
        if state_name == "green" and remaining > 5:
            state_start = now - (state_duration - 5)
        if state_name != "red":
            next_red_duration = 60

    # Detectar soltado de S (antes presionado y ahora no) -> reproducir sonido
    if prev_s_pressed and not s_pressed:
        play_sound_on_release()

# Cleanup
cv2.destroyAllWindows()
try:
    pygame.mixer.quit()
except Exception:
    pass
