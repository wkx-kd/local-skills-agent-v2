# ============================================================================
# Copyright (c) 2026 深维大模型（DeepDimension AI）
# All Rights Reserved. 版权所有，盗版必究。
#
# 本软件及其相关文档受版权法保护。未经深维大模型书面授权，
# 任何单位和个人不得擅自复制、修改、分发或以其他方式使用本软件
# 的全部或部分内容。违者将依法追究法律责任。
# ============================================================================
import sys
from pypdf import PdfReader




reader = PdfReader(sys.argv[1])
if (reader.get_fields()):
    print("This PDF has fillable form fields")
else:
    print("This PDF does not have fillable form fields; you will need to visually determine where to enter data")
