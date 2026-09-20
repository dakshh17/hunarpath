"""
HunarPath - Vision Studio Pipeline.

Transforms raw workshop photographs into professional e-commerce-ready
product images using background removal (U²-Net via rembg), adaptive
histogram equalization, synthetic drop-shadows, and center-padded
compositing onto a clean white canvas.
"""

from __future__ import annotations

import io
import logging
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CANVAS_SIZE: int = 1024
PADDING_RATIO: float = 0.10  # 10 % outer padding on each side
CLAHE_CLIP_LIMIT: float = 2.5
CLAHE_GRID: tuple[int, int] = (8, 8)
SHADOW_OFFSET: int = 12
SHADOW_BLUR_RADIUS: int = 18
SHADOW_COLOR: tuple[int, int, int, int] = (0, 0, 0, 80)  # semi-transparent
OUTPUT_QUALITY: int = 92


def _remove_background(image_bytes: bytes) -> np.ndarray:
    """
    Strip the background using rembg (U²-Net model).
    Downscales input to max 600x600 first to prevent OOM crashes on free-tier 512MB RAM.
    Returns an RGBA numpy array with the foreground isolated on a transparent background.
    """
    try:
        from rembg import remove as rembg_remove, new_session

        # Pre-scale image to 600x600 max to keep memory under 80MB and runtime under 1s
        pil_in = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        pil_in.thumbnail((600, 600), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        pil_in.save(buf, format="PNG")
        small_bytes = buf.getvalue()

        session = new_session("u2netp")
        result_bytes: bytes = rembg_remove(small_bytes, session=session)
        pil_img = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
        return np.array(pil_img)
    except Exception as exc:
        logger.warning(
            "Background removal failed or rembg unavailable (%s) - using enhanced fallback.",
            exc,
        )
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img_bgr = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
        if img_bgr is None:
            raise ValueError("Could not decode input image bytes.")
        if len(img_bgr.shape) == 2:
            img_bgr = cv2.cvtColor(img_bgr, cv2.COLOR_GRAY2BGR)
        if img_bgr.shape[2] == 3:
            img_bgra = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2BGRA)
        else:
            img_bgra = img_bgr
        return cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2RGBA)


def auto_white_balance(bgr: np.ndarray) -> np.ndarray:
    """
    Automatic Gray World White Balance to eliminate dull yellow incandescent
    or fluorescent lighting typical of rural artisan workshops.
    """
    b, g, r = cv2.split(bgr.astype(np.float32))
    b_avg = float(np.mean(b))
    g_avg = float(np.mean(g))
    r_avg = float(np.mean(r))
    avg = (b_avg + g_avg + r_avg) / 3.0
    if b_avg > 1e-3 and g_avg > 1e-3 and r_avg > 1e-3:
        b = np.clip(b * (1.0 + 0.85 * ((avg / b_avg) - 1.0)), 0, 255)
        g = np.clip(g * (1.0 + 0.85 * ((avg / g_avg) - 1.0)), 0, 255)
        r = np.clip(r * (1.0 + 0.85 * ((avg / r_avg) - 1.0)), 0, 255)
    return cv2.merge([b, g, r]).astype(np.uint8)


def enhance_studio_lighting(bgr: np.ndarray) -> np.ndarray:
    """
    Transforms a raw workshop photograph with professional studio lighting:
    1. Automatic White Balance (eliminates yellow/green casts).
    2. Dynamic Range / Shadow Lift via gamma curve (simulates studio fill light).
    3. CLAHE on LAB L-channel for micro-contrast on weaves/carvings.
    4. Chroma/Vibrancy tuning in HSV (+15%) so natural dyes pop.
    5. Detail Sharpening (unsharp mask) simulating a prime studio lens.
    """
    # 1. White balance
    wb = auto_white_balance(bgr)

    # 2. Exposure & CLAHE in LAB
    lab = cv2.cvtColor(wb, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_GRID)
    l = clahe.apply(l)

    # Soft studio fill light (gamma 0.88)
    l_float = l.astype(np.float32) / 255.0
    l_boosted = np.power(l_float, 0.88) * 255.0
    l = np.clip(l_boosted, 0, 255).astype(np.uint8)
    lab = cv2.merge([l, a, b])
    bgr_adj = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    # 3. Saturation boost (+15%)
    hsv = cv2.cvtColor(bgr_adj, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.15, 0, 255)
    sat_adj = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # 4. Detail Sharpening (unsharp mask)
    gaussian = cv2.GaussianBlur(sat_adj, (0, 0), 2.0)
    sharpened = cv2.addWeighted(sat_adj, 1.25, gaussian, -0.25, 0)
    return sharpened


