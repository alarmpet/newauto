param(
    [Parameter(Mandatory = $true)]
    [string]$ScriptName
)

$needle = $ScriptName.Trim()
if (-not $needle) {
    exit 0
}

Get-CimInstance Win32_Process |
    Where-Object {
        $commandLine = [string]$_.CommandLine
        $commandLine -like "*$needle*"
    } |
    Select-Object -First 1 -ExpandProperty ProcessId
