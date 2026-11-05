支持分卷选择、合并或逐卷导出 EPUB，可同时保存选卷 TXT。在线书籍自动读取文库封面，嵌入 EPUB 并另存封面图片；支持手动选择封面。保留二次元软件图标，窗口内也显示图标。

- **Windows：下载 `windows-x64.exe`，直接双击运行。** 32 位环境选 `windows-x86.exe`，无需解压或安装 Python。
- macOS：按 Intel / Apple Silicon 下载对应 ZIP，解压后打开应用。
- Linux：按 x64 / ARM64 下载对应 tar.gz，解压后运行程序。

六种原生构建均通过源码测试、打包后转换和图形界面冒烟测试。每个平台的实际系统版本和检查项见附带 `test-report.json`，校验值见 `SHA256SUMS.txt`。未覆盖所有旧系统或阅读器；程序未签名或公证。

在线模式仍需先读取完整 TXT，再仅导出所选卷。封面为网站书籍封面，不含正文插图。EPUB 在阅读器中可显示封面，文件管理器缩略图依赖系统支持；TXT 本身不能嵌入封面。

交互设计参考：https://github.com/ShqWW/lightnovel-download
