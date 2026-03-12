$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start backend minimized
Start-Process "cmd" -ArgumentList "/k cd `"$root\backend`" && python3 -m uvicorn main:app --reload" `
    -WindowStyle Minimized

# Start frontend minimized
Start-Process "cmd" -ArgumentList "/k cd `"$root\frontend`" && npm run dev" `
    -WindowStyle Minimized

# Poll until frontend is ready on port 5173 or 5174
$url = $null
$timeout = 120  # seconds
$elapsed = 0

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++

    foreach ($port in @(5173, 5174)) {
        try {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $tcp.Connect("localhost", $port)
            $tcp.Close()
            $url = "http://localhost:$port"
            break
        } catch {}
    }

    if ($url) { break }
}

if ($url) {
    Start-Process $url
} else {
    [System.Windows.Forms.MessageBox]::Show(
        "Frontend did not start within 2 minutes. Check the terminal window for errors.",
        "GMDS Launch Failed"
    )
}
