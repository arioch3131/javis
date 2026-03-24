from typing import Optional, Tuple

from PIL import Image, ImageOps

try:
    from PyQt6.QtGui import QImage, QPixmap

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

from ai_content_classifier.services.thumbnail.generators import BaseThumbnailGenerator


class QtPilGenerator(BaseThumbnailGenerator):
    """Thumbnail generator for raster images using PIL/Pillow with Qt output."""

    def generate(
        self, image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
    ) -> Optional[QPixmap]:
        if not QT_AVAILABLE:
            self.logger.warning("Qt thumbnails require Qt, which is not available")
            return None

        pil_img = None
        try:
            try:
                pil_img = Image.open(image_path)
            except (IOError, UnicodeEncodeError, UnicodeDecodeError):
                try:
                    with open(image_path, "rb") as f:
                        pil_img = Image.open(f)
                        pil_img.load()
                except Exception as e:
                    self.logger.error(f"Could not open image {image_path}: {e}")
                    return None

            if pil_img is None:
                self.logger.error(f"PIL image null after opening: {image_path}")
                return None

            if pil_img.format == "JPEG":
                try:
                    is_progressive = pil_img.info.get("progressive", False)
                    if is_progressive:
                        self.logger.debug(
                            f"Progressive JPEG detected for {image_path}, converting to baseline"
                        )
                        import io

                        baseline_buffer = io.BytesIO()
                        pil_img.save(
                            baseline_buffer,
                            format="JPEG",
                            quality=95,
                            progressive=False,
                            optimize=True,
                        )
                        baseline_buffer.seek(0)
                        pil_img.close()
                        pil_img = Image.open(baseline_buffer)
                        pil_img.load()
                except Exception as e:
                    self.logger.warning(
                        f"Error converting JPEG baseline for {image_path}: {e}"
                    )

            try:
                pil_img = ImageOps.exif_transpose(pil_img)
            except Exception as e:
                self.logger.warning(
                    f"Error correcting orientation for {image_path}: {e}"
                )

            # Convert to appropriate mode for Qt
            if pil_img.mode not in ["RGB", "RGBA"]:
                if pil_img.mode == "P":
                    if "transparency" in pil_img.info:
                        pil_img = pil_img.convert("RGBA")
                    else:
                        pil_img = pil_img.convert("RGB")
                elif pil_img.mode in ["L", "LA"]:
                    if pil_img.mode == "LA":
                        pil_img = pil_img.convert("RGBA")
                    else:
                        pil_img = pil_img.convert("RGB")
                elif pil_img.mode == "CMYK":
                    pil_img = pil_img.convert("RGB")
                else:
                    pil_img = pil_img.convert("RGB")

            if quality_factor < 1.0:
                target_width = max(int(size[0] * quality_factor), 1)
                target_height = max(int(size[1] * quality_factor), 1)
                target_size = (target_width, target_height)
            else:
                target_size = size

            try:
                pil_img.thumbnail(target_size, Image.Resampling.LANCZOS)
            except Exception:
                try:
                    pil_img.thumbnail(target_size, Image.Resampling.BICUBIC)
                except Exception:
                    pil_img.thumbnail(target_size, Image.Resampling.NEAREST)

            # Convert PIL image to QPixmap
            try:
                if pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")
                width, height = pil_img.size
                img_data = pil_img.tobytes("raw", "RGB")
                bytes_per_line = width * 3
                qt_img = QImage(
                    img_data, width, height, bytes_per_line, QImage.Format.Format_RGB888
                )
                if qt_img.isNull():
                    return None
                pixmap = QPixmap.fromImage(qt_img)
                if pixmap.isNull():
                    return None
                return pixmap
            except Exception as e:
                self.logger.error(f"Qt conversion error for {image_path}: {e}")
                return None

        except Exception as e:
            self.logger.error(f"General error in QtPilGenerator for {image_path}: {e}")
            return None
        finally:
            if pil_img:
                pil_img.close()
