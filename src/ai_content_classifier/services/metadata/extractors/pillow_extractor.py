"""
Pillow-based image metadata extractor module.

This module provides metadata extraction for image files using the Pillow library.
"""

import importlib
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict

from ai_content_classifier.services.metadata.extractors.base_extractor import (
    BaseMetadataExtractor,
)
from ai_content_classifier.services.file.file_type_service import FileTypeService


class PillowImageExtractor(BaseMetadataExtractor):
    """Metadata extractor for images using Pillow."""

    # Map of EXIF date tags to look for
    EXIF_DATE_TAGS = ["DateTimeOriginal", "DateTimeDigitized", "DateTime"]

    # Map of important EXIF tags to extract and their human-readable names
    IMPORTANT_EXIF_TAGS = {
        "Make": "camera_make",
        "Model": "camera_model",
        "Software": "software",
        "Artist": "artist",
        "Copyright": "copyright",
        "ExposureTime": "exposure_time",
        "FNumber": "f_number",
        "ISOSpeedRatings": "iso",
        "FocalLength": "focal_length",
        "Flash": "flash_used",
        "Orientation": "orientation",
        "XResolution": "x_resolution",
        "YResolution": "y_resolution",
    }

    # GPS tag mapping for more user-friendly keys
    GPS_TAG_MAPPING = {
        "GPSLatitude": "latitude",
        "GPSLongitude": "longitude",
        "GPSAltitude": "altitude",
        "GPSDateStamp": "date",
        "GPSTimeStamp": "time",
        "GPSProcessingMethod": "processing_method",
    }

    def __init__(self):
        """Initialize the image extractor."""
        super().__init__()

        # Standard image formats supported by Pillow
        self.supported_extensions = set(FileTypeService.IMAGE_EXTENSIONS)

        # Check if Pillow is available
        self.pillow_available = self._check_dependency("PIL")

        if not self.pillow_available:
            self.logger.warning(
                "Pillow library not available. Image metadata extraction will not work."
            )

    def _check_dependency(self, module_name: str) -> bool:
        """
        Check if a Python module is available.

        Args:
            module_name: Name of the module to check

        Returns:
            True if the module is available, False otherwise
        """
        try:
            importlib.import_module(module_name)
            return True
        except ImportError:
            return False

    def can_handle(self, file_path: str) -> bool:
        """
        Check if the file is an image supported by Pillow.

        Args:
            file_path: Path to the file

        Returns:
            True if it's a supported image, False otherwise
        """
        if not self.pillow_available:
            return False

        ext = Path(file_path).suffix.lower()
        return ext in self.supported_extensions

    def get_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from an image.

        Args:
            file_path: Path to the image

        Returns:
            Dictionary of metadata
        """
        # Get basic metadata
        metadata = self.get_basic_metadata(file_path)

        if not self.pillow_available:
            metadata["error"] = "Pillow library is not installed"
            return metadata

        try:
            from PIL import Image

            # Import TAGS and GPSTAGS only if available (they might not be in all Pillow versions)
            try:
                from PIL.ExifTags import GPSTAGS, TAGS
            except ImportError:
                TAGS = None
                GPSTAGS = None
                self.logger.warning(
                    "ExifTags.TAGS and GPSTAGS not available in this Pillow version"
                )

            with Image.open(file_path) as img:
                # Add basic image information
                metadata["dimensions"] = img.size
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["format"] = img.format
                metadata["mode"] = img.mode
                metadata["aspect_ratio"] = (
                    round(img.width / img.height, 2) if img.height != 0 else 0
                )

                # Initialize containers for different metadata types
                metadata["exif"] = {}
                metadata["gps"] = {}
                metadata["icc_profile"] = {}

                # Process format-specific metadata
                format_handler = self._get_format_handler(img.format)
                if format_handler:
                    format_metadata = format_handler(img, file_path)
                    if format_metadata:
                        metadata.update(format_metadata)

                # Extract EXIF data
                self._extract_exif_data(img, metadata, TAGS, GPSTAGS)

                # Extract ICC profile information
                self._extract_icc_profile(img, metadata)

                # Add a caption/alt text suggestion based on the extracted metadata
                metadata["suggested_caption"] = self._generate_caption(metadata)

        except Exception as e:
            self.logger.error(f"Error extracting image metadata: {str(e)}")
            metadata["error"] = str(e)

        return metadata

    def _get_format_handler(self, format_name: str):
        """
        Get the appropriate format-specific handler function.

        Args:
            format_name: Image format name (e.g., 'JPEG', 'PNG')

        Returns:
            Handler function or None if no specific handler exists
        """
        format_handlers = {
            "JPEG": self._process_jpeg_specific,
            "PNG": self._process_png_specific,
            "GIF": self._process_gif_specific,
            "TIFF": self._process_tiff_specific,
            "WEBP": self._process_webp_specific,
        }

        return format_handlers.get(format_name)

    def _extract_exif_data(self, img, metadata, TAGS, GPSTAGS):
        """
        Extract and process EXIF data from the image.

        Args:
            img: PIL Image object
            metadata: Metadata dictionary to update
            TAGS: PIL ExifTags.TAGS mapping
            GPSTAGS: PIL ExifTags.GPSTAGS mapping
        """
        exif_data = None

        # Try different methods to get EXIF data
        if hasattr(img, "_getexif") and callable(img._getexif):
            exif_data = img._getexif()
        elif hasattr(img, "getexif") and callable(img.getexif):
            exif_data = img.getexif()

        if not exif_data:
            return

        # Process EXIF data
        for tag_id, value in exif_data.items():
            # Convert tag ID to name if TAGS is available
            tag = TAGS.get(tag_id, str(tag_id)) if TAGS else str(tag_id)

            # Special handling for GPS data
            if tag == "GPSInfo" and GPSTAGS:
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, str(gps_tag_id))

                    # Use friendly names for GPS tags
                    friendly_name = self.GPS_TAG_MAPPING.get(gps_tag, gps_tag)
                    metadata["gps"][friendly_name] = gps_value

                # Process GPS coordinates if available
                self._process_gps_coordinates(metadata)
            else:
                # Use meaningful names for important EXIF tags
                if tag in self.IMPORTANT_EXIF_TAGS:
                    friendly_name = self.IMPORTANT_EXIF_TAGS[tag]
                    metadata[friendly_name] = value

                # Store all EXIF data
                metadata["exif"][tag] = self._sanitize_exif_value(value)

        # Extract date from EXIF if available
        self._extract_date_from_exif(metadata)

    def _sanitize_exif_value(self, value):
        """
        Sanitize EXIF value for serialization.

        Args:
            value: EXIF value to sanitize

        Returns:
            Sanitized value
        """
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        elif isinstance(value, bytes):
            return "binary_data"
        elif isinstance(value, tuple) and all(isinstance(x, int) for x in value):
            return value
        elif hasattr(value, "__iter__"):
            try:
                return list(value)
            except Exception:
                return self._get_stable_object_fallback(value)
        else:
            return self._get_stable_object_fallback(value)

    @staticmethod
    def _get_stable_object_fallback(value: Any) -> str:
        """Return a deterministic fallback string for non-serializable EXIF values."""
        return f"<{value.__class__.__module__}.{value.__class__.__qualname__}>"

    def _extract_date_from_exif(self, metadata):
        """
        Extract creation date from EXIF data.

        Args:
            metadata: Metadata dictionary containing EXIF data
        """
        for date_tag in self.EXIF_DATE_TAGS:
            if date_tag in metadata["exif"]:
                date_str = metadata["exif"][date_tag]
                if isinstance(date_str, str):
                    parsed = False
                    for fmt in ["%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            metadata["creation_date"] = datetime.strptime(date_str, fmt)
                            parsed = True
                            break
                        except ValueError:
                            continue
                    if not parsed:
                        self.logger.debug(
                            f"Could not parse date '{date_str}' with known formats."
                        )
                else:
                    self.logger.debug(f"Date value '{date_str}' is not a string.")
                break

    def _process_gps_coordinates(self, metadata):
        """
        Process GPS coordinates into a more usable format.

        Args:
            metadata: Metadata dictionary containing GPS data
        """
        if "latitude" in metadata["gps"] and "longitude" in metadata["gps"]:
            try:
                lat = metadata["gps"]["latitude"]
                lon = metadata["gps"]["longitude"]
                lat_ref = metadata["gps"].get("GPSLatitudeRef", "N")
                lon_ref = metadata["gps"].get("GPSLongitudeRef", "E")

                # Convert coordinates to decimal degrees
                lat_value = self._convert_to_decimal_degrees(lat)
                lon_value = self._convert_to_decimal_degrees(lon)

                # Apply reference direction
                if lat_ref == "S":
                    lat_value = -lat_value
                if lon_ref == "W":
                    lon_value = -lon_value

                # Store decimal coordinates
                metadata["gps"]["decimal_latitude"] = lat_value
                metadata["gps"]["decimal_longitude"] = lon_value

                # Generate Google Maps URL
                metadata["gps"]["maps_url"] = (
                    f"https://maps.google.com/maps?q={lat_value},{lon_value}"
                )

            except Exception as e:
                self.logger.debug(f"Could not process GPS coordinates: {str(e)}")

    def _convert_to_decimal_degrees(self, dms_coords):
        """
        Convert GPS coordinates from DMS (degrees, minutes, seconds) to decimal degrees.

        Args:
            dms_coords: DMS coordinates tuple (degrees, minutes, seconds)

        Returns:
            Decimal degrees
        """
        # Handle different coordinate formats
        if len(dms_coords) == 3:
            degrees, minutes, seconds = dms_coords

            # Convert to float if necessary
            if isinstance(degrees, tuple) and len(degrees) == 2:
                degrees = degrees[0] / degrees[1]
            if isinstance(minutes, tuple) and len(minutes) == 2:
                minutes = minutes[0] / minutes[1]
            if isinstance(seconds, tuple) and len(seconds) == 2:
                seconds = seconds[0] / seconds[1]

            return degrees + (minutes / 60.0) + (seconds / 3600.0)
        else:
            # If not in expected format, return as is
            return dms_coords

    def _extract_icc_profile(self, img, metadata):
        """
        Extract ICC profile information if available.

        Args:
            img: PIL Image object
            metadata: Metadata dictionary to update
        """
        if "icc_profile" in img.info:
            metadata["has_icc_profile"] = True

            metadata["icc_profile"] = {}
            # Try to get color space information
            try:
                icc_profile = img.info["icc_profile"]
                if icc_profile:
                    # We can only store basic info since the full profile is binary data
                    metadata["icc_profile"]["size"] = len(icc_profile)

                    # Try to get color profile name if PIL has the necessary module
                    try:
                        from PIL import ImageCms

                        profile = ImageCms.getOpenProfile(BytesIO(icc_profile))
                        metadata["icc_profile"]["description"] = (
                            ImageCms.getProfileDescription(profile)
                        )
                    except (ImportError, Exception) as e:
                        self.logger.debug(
                            f"Could not get ICC profile description: {str(e)}"
                        )
            except Exception as e:
                self.logger.debug(f"Could not process ICC profile: {str(e)}")

    def _process_jpeg_specific(self, img, file_path):
        """
        Process JPEG-specific metadata.

        Args:
            img: PIL Image object
            file_path: Path to the image file

        Returns:
            Dictionary of JPEG-specific metadata
        """
        jpeg_info = {}

        # Check for JPEG markers and compression info
        if hasattr(img, "applist"):
            markers = [marker[0] for marker in img.applist]
            jpeg_info["markers"] = markers

        # Get subsampling info if available
        if "progression" in img.info:
            jpeg_info["progressive"] = img.info["progression"]

        # Get quality estimate
        try:
            quality = self._estimate_jpeg_quality(img)
            if quality:
                jpeg_info["estimated_quality"] = quality
        except Exception:
            pass

        return {"jpeg_info": jpeg_info} if jpeg_info else {}

    def _process_png_specific(self, img, file_path):
        """
        Process PNG-specific metadata.

        Args:
            img: PIL Image object
            file_path: Path to the image file

        Returns:
            Dictionary of PNG-specific metadata
        """
        png_info = {}

        # Extract PNG chunks
        chunks = []
        if hasattr(img, "png") and hasattr(img.png, "chunks"):
            for chunk_type, chunk_data in img.png.chunks:
                chunks.append(
                    chunk_type.decode("ascii")
                    if isinstance(chunk_type, bytes)
                    else chunk_type
                )

            png_info["chunks"] = chunks

        # Check for transparency
        if "transparency" in img.info:
            png_info["has_transparency"] = True

        # Check for animation
        if "loop" in img.info or "duration" in img.info:
            png_info["is_animated"] = True
            if "duration" in img.info:
                png_info["frame_duration"] = img.info["duration"]
            if "loop" in img.info:
                png_info["loop_count"] = img.info["loop"]

        return {"png_info": png_info} if png_info else {}

    def _process_gif_specific(self, img, file_path):
        """
        Process GIF-specific metadata.

        Args:
            img: PIL Image object
            file_path: Path to the image file

        Returns:
            Dictionary of GIF-specific metadata
        """
        gif_info = {}

        # Check for animation info
        if "duration" in img.info:
            gif_info["is_animated"] = True
            gif_info["frame_duration"] = img.info["duration"]

        if "loop" in img.info:
            gif_info["loop_count"] = img.info["loop"]

        # Get frame count
        try:
            frames = 0
            try:
                while True:
                    img.seek(frames)
                    frames += 1
            except EOFError:
                pass
            gif_info["frame_count"] = frames
            img.seek(0)  # Reset frame position
        except Exception:
            pass

        # Check for transparency
        if "transparency" in img.info:
            gif_info["has_transparency"] = True

        return {"gif_info": gif_info} if gif_info else {}

    def _process_tiff_specific(self, img, file_path):
        """
        Process TIFF-specific metadata.

        Args:
            img: PIL Image object
            file_path: Path to the image file

        Returns:
            Dictionary of TIFF-specific metadata
        """
        tiff_info = {}

        # Check for multi-page TIFF
        try:
            from PIL import TiffImagePlugin  # noqa: F401

            if hasattr(img, "n_frames") and img.n_frames > 1:
                tiff_info["page_count"] = img.n_frames
        except (ImportError, AttributeError):
            pass

        return {"tiff_info": tiff_info} if tiff_info else {}

    def _process_webp_specific(self, img, file_path):
        """
        Process WebP-specific metadata.

        Args:
            img: PIL Image object
            file_path: Path to the image file

        Returns:
            Dictionary of WebP-specific metadata
        """
        webp_info = {}

        # Check for animation
        if hasattr(img, "is_animated") and img.is_animated:
            webp_info["is_animated"] = True
            if hasattr(img, "n_frames"):
                webp_info["frame_count"] = img.n_frames

        # Check WebP features
        if "lossless" in img.info:
            webp_info["lossless"] = img.info["lossless"]

        return {"webp_info": webp_info} if webp_info else {}

    def _estimate_jpeg_quality(self, img):
        """
        Estimate JPEG quality based on quantization tables.
        This is a rough estimate.

        Args:
            img: PIL Image object

        Returns:
            Estimated quality (0-100) or None if not possible
        """
        if not hasattr(img, "quantization"):
            return None

        quantization = img.quantization
        if not quantization:
            return None

        # Convert quantization tables to average values
        qtables_avg = []
        for table in quantization.values():
            if len(table) > 0:
                qtables_avg.append(sum(table) / len(table))

        # Estimate quality based on average quantization value
        # This is a rough approximation
        if not qtables_avg:
            return None

        avg_value = sum(qtables_avg) / len(qtables_avg)

        # Convert average quantization to quality
        # Lower quantization = higher quality
        if avg_value <= 1:
            return 100
        if avg_value >= 100:
            return 1

        # Rough formula, can be improved
        return max(1, min(100, int(100 - (avg_value * 0.9))))

    def _generate_caption(self, metadata):
        """
        Generate a descriptive caption based on extracted metadata.

        Args:
            metadata: Image metadata dictionary

        Returns:
            Generated caption string
        """
        caption_parts = []

        # Add basic image info
        if "width" in metadata and "height" in metadata:
            caption_parts.append(
                f"{metadata['width']}x{metadata['height']} {metadata.get('format', 'image')}"
            )

        # Add camera info if available
        camera_info = []
        if "camera_make" in metadata:
            camera_info.append(metadata["camera_make"])
        if "camera_model" in metadata:
            camera_info.append(metadata["camera_model"])

        if camera_info:
            caption_parts.append("taken with " + " ".join(camera_info))

        # Add date if available
        if "creation_date" in metadata:
            caption_parts.append(
                f"on {metadata['creation_date'].strftime('%B %d, %Y')}"
            )

        # Join all parts
        if caption_parts:
            return " ".join(caption_parts)
        else:
            return f"Image file: {metadata.get('filename', 'unknown')}"
