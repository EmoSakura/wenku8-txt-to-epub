$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$assets=Join-Path (Get-Location) 'outputs\wenku8-txt-to-epub\assets'
$source=[Drawing.Image]::FromFile((Join-Path $assets 'app-icon.png'))
$frames=@()
try {
 foreach($size in @(16,24,32,48,64,128,256)) {
  $bitmap=[Drawing.Bitmap]::new($size,$size,[Drawing.Imaging.PixelFormat]::Format32bppArgb)
  $graphics=[Drawing.Graphics]::FromImage($bitmap)
  $graphics.CompositingMode=[Drawing.Drawing2D.CompositingMode]::SourceCopy
  $graphics.InterpolationMode=[Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
  $graphics.PixelOffsetMode=[Drawing.Drawing2D.PixelOffsetMode]::HighQuality
  $graphics.DrawImage($source,0,0,$size,$size)
  $memory=[IO.MemoryStream]::new()
  $bitmap.Save($memory,[Drawing.Imaging.ImageFormat]::Png)
  $frames+=@{size=$size;data=$memory.ToArray()}
  if($size -eq 256){$bitmap.Save((Join-Path $assets 'icon-preview.png'),[Drawing.Imaging.ImageFormat]::Png)}
  $memory.Dispose();$graphics.Dispose();$bitmap.Dispose()
 }
 $writer=[IO.BinaryWriter]::new([IO.File]::Create((Join-Path $assets 'app.ico')))
 try {
  $writer.Write([uint16]0);$writer.Write([uint16]1);$writer.Write([uint16]$frames.Count)
  $offset=6+16*$frames.Count
  foreach($frame in $frames){$dim=if($frame.size -eq 256){0}else{$frame.size};$writer.Write([byte]$dim);$writer.Write([byte]$dim);$writer.Write([byte]0);$writer.Write([byte]0);$writer.Write([uint16]1);$writer.Write([uint16]32);$writer.Write([uint32]$frame.data.Length);$writer.Write([uint32]$offset);$offset+=$frame.data.Length}
  foreach($frame in $frames){$writer.Write([byte[]]$frame.data)}
 } finally {$writer.Dispose()}
} finally {$source.Dispose()}
