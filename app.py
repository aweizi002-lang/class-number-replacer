"""
班号批量替换工具 v7.1 - 智能纹理填充（避免覆盖其他文字）
功能：智能检测背景纹理，完美融入原设计，保护周围文字
作者：微酱
"""

import streamlit as st
import pymupdf
import zipfile
import io
import re
import os
from datetime import datetime
from collections import Counter

st.set_page_config(
    page_title="班号批量替换工具",
    page_icon="📝",
    layout="wide"
)

st.title("📝 班号批量替换工具")
st.markdown("---")

with st.expander("📖 使用说明"):
    st.markdown("""
    ### 功能说明
    智能替换PDF中的班号文本，自动处理背景纹理
    
    ### 核心优化
    - ✅ 自动检测背景纹理，智能填充
    - ✅ 支持渐变、纹理等复杂背景
    - ✅ 替换效果更自然，无生硬色块
    
    ### 推荐上传字体
    上传 HarmonyOS Sans SC 可确保任意字符正常显示
    """)

st.markdown("### 1️⃣ 上传PDF文件")

uploaded_files = st.file_uploader(
    "选择PDF文件（可多选）",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    st.success(f"已上传 {len(uploaded_files)} 个文件")

st.markdown("---")
st.markdown("### 2️⃣ 上传字体文件（可选但推荐）")

font_file = st.file_uploader(
    "上传字体文件（TTF/OTF）",
    type=["ttf", "otf"],
    help="推荐上传 HarmonyOS Sans SC"
)

if font_file:
    st.success(f"✅ 已上传字体：{font_file.name}")

st.markdown("---")
st.markdown("### 3️⃣ 输入班号")

col1, col2 = st.columns(2)

with col1:
    old_class_numbers = st.text_input(
        "旧班号（要被替换的）",
        placeholder="如：B250675"
    )

with col2:
    new_class_numbers = st.text_input(
        "新班号",
        placeholder="如：B260830"
    )

def parse_class_numbers(text):
    if not text:
        return []
    numbers = [n.strip().upper() for n in text.split(",")]
    return [n for n in numbers if n]

def validate_class_number(number):
    if not number:
        return False
    pattern = r"^[A-Z0-9]{3,10}$"
    return bool(re.match(pattern, number))

old_numbers = parse_class_numbers(old_class_numbers)
new_numbers = parse_class_numbers(new_class_numbers)

if old_numbers and new_numbers:
    if len(old_numbers) != len(new_numbers):
        st.warning(f"⚠️ 班号数量不匹配")
    else:
        invalid_old = [n for n in old_numbers if not validate_class_number(n)]
        invalid_new = [n for n in new_numbers if not validate_class_number(n)]
        
        if invalid_old:
            st.error(f"❌ 旧班号格式错误：{', '.join(invalid_old)}")
        if invalid_new:
            st.error(f"❌ 新班号格式错误：{', '.join(invalid_new)}")
        
        if not invalid_old and not invalid_new:
            st.success("✅ 班号格式正确")

st.markdown("---")
st.markdown("### 4️⃣ 开始替换")

can_process = (
    uploaded_files and 
    old_numbers and 
    new_numbers and 
    len(old_numbers) == len(new_numbers) and
    all(validate_class_number(n) for n in old_numbers) and
    all(validate_class_number(n) for n in new_numbers)
)

def fill_with_texture(page, rect, all_text_rects):
    """用周围纹理智能填充区域，避免覆盖其他文字"""
    try:
        # 检查周围区域是否有其他文字
        margin = 5  # 扩大一点范围
        
        # 扩大rect用于采样
        expanded_rect = pymupdf.Rect(
            rect.x0 - margin,
            rect.y0 - margin,
            rect.x1 + margin,
            rect.y1 + margin
        )
        
        # 找一个没有文字的纯净区域来采样
        def find_clean_area(base_rect, direction, width):
            """在指定方向找一个没有文字的区域"""
            if direction == "left":
                sample_rect = pymupdf.Rect(
                    base_rect.x0 - width,
                    base_rect.y0,
                    base_rect.x0,
                    base_rect.y1
                )
            elif direction == "right":
                sample_rect = pymupdf.Rect(
                    base_rect.x1,
                    base_rect.y0,
                    base_rect.x1 + width,
                    base_rect.y1
                )
            elif direction == "top":
                sample_rect = pymupdf.Rect(
                    base_rect.x0,
                    base_rect.y0 - width,
                    base_rect.x1,
                    base_rect.y0
                )
            else:  # bottom
                sample_rect = pymupdf.Rect(
                    base_rect.x0,
                    base_rect.y1,
                    base_rect.x1,
                    base_rect.y1 + width
                )
            
            # 检查这个区域是否与其他文字重叠
            for text_rect in all_text_rects:
                if sample_rect.intersects(text_rect):
                    return None  # 有重叠，不能用
            
            return sample_rect
        
        # 尝试从各个方向找纯净区域
        sample_width = max(20, int((rect.x1 - rect.x0) * 0.3))
        
        for direction in ["left", "right", "top", "bottom"]:
            sample_rect = find_clean_area(rect, direction, sample_width)
            if sample_rect:
                try:
                    pix = page.get_pixmap(clip=sample_rect)
                    if pix.width > 0 and pix.height > 0:
                        # 将纹理粘贴到目标区域
                        img = pix.tobytes("png")
                        page.insert_image(rect, stream=img, keep_proportion=False)
                        return True
                except:
                    continue
        
    except Exception as e:
        pass
    
    return False

def get_avg_background_color(page, rect):
    """获取背景平均颜色（作为备选）"""
    try:
        margin = 5
        sample_rect = pymupdf.Rect(
            rect.x0 - margin,
            rect.y0 - margin,
            rect.x1 + margin,
            rect.y1 + margin
        )
        
        pix = page.get_pixmap(clip=sample_rect)
        w, h = pix.width, pix.height
        
        if w == 0 or h == 0:
            return (1, 1, 1)
        
        # 取边缘像素的平均值
        samples = []
        for x in range(0, w, max(1, w//10)):
            for y in [0, h-1]:
                pixel = pix.pixel(x, y)
                if isinstance(pixel, (list, tuple)) and len(pixel) >= 3:
                    samples.append(pixel[:3])
        
        for y in range(0, h, max(1, h//10)):
            for x in [0, w-1]:
                pixel = pix.pixel(x, y)
                if isinstance(pixel, (list, tuple)) and len(pixel) >= 3:
                    samples.append(pixel[:3])
        
        if not samples:
            return (1, 1, 1)
        
        # 计算平均值
        avg_r = sum(s[0] for s in samples) / len(samples)
        avg_g = sum(s[1] for s in samples) / len(samples)
        avg_b = sum(s[2] for s in samples) / len(samples)
        
        return (avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
        
    except:
        return (1, 1, 1)

def replace_text_smart(page, old_text, new_text):
    """直接修改内容流（最无痕）"""
    replacements = 0
    try:
        for xref in page.get_contents():
            content = page.parent.xref_stream(xref)
            if isinstance(content, bytes):
                try:
                    content_str = content.decode('latin-1')
                    if old_text in content_str:
                        new_content = content_str.replace(old_text, new_text)
                        page.parent.update_stream(xref, new_content.encode('latin-1'))
                        replacements += content_str.count(old_text)
                except:
                    pass
    except:
        pass
    return replacements

def get_all_text_rects(page):
    """获取页面上所有文本的位置"""
    rects = []
    text_dict = page.get_text("dict")
    for block in text_dict.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                bbox = span.get("bbox")
                if bbox:
                    rects.append(pymupdf.Rect(bbox))
    return rects

def replace_text_with_font(page, old_text, new_text, font_buffer=None, font_name=None, all_text_rects=None):
    """使用指定字体替换文本，智能处理背景"""
    replacements = 0
    
    text_dict = page.get_text("dict")
    
    for block in text_dict.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if old_text in text:
                    bbox = span.get("bbox")
                    if not bbox:
                        continue
                    
                    rect = pymupdf.Rect(bbox)
                    size = span.get("size", 11)
                    origin = span.get("origin", (bbox[0], bbox[1]))
                    
                    # 获取文本颜色
                    color = span.get("color", 0)
                    if isinstance(color, int):
                        r = ((color >> 16) & 0xFF) / 255.0
                        g = ((color >> 8) & 0xFF) / 255.0
                        b = (color & 0xFF) / 255.0
                        text_color = (r, g, b)
                    else:
                        text_color = (1, 1, 1)
                    
                    # 🔥 核心：智能填充背景（避免覆盖其他文字）
                    texture_filled = False
                    if all_text_rects:
                        texture_filled = fill_with_texture(page, rect, all_text_rects)
                    
                    if not texture_filled:
                        # 纹理填充失败，使用平均背景色
                        bg_color = get_avg_background_color(page, rect)
                        shape = page.new_shape()
                        shape.draw_rect(rect)
                        shape.finish(fill=bg_color, color=bg_color)
                        shape.commit()
                    
                    new_full_text = text.replace(old_text, new_text)
                    
                    # 使用上传的字体
                    if font_buffer and font_name:
                        try:
                            page.insert_font(fontname=font_name, fontbuffer=font_buffer)
                            page.insert_text(
                                (bbox[0], origin[1]),
                                new_full_text,
                                fontname=font_name,
                                fontsize=size,
                                color=text_color
                            )
                            replacements += 1
                            continue
                        except:
                            pass
                    
                    # 备选：使用原字体
                    font = span.get("font", "helv")
                    try:
                        page.insert_text(
                            (bbox[0], origin[1]),
                            new_full_text,
                            fontname=font,
                            fontsize=size,
                            color=text_color
                        )
                        replacements += 1
                    except:
                        for fallback_font in ["helv", "arial", "times-roman"]:
                            try:
                                page.insert_text(
                                    (bbox[0], origin[1]),
                                    new_full_text,
                                    fontname=fallback_font,
                                    fontsize=size,
                                    color=text_color
                                )
                                replacements += 1
                                break
                            except:
                                continue
    
    return replacements

if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_files = []
    success_count = 0
    error_count = 0
    
    replace_map = dict(zip(old_numbers, new_numbers))
    
    font_buffer = None
    font_name = None
    if font_file:
        font_buffer = font_file.read()
        font_name = os.path.splitext(font_file.name)[0]
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"正在处理：{uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            total_replacements = 0
            
            for page in doc:
                # 先获取页面上所有文本的位置，避免纹理填充时覆盖其他文字
                all_text_rects = get_all_text_rects(page)
                
                for old_num, new_num in replace_map.items():
                    # 优先直接修改内容流
                    if not font_file:
                        reps = replace_text_smart(page, old_num, new_num)
                        if reps > 0:
                            total_replacements += reps
                            continue
                    
                    # 智能纹理填充替换
                    reps = replace_text_with_font(page, old_num, new_num, font_buffer, font_name, all_text_rects)
                    total_replacements += reps
            
            original_name = uploaded_file.name
            new_name = original_name[:-4] + "_replaced.pdf" if original_name.endswith(".pdf") else original_name + "_replaced.pdf"
            
            output_buffer = io.BytesIO()
            doc.save(output_buffer, garbage=4, deflate=True, clean=True)
            doc.close()
            
            output_buffer.seek(0)
            processed_files.append({
                "name": new_name,
                "data": output_buffer,
                "replacements": total_replacements
            })
            
            success_count += 1
            
        except Exception as e:
            st.error(f"❌ 处理失败：{uploaded_file.name} - {str(e)}")
            error_count += 1
        
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    status_text.text("处理完成！")
    
    st.markdown("---")
    st.markdown("### 5️⃣ 处理结果")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("成功处理", success_count)
    with col2:
        st.metric("处理失败", error_count)
    with col3:
        total_reps = sum(f["replacements"] for f in processed_files)
        st.metric("总替换次数", total_reps)
    
    if processed_files:
        with st.expander("📋 查看处理详情"):
            for f in processed_files:
                st.text(f"✅ {f['name']} - 替换了 {f['replacements']} 处")
    
    if len(processed_files) == 1:
        st.download_button(
            label="📥 下载处理后的文件",
            data=processed_files[0]["data"],
            file_name=processed_files[0]["name"],
            mime="application/pdf"
        )
    elif len(processed_files) > 1:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for f in processed_files:
                zip_file.writestr(f["name"], f["data"].getvalue())
        
        zip_buffer.seek(0)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"班号替换结果_{timestamp}.zip"
        
        st.download_button(
            label="📥 下载所有文件（ZIP压缩包）",
            data=zip_buffer,
            file_name=zip_name,
            mime="application/zip"
        )

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 12px;">
    Made with ❤️ by 微酱 | v7.1 智能纹理填充版
</div>
""", unsafe_allow_html=True)
