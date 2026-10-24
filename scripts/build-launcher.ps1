# 重新编译一键启动程序（启动活动报名系统.exe）
# 仅依赖 Windows 自带的 .NET Framework 4.8 编译器，不需要联网。

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$source = Join-Path $root 'launcher\Program.cs'
$output = Join-Path $root '启动活动报名系统.exe'
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'

if (-not (Test-Path -LiteralPath $csc)) {
    throw "找不到 csc.exe：$csc（需要 .NET Framework 4.8）"
}
if (-not (Test-Path -LiteralPath $source)) {
    throw "找不到源码：$source"
}

& $csc /nologo /codepage:65001 /target:exe "/out:$output" $source
if ($LASTEXITCODE -ne 0) {
    throw "编译失败，退出码 $LASTEXITCODE"
}

Write-Host "已生成：$output"
