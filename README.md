# 轻小说文库 TXT 转 EPUB

<img src="assets/icon-preview.png" width="112" alt="软件图标" />

面向轻小说文库（Wenku8）的非官方桌面工具。支持在线读取 TXT、本地 TXT 转换、分卷选择与 EPUB 封面。

**[下载发布版](https://github.com/EmoSakura/wenku8-txt-to-epub/releases/latest)** · [测试记录](https://github.com/EmoSakura/wenku8-txt-to-epub/actions)

## 使用

1. Windows 下载对应架构的 `.exe`，直接运行；macOS 解压后打开 `.app`；Linux 解压后运行 `WenkuTxtEpub`。
2. 输入书籍链接，点击“读取在线卷目”；或选择本地 TXT。
3. 选择需要的卷。勾选“合并所选卷”生成一个 EPUB，取消勾选则每卷单独保存。
4. 点击“导出所选卷为 EPUB”。可同时保存所选内容的 UTF-8 TXT。

链接示例：`https://www.wenku8.net/book/xxxxx.htm`。将 `xxxxx` 替换为实际书籍编号。

默认输出到用户下载目录下的 `WenkuTxtEpub` 文件夹；同名文件自动追加编号。一次选择多个本地 TXT 时，每个文件直接转换为一个完整 EPUB。

## 封面与格式

- 在线书籍自动读取网站书籍封面，嵌入 EPUB 并保存同名 `.cover.png`；也可手动选择封面。各卷使用同一书籍封面，不代表各卷原版封面。不下载正文插图。
- EPUB 包含标准封面标记、导航目录和 NCX 目录。阅读器可识别封面；资源管理器是否显示封面缩略图取决于系统支持。TXT 不含图片，不能自行显示书籍封面图标。
- 支持 UTF-8、带 BOM 的 UTF-16/UTF-32、GBK/GB18030。无 BOM 时优先 UTF-8，失败后尝试 GB18030，识别可能存在歧义。
- 分卷按“第X卷”标题识别，章节按“第X章”“序章”等规则识别。无法识别分卷时按全文处理，请在导出前核对卷目。

## 平台与测试

| 下载文件 | 原生测试环境 |
| --- | --- |
| `windows-x64.exe` / `windows-x86.exe` | Windows Server 2022；本机 Windows 测试见发布说明 |
| `macos-x64.zip` | macOS 15 Intel |
| `macos-arm64.zip` | macOS 15 Apple Silicon |
| `linux-x64.tar.gz` / `linux-arm64.tar.gz` | Ubuntu 22.04，Xvfb 图形会话 |

各平台分别编译，并测试打包程序的 TXT 转换、图形窗口、图标加载、分卷导出、封面与 EPUB 结构。Release 附测试报告和 SHA-256 校验值。测试环境以报告为准，不表示覆盖所有系统版本或阅读器。程序未进行商业代码签名或 macOS 公证。

## 限制

在线模式先读取整本 TXT，再导出所选卷；不使用浏览器登录状态。网站拒绝下载时，可在浏览器下载 TXT 后导入。封面失败不影响正文导出。

单个 TXT 不超过 80 MiB。转换忽略空行、去除行首尾空白并重新排版。EPUB 应用阅读器打开，不能用记事本查看。请遵守来源网站条款和作品版权要求。

## 开发

Python 3.12 与 Tkinter。安装 `requirements.txt` 后运行 `python app/main.py`。命令行转换：

```sh
python app/main.py --convert "example.txt" --output "books"
python -m unittest discover -s tests -v
```

原生打包：安装 `requirements-build.txt`，执行 `python scripts/package.py --platform windows-x64`（平台名称按实际环境填写）。Linux 图形测试需要 Tk 和 Xvfb。旧版 C# 源码保留在 `src/`，`scripts/build.ps1` 仅用于旧版。

交互设计参考 [ShqWW/lightnovel-download](https://github.com/ShqWW/lightnovel-download) 的分卷选择、封面展示与进度提示。

反馈请提交 [Issue](https://github.com/EmoSakura/wenku8-txt-to-epub/issues)，附版本、步骤及错误信息。
