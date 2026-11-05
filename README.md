# 轻小说文库 TXT 转 EPUB

<img src="https://raw.githubusercontent.com/EmoSakura/wenku8-txt-to-epub/main/assets/icon-preview.png" width="128" alt="软件图标" />

面向轻小说文库（Wenku8）的非官方 Windows 工具，支持通过书籍链接下载 TXT 并转换为 EPUB，也支持本地 TXT 批量转换。

**[下载 Windows 版 1.0.1](https://github.com/EmoSakura/wenku8-txt-to-epub/raw/refs/heads/main/downloads/WenkuTxtEpub-1.0.1-win.zip)**

## 使用

运行环境：Windows 10/11，需 .NET Framework 4.5 或更高版本。解压后运行 `WenkuTxtEpub.exe`。

- **链接下载**：粘贴文库书籍链接，选择保存位置，点击“下载并转 EPUB”。成功后保存 TXT 和 EPUB。
- **本地转换**：点击“选择 TXT 转换”，选择一个或多个 TXT 文件，生成 EPUB。

链接格式示例：`https://www.wenku8.net/book/xxxxx.htm`，其中 `xxxxx` 应替换为实际书籍编号。

默认保存到程序目录下的“电子书”文件夹；同名输出自动追加编号。EPUB 请使用支持该格式的阅读器打开。

## 格式支持

- 输入：UTF-8、带 BOM 的 UTF-16/UTF-32、GBK/GB18030 文本。无 BOM 时优先按 UTF-8 解码，失败后尝试 GB18030，编码识别可能存在歧义。
- 输出：纯文字 EPUB 3，包含导航目录和 NCX 目录；不包含封面或插图。
- 目录：按“第X卷”“第X章”“序章”等标题规则识别，保留空章节标题；过长章节按字符数分段。

## 限制

- 单个输入文件不超过 80 MiB。转换会忽略空行、去除行首尾空白并重新排版，不保留 TXT 原始版式。
- 网站下载依赖文库 TXT 下载入口，不使用浏览器登录状态。若下载被拒绝，请在浏览器下载 TXT 后使用本地转换。
- 本地编码转换、章节保留、正文顺序和基本文件结构已验证；联网下载、图形界面及阅读器兼容性尚未完成全面测试。

## 编译

使用 C# / Windows Forms，无第三方 NuGet 依赖。在仓库根目录执行：

```powershell
powershell -File .\scripts\build.ps1
```

输出文件：`dist/WenkuTxtEpub.exe`。版本变更见 [CHANGELOG](https://github.com/EmoSakura/wenku8-txt-to-epub/blob/main/CHANGELOG.md)。

## 反馈

提交 [Issue](https://github.com/EmoSakura/wenku8-txt-to-epub/issues) 时，请附上软件版本、操作步骤和错误信息。转换问题可附最小测试文本，请勿包含账号凭据或私人信息。
