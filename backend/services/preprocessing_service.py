import cv2
import numpy as np
from PIL import Image
from backend.utils.logger import logger

class ImagePreprocessingService:
    """OpenCV & NumPy image preprocessing pipeline for scanned government documents."""

    @staticmethod
    def remove_shadows(gray_img: np.ndarray) -> np.ndarray:
        """Removes uneven shadows and scanner lighting artifacts."""
        try:
            dilated = cv2.dilate(gray_img, np.ones((7, 7), np.uint8))
            bg_img = cv2.medianBlur(dilated, 21)
            diff_img = 255 - cv2.absdiff(gray_img, bg_img)
            norm_img = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
            return norm_img
        except Exception:
            return gray_img

    @staticmethod
    def remove_borders(gray_img: np.ndarray) -> np.ndarray:
        """Strips dark scanner borders and margin artifacts around page edges."""
        try:
            h, w = gray_img.shape[:2]
            margin_h, margin_w = int(h * 0.02), int(w * 0.02)
            mask = np.ones((h, w), dtype=np.uint8) * 255
            mask[:margin_h, :] = 0
            mask[-margin_h:, :] = 0
            mask[:, :margin_w] = 0
            mask[:, -margin_w:] = 0
            result = gray_img.copy()
            result[mask == 0] = 255
            return result
        except Exception:
            return gray_img

    @staticmethod
    def preprocess_image(cv_img: np.ndarray) -> np.ndarray:
        """Run full preprocessing pipeline: Grayscale -> Remove Shadows -> Denoise -> CLAHE -> Deskew -> Border Clean."""
        try:
            # 1. Convert to grayscale if color
            if len(cv_img.shape) == 3:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_img.copy()

            # 2. Shadow & Lighting Normalization
            shadow_free = ImagePreprocessingService.remove_shadows(gray)

            # 3. Denoise
            denoised = cv2.fastNlMeansDenoising(shadow_free, h=10, templateWindowSize=7, searchWindowSize=21)

            # 4. Contrast Enhancement (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)

            # 5. Border Cleaning
            border_cleaned = ImagePreprocessingService.remove_borders(enhanced)

            # 6. Sharpening
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
            sharpened = cv2.filter2D(border_cleaned, -1, kernel)

            # 7. Deskewing
            deskewed = ImagePreprocessingService.deskew(sharpened)

            return deskewed
        except Exception as e:
            logger.warning(f"Preprocessing encountered an issue, returning original image: {e}")
            return cv_img

    @staticmethod
    def deskew(gray_img: np.ndarray) -> np.ndarray:
        """Calculate skew angle using text contour bounding boxes and Hough lines."""
        try:
            # Binarize for contour detection
            _, thresh = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Find non-zero points
            coords = np.column_stack(np.where(thresh > 0))
            if len(coords) < 100:
                return gray_img

            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            # Ignore tiny angles < 0.5 deg or extreme angles > 45 deg
            if abs(angle) < 0.5 or abs(angle) > 45:
                return gray_img

            (h, w) = gray_img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(gray_img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            return rotated
        except Exception:
            return gray_img

    @staticmethod
    def adaptive_threshold(gray_img: np.ndarray) -> np.ndarray:
        """Applies adaptive Gaussian thresholding for low-contrast scans."""
        try:
            return cv2.adaptiveThreshold(
                gray_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 11
            )
        except Exception:
            return gray_img

    @staticmethod
    def enhance_for_retry(cv_img: np.ndarray, pass_num: int = 1) -> np.ndarray:
        """Multi-stage enhancement pipeline specifically for retrying low-confidence OCR regions."""
        try:
            if len(cv_img.shape) == 3:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = cv_img.copy()

            if pass_num == 1:
                # Pass 1: CLAHE + Deskew + Sharpening
                clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                return ImagePreprocessingService.deskew(enhanced)
            elif pass_num == 2:
                # Pass 2: Adaptive Thresholding
                deskewed = ImagePreprocessingService.deskew(gray)
                return ImagePreprocessingService.adaptive_threshold(deskewed)
            else:
                # Pass 3: High-pass Sharpening & Denoise
                denoised = cv2.fastNlMeansDenoising(gray, h=12)
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
                return cv2.filter2D(denoised, -1, kernel)
        except Exception:
            return cv_img

    @staticmethod
    def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
        open_cv_image = np.array(pil_img.convert('RGB'))
        return cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)

    @staticmethod
    def cv2_to_pil(cv_img: np.ndarray) -> Image.Image:
        if len(cv_img.shape) == 2:
            return Image.fromarray(cv_img)
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)
