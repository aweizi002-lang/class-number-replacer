"""
班号批量替换工具 v11 - 稳定覆盖版
核心思路：用背景色覆盖 + 重新写入文字
作者：微酱
"""

import streamlit as st
import pymupdf
import zipfile
import io
import re
import os
from datetime import datetime

st.set_page_config(
    page_title="班号批量替换工具",
    page_icon="📝",
    layout="wide"
)

st.title("📝 班号批量替换工具 v11")
st.markdown("**精准定位，背景覆盖重写**")
st.markdown("---")

with st.expander("📖 使用说明"):
    st.markdown("""
    ### 工作原理
    1. 精确搜索PDF中所有班号位置
    2. 识别班号周围的背景色
    3. 用背景色覆盖原班号区域
    4. 在原位置写入新班号
    
    ### 注意事项
    - **必须上传字体文件**（HarmonyOS Sans SC）
    - 确保新旧班号长度相同效果最佳
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
st.markdown("### 2️⃣ 上传字体文件（必须）")

font_file = st.file_uploader(
    "上传字体文件（TTF/OTF）",
    type=["ttf", "otf"],
    help="必须上传与原PDF相同的字体文件"
)

if font_file:
    st.success(f"✅ 已上传字体：{font_file.name}")

st.markdown("---")
st.markdown("### 3️⃣ 输入班号")

col1, col2 = st.columns(2)

with col1:
    old_class_numbers = st.text_input(
        "旧班号",
        placeholder="如：B260758"
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
            st.error(f"❌ 旧班号格式错误")
        if invalid_new:
            st.error(f"❌ 新班号格式错误")
        
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
    all(validate_class_number(n) for n in new_numbers) and
    font_file is not None
)

if not font_file and uploaded_files:
    st.warning("⚠️ 请上传字体文件")


def get_background_color(page, rect, exclude_rect=None):
    """获取矩形区域的背景色"""
    # 扩大采样区域
    sample_rects = [
        pymupdf.Rect(rect.x0 - 10, rect.y0 - 10, rect.x0 - 5, rect.y0 - 5),  # 左上
        pymupdf.Rect(rect.x1 + 5, rect.y0 - 10, rect.x1 + 10, rect.y0 - 5),  # 右上
        pymupdf.Rect(rect.x0 - 10, rect.y1 + 5, rect.x0 - 5, rect.y1 + 10),  # 左下
        pymupdf.Rect(rect.x1 + 5, rect.y1 + 5, rect.x1 + 10, rect.y1 + 10),  # 右下
        pymupdf.Rect(rect.x0 - 10, rect.y0, rect.x0 - 5, rect.y1),  # 左
        pymupdf.Rect(rect.x1 + 5, rect.y0, rect.x1 + 10, rect.y1),  # 右
    ]
    
    colors = []
    for sr in sample_rects:
        # 确保在页面内
        if sr.x0 < 0 or sr.y0 < 0 or sr.x1 > page.rect.width or sr.y1 > page.rect.height:
            continue
        try:
            pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=sr)
            # 取中心点颜色
            cx, cy = pix.width // 2, pix.height // 2
            pixel = pix.pixel(cx, cy)
            if len(pixel) >= 3:
                colors.append((pixel[0]/255, pixel[1]/255, pixel[2]/255))
        except:
            continue
    
    if colors:
        # 取中位数，避免极端值
        r_sorted = sorted([c[0] for c in colors])
        g_sorted = sorted([c[1] for c in colors])
        b_sorted = sorted([c[2] for c in colors])
        mid = len(colors) // 2
        return (r_sorted[mid], g_sorted[mid], b_sorted[mid])
    
    return (0.8, 0.2, 0.2)  # 默认红色


def replace_text_overlay(doc, page, old_text, new_text, font_buffer, font_name):
    """覆盖方式替换文字"""
    replacements = 0
    
    # 搜索班号（可能带"班"字）
    # 尝试多种形式：纯班号、班号+"班"
    search_patterns = [old_text, old_text + "班"]
    all_instances = []
    
    for pattern in search_patterns:
        instances = page.search_for(pattern)
        for rect in instances:
            # 避免重复（如果搜索"B260758班"和"B260758"可能重叠）
            is_dup = False
            for existing_rect in all_instances:
                if abs(rect.x0 - existing_rect.x0) < 5 and abs(rect.y0 - existing_rect.y0) < 5:
                    is_dup = True
                    break
            if not is_dup:
                all_instances.append(rect)
    
    if not all_instances:
        return 0
    
    st.info(f"  找到 {len(all_instances)} 处班号")
    
    for i, rect in enumerate(all_instances):
        try:
            # 获取文本样式
            text_info = page.get_text("dict", clip=rect)
            
            font_size = 12
            text_color = (1, 1, 1)
            actual_text = ""
            
            for block in text_info.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            actual_text = span.get("text", "")
                            font_size = span.get("size", 12)
                            color = span.get("color", 0)
                            if isinstance(color, int):
                                r = ((color >> 16) & 0xFF) / 255.0
                                g = ((color >> 8) & 0xFF) / 255.0
                                b = (color & 0xFF) / 255.0
                                text_color = (r, g, b)
            
            # 判断是否带"班"字
            has_ban = actual_text.endswith("班")
            
            # 获取背景色
            bg_color = get_background_color(page, rect)
            
            # 如果带"班"字，覆盖范围要缩小（不覆盖"班"字）
            if has_ban and len(actual_text) > len(old_text):
                # 估算"班"字的宽度（大约等于一个字符宽度）
                char_width = (rect.x1 - rect.x0) / len(actual_text)
                cover_rect = pymupdf.Rect(
                    rect.x0 - 1,
                    rect.y0 - 1,
                    rect.x1 - char_width + 1,  # 不覆盖"班"字
                    rect.y1 + 1
                )
                new_display_text = new_text + "班"
            else:
                cover_rect = pymupdf.Rect(
                    rect.x0 - 1,
                    rect.y0 - 1,
                    rect.x1 + 1,
                    rect.y1 + 1
                )
                new_display_text = new_text
            
            # 绘制背景矩形覆盖原文字
            page.draw_rect(cover_rect, color=bg_color, fill=bg_color)
            
            # 插入新文字
            # 注册字体
            page.insert_font(fontname=font_name, fontbuffer=font_buffer)
            
            # 计算插入位置（基线位置）
            insert_x = rect.x0
            insert_y = rect.y1 - font_size * 0.2  # 基线位置
            
            page.insert_text(
                (insert_x, insert_y),
                new_display_text,
                fontname=font_name,
                fontsize=font_size,
                color=text_color
            )
            
            replacements += 1
            st.text(f"    ✓ 第{i+1}处已替换")
            
        except Exception as e:
            st.text(f"    ✗ 第{i+1}处替换失败: {str(e)}")
            continue
    
    return replacements


if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_files = []
    success_count = 0
    error_count = 0
    
    replace_map = dict(zip(old_numbers, new_numbers))
    
    # 读取字体
    font_buffer = font_file.read()
    font_name = "custom_font"
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"正在处理：{uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            total_replacements = 0
            
            for page_num, page in enumerate(doc):
                st.text(f"处理第 {page_num + 1} 页...")
                for old_num, new_num in replace_map.items():
                    reps = replace_text_overlay(doc, page, old_num, new_num, font_buffer, font_name)
                    total_replacements += reps
            
            original_name = uploaded_file.name
            new_name = original_name[:-4] + "_replaced.pdf" if original_name.endswith(".pdf") else original_name + "_replaced.pdf"
            
            output_buffer = io.BytesIO()
            doc.save(output_buffer, garbage=4, deflate=True)
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
    Made with ❤️ by 微酱 | v11.0 稳定覆盖版
</div>
""", unsafe_allow_html=True)
