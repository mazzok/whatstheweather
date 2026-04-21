import logging
from PIL import Image

logger = logging.getLogger(__name__)


def update_display(image: Image.Image) -> bool:
    """Send a Pillow image to the Waveshare 7.5" E-Ink display.
    Returns True on success, False if hardware unavailable.
    """
    try:
        from waveshare_epd import epd7in5_V2

        epd = epd7in5_V2.EPD()
        epd.init()

        # Convert grayscale image to 1-bit for standard mode
        bw_image = image.convert("1")
        epd.display(epd.getbuffer(bw_image))

        epd.sleep()
        logger.info("Display updated successfully")
        return True
    except ImportError:
        logger.warning("waveshare_epd not available — skipping display update")
        return False
    except Exception as e:
        logger.error("Display update failed: %s", e)
        return False


def update_display_4gray(image: Image.Image) -> bool:
    """Send a grayscale image using 4-gray mode for better gray rendering."""
    try:
        from waveshare_epd import epd7in5_V2

        epd = epd7in5_V2.EPD()
        epd.init_4Gray()

        # Image should be mode 'L' (grayscale)
        gray_image = image.convert("L")
        epd.display_4Gray(epd.getbuffer_4Gray(gray_image))

        epd.sleep()
        logger.info("Display updated (4-gray) successfully")
        return True
    except ImportError:
        logger.warning("waveshare_epd not available — skipping display update")
        return False
    except Exception as e:
        logger.error("Display update (4-gray) failed: %s", e)
        return False
