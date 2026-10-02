# Autorise l'acces LAN au port 8090 (JARVIS Mail) pour le telephone.
# A lancer en clic droit -> "Executer avec PowerShell" (ou terminal Admin).
# Necessite les droits administrateur (modification pare-feu).

New-NetFirewallRule -DisplayName "JARVIS Mail" -Direction Inbound -LocalPort 8090 -Protocol TCP -Action Allow

Write-Host ""
Write-Host "Regle firewall ajoutee. Depuis ton telephone (meme wifi), ouvre:"
$ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Dhcp -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
if (-not $ip) { $ip = "<IP-du-PC>" }
Write-Host "http://${ip}:8090" -ForegroundColor Cyan
