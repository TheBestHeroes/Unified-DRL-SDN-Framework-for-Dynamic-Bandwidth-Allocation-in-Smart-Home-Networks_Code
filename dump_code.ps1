#  ÕœÌœ «·„Ã·œ «·Õ«·Ì «·–Ì ÌÕ ÊÌ ⁄·Ï «·›Ê·œ—«  («·»—ÊÃﬂ « )
$rootPath = Get-Location
$outputFile = Join-Path $rootPath "project_dump.txt"

# ≈„ œ«œ«  «·„·›«  «· Ì  —Ìœ ﬁ—«¡ Â« ›ﬁÿ (Ì„ﬂ‰ﬂ  ⁄œÌ·Â«)
$allowedExtensions = @(".cs", ".json", ".xml", ".config", ".html", ".css", ".js", ".sql", ".txt", ".md", ".csproj")

# «·„Ã·œ«  «· Ì ÌÃ»  Ã«Â·Â« („À· „Ã·œ«  «·»‰«¡ Ê«·„ﬂ »« )
$excludeFolders = @("bin", "obj", ".git", ".vs", "node_modules", "packages")

# «·»œ¡ »ﬂ «»…  —ÊÌ”… «· ﬁ—Ì—
Set-Content -Path $outputFile -Value "==================================================" -Encoding UTF8
Add-Content -Path $outputFile -Value "           PROJECT CODE DUMP REPORT" -Encoding UTF8
Add-Content -Path $outputFile -Value "==================================================" -Encoding UTF8
Add-Content -Path $outputFile -Value "Generated On: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8
Add-Content -Path $outputFile -Value "Root Directory: $rootPath" -Encoding UTF8
Add-Content -Path $outputFile -Value "==================================================`n`n" -Encoding UTF8

# ﬁ—«¡… ﬂ«›… «·„·›«  œ«Œ· «·›Ê·œ—«  Ê«·„Ã·œ«  «·›—⁄Ì…
Get-ChildItem -Path $rootPath -Recurse -File | Where-Object {
    # «” »⁄«œ «·„Ã·œ«  «·Œ«’… »‹ bin Ê obj Ê git
    $relativePath = $_.FullName.Replace($rootPath.Path, "")
    $skip = $false
    foreach ($folder in $excludeFolders) {
        if ($relativePath -like "*\$folder\*" -or $relativePath -like "*\$folder") {
            $skip = $true
            break
        }
    }
    
    # ›· —… «·„·›«  »Õ”» «·≈„ œ«œ«  «·„Õœœ…
    (-not $skip) -and ($allowedExtensions -contains $_.Extension.ToLower())
} | ForEach-Object {
    $filePath = $_.FullName
    $relativePath = $filePath.Replace($rootPath.Path, "")

    # ﬂ «»… «·›Ê«’· Ê„”«— «·„·› ··‹ AI
    Add-Content -Path $outputFile -Value "==================================================" -Encoding UTF8
    Add-Content -Path $outputFile -Value "FILE PATH: $relativePath" -Encoding UTF8
    Add-Content -Path $outputFile -Value "FULL PATH: $filePath" -Encoding UTF8
    Add-Content -Path $outputFile -Value "==================================================" -Encoding UTF8
    Add-Content -Path $outputFile -Value "[START OF FILE CONTENT]`n" -Encoding UTF8

    try {
        # ﬁ—«¡… „Õ ÊÏ «·„·› Ê≈÷«› Â
        $content = Get-Content -Path $filePath -Raw -ErrorAction Stop
        Add-Content -Path $outputFile -Value $content -Encoding UTF8
    }
    catch {
        Add-Content -Path $outputFile -Value "[ERROR: Could not read file content. $($_.Exception.Message)]" -Encoding UTF8
    }

    Add-Content -Path $outputFile -Value "`n[END OF FILE CONTENT]`n`n" -Encoding UTF8
}

Write-Host "Done! All code exported successfully to: $outputFile" -ForegroundColor Green