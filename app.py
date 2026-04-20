"""
班号批量替换工具 v2
功能：批量替换PDF文件中的班号文本，保持原样式
作者：微酱
"""

import streamlit as st
import pymupdf
import zipfile
import io
import re
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="班号批量替换工具",
    page_icon="📝",
    layout="wide"
)

# 标题
st.title("📝 班号批量替换工具")
st.markdown("---")

# 使用说明
with st.expander("📖 使用说明"):
    st.markdown("""
    ### 如何使用
    1. **上传PDF文件**：支持批量上传，最多20个文件
    2. **输入班号**：
       - 填写要替换的旧班号（如 `B250675`）
       - 填写新的班号
    3. **点击替换**：系统会自动处理所有文件
    4. **下载结果**：处理完成后可下载所有文件
    
    ### 班号格式
    - 格式：字母 + 6位数字，如 `B250675`、`A123456`
    
    ### 注意事项
    - 替换后的文件会自动添加 `_replaced` 后缀
    - 新班号长度需与旧班号一致（7位），以保持排版
    """)

st.markdown("### 1️⃣ 上传PDF文件")

uploaded_files = st.file_uploader(
    "选择PDF文件（可多选）",
    type=["pdf"],
    accept_multiple_files=True,
    help="支持批量上传，建议每次不超过20个文件"
)

if uploaded_files:
    st.success(f"已上传 {len(uploaded_files)} 个文件")
    with st.expander("📄 查看上传的文件"):
        for i, file in enumerate(uploaded_files, 1):
            st.text(f"{i}. {file.name}")

st.markdown("---")
st.markdown("### 2️⃣ 输入班号")

col1, col2 = st.columns(2)

with col1:
    old_class_numbers = st.text_input(
        "旧班号（要被替换的）",
        placeholder="如：B250675",
        help="输入要替换的班号"
    )

with col2:
    new_class_numbers = st.text_input(
        "新班号",
        placeholder="如：B250676",
        help="输入新的班号"
    )

def parse_class_numbers(text):
    if not text:
        return []
    numbers = [n.strip().upper() for n in text.split(",")]
    return [n for n in numbers if n]

def validate_class_number(number):
    pattern = r"^[A-Z][0-9]{6}$"
    return bool(re.match(pattern, number))

old_numbers = parse_class_numbers(old_class_numbers)
new_numbers = parse_class_numbers(new_class_numbers)

if old_numbers and new_numbers:
    if len(old_numbers) != len(new_numbers):
        st.warning(f"⚠️ 班号数量不匹配：旧班号 {len(old_numbers)} 个，新班号 {len(new_numbers)} 个")
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
st.markdown("### 3️⃣ 开始替换")

can_process = (
    uploaded_files and 
    old_numbers and 
    new_numbers and 
    len(old_numbers) == len(new_numbers) and
    all(validate_class_number(n) for n in old_numbers) and
    all(validate_class_number(n) for n in new_numbers)
)

if st.button("🚀 开始替换", disabled=not can_process, type="primary"):
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    processed_files = []
    success_count = 0
    error_count = 0
    
    replace_map = dict(zip(old_numbers, new_numbers))
    
    for i, uploaded_file in enumerate(uploaded_files):
        try:
            status_text.text(f"正在处理：{uploaded_file.name} ({i+1}/{len(uploaded_files)})")
            
            pdf_bytes = uploaded_file.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            
            total_replacements = 0
            
            for page in doc:
                for old_num, new_num in replace_map.items():
                    # 先提取文本块，获取样式信息
                    text_dict = page.get_text("dict")
                    replacements_info = []
                    
                    for block in text_dict.get("blocks", []):
                        if "lines" not in block:
                            continue
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "")
                                if old_num in text:
                                    # 提取原样式
                                    font = span.get("font", "helv")
                                    size = span.get("size", 11)
                                    color = span.get("color", 0)
                                    origin = span.get("origin", (0, 0))
                                    bbox = span.get("bbox")
                                    
                                    # 处理颜色（可能是整数或元组）
                                    if isinstance(color, int):
                                        # 整数颜色转RGB
                                        r = ((color >> 16) & 0xFF) / 255.0
                                        g = ((color >> 8) & 0xFF) / 255.0
                                        b = (color & 0xFF) / 255.0
                                        color_tuple = (r, g, b)
                                    else:
                                        color_tuple = (0, 0, 0)
                                    
                                    replacements_info.append({
                                        "bbox": bbox,
                                        "origin": origin,
                                        "font": font,
                                        "size": size,
                                        "color": color_tuple,
                                        "text": text,
                                        "old": old_num,
                                        "new": new_num
                                    })
                    
                    # 按位置从后往前处理，避免坐标偏移问题
                    replacements_info.sort(key=lambda x: x["bbox"][1] if x["bbox"] else 0, reverse=True)
                    
                    for info in replacements_info:
                        bbox = info["bbox"]
                        if not bbox:
                            continue
                        
                        rect = pymupdf.Rect(bbox)
                        
                        # 涂黑原文本（用背景色覆盖）
                        page.add_redact_annot(rect, fill=(1, 1, 1))
                        page.apply_redactions()
                        
                        # 在原位置插入新文本，保持原样式
                        new_text = info["text"].replace(info["old"], info["new"])
                        
                        # 尝试用原字体，如果失败就用默认字体
                        try:
                            page.insert_text(
                                (bbox[0], info["origin"][1]),
                                new_text,
                                fontname=info["font"] if info["font"] else "helv",
                                fontsize=info["size"],
                                color=info["color"]
                            )
                        except:
                            # 如果原字体不支持，用默认字体
                            page.insert_text(
                                (bbox[0], info["origin"][1]),
                                new_text,
                                fontname="helv",
                                fontsize=info["size"],
                                color=info["color"]
                            )
                        
                        total_replacements += 1
            
            # 生成新文件名
            original_name = uploaded_file.name
            if original_name.endswith(".pdf"):
                new_name = original_name[:-4] + "_replaced.pdf"
            else:
                new_name = original_name + "_replaced.pdf"
            
            output_buffer = io.BytesIO()
            # 压缩保存：garbage=4 清理垃圾数据，deflate=True 启用压缩
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
    st.markdown("### 4️⃣ 处理结果")
    
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
    Made with ❤️ by 微酱 | v2.0
</div>
""", unsafe_allow_html=True)