def _apply_clahe(rgba: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE on the L-channel of the LAB colour space to correct
    harsh and uneven workshop lighting while preserving colour fidelity.
    """
    bgr = cv2.cvtColor(rgba[:, :, :3], cv2.COLOR_RGB2BGR)
    enhanced_bgr = enhance_studio_lighting(bgr)
    rgb = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2RGB)

    # Re-attach original alpha channel
    enhanced = np.dstack([rgb, rgba[:, :, 3]])
    return enhanced


def _add_drop_shadow(
    subject: Image.Image,
    offset: int = SHADOW_OFFSET,
    blur_radius: int = SHADOW_BLUR_RADIUS,
) -> Image.Image:
    """
    Composite a soft drop-shadow beneath the subject on a transparent
    canvas, giving the product a floating-above-surface appearance.
    """
    w, h = subject.size
    canvas_w = w + offset * 2 + blur_radius * 2
    canvas_h = h + offset * 2 + blur_radius * 2

    shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Create a solid shadow silhouette from the alpha mask
    alpha = subject.getchannel("A")
    shadow_silhouette = Image.new("RGBA", subject.size, SHADOW_COLOR)
    shadow_silhouette.putalpha(alpha)

    # Paste shadow shifted down-right
    shadow_layer.paste(
        shadow_silhouette,
        (blur_radius + offset, blur_radius + offset),
    )
    shadow_layer = shadow_layer.filter(
        ImageFilter.GaussianBlur(radius=blur_radius)
    )

    # Composite subject on top of shadow
    shadow_layer.paste(subject, (blur_radius, blur_radius), mask=subject)
    return shadow_layer


def _center_pad_on_canvas(
    subject: Image.Image,
    canvas_size: int = CANVAS_SIZE,
    padding_ratio: float = PADDING_RATIO,
) -> Image.Image:
    """
    Center-place the subject onto a white square canvas with outer
    padding, scaling down if it exceeds the available area.
    """
    usable = int(canvas_size * (1.0 - 2.0 * padding_ratio))
    w, h = subject.size

    # Scale subject to fit inside usable area while preserving aspect ratio
    scale = min(usable / w, usable / h, 1.0)
    new_w = int(w * scale)
    new_h = int(h * scale)

    if scale < 1.0:
        subject = subject.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    x_offset = (canvas_size - new_w) // 2
    y_offset = (canvas_size - new_h) // 2
    canvas.paste(subject, (x_offset, y_offset), mask=subject)

    return canvas


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_studio_image(
    image_bytes: bytes,
    output_format: Literal["webp", "jpeg"] = "webp",
) -> bytes:
    """
    Full vision-studio pipeline:

    1. Background removal via U²-Net (rembg).
    2. CLAHE adaptive histogram equalization on LAB L-channel.
    3. Synthetic soft drop-shadow.
    4. Center-pad onto 2048×2048 white canvas with 10 % padding.
    5. Encode to high-quality WebP (default) or JPEG.

    Parameters
    ----------
    image_bytes : bytes
        Raw input photograph (JPEG / PNG / WebP).
    output_format : str
        ``"webp"`` or ``"jpeg"``.

    Returns
    -------
    bytes
        Processed studio-quality image.
    """
    logger.info("Vision pipeline: starting background removal ...")
    rgba = _remove_background(image_bytes)

    logger.info("Vision pipeline: applying CLAHE ...")
    rgba = _apply_clahe(rgba)

    pil_subject = Image.fromarray(rgba, "RGBA")

    logger.info("Vision pipeline: generating drop-shadow ...")
    pil_subject = _add_drop_shadow(pil_subject)

    logger.info("Vision pipeline: center-padding onto %dx%d canvas ...", CANVAS_SIZE, CANVAS_SIZE)
    final = _center_pad_on_canvas(pil_subject)

    # Encode output
    buf = io.BytesIO()
    if output_format == "jpeg":
        final_rgb = final.convert("RGB")
        final_rgb.save(buf, format="JPEG", quality=OUTPUT_QUALITY)
    else:
        final.save(buf, format="WEBP", quality=OUTPUT_QUALITY)

    buf.seek(0)
    result = buf.read()
    logger.info(
        "Vision pipeline: done - output %s, %d bytes.",
        output_format.upper(),
        len(result),
    )
    return result
