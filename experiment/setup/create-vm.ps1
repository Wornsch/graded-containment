$Name = 'gc-experiment'
$Path = 'C:\VMs'
$Iso  = "C:\Users\Chrisi\Downloads\ubuntu-26.04.1-live-server-amd64.iso"

New-VM -Name $Name -Generation 2 -MemoryStartupBytes 8GB -Path $Path `
  -NewVHDPath "$Path\$Name\$Name.vhdx" -NewVHDSizeBytes 250GB -SwitchName 'Default Switch'
Set-VMMemory    -VMName $Name -DynamicMemoryEnabled $false
Set-VMProcessor -VMName $Name -Count 8
Set-VMFirmware  -VMName $Name -SecureBootTemplate MicrosoftUEFICertificateAuthority
Add-VMDvdDrive  -VMName $Name -Path $Iso
Set-VMFirmware  -VMName $Name -FirstBootDevice (Get-VMDvdDrive -VMName $Name)
Set-VM -Name $Name -AutomaticCheckpointsEnabled $false -CheckpointType Standard
Start-VM $Name
vmconnect localhost $Name