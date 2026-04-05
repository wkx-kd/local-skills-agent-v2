# ============================================================================
# Copyright (c) 2026 深维大模型（DeepDimension AI）
# All Rights Reserved. 版权所有，盗版必究。
#
# 本软件及其相关文档受版权法保护。未经深维大模型书面授权，
# 任何单位和个人不得擅自复制、修改、分发或以其他方式使用本软件
# 的全部或部分内容。违者将依法追究法律责任。
# ============================================================================
import os
import sys

from pdf2image import convert_from_path




def convert(pdf_path, output_dir, max_dim=1000):
    images = convert_from_path(pdf_path, dpi=200)

    for i, image in enumerate(images):
        width, height = image.size
        if width > max_dim or height > max_dim:
            scale_factor = min(max_dim / width, max_dim / height)
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            image = image.resize((new_width, new_height))
        
        image_path = os.path.join(output_dir, f"page_{i+1}.png")
        image.save(image_path)
        print(f"Saved page {i+1} as {image_path} (size: {image.size})")

    print(f"Converted {len(images)} pages to PNG images")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: convert_pdf_to_images.py [input pdf] [output directory]")
        sys.exit(1)
    pdf_path = sys.argv[1]
    output_directory = sys.argv[2]
    convert(pdf_path, output_directory)
