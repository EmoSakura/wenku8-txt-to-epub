import codecs
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core

SAMPLE = '<测试小说>\n第一卷 起点\n第一章 初遇\n中文，繁體，こんにちは & < >。\n第二章 空章节\n第三章 结尾\n结束。'

class Tests(unittest.TestCase):
    def test_encodings(self):
        for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'utf-16-be', 'utf-32', 'gbk', 'gb18030'):
            data = SAMPLE.encode(encoding)
            if encoding == 'utf-16-be':
                data = codecs.BOM_UTF16_BE + data
            self.assertEqual(core.decode(data), SAMPLE, encoding)

    def test_invalid(self):
        for data in (b'', b'  ', b'<html>blocked</html>', b'<!DOCTYPE HTML>error', b'a\x00b'):
            with self.assertRaises(ValueError):
                core.decode(data)

    def test_urls(self):
        for link in ('https://www.wenku8.net/book/123.htm', 'https://wenku8.cc/novel/0/123/index.htm', 'https://www.wenku8.com/modules/article/articleinfo.php?id=123'):
            self.assertEqual(core.book_id(link), '123')
        for link in ('https://wenku8.net.evil.example/book/123.htm', 'file:///book/123.htm', 'https://wenku8.net/book/xxxxx.htm', 'https://wenku8.net/book/0.htm'):
            with self.assertRaises(ValueError):
                core.book_id(link)

    def test_epub_content_and_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.txt'
            source.write_text(SAMPLE, encoding='utf-8')
            first = core.convert_file(source, directory)
            before = first.read_bytes()
            second = core.convert_file(source, directory)
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_bytes(), before)
            core.verify(first)
            with zipfile.ZipFile(first) as archive:
                lines = []
                for name in sorted(archive.namelist()):
                    if name.startswith('OEBPS/c') and name.endswith('.xhtml'):
                        body = ET.fromstring(archive.read(name)).find(f'{{{core.XHTML}}}body')
                        lines.extend(n.text or '' for n in body if n.text != '书籍信息')
                self.assertEqual(lines, SAMPLE.splitlines())
                self.assertEqual(archive.infolist()[0].compress_type, zipfile.ZIP_STORED)

    def test_size_guard(self):
        with patch.object(core, 'LIMIT', 3):
            with self.assertRaises(ValueError):
                core.decode(b'abcd')

    def test_volume_selection_and_merge(self):
        text = '<书名>\n第一卷 序\n甲文\n第一卷 第二章\n乙文\n第二卷 序\n丙文\n第三卷 尾声\n丁文'
        self.assertEqual([v[0] for v in core.volumes(text)], ['第一卷', '第二卷', '第三卷'])
        with tempfile.TemporaryDirectory() as directory:
            merged = core.export_volumes(text, '书名', [2, 0], directory, True)
            self.assertEqual(len(merged), 1)
            with zipfile.ZipFile(merged[0]) as z:
                content = ''.join(z.read(n).decode() for n in z.namelist() if n.endswith('.xhtml'))
                self.assertIn('甲文', content)
                self.assertIn('丁文', content)
                self.assertNotIn('丙文', content)
            separate = core.export_volumes(text, '书名', [0, 2], directory, False)
            self.assertEqual(len(separate), 2)
            for path in separate:
                core.verify(path)
            with self.assertRaises(ValueError):
                core.export_volumes(text, '书名', [], directory)

    def test_filename(self):
        self.assertEqual(core.safe_name('CON'), '_CON')
        self.assertEqual(core.safe_name('a/b:c'), 'a_b_c')

    def test_cover_and_selected_txt(self):
        from PIL import Image
        image = io.BytesIO()
        Image.new('RGB', (30, 50), '#445588').save(image, format='JPEG')
        cover = core.normalize_cover(image.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            text = '第一卷 开始\n甲文\n第二卷 继续\n乙文'
            paths = core.export_volumes(text, '封面测试', [1], directory, cover=cover, save_txt=True)
            self.assertEqual(len(paths), 3)
            self.assertNotIn('甲文', paths[1].read_text(encoding='utf-8-sig'))
            self.assertIn('乙文', paths[1].read_text(encoding='utf-8-sig'))
            self.assertEqual(paths[2].read_bytes(), cover)
            with zipfile.ZipFile(paths[0]) as archive:
                self.assertEqual(archive.read('OEBPS/cover.png'), cover)
                package = ET.fromstring(archive.read('OEBPS/content.opf'))
                items = package.findall(f'{{{core.OPF}}}manifest/{{{core.OPF}}}item')
                self.assertEqual(len([i for i in items if i.get('properties') == 'cover-image']), 1)
                self.assertEqual(package.find(f'{{{core.OPF}}}spine')[0].get('idref'), 'cover-page')
        with self.assertRaises(Exception):
            core.normalize_cover(b'<html>blocked</html>')

    def test_cover_failure_is_optional(self):
        messages = []
        with patch('urllib.request.urlopen', side_effect=OSError('unavailable')):
            self.assertIsNone(core.fetch_cover('123', messages.append))
        self.assertIn('仍可导出正文', messages[-1])

    def test_download_retry_and_rejection(self):
        class Response(io.BytesIO):
            headers = {'Content-Type': 'application/octet-stream'}
        data = (SAMPLE + '\n正文' * 200).encode('utf-8')
        with patch('urllib.request.urlopen', side_effect=[OSError('unavailable'), Response(data)]) as request:
            self.assertIn('测试小说', core.fetch_txt('123'))
            self.assertEqual(request.call_count, 2)
        with patch('urllib.request.urlopen', side_effect=lambda *a, **k: Response(b'<html>blocked</html>')):
            with self.assertRaises(ValueError):
                core.fetch_txt('123')

if __name__ == '__main__':
    unittest.main()
