import time
import math
import board
import digitalio
import neopixel

# ============================================================
# NEOPIXEL SETUP (RGBW)
# ============================================================

PIXEL_PIN = board.NEOPIXEL1
NUM_PIXELS = 3

# If colors are wrong (red/green swapped), try neopixel.GRBW instead.
PIXEL_ORDER = neopixel.RGBW

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    NUM_PIXELS,
    brightness=1.0,  # full global brightness
    auto_write=False,
    pixel_order=PIXEL_ORDER,
)

# LED index mapping
LED_A = 0  # warm white
LED_B = 1  # moonlight OR effect pixel 1
LED_C = 2  # effect pixel 2

# ============================================================
# BUTTONS (3-wire S / V / G modules)
# Wire: V->3V, G->GND, S->pin
# ============================================================

BTN_A_PIN = board.D6  # button A
BTN_B_PIN = board.D5  # button B
BTN_E_PIN = board.D9  # effect button

BTN_PINS = [BTN_A_PIN, BTN_B_PIN, BTN_E_PIN]

buttons = []
last_pressed = [False, False, False]

for pin in BTN_PINS:
    b = digitalio.DigitalInOut(pin)
    b.direction = digitalio.Direction.INPUT
    b.pull = digitalio.Pull.DOWN  # active-HIGH modules
    buttons.append(b)
# ============================================================
# COLORS (RGBW tuples: R, G, B, W) 0..255
# ============================================================

# A: bright warm white
WARM_WHITE = (0, 0, 0, 255)

# B: moonlight (blue + white)
MOONLIGHT = (0, 0, 140, 110)

OFF = (0, 0, 0, 0)

# ============================================================
# RIVER EFFECT (no intentional dimming)
# Two LEDs rotate contrasting colors, never intentionally dimming.
# ============================================================

# Palette (RGBW). Keep W=0 for saturated color.
PALETTE = [
    (0, 255, 80, 0),  # green/aqua
    (0, 80, 255, 0),  # blue
    (0, 0, 255, 0),  # purple  (fixed)
]


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def blend_rgbw(c1, c2, t: float):
    """Blend two RGBW colors."""
    t = clamp01(t)
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
        int(lerp(c1[3], c2[3], t)),
    )


def normalize_max255(c):
    """
    Prevents the 'dimming' feel by scaling so the brightest channel is 255.
    (At least one channel stays at full strength during transitions.)
    """
    r, g, b, w = c
    m = max(r, g, b, w)
    if m <= 0:
        return OFF
    s = 255.0 / m
    return (int(r * s), int(g * s), int(b * s), int(w * s))


def smoothstep(x: float) -> float:
    """Smooth 0..1 -> 0..1 easing."""
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def palette_cycle(phase01: float):
    """
    phase01 wraps smoothly through PALETTE.
    """
    p = phase01 % 1.0
    n = len(PALETTE)

    pos = p * n
    i0 = int(pos) % n
    i1 = (i0 + 1) % n
    t = smoothstep(pos - int(pos))

    blended = blend_rgbw(PALETTE[i0], PALETTE[i1], t)
    return normalize_max255(blended)


# ============================================================
# STATE
# ============================================================

a_on = False  # LED A toggle
b_on = False  # LED B toggle
effect_on = False

# ============================================================
# MAIN LOOP
# ============================================================

while True:
    # ----- button edge detection -----
    for i, b in enumerate(buttons):
        pressed = b.value
        if pressed and not last_pressed[i]:
            # Button A: always works
            if i == 0:
                a_on = not a_on
            # Button B: only when effect is OFF
            elif i == 1:
                if not effect_on:
                    b_on = not b_on
            # Effect button: toggles river effect and forces B off
            elif i == 2:
                effect_on = not effect_on
                if effect_on:
                    b_on = False
        last_pressed[i] = pressed
    # ----- Render LED A (unaffected by effect) -----
    pixels[LED_A] = WARM_WHITE if a_on else OFF

    # ----- Render B or effect -----
    if effect_on:
        t = time.monotonic()

        # ----- SPEED CONTROLS -----
        # Color rotates fast (ripples / shimmer)
        COLOR_SPEED = 0.06  # increase for faster color travel
        # A slower wave modulates how quickly the color "slides" (gives ripple feel)
        WAVE_SPEED = 0.4  # increase for faster ripple motion
        # How strong the wave influence is (0.0–0.5 is a good range)
        WAVE_DEPTH = 0.22

        # Base phase: smooth fast movement through palette space
        base = t * COLOR_SPEED

        # Ripple wave (smooth, not jerky): -1..1
        wave1 = math.sin(2 * math.pi * (t * WAVE_SPEED))
        wave2 = math.sin(2 * math.pi * (t * (WAVE_SPEED * 1.31) + 0.23))

        # Combine waves into a smooth "current" offset
        ripple = WAVE_DEPTH * (0.65 * wave1 + 0.35 * wave2)

        # Two LEDs: same motion, different phase offsets for contrast
        phase_a = base + ripple + 0.00
        phase_b = base - ripple + 0.25  # opposite side of palette for contrast

        pixels[LED_B] = palette_cycle(phase_a)
        pixels[LED_C] = palette_cycle(phase_b)
    else:
        pixels[LED_B] = MOONLIGHT if b_on else OFF
        pixels[LED_C] = OFF
    pixels.show()
    time.sleep(0.01)
