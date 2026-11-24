# Run once after the Ubuntu installation has finished (as Administrator).
$Name = 'gc-experiment'

Stop-VM -Name $Name                                   # VM must be off to change firmware
Set-VMDvdDrive -VMName $Name -Path $null              # eject installation ISO
Set-VMFirmware -VMName $Name -FirstBootDevice (Get-VMHardDiskDrive -VMName $Name)
Start-VM -Name $Name