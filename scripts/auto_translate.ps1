<#
    .Synopsis
    Google Language Translator API

    .DESCRIPTION
    This cmdlet allows you to pass in string content and translate
    it into another supported languages.

    See this link for supported language codes: 
    https://cloud.google.com/translate/docs/languages

    .EXAMPLE
    This demonstrates using english as source lang and swahili
    as target lang: 

    Get-GoogleTranslation.ps1 -SourceLang en `
        -TargetLang sw `
        -Content "The bubble gum cigars"
#>

function Get-GoogleTranslation
{
  Param(
    [parameter(Mandatory)]
    [string]$To,

    [parameter(Mandatory)]
    [string]$Content
  )

  $SourceLang = 'en'
  $TargetLang = $To
  $contentStr = $Content.TrimStart('"').TrimEnd('"')
  $uri = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=$SourceLang&tl=$TargetLang&dt=t&q=$contentStr"
  $Translator = Invoke-WebRequest -Uri $uri `
    -SessionVariable Session `
    -UserAgent ([Microsoft.PowerShell.Commands.PSUserAgent]::Chrome) `
    -Method Get `
    -ContentType 'application/json'

  $result = ($Translator.Content.TrimStart('[').TrimEnd(']') -split ',' | select-object -First 1).TrimStart('"').TrimEnd('"')
  $result = $result.Replace("\\n", "\n")
  $result = $result.Replace("\u003e", ">")

  return $result
}

function Convert-File
{
  Param(
    [parameter(Mandatory)]
    [string[]]$source,

    [parameter(Mandatory)]
    [string[]]$target,

    [parameter(Mandatory)]
    [string]$language
  )

  $targetIndex = 0
  $matching = $True
  for ($i = 0; $i -lt $source.Length; $i++)
  {
    $isString = $source[$i] -match '(\s*)?\"(.*)?\": \"(.*)?"'
    if ($isString)
    {
      $whiteSpace = $matches[1]
      $sourceKey = $matches[2]
      $content = $matches[3]

      # Now analyze the target file
      $isString = $target[$targetIndex] -match '(\s*)?\"(.*)?\": \"(.*)?"'
      if ($isString)
      {
        $targetKey = $matches[2]
        Write-Host "Comparing $($sourceKey):$i to $($targetKey):$targetIndex"
        if ($sourceKey -eq $targetKey)
        {
          # TODO - Determine if source has changed.
          if (($source[$i] -match '.*,$') -and !($target[$targetIndex] -match '.*,$'))
          {
            "$($target[$targetIndex]),"
          }
          else
          {
            $target[$targetIndex]
          }
          $matching = $True
          $targetIndex++
          continue
        }
      }

      # Target does not have this line. Print out a translation.
      Write-Host "Translating $sourceKey"
      $translation = Get-GoogleTranslation -To $language -Content $content
      $newLine = $whiteSpace + '"' + $sourceKey + '": "' + $translation + '"'
      if ($source[$i] -match '.*,')
      {
        $newLine += ','
      }
      $newLine
      continue
    }

    $source[$i]

    $matching = ($source[$i] -eq $target[$targetIndex])
    if ($matching)
    {
      $targetIndex++
    }
  }
}

$sourceDir = "$PSScriptRoot\..\custom_components\bambu_lab\translations"

$english = Get-Content -Encoding UTF8 -Path "$sourceDir\en.json"

$languageFiles = Get-ChildItem "$sourceDir\*.json"

foreach ($file in $languageFiles)
{
  $language = $file.BaseName
  if ($language -eq 'en')
  {
    continue
  }
  if ($language -eq 'no-NB')
  {
    $language = 'no'
  }
  if ($language -eq 'cz')
  {
    $language = 'cs'
  }

  Write-Host "`nConverting to $language.`n"

  $langFile = Get-Content -Encoding UTF8 -Path $file

  $newContent = Convert-File $english $langFile $language
  $newContent = ($newContent -join "`n") + "`n"
  
  # Use Set-Content with UTF8 encoding without BOM
  [System.IO.File]::WriteAllText($file, $newContent, [System.Text.UTF8Encoding]::new($false))

  # Convert CRLFs to LFs only.
  # Note:
  #  * (...) around Get-Content ensures that $file is read *in full*
  #    up front, so that it is possible to write back the transformed content
  #    to the same file.
  #  * + "`n" ensures that the file has a *trailing LF*, which Unix platforms
  #     expect.
  #((Get-Content -Encoding UTF8 $file) -join "`n") + "`n" | Set-Content -Encoding UF8 -NoNewline $file
}
