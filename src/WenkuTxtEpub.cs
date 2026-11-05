using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Xml;
using System.Xml.Linq;

namespace WenkuTxtEpub {
  static class Program {
    [STAThread] static int Main(string[] args) {
      try {
        if (args.Length == 3 && args[0] == "--convert") {
          var result = Converter.Local(args[1], args[2]);
          File.WriteAllText(Path.Combine(args[2], "test-result.txt"), result, Encoding.UTF8);
          return 0;
        }
        if (args.Length == 3 && args[0] == "--download") {
          var result = Converter.Download(args[1], args[2], delegate(string s) {});
          File.WriteAllText(Path.Combine(args[2], "test-result.txt"), result, Encoding.UTF8);
          return 0;
        }
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MainForm());
        return 0;
      } catch (Exception ex) {
        if (args.Length == 3) {
          Directory.CreateDirectory(args[2]);
          File.WriteAllText(Path.Combine(args[2], "test-error.txt"), ex.ToString(), Encoding.UTF8);
        } else MessageBox.Show(ex.Message, "无法启动");
        return 1;
      }
    }
  }

  sealed class MainForm : Form {
    TextBox url = new TextBox(), destination = new TextBox(), log = new TextBox();
    Button download = new Button(), local = new Button(), browse = new Button();
    bool busy;
    public MainForm() {
      Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
      Text = "轻小说文库 · TXT 转 EPUB";
      ClientSize = new Size(700, 490); MinimumSize = new Size(716, 529);
      Font = new Font("Microsoft YaHei UI", 10); StartPosition = FormStartPosition.CenterScreen;
      var heading = new Label {Text="小说下载与转换", Font=new Font(Font.FontFamily,18,FontStyle.Bold), AutoSize=true, Location=new Point(24,20)};
      var hint = new Label {Text="粘贴文库书籍链接，自动保存 TXT 和带目录的 EPUB。也可转换本地 TXT。", AutoSize=true, Location=new Point(24,66)};
      url.SetBounds(24,100,650,30); url.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;
      var urlHint = new Label {Text="例如：https://www.wenku8.net/book/xxxxx.htm", AutoSize=true, Location=new Point(24,137), ForeColor=Color.DimGray};
      var outputLabel = new Label {Text="保存位置", AutoSize=true, Location=new Point(24,177)};
      destination.SetBounds(106,173,478,30); destination.ReadOnly=true; destination.Anchor=AnchorStyles.Top|AnchorStyles.Left|AnchorStyles.Right;
      destination.Text=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"电子书");
      browse.Text="选择…"; browse.SetBounds(594,171,80,34); browse.Anchor=AnchorStyles.Top|AnchorStyles.Right;
      browse.Click += delegate {using(var d=new FolderBrowserDialog()){d.Description="选择电子书保存文件夹"; if(Directory.Exists(destination.Text))d.SelectedPath=destination.Text;if(d.ShowDialog()==DialogResult.OK)destination.Text=d.SelectedPath;}};
      download.Text="下载并转 EPUB"; download.SetBounds(24,225,190,42);
      local.Text="选择 TXT 转换"; local.SetBounds(226,225,190,42);
      var open = new Button {Text="打开保存文件夹", Location=new Point(428,225), Size=new Size(190,42)};
      open.Click += delegate {try{Directory.CreateDirectory(destination.Text);System.Diagnostics.Process.Start("explorer.exe", "\""+destination.Text+"\"");}catch(Exception ex){MessageBox.Show(ex.Message);}};
      download.Click += async delegate {
        if(busy)return;
        string input=url.Text.Trim(), dir=destination.Text;
        await RunJob(delegate {return Converter.Download(input,dir,Report);});
      };
      local.Click += async delegate {
        if(busy)return;
        using(var d=new OpenFileDialog()){d.Filter="TXT 文本文件 (*.txt)|*.txt";d.Multiselect=true;
          if(d.ShowDialog()!=DialogResult.OK)return;
          string[] files=d.FileNames;string dir=destination.Text;
          await RunJob(delegate {var results=new List<string>();foreach(string f in files){Report("正在转换："+Path.GetFileName(f));results.Add(Converter.Local(f,dir));}return String.Join("\r\n\r\n",results);});
        }
      };
      log.SetBounds(24,288,650,140);log.Multiline=true;log.ReadOnly=true;log.ScrollBars=ScrollBars.Vertical;log.Anchor=AnchorStyles.Top|AnchorStyles.Bottom|AnchorStyles.Left|AnchorStyles.Right;
      log.Text="准备就绪。\r\nEPUB 请用电子书阅读器打开；记事本请打开 TXT。";
      var footer=new Label {Text="纯文字 EPUB，不含插图。网站拒绝下载时，可在浏览器下载 TXT 后导入。", AutoSize=true, Location=new Point(24,449), ForeColor=Color.DimGray, Anchor=AnchorStyles.Bottom|AnchorStyles.Left};
      Controls.AddRange(new Control[]{heading,hint,url,urlHint,outputLabel,destination,browse,download,local,open,log,footer});
      FormClosing += delegate(object sender,FormClosingEventArgs e){if(busy){e.Cancel=true;MessageBox.Show("任务正在进行，请等待完成后再关闭（网络请求会自动超时）。");}};
    }
    void Report(string message){if(IsDisposed)return;BeginInvoke(new Action(delegate{log.AppendText(message+"\r\n");}));}
    async Task RunJob(Func<string> job){
      busy=true;download.Enabled=local.Enabled=browse.Enabled=false;url.Enabled=false;log.Clear();
      try {log.AppendText("开始处理…\r\n");string result=await Task.Run(job);log.AppendText("完成！\r\n"+result+"\r\n");}
      catch(Exception ex){log.AppendText("未完成："+ex.Message+"\r\n");}
      finally{busy=false;download.Enabled=local.Enabled=browse.Enabled=true;url.Enabled=true;}
    }
  }

  static class Converter {
    const long Limit=80L*1024*1024;
    static readonly UTF8Encoding Utf8=new UTF8Encoding(false,true);
    sealed class Chapter {public string Title;public List<string> Lines=new List<string>();}
    public static string Download(string link,string dir,Action<string> report){
      Uri uri;
      if(!Uri.TryCreate(link,UriKind.Absolute,out uri)||!(uri.Scheme=="https"||uri.Scheme=="http")||
        !Regex.IsMatch(uri.Host,@"^(www\.)?wenku8\.(net|com|cc)$",RegexOptions.IgnoreCase))
        throw new Exception("请输入轻小说文库的书籍链接，例如 https://www.wenku8.net/book/xxxxx.htm");
      Match m=Regex.Match(uri.AbsolutePath,@"^/book/(\d+)\.htm$",RegexOptions.IgnoreCase);
      if(!m.Success)m=Regex.Match(uri.AbsolutePath,@"^/novel/\d+/(\d+)(?:/|$)",RegexOptions.IgnoreCase);
      if(!m.Success && (uri.AbsolutePath=="/modules/article/articleinfo.php"||uri.AbsolutePath=="/modules/article/packshow.php"))
        m=Regex.Match(uri.Query,@"(?:\?|&)id=(\d+)(?:&|$)");
      int id;if(!m.Success||!Int32.TryParse(m.Groups[1].Value,out id)||id<=0)throw new Exception("未找到书籍编号，请使用 /book/数字.htm 格式的书籍链接。");
      ServicePointManager.SecurityProtocol=SecurityProtocolType.Tls12;
      byte[] bytes=null;Exception last=null;
      for(int node=1;node<=2;node++){
        report("正在从下载载点 "+node+" 获取书籍 "+id+"…");
        try{
          var request=(HttpWebRequest)WebRequest.Create("https://dl.wenku8.com/down.php?type=utf8&node="+node+"&id="+id);
          request.Timeout=25000;request.ReadWriteTimeout=25000;request.UserAgent="WenkuTxtEpub/1.0";request.AutomaticDecompression=DecompressionMethods.GZip|DecompressionMethods.Deflate;
          using(var response=(HttpWebResponse)request.GetResponse()){
            if(response.ContentType.IndexOf("text/html",StringComparison.OrdinalIgnoreCase)>=0)throw new Exception("网站返回了网页，而不是小说 TXT。");
            using(var input=response.GetResponseStream())using(var output=new MemoryStream()){
              byte[] buffer=new byte[32768];int count;while((count=input.Read(buffer,0,buffer.Length))>0){if(output.Length+count>Limit)throw new Exception("文件超过 80 MB 限制。");output.Write(buffer,0,count);}bytes=output.ToArray();
            }
          }
          string decoded=Decode(bytes);ValidateText(decoded);
          if(decoded.Length<300 || !Regex.IsMatch(decoded,@"(?m)^第[一二三四五六七八九十百零〇0-9]+[卷章]"))throw new Exception("下载结果不像完整小说 TXT，请在浏览器确认该书可下载。");
          break;
        }catch(Exception ex){last=ex;bytes=null;report("载点 "+node+" 未能完成："+ex.Message);}
      }
      if(bytes==null)throw new Exception("网站下载失败。请在已登录的浏览器打开书籍页面，下载 TXT，再点击“选择 TXT 转换”。\r\n原因："+(last==null?"未知":last.Message));
      string text=Decode(bytes), title=FindTitle(text,"文库小说_"+id);
      Directory.CreateDirectory(dir);string stem=UniqueStem(dir,SafeName(title));
      string txt=stem+".txt";File.WriteAllText(txt,text,new UTF8Encoding(true));
      report("TXT 下载完成，正在生成目录和 EPUB…");
      int chapters=Build(text,title,stem+".epub","https://www.wenku8.net/book/"+id+".htm");
      return "章节条目："+chapters+"\r\nEPUB："+stem+".epub\r\nTXT："+txt;
    }
    public static string Local(string source,string dir){
      if(new FileInfo(source).Length>Limit)throw new Exception("TXT 超过 80 MB 限制。");
      string text=Decode(File.ReadAllBytes(source));ValidateText(text);
      string title=FindTitle(text,Path.GetFileNameWithoutExtension(source));
      Directory.CreateDirectory(dir);string stem=UniqueStem(dir,SafeName(title));
      int count=Build(text,title,stem+".epub",null);
      return "章节条目："+count+"\r\nEPUB："+stem+".epub";
    }
    static string Decode(byte[] data){
      if(data.Length>=4 && ((data[0]==0xff&&data[1]==0xfe&&data[2]==0&&data[3]==0)||(data[0]==0&&data[1]==0&&data[2]==0xfe&&data[3]==0xff)))
        return new UTF32Encoding(data[0]==0,true,true).GetString(data,4,data.Length-4);
      if(data.Length>=2&&data[0]==0xff&&data[1]==0xfe)return new UnicodeEncoding(false,true,true).GetString(data,2,data.Length-2);
      if(data.Length>=2&&data[0]==0xfe&&data[1]==0xff)return new UnicodeEncoding(true,true,true).GetString(data,2,data.Length-2);
      if(data.Length>=3&&data[0]==0xef&&data[1]==0xbb&&data[2]==0xbf)return Utf8.GetString(data,3,data.Length-3);
      try{return Utf8.GetString(data);}catch(DecoderFallbackException){return Encoding.GetEncoding(54936,EncoderFallback.ExceptionFallback,DecoderFallback.ExceptionFallback).GetString(data);}
    }
    static void ValidateText(string text){
      if(String.IsNullOrWhiteSpace(text))throw new Exception("TXT 内容为空。");
      string beginning=text.TrimStart();
      if(Regex.IsMatch(beginning,@"^(<!doctype\s+html|<html|<\?xml)",RegexOptions.IgnoreCase))throw new Exception("该文件是网页或 XML，不是小说 TXT。");
      if(text.IndexOf('\0')>=0)throw new Exception("文本编码无法识别，请先另存为 UTF-8 TXT。");
    }
    static string FindTitle(string text,string fallback){
      var match=Regex.Match(text.Substring(0,Math.Min(1500,text.Length)),@"(?m)^\s*<([^<>\r\n]{1,180})>\s*$");
      return match.Success?match.Groups[1].Value.Trim():fallback;
    }
    static string SafeName(string title){foreach(char c in Path.GetInvalidFileNameChars())title=title.Replace(c,'_');title=title.Trim().TrimEnd('.');if(title.Length>70)title=title.Substring(0,70);if(title.Length==0)title="电子书";if(Regex.IsMatch(title,@"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)",RegexOptions.IgnoreCase))title="_"+title;return title;}
    static string UniqueStem(string dir,string name){string stem=Path.Combine(dir,name);int i=2;while(File.Exists(stem+".epub")||File.Exists(stem+".txt")){stem=Path.Combine(dir,name+" ("+i+++")");}return stem;}
    static bool IsHeading(string line){return line.Length<150&&(Regex.IsMatch(line,@"^第[一二三四五六七八九十百千万两零〇0-9]+[卷章回节集部](?:\s|[：:、.．]|$)")||Regex.IsMatch(line,@"^(序章|序幕|终章|終章|尾声|尾聲|后记|後記|番外)(?:\s|[：:、]|$)"));}
    static List<Chapter> Split(string text){
      var result=new List<Chapter>();Chapter current=new Chapter{Title="书籍信息"};int size=0;
      foreach(string raw in text.Replace("\r\n","\n").Replace('\r','\n').Split('\n')){
        string line=raw.Trim();if(line.Length==0)continue;
        if(IsHeading(line)){
          if(current.Lines.Count>0 || current.Title!="书籍信息")result.Add(current);
          current=new Chapter{Title=line};size=0;
        }else{
          if(size>65000){result.Add(current);current=new Chapter{Title=current.Title+"（续）"};size=0;}
          current.Lines.Add(line);size+=line.Length;
        }
      }
      if(current.Lines.Count>0 || current.Title!="书籍信息")result.Add(current);
      return result;
    }
    static string Clean(string value){return new string(value.Where(c=>XmlConvert.IsXmlChar(c)||Char.IsSurrogate(c)).ToArray());}
    static readonly XNamespace Html="http://www.w3.org/1999/xhtml", Opf="http://www.idpf.org/2007/opf", Dc="http://purl.org/dc/elements/1.1/", Ncx="http://www.daisy.org/z3986/2005/ncx/", Epub="http://www.idpf.org/2007/ops";
    static XDocument Page(string title,object content){return new XDocument(new XDeclaration("1.0","utf-8",null),new XElement(Html+"html",new XAttribute(XNamespace.Xml+"lang","zh-CN"),new XElement(Html+"head",new XElement(Html+"meta",new XAttribute("charset","utf-8")),new XElement(Html+"title",Clean(title)),new XElement(Html+"link",new XAttribute("rel","stylesheet"),new XAttribute("href","style.css"),new XAttribute("type","text/css"))),new XElement(Html+"body",content)));}
    static void Write(ZipArchive zip,string name,string content,bool plain=false){var entry=zip.CreateEntry(name,plain?CompressionLevel.NoCompression:CompressionLevel.Optimal);using(var writer=new StreamWriter(entry.Open(),new UTF8Encoding(false)))writer.Write(content);}
    static void WriteXml(ZipArchive zip,string name,XDocument doc){using(var stream=zip.CreateEntry(name,CompressionLevel.Optimal).Open())using(var writer=XmlWriter.Create(stream,new XmlWriterSettings{Encoding=new UTF8Encoding(false),Indent=false}))doc.Save(writer);}
    static int Build(string text,string title,string path,string source){
      var chapters=Split(text);if(chapters.Count==0)throw new Exception("没有可转换的正文。");
      string tmp=path+"."+Guid.NewGuid().ToString("N")+".tmp",uid="urn:uuid:"+Guid.NewGuid();
      try{
        using(var zip=new ZipArchive(File.Create(tmp),ZipArchiveMode.Create)){
          Write(zip,"mimetype","application/epub+zip",true);
          Write(zip,"META-INF/container.xml","<?xml version=\"1.0\" encoding=\"utf-8\"?><container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\"><rootfiles><rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/></rootfiles></container>");
          Write(zip,"OEBPS/style.css","body{margin:5%;line-height:1.8}h1{font-size:1.4em}p{text-indent:2em;margin:.5em 0}nav ol{padding-left:1.5em}");
          var manifest=new XElement(Opf+"manifest",Item("nav","nav.xhtml","application/xhtml+xml","nav"),Item("ncx","toc.ncx","application/x-dtbncx+xml",null),Item("css","style.css","text/css",null));
          var spine=new XElement(Opf+"spine",new XAttribute("toc","ncx"));var list=new XElement(Html+"ol");var navMap=new XElement(Ncx+"navMap");
          for(int i=0;i<chapters.Count;i++){
            string id="c"+(i+1).ToString("D4"),file=id+".xhtml",heading=Clean(chapters[i].Title);
            WriteXml(zip,"OEBPS/"+file,Page(heading,new object[]{new XElement(Html+"h1",heading),chapters[i].Lines.Select(line=>new XElement(Html+"p",Clean(line)))}));
            manifest.Add(Item(id,file,"application/xhtml+xml",null));spine.Add(new XElement(Opf+"itemref",new XAttribute("idref",id)));
            list.Add(new XElement(Html+"li",new XElement(Html+"a",new XAttribute("href",file),heading)));
            navMap.Add(new XElement(Ncx+"navPoint",new XAttribute("id",id),new XAttribute("playOrder",i+1),new XElement(Ncx+"navLabel",new XElement(Ncx+"text",heading)),new XElement(Ncx+"content",new XAttribute("src",file))));
          }
          WriteXml(zip,"OEBPS/nav.xhtml",Page("目录",new XElement(Html+"nav",new XAttribute(Epub+"type","toc"),new XElement(Html+"h1",Clean(title)),list)));
          WriteXml(zip,"OEBPS/toc.ncx",new XDocument(new XElement(Ncx+"ncx",new XAttribute("version","2005-1"),new XElement(Ncx+"head",new XElement(Ncx+"meta",new XAttribute("name","dtb:uid"),new XAttribute("content",uid)),new XElement(Ncx+"meta",new XAttribute("name","dtb:depth"),new XAttribute("content","1")),new XElement(Ncx+"meta",new XAttribute("name","dtb:totalPageCount"),new XAttribute("content","0")),new XElement(Ncx+"meta",new XAttribute("name","dtb:maxPageNumber"),new XAttribute("content","0"))),new XElement(Ncx+"docTitle",new XElement(Ncx+"text",Clean(title))),navMap)));
          var metadata=new XElement(Opf+"metadata",new XElement(Dc+"identifier",new XAttribute("id","bookid"),uid),new XElement(Dc+"title",Clean(title)),new XElement(Dc+"language","zh-CN"),new XElement(Opf+"meta",new XAttribute("property","dcterms:modified"),DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")));
          if(source!=null)metadata.Add(new XElement(Dc+"source",source));
          WriteXml(zip,"OEBPS/content.opf",new XDocument(new XElement(Opf+"package",new XAttribute("version","3.0"),new XAttribute("unique-identifier","bookid"),metadata,manifest,spine)));
        }
        NormalizeZip(tmp);Verify(tmp,chapters.Count);File.Move(tmp,path);
      }finally{if(File.Exists(tmp))File.Delete(tmp);}
      return chapters.Count;
    }
    static XElement Item(string id,string href,string media,string properties){var item=new XElement(Opf+"item",new XAttribute("id",id),new XAttribute("href",href),new XAttribute("media-type",media));if(properties!=null)item.Add(new XAttribute("properties",properties));return item;}
    sealed class ZipRecord {public byte[] Name;public uint Crc,Size,Packed,Offset;public ushort Method;}
    // Framework ZipArchive uses Deflate even at NoCompression. EPUB requires
    // the first mimetype entry to use ZIP method 0, with no extra field.
    static void NormalizeZip(string path){
      string fixedPath=path+".fixed";
      try{
        using(var input=ZipFile.OpenRead(path))using(var file=File.Create(fixedPath))using(var writer=new BinaryWriter(file)){
          var records=new List<ZipRecord>();
          foreach(var entry in input.Entries){
            byte[] data;using(var stream=entry.Open())using(var memory=new MemoryStream()){stream.CopyTo(memory);data=memory.ToArray();}
            uint crc=0xffffffff;foreach(byte b in data){crc^=b;for(int bit=0;bit<8;bit++)crc=(crc>>1)^((crc&1)!=0?0xedb88320u:0u);}crc^=0xffffffff;
            byte[] packed=data;ushort method=0;
            if(entry.FullName!="mimetype"){
              method=8;using(var memory=new MemoryStream()){using(var deflate=new DeflateStream(memory,CompressionLevel.Optimal,true))deflate.Write(data,0,data.Length);packed=memory.ToArray();}
            }
            var r=new ZipRecord{Name=Encoding.UTF8.GetBytes(entry.FullName),Crc=crc,Size=(uint)data.Length,Packed=(uint)packed.Length,Offset=(uint)file.Position,Method=method};
            writer.Write(0x04034b50u);writer.Write((ushort)20);writer.Write((ushort)0x800);writer.Write(method);writer.Write((ushort)0);writer.Write((ushort)33);writer.Write(r.Crc);writer.Write(r.Packed);writer.Write(r.Size);writer.Write((ushort)r.Name.Length);writer.Write((ushort)0);writer.Write(r.Name);writer.Write(packed);records.Add(r);
          }
          uint start=(uint)file.Position;
          foreach(var r in records){writer.Write(0x02014b50u);writer.Write((ushort)20);writer.Write((ushort)20);writer.Write((ushort)0x800);writer.Write(r.Method);writer.Write((ushort)0);writer.Write((ushort)33);writer.Write(r.Crc);writer.Write(r.Packed);writer.Write(r.Size);writer.Write((ushort)r.Name.Length);writer.Write((ushort)0);writer.Write((ushort)0);writer.Write((ushort)0);writer.Write((ushort)0);writer.Write(0u);writer.Write(r.Offset);writer.Write(r.Name);}
          uint length=(uint)file.Position-start;writer.Write(0x06054b50u);writer.Write((ushort)0);writer.Write((ushort)0);writer.Write((ushort)records.Count);writer.Write((ushort)records.Count);writer.Write(length);writer.Write(start);writer.Write((ushort)0);
        }
        File.Delete(path);File.Move(fixedPath,path);
      }finally{if(File.Exists(fixedPath))File.Delete(fixedPath);}
    }
    static void Verify(string file,int count){
      using(var zip=ZipFile.OpenRead(file)){
        foreach(var entry in zip.Entries)if(Regex.IsMatch(entry.FullName,@"\.(xhtml|xml|opf|ncx)$"))using(var input=entry.Open())XDocument.Load(input);
        using(var input=zip.GetEntry("OEBPS/content.opf").Open()){
          var doc=XDocument.Load(input);if(doc.Descendants(Opf+"itemref").Count()!=count)throw new Exception("EPUB 目录校验失败。");
          foreach(var item in doc.Descendants(Opf+"item"))if(zip.GetEntry("OEBPS/"+(string)item.Attribute("href"))==null)throw new Exception("EPUB 资源缺失。");
        }
      }
    }
  }
}
