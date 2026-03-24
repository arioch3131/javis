from typing import Optional, Tuple

from PIL import Image, ImageOps

from ai_content_classifier.services.thumbnail.generators import BaseThumbnailGenerator


class PilGenerator(BaseThumbnailGenerator):
    """Thumbnail generator for raster images using PIL/Pillow only."""

    def generate(
        self, image_path: str, size: Tuple[int, int], quality_factor: float = 1.0
    ) -> Optional[Image.Image]:
        """Generate a PIL thumbnail for the given image."""
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

            # Handle progressive JPEG conversion
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

            # Fix orientation based on EXIF data
            try:
                pil_img = ImageOps.exif_transpose(pil_img)
            except Exception as e:
                self.logger.warning(
                    f"Error correcting orientation for {image_path}: {e}"
                )

            # Calculate target size based on quality factor
            if quality_factor < 1.0:
                target_width = max(int(size[0] * quality_factor), 1)
                target_height = max(int(size[1] * quality_factor), 1)
                target_size = (target_width, target_height)
            else:
                target_size = size

            # Create thumbnail with fallback resampling methods
            try:
                pil_img.thumbnail(target_size, Image.Resampling.LANCZOS)
            except Exception:
                try:
                    pil_img.thumbnail(target_size, Image.Resampling.BICUBIC)
                except Exception:
                    pil_img.thumbnail(target_size, Image.Resampling.NEAREST)

            # Return a copy to avoid issues with the original image being closed
            return pil_img.copy()

        except Exception as e:
            self.logger.error(f"General error in PilGenerator for {image_path}: {e}")
            return None
        finally:
            if pil_img:
                pil_img.close()
