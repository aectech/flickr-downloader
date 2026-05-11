# Flickr Downloader

现代化重写的Flickr下载器，使用Python 3.10+和PySide6构建的跨平台桌面应用。

## 项目背景

原项目是 WeilJimmer 的 Flickr_Downloader（C# WinForms），2023年2月停更，BSD-3协议。本项目使用现代技术栈完整复刻所有功能并修复已知bug。

## 主要特性

### 八种下载类型
- 相簿下载 (Album)
- 单张照片下载 (Single Photo)
- 用户全部照片 (User's All Photos)
- 用户收藏 (User's Favorites)
- 群组照片 (Group Pool)
- 用户最爱照片 (另一个类型)
- 人工挑选相簿照片 (Pick from Album)
- 人工挑选用户照片 (Pick from User)

### 搜索功能
- 关键词搜索 (flickr.photos.search)
- 用户ID搜索 (flickr.people.getPhotos)
- 群组ID搜索 (flickr.groups.pools.getPhotos)
- 隐私过滤和安全搜索选项
- 灵活的分页设置

### 17种文件命名格式
```
0:  数字序号 (001, 002, ...)
1:  原标题 (Photo Title)
2:  原ID (Photo ID)
3:  标题-ID (Title - ID)
4:  ID-标题 (ID - Title)
5:  相簿名-标题-ID (Album - Title - ID)
6:  相簿名-ID (Album - ID)
7:  相簿名-标题 (Album - Title)
8:  拍摄日期-标题-ID (DateTaken - Title - ID)
9:  拍摄日期-标题 (DateTaken - Title)
10: 拍摄日期-ID (DateTaken - ID)
11: 标题-ID-拍摄日期 (Title - ID - DateTaken)
12: 标题-拍摄日期-ID (Title - DateTaken - ID)
13: 标题-拍摄日期 (Title - DateTaken)
14: ID-拍摄日期-标题 (ID - DateTaken - Title)
15: ID-拍摄日期 (ID - DateTaken)
16: 拍摄日期 (DateTaken)
```

### 下载选项
- 照片尺寸选择 (13级: Auto ~ Small)
- 自动创建子文件夹
- 照片预览
- 跳过已存在文件
- 视频下载支持
- 多线程下载 (1-10线程可配置)
- 自定义时间格式
- 断点续传
- 暂停/继续下载
- EXIF方向自动纠正

### 其他功能
- OAuth 1.0a认证 (完整流程)
- 剪贴板监控 (自动检测Flickr URL)
- 相簿/照片选择窗口 (带缩略图)
- 配置系统 (自动保存)
- 版本检查和自动更新
- **多语言支持** (简体中文、繁体中文、English、日語)
- 彩色日志显示

## 技术栈

- **语言**: Python 3.10+
- **GUI框架**: PySide6 (Qt6) - 跨平台、现代UI
- **HTTP**: httpx - 异步支持、超时、连接池
- **图片处理**: Pillow - EXIF处理、图片操作

## 安装

### 从源码运行

```bash
# 克隆项目
git clone <repository-url>
cd flickr_downloader

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

### 使用可执行文件

下载对应平台的预编译版本，解压后直接运行。

## 构建打包

### 使用PyInstaller

```bash
# 安装PyInstaller
pip install pyinstaller

# 打包
pyinstaller --name="FlickrDownloader" \
             --windowed \
             --onefile \
             --add-data="resources:resources" \
             main.py
```

### 使用build.py脚本

```bash
python build.py
```

## 项目结构

```
flickr_downloader/
├── main.py              # 程序入口
├── requirements.txt      # 依赖列表
├── README.md            # 本文件
├── CHANGELOG.md         # 更新日志
├── build.py             # 打包脚本
│
├── core/                # 核心模块
│   ├── config.py        # 配置管理
│   ├── downloader.py    # 下载管理器
│   ├── flickr_api.py    # Flickr API封装
│   ├── i18n.py         # 国际化支持
│   ├── naming.py        # 文件命名策略
│   └── url_resolver.py  # URL解析
│
├── ui/                  # UI模块
│   ├── main_window.py   # 主窗口
│   ├── album_picker.py  # 相册选择对话框
│   ├── photo_picker.py  # 照片选择对话框
│   └── auth_dialog.py   # OAuth认证对话框
│
├── lang/                # 语言文件
│   ├── zh_CN.json       # 简体中文
│   ├── zh_TW.json       # 繁体中文
│   ├── en.json          # English
│   └── ja.json          # 日語
│
├── utils/               # 工具模块
│   └── helpers.py       # 辅助函数
│
└── resources/           # 资源文件
    └── icon.png         # 应用图标
```

## 修复的Bug

本项目在原项目基础上修复了以下问题：

### 严重Bug
1. ✅ **SSL证书验证被全局禁用** - 已移除不安全的代码
2. ✅ **跨线程UI操作不安全** - 使用PySide6信号槽替代
3. ✅ **数组越界风险** - 使用动态数据结构
4. ✅ **递归下载重试无深度限制** - 改为迭代方式
5. ✅ **GC.Collect()定时强制调用** - 已移除

### 中等Bug
6. ✅ **WebClient已过时** - 使用httpx替代
7. ✅ **硬编码4线程上限** - 支持1-10线程
8. ✅ **配置文件保存时无原子性** - 使用临时文件+原子重命名
9. ✅ **richTextBox 50000字符清空策略** - 优化处理
10. ✅ **User-Agent过时** - 更新为现代版本
11. ✅ **OAuth回调硬编码端口** - 支持配置和自动重试
12. ✅ **视频下载URL构造** - 完善降级逻辑

### 轻微Bug
13. ✅ **繁体中文硬编码** - 所有文字使用简体中文
14. ✅ **大量重复代码** - 使用策略模式和函数封装
15. ✅ **fast_split用正则** - 优化为简单字符串操作
16. ✅ **Request URL拼接方式** - 使用urllib.parse
17. ✅ **文件名过滤不完善** - 完善非法字符过滤

## 使用说明

### 首次使用

1. 运行程序
2. 点击菜单"帮助" -> "登录Flickr"进行OAuth认证
3. 选择下载类型和输入URL
4. 配置保存路径和下载选项
5. 点击"开始下载"

### 下载类型说明

- **相簿下载**: 输入相簿URL或ID
- **单张照片**: 输入照片URL或ID
- **用户全部照片**: 输入用户URL或ID
- **用户收藏**: 输入用户URL或ID
- **群组照片**: 输入群组URL或ID
- **人工挑选**: 先列出所有项目再选择

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+S | 保存配置 |
| Ctrl+B | 浏览保存路径 |
| Ctrl+Enter | 开始下载 |
| Esc | 停止下载 |

## 多语言支持

### 支持的语言
- 🌐 **自动检测** (Auto Detect) - 根据系统语言自动选择
- 🇨🇳 **简体中文** (zh_CN) - 简体中文界面
- 🇹🇼 **繁體中文** (zh_TW) - 繁体中文界面
- 🇺🇸 **English** (en) - 英文界面
- 🇯🇵 **日本語** (ja) - 日语界面

### 使用方法

1. **自动检测**: 首次运行时，程序会根据系统语言自动选择对应界面
2. **手动切换**: 在主窗口工具栏的语言下拉框中选择所需语言
3. **偏好保存**: 手动选择语言后会自动保存，下次启动优先使用用户选择
4. **即时生效**: 切换语言后无需重启，所有界面文字立即刷新

### 界面预览

```
工具栏: [保存路径: ____________] [浏览...] [线程数: 4] [语言: 简体中文▼] [开始下载] [停止]
```

## API Keys

本项目保留了原项目内置的API Keys供使用：

- Default API Key: `021e1fd66f561b265eac365661879785`
- Default API Secret: `48685f9b9271b284`
- V4 API Key: `6f92fee8b4a726215b827c0af43afc70`
- V4 API Secret: `4c4fa981ad30e375`

如需使用自己的API Keys，请在配置中修改。

## 注意事项

1. 请勿滥用API访问，遵守Flickr的使用条款
2. 部分功能需要Flickr账号登录后才能使用
3. 视频下载可能受到Flickr政策限制
4. 建议定期保存配置和下载进度

## 许可证

BSD-3-Clause License

## 致谢

- 原项目作者 WeilJimmer
- 所有贡献者和测试者

## 更新日志

### v2.0.1 (2026-05-12)
- **新增多语言支持**: 简体中文、繁体中文、English、日語
- 语言自动检测: 启动时自动根据系统语言适配
- 语言选择器: 主窗口工具栏提供语言下拉框
- 手动选择: 用户可随时手动切换语言
- 即时生效: 切换语言无需重启，所有UI文字立即刷新

### v2.0.0 (2026-05-11)
- 全新Python + PySide6重写
- 修复原项目所有已知bug
- 现代化UI设计
- 跨平台支持 (Windows/macOS/Linux)
- 所有文字使用简体中文
