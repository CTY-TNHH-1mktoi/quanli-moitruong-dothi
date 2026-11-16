param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$PdfPath,[switch]$SkipFields)
$ErrorActionPreference='Stop'
$wordApp=$null
$reportDoc=$null
try {
    $wordApp=New-Object -ComObject Word.Application
    $wordApp.Visible=$false
    $wordApp.DisplayAlerts=0
    $reportDoc=$wordApp.Documents.Open($InputDocx,$false,$false,$false)
    if(-not $SkipFields){
        $reportDoc.Fields.Update() | Out-Null
        foreach($contents in $reportDoc.TablesOfContents){$contents.Update()}
        $reportDoc.Repaginate()
        foreach($contents in $reportDoc.TablesOfContents){$contents.UpdatePageNumbers()}
    }
    $reportDoc.Save()
    $pageCount=$reportDoc.ComputeStatistics(2)
    $reportDoc.ExportAsFixedFormat($PdfPath,17,$false,0)
    @{pages=$pageCount;toc_count=$reportDoc.TablesOfContents.Count;tables=$reportDoc.Tables.Count;pdf=$PdfPath}|ConvertTo-Json -Compress
} finally {
    if($null -ne $reportDoc){$reportDoc.Close(0);[System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($reportDoc)|Out-Null}
    if($null -ne $wordApp){$wordApp.Quit();[System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($wordApp)|Out-Null}
}
