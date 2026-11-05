"""TXT conversion and Wenku8 downloads, independent of the GUI."""
from pathlib import Path
import codecs
import io
import os
import re
import tempfile
import uuid
import zipfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

LIMIT = 80 * 1024 * 1024
XHTML = 'http://www.w3.org/1999/xhtml'
OPF = 'http://www.idpf.org/2007/opf'
DC = 'http://purl.org/dc/elements/1.1/'
NCX = 'http://www.daisy.org/z3986/2005/ncx/'
EPUB = 'http://www.idpf.org/2007/ops'
HEADING = re.compile(r'^(第[一二三四五六七八九十百千万两零〇0-9]+[卷章回节集部]|序章|序幕|终章|終章|尾声|尾聲|后记|後記|番外)(?:\s|[：:、.．]|$)')

def decode(data):
    if len(data) > LIMIT:
        raise ValueError('输入文件超过 80 MiB。')
    if data.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        text = data.decode('utf-32')
    elif data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = data.decode('utf-16')
    else:
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = data.decode('gb18030')
    if not text.strip():
        raise ValueError('TXT 内容为空。')
    if '\x00' in text or re.match(r'\s*(<!doctype\s+html|<html|<\?xml)', text, re.I):
        raise ValueError('输入不是有效的小说 TXT。')
    return text

def book_id(link):
    uri = urllib.parse.urlsplit(link.strip())
    if uri.scheme not in ('http', 'https') or not re.fullmatch(r'(www\.)?wenku8\.(net|com|cc)', uri.hostname or '', re.I):
        raise ValueError('请输入轻小说文库书籍链接。')
    match = re.match(r'^/book/(\d+)\.htm$|^/novel/\d+/(\d+)(?:/|$)', uri.path)
    value = next((x for x in match.groups() if x), '') if match else ''
    if not value and uri.path in ('/modules/article/articleinfo.php', '/modules/article/packshow.php'):
        value = urllib.parse.parse_qs(uri.query).get('id', [''])[0]
    if not re.fullmatch(r'\d+', value) or not 0 < int(value) <= 2147483647:
        raise ValueError('链接中缺少有效的书籍编号。')
    return str(int(value))

def title_of(text, fallback):
    match = re.search(r'^\s*<([^<>\r\n]{1,180})>\s*$', text[:1500], re.M)
    return match[1].strip() if match else fallback

def safe_name(title):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip().rstrip('.')[:70] or '电子书'
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I):
        name = '_' + name
    return name

def unique_stem(folder, title):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = safe_name(title)
    stem, suffix = folder / name, 2
    while any(Path(str(stem) + extension).exists() for extension in ('.epub', '.txt', '.cover.png')):
        stem = folder / f'{name} ({suffix})'
        suffix += 1
    return stem

def split_chapters(text):
    chapters, heading, lines, count = [], '书籍信息', [], 0
    explicit = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if len(line) < 150 and HEADING.match(line):
            if lines or explicit:
                chapters.append((heading, lines))
            heading, lines, count, explicit = line, [], 0, True
        else:
            if count > 65000:
                chapters.append((heading, lines))
                heading, lines, count = heading + '（续）', [], 0
            lines.append(line)
            count += len(line)
    if lines or explicit:
        chapters.append((heading, lines))
    return chapters

def element(ns, tag, text=None, **attrs):
    node = ET.Element(f'{{{ns}}}{tag}', attrs)
    if text is not None:
        node.text = ''.join(c for c in text if c in '\t\n\r' or 0x20 <= ord(c) <= 0xd7ff or 0xe000 <= ord(c) <= 0xfffd or 0x10000 <= ord(c) <= 0x10ffff)
    return node

def xml(node):
    return ET.tostring(node, encoding='utf-8', xml_declaration=True)

def page(title):
    root = element(XHTML, 'html', **{'lang': 'zh-CN'})
    head = ET.SubElement(root, f'{{{XHTML}}}head')
    head.append(element(XHTML, 'title', title))
    head.append(element(XHTML, 'meta', charset='utf-8'))
    head.append(element(XHTML, 'link', rel='stylesheet', href='style.css', type='text/css'))
    body = ET.SubElement(root, f'{{{XHTML}}}body')
    return root, body

