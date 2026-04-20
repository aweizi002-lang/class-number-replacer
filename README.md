# 班号批量替换工具

一个简单的网页工具，用于批量替换PDF文件中的班号文本。

## 功能特点

- ✅ 批量上传PDF文件
- ✅ 支持多个班号同时替换
- ✅ 自动验证班号格式
- ✅ 一键下载处理结果

## 部署到 Streamlit Cloud（免费）

### 第一步：注册 GitHub 账号
如果还没有GitHub账号，去 https://github.com 注册一个（免费）

### 第二步：创建新仓库
1. 登录 GitHub
2. 点击右上角 "+" → "New repository"
3. 仓库名填写：`class-number-replacer`
4. 选择 "Public"（公开）
5. 点击 "Create repository"

### 第三步：上传文件
1. 在新建的仓库页面，点击 "uploading an existing file"
2. 把以下三个文件拖进去上传：
   - `app.py`
   - `requirements.txt`
   - `README.md`（可选）
3. 点击 "Commit changes"

### 第四步：部署到 Streamlit Cloud
1. 打开 https://share.streamlit.io/
2. 用 GitHub 账号登录
3. 点击 "New app"
4. 填写信息：
   - Repository：选择你刚创建的 `class-number-replacer`
   - Branch：main
   - Main file path：app.py
5. 点击 "Deploy!"

### 第五步：分享链接
部署成功后，你会得到一个链接，类似：
```
https://class-number-replacer-xxxxx.streamlit.app
```

把这个链接分享给同事，他们就能直接使用了！

---

## 本地运行（可选）

如果你想在本地测试：

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
streamlit run app.py
```

---

## 使用说明

1. 上传PDF文件（支持多选）
2. 输入旧班号和新班号
3. 点击"开始替换"
4. 下载处理后的文件

班号格式：字母 + 6位数字，如 `B250675`

---

Made with ❤️ by 微酱
