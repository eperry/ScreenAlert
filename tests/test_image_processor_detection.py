from PIL import Image

from screenalert_core.core.image_processor import ImageProcessor


def _solid(color, size=(64, 64)):
    return Image.new("RGB", size, color=color)


def _patterned(size=(64, 64)):
    image = Image.new("RGB", size, color=(0, 0, 0))
    for x in range(16, 48):
        for y in range(16, 48):
            image.putpixel((x, y), (255, 255, 255))
    return image


def test_ssim_and_phash_detection():
    img1 = _solid((0, 0, 0))
    img2 = _solid((255, 255, 255))
    img3 = _patterned()

    assert bool(ImageProcessor.detect_change(img1, img2, threshold=0.99, method="ssim"))
    assert bool(ImageProcessor.detect_change(img1, img3, threshold=0.99, method="phash"))


def test_phash_similarity_identical():
    img = _solid((20, 30, 40))
    score = ImageProcessor.calculate_phash_similarity(img, img.copy())
    assert score >= 0.99
