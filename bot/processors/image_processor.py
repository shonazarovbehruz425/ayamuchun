import os
import io
import asyncio
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps, ImageFilter, ImageEnhance
import numpy as np

class ImageProcessor:
    """
    Professional Document & ID Photo (3x4 cm) Processor.
    Handles standard portrait framing, smart background coloring/replacement,
    aspect ratio enforcement (3:4 at 300 DPI), and ready-to-print 10x15 cm photo sheets.
    """

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> tuple:
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 3:
            hex_str = ''.join([c*2 for c in hex_str])
        if len(hex_str) == 6:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        return (255, 255, 255)

    @classmethod
    def _process_photo_3x4_sync(
        cls,
        input_path: str,
        output_single_path: str,
        output_sheet_path: str,
        bg_color_hex: str = "#FFFFFF",
        change_bg: bool = False,
        add_corner: bool = False,
        brightness: float = 1.0,
        contrast: float = 1.0,
        dpi: int = 300
    ) -> dict:
        with Image.open(input_path) as raw_img:
            img = ImageOps.exif_transpose(raw_img)
            if img.mode != 'RGB':
                img = img.convert('RGB')

        orig_w, orig_h = img.size

        # Standard 30x40 mm at 300 DPI
        target_w = int(round(30 / 25.4 * dpi)) # ~354 px
        target_h = int(round(40 / 25.4 * dpi)) # ~472 px

        # Smart Portrait Framing (Focus on upper body & head)
        target_aspect = target_w / target_h # 0.75
        current_aspect = orig_w / orig_h

        if current_aspect > target_aspect:
            new_w = int(orig_h * target_aspect)
            left = (orig_w - new_w) // 2
            crop_box = (left, 0, left + new_w, orig_h)
        else:
            new_h = int(orig_w / target_aspect)
            top_offset = int((orig_h - new_h) * 0.20)
            top_offset = max(0, min(top_offset, orig_h - new_h))
            crop_box = (0, top_offset, orig_w, top_offset + new_h)

        cropped = img.crop(crop_box)
        single = cropped.resize((target_w, target_h), Image.LANCZOS)

        # Background Replacement using GrabCut
        if change_bg:
            try:
                import cv2
                cv_img = np.array(single)
                cv_img_bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)

                h, w = cv_img_bgr.shape[:2]
                mask = np.zeros((h, w), np.uint8)
                bgd_model = np.zeros((1, 65), np.float64)
                fgd_model = np.zeros((1, 65), np.float64)

                rect = (int(w * 0.08), int(h * 0.05), int(w * 0.84), int(h * 0.93))
                cv2.grabCut(cv_img_bgr, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)

                mask2 = np.where((mask == 2) | (mask == 0), 0, 1).astype('uint8')
                mask_pil = Image.fromarray((mask2 * 255).astype(np.uint8))
                mask_pil = mask_pil.filter(ImageFilter.GaussianBlur(1.5))

                target_bg_rgb = cls._hex_to_rgb(bg_color_hex)
                bg_image = Image.new("RGB", (w, h), target_bg_rgb)
                single = Image.composite(single, bg_image, mask_pil)
            except Exception:
                pass

        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(single)
            single = enhancer.enhance(brightness)

        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(single)
            single = enhancer.enhance(contrast)

        enhancer = ImageEnhance.Sharpness(single)
        single = enhancer.enhance(1.12)

        if add_corner:
            corner_draw = ImageDraw.Draw(single)
            r = int(target_w * 0.24)
            corner_box = [target_w - r*2, target_h - r*2, target_w, target_h]
            corner_draw.arc(corner_box, start=0, end=90, fill=(210, 210, 210), width=2)

        single.save(output_single_path, format="JPEG", quality=95, dpi=(dpi, dpi))

        # 10x15 cm (4x6 inch) Print Sheet with 6 photos (2 rows x 3 cols)
        sheet_w = int(round(150 / 25.4 * dpi)) # 1772 px
        sheet_h = int(round(100 / 25.4 * dpi)) # 1181 px

        sheet = Image.new("RGB", (sheet_w, sheet_h), (255, 255, 255))
        draw = ImageDraw.Draw(sheet)

        cols = 3
        rows = 2
        gap_x = int(round(9 / 25.4 * dpi))
        gap_y = int(round(9 / 25.4 * dpi))

        total_grid_w = cols * target_w + (cols - 1) * gap_x
        total_grid_h = rows * target_h + (rows - 1) * gap_y

        start_x = (sheet_w - total_grid_w) // 2
        start_y = (sheet_h - total_grid_h) // 2

        for r_idx in range(rows):
            for c_idx in range(cols):
                px = start_x + c_idx * (target_w + gap_x)
                py = start_y + r_idx * (target_h + gap_y)

                sheet.paste(single, (px, py))
                draw.rectangle([px-1, py-1, px + target_w, py + target_h], outline=(225, 225, 225), width=1)

                c_len = 12
                draw.line([(px - c_len, py), (px, py)], fill=(185, 185, 185), width=1)
                draw.line([(px, py - c_len), (px, py)], fill=(185, 185, 185), width=1)
                draw.line([(px + target_w, py), (px + target_w + c_len, py)], fill=(185, 185, 185), width=1)
                draw.line([(px + target_w, py - c_len), (px + target_w, py)], fill=(185, 185, 185), width=1)
                draw.line([(px - c_len, py + target_h), (px, py + target_h)], fill=(185, 185, 185), width=1)
                draw.line([(px, py + target_h), (px, py + target_h + c_len)], fill=(185, 185, 185), width=1)
                draw.line([(px + target_w, py + target_h), (px + target_w + c_len, py + target_h)], fill=(185, 185, 185), width=1)
                draw.line([(px + target_w, py + target_h), (px + target_w, py + target_h + c_len)], fill=(185, 185, 185), width=1)

        sheet.save(output_sheet_path, format="JPEG", quality=95, dpi=(dpi, dpi))

        return {
            "single_width": target_w,
            "single_height": target_h,
            "single_size_bytes": os.path.getsize(output_single_path),
            "sheet_width": sheet_w,
            "sheet_height": sheet_h,
            "sheet_size_bytes": os.path.getsize(output_sheet_path),
            "dpi": dpi,
            "photo_count_sheet": 6
        }

    async def process_photo_3x4(
        self,
        input_path: str,
        output_single_path: str,
        output_sheet_path: str,
        bg_color_hex: str = "#FFFFFF",
        change_bg: bool = False,
        add_corner: bool = False,
        brightness: float = 1.0,
        contrast: float = 1.0,
        dpi: int = 300
    ) -> dict:
        return await asyncio.to_thread(
            self._process_photo_3x4_sync,
            input_path,
            output_single_path,
            output_sheet_path,
            bg_color_hex,
            change_bg,
            add_corner,
            brightness,
            contrast,
            dpi
        )