def build(text, title, path, source=None, cover=None):
    chapters = split_chapters(text)
    if not chapters:
        raise ValueError('没有可转换的正文。')
    uid = 'urn:uuid:' + str(uuid.uuid4())
    package = element(OPF, 'package', version='3.0', **{'unique-identifier': 'bookid'})
    metadata = ET.SubElement(package, f'{{{OPF}}}metadata')
    metadata.extend([element(DC, 'identifier', uid, id='bookid'), element(DC, 'title', title), element(DC, 'language', 'zh-CN'), element(OPF, 'meta', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), property='dcterms:modified')])
    if source:
        metadata.append(element(DC, 'source', source))
    manifest = ET.SubElement(package, f'{{{OPF}}}manifest')
    spine = ET.SubElement(package, f'{{{OPF}}}spine', toc='ncx')
    for name, media, extra in [('nav.xhtml', 'application/xhtml+xml', {'properties': 'nav'}), ('toc.ncx', 'application/x-dtbncx+xml', {}), ('style.css', 'text/css', {})]:
        manifest.append(element(OPF, 'item', id={'toc.ncx': 'ncx'}.get(name, name.split('.')[0]), href=name, **{'media-type': media, **extra}))
    nav, navbody = page('目录')
    navsection = element(XHTML, 'nav', **{f'{{{EPUB}}}type': 'toc'})
    navbody.append(navsection)
    navsection.append(element(XHTML, 'h1', title))
    toc = ET.SubElement(navsection, f'{{{XHTML}}}ol')
    ncx = element(NCX, 'ncx', version='2005-1')
    head = ET.SubElement(ncx, f'{{{NCX}}}head')
    for name, val in [('uid', uid), ('depth', '1'), ('totalPageCount', '0'), ('maxPageNumber', '0')]:
        head.append(element(NCX, 'meta', name='dtb:' + name, content=val))
    ET.SubElement(ncx, f'{{{NCX}}}docTitle').append(element(NCX, 'text', title))
    navmap = ET.SubElement(ncx, f'{{{NCX}}}navMap')
    path = Path(path)
    fd, temp = tempfile.mkstemp(suffix='.tmp', dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
            archive.writestr('META-INF/container.xml', '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
            archive.writestr('OEBPS/style.css', 'body{margin:5%;line-height:1.8}h1{font-size:1.4em}p{text-indent:2em;margin:.5em 0}')
            if cover:
                archive.writestr('OEBPS/cover.png', cover)
                document, body = page('封面')
                body.append(element(XHTML, 'img', src='cover.png', alt=title, style='max-width:100%;height:auto'))
                archive.writestr('OEBPS/cover.xhtml', xml(document))
                metadata.append(element(OPF, 'meta', name='cover', content='cover-image'))
                manifest.append(element(OPF, 'item', id='cover-image', href='cover.png', **{'media-type': 'image/png', 'properties': 'cover-image'}))
                manifest.append(element(OPF, 'item', id='cover-page', href='cover.xhtml', **{'media-type': 'application/xhtml+xml'}))
                spine.append(element(OPF, 'itemref', idref='cover-page'))
                guide = ET.SubElement(package, f'{{{OPF}}}guide')
                guide.append(element(OPF, 'reference', type='cover', title='封面', href='cover.xhtml'))
            for index, (heading, lines) in enumerate(chapters, 1):
                name = f'c{index:04d}'
                document, body = page(heading)
                body.append(element(XHTML, 'h1', heading))
                body.extend(element(XHTML, 'p', line) for line in lines)
                archive.writestr(f'OEBPS/{name}.xhtml', xml(document))
                manifest.append(element(OPF, 'item', id=name, href=name + '.xhtml', **{'media-type': 'application/xhtml+xml'}))
                spine.append(element(OPF, 'itemref', idref=name))
                ET.SubElement(toc, f'{{{XHTML}}}li').append(element(XHTML, 'a', heading, href=name + '.xhtml'))
                point = element(NCX, 'navPoint', id=name, playOrder=str(index))
                ET.SubElement(point, f'{{{NCX}}}navLabel').append(element(NCX, 'text', heading))
                point.append(element(NCX, 'content', src=name + '.xhtml'))
                navmap.append(point)
            archive.writestr('OEBPS/nav.xhtml', xml(nav))
            archive.writestr('OEBPS/toc.ncx', xml(ncx))
            archive.writestr('OEBPS/content.opf', xml(package))
        verify(temp)
        # Exclusive publication prevents overwriting another concurrent conversion.
        with open(temp, 'rb') as src, open(path, 'xb') as dst:
            import shutil
            shutil.copyfileobj(src, dst)
    finally:
        Path(temp).unlink(missing_ok=True)
    return len(chapters)

def verify(path):
    with zipfile.ZipFile(path) as archive:
        first = archive.infolist()[0]
        if first.filename != 'mimetype' or first.compress_type != zipfile.ZIP_STORED or first.extra or archive.read('mimetype') != b'application/epub+zip':
            raise ValueError('EPUB mimetype 校验失败。')
        if archive.testzip():
            raise ValueError('EPUB ZIP 校验失败。')
        for name in archive.namelist():
            if name.endswith(('.xml', '.xhtml', '.opf', '.ncx')):
                ET.fromstring(archive.read(name))
        package = ET.fromstring(archive.read('OEBPS/content.opf'))
        items = {item.attrib['id']: item for item in package.findall(f'{{{OPF}}}manifest/{{{OPF}}}item')}
        for item in items.values():
            if 'OEBPS/' + item.attrib['href'] not in archive.namelist():
                raise ValueError('EPUB 资源缺失。')
        for item in package.findall(f'{{{OPF}}}spine/{{{OPF}}}itemref'):
            if item.attrib['idref'] not in items:
                raise ValueError('EPUB 阅读顺序无效。')

def convert_file(source, folder):
    source = Path(source)
    if source.stat().st_size > LIMIT:
        raise ValueError('输入文件超过 80 MiB。')
    text = decode(source.read_bytes())
    title = title_of(text, source.stem)
    stem = unique_stem(folder, title)
    path = stem.with_name(stem.name + '.epub')
    build(text, title, path)
    return path

def fetch_txt(identifier, report=lambda message: None):
    errors = []
    for node in (1, 2):
        report(f'正在请求下载载点 {node}…')
        try:
            request = urllib.request.Request(f'https://dl.wenku8.com/down.php?type=utf8&node={node}&id={identifier}', headers={'User-Agent': 'WenkuTxtEpub/1.1'})
            with urllib.request.urlopen(request, timeout=25) as response:
                if 'text/html' in response.headers.get('Content-Type', '').lower():
                    raise ValueError('网站返回了网页。')
                data = response.read(LIMIT + 1)
            text = decode(data)
            if len(text) < 300 or not re.search(r'^第[一二三四五六七八九十百零〇0-9]+[卷章]', text, re.M):
                raise ValueError('下载结果未通过小说文本检查。')
            return text
        except Exception as error:
            errors.append(str(error))
    raise ValueError('下载失败，请在浏览器下载 TXT 后导入。\n' + '\n'.join(errors))

def download(link, folder, report=lambda message: None):
    identifier = book_id(link)
    text = fetch_txt(identifier, report)
    title = title_of(text, '文库小说_' + identifier)
    stem = unique_stem(folder, title)
    with open(str(stem) + '.txt', 'x', encoding='utf-8-sig') as file:
        file.write(text)
    path = Path(str(stem) + '.epub')
    build(text, title, path, f'https://www.wenku8.net/book/{identifier}.htm')
    return path

def volumes(text):
    """Group repeated volume-prefixed chapter headings in their source order."""
    result, key, lines = [], None, []
    for raw in text.splitlines():
        line = raw.strip()
        match = re.match(r'^(第[一二三四五六七八九十百千万两零〇0-9]+卷)(?:\s|[：:、.．]|$)', line) if len(line) < 150 else None
        if match and match[1] != key:
            if key is not None:
                result.append((key, '\n'.join(lines)))
            key, lines = match[1], []
        if key is not None:
            lines.append(raw)
    if key is not None:
        result.append((key, '\n'.join(lines)))
    return result or [('全文（未识别到分卷）', text)]

def export_volumes(text, title, indexes, folder, merge=True, source=None, cover=None, save_txt=False):
    available = volumes(text)
    indexes = sorted(set(indexes))
    if not indexes or any(i < 0 or i >= len(available) for i in indexes):
        raise ValueError('请至少选择一卷。')
    selected = [available[i] for i in indexes]
    if merge:
        label = title if len(selected) == len(available) else title + '（选卷合并）'
        groups = [(label, '\n\n'.join(content for _, content in selected))]
    else:
        groups = [(title + ' ' + name, content) for name, content in selected]
    paths = []
    for label, content in groups:
        stem = unique_stem(folder, label)
        path = Path(str(stem) + '.epub')
        build(content, label, path, source, cover)
        paths.append(path)
        if save_txt:
            txt_path = Path(str(stem) + '.txt')
            with txt_path.open('x', encoding='utf-8-sig') as stream:
                stream.write('<' + label + '>\n\n' + content)
            paths.append(txt_path)
        if cover:
            image_path = Path(str(stem) + '.cover.png')
            with image_path.open('xb') as stream:
                stream.write(cover)
            paths.append(image_path)
    return paths


def normalize_cover(data):
    """Decode a bounded image and return a portable PNG without source metadata."""
    from PIL import Image
    if len(data) > 10 * 1024 * 1024:
        raise ValueError('封面超过 10 MiB。')
    with Image.open(io.BytesIO(data)) as picture:
        if picture.width * picture.height > 20_000_000:
            raise ValueError('封面尺寸过大。')
        picture.load()
        picture = picture.convert('RGB')
        picture.thumbnail((1600, 2400))
        output = io.BytesIO()
        picture.save(output, format='PNG')
        return output.getvalue()


def fetch_cover(identifier, report=lambda message: None):
    """The site's public book cover; all selected volumes share this cover."""
    if not re.fullmatch(r'[1-9][0-9]{0,9}', str(identifier)):
        raise ValueError('无效书籍编号。')
    url = f'https://img.wenku8.com/image/{int(identifier) // 1000}/{identifier}/{identifier}s.jpg'
    report('正在读取网站封面…')
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'WenkuTxtEpub/1.1', 'Referer': 'https://www.wenku8.net/'})
        with urllib.request.urlopen(request, timeout=15) as response:
            data = response.read(10 * 1024 * 1024 + 1)
        return normalize_cover(data)
    except Exception as error:
        report('封面未获取，仍可导出正文：' + str(error))
        return None
