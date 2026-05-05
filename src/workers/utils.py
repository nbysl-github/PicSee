from PIL import Image

def process_enhanced_image(pil_image, target_w, target_h):
    """
    仅执行缩放，不进行图像增强（锐化、对比度等）
    """
    try:
        # 使用 Lanczos (兰索斯) 算法进行高质量缩放
        resample_method = getattr(Image.Resampling, "LANCZOS", Image.LANCZOS)
        hq_img = pil_image.resize((target_w, target_h), resample_method)
        return hq_img
    except Exception as e:
        return pil_image.resize((target_w, target_h))
