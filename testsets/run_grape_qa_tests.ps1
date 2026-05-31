param(
  [ValidateSet("offline", "api", "all")]
  [string]$Mode = "offline",
  [string]$BaseUrl = "http://127.0.0.1:5000",
  [string]$Testset = ".\tests\grape_qa_testset.csv",
  [string]$Report = ".\tests\test_report.json",
  [int]$TimeoutSec = 60,
  [switch]$SkipChat
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$OntologyFile = Join-Path $Root "知识图谱体系.txt"
$TextDir = Join-Path $Root "data\texts"

function Split-ListValue($Value) {
  if ($null -eq $Value) { return @() }
  return @(([string]$Value -split "\|" | ForEach-Object { $_.Trim() } | Where-Object { $_ }))
}

function Import-Testset($Path) {
  $resolved = Resolve-Path $Path
  if ([IO.Path]::GetExtension($resolved).ToLowerInvariant() -eq ".json") {
    return (Get-Content $resolved -Raw -Encoding UTF8 | ConvertFrom-Json)
  }

  $rows = Import-Csv $resolved -Encoding UTF8
  $entityLabels = @(
    "Disease", "Pest", "Alias", "Symptom", "Part", "Rule", "Method",
    "Drug", "Treatment", "Pathogen", "Characteristic", "Condition", "Period", "Vector"
  )
  $relationTypes = @(
    "HAS_ALIAS", "ALIAS_OF", "HAS_SYMPTOM", "SYMPTOM_OF",
    "AFFECTS_PART", "PART_AFFECTED_BY", "HAS_RULE", "HAS_METHOD",
    "HAS_TREATMENT", "USES_DRUG", "HAS_PATHOGEN", "HAS_CHARACTERISTIC",
    "FAVORED_BY", "OCCURS_IN", "AGGRAVATES", "TRANSMITTED_BY"
  )

  $qaTests = @()
  $detailTests = @()
  $seen = @{}

  foreach ($row in $rows) {
    $keywords = @(Split-ListValue $row.expected_keywords)
    $requiredSections = @(Split-ListValue $row.required_sections)
    $relations = @(Split-ListValue $row.expected_relation_types)
    $sourceFile = if ([string]::IsNullOrWhiteSpace($row.source_file)) { $row.expected_entity } else { $row.source_file }
    $entity = if ([string]::IsNullOrWhiteSpace($row.expected_entity)) { $sourceFile } else { $row.expected_entity }
    $minHits = if ([string]::IsNullOrWhiteSpace($row.min_keyword_hits)) { 2 } else { [int]$row.min_keyword_hits }

    $qaTests += [pscustomobject]@{
      id = $row.id
      type = $row.case_type
      question = $row.question
      expected_entity = $entity
      source_file = $sourceFile
      expected_relation_types = $relations
      expected_keywords = $keywords
      min_keyword_hits = $minHits
    }

    if (![string]::IsNullOrWhiteSpace($sourceFile) -and !$seen.ContainsKey($sourceFile)) {
      $seen[$sourceFile] = $true
      $detailTests += [pscustomobject]@{
        id = "KD_$sourceFile"
        name = $entity
        source_file = $sourceFile
        category = $row.category
        required_sections = $requiredSections
        expected_keywords = @($keywords | Select-Object -First 4)
      }
    }
  }

  return [pscustomobject]@{
    meta = [pscustomobject]@{
      name = "葡萄病虫害知识图谱 CSV 测试集"
      version = "2.0.0"
      description = "由 data/texts 中各病虫害章节生成，默认每个实体 2 条。"
    }
    ontology = [pscustomobject]@{
      expected_entity_labels = $entityLabels
      expected_relation_types = $relationTypes
    }
    knowledge_detail_tests = $detailTests
    qa_tests = $qaTests
  }
}

function Normalize-Text([string]$Text) {
  if ($null -eq $Text) { return "" }
  return (($Text -replace "\s+", "").ToLowerInvariant())
}

function Get-KeywordHits([string]$Text, [object[]]$Keywords) {
  $compact = Normalize-Text $Text
  $hits = @()
  foreach ($keyword in $Keywords) {
    if ($compact.Contains((Normalize-Text ([string]$keyword)))) {
      $hits += [string]$keyword
    }
  }
  return $hits
}

function New-TestResult($Id, $Name, [bool]$Passed, $Detail = "", $ElapsedMs = $null) {
  $item = [ordered]@{
    id = $Id
    name = $Name
    passed = $Passed
    detail = $Detail
  }
  if ($null -ne $ElapsedMs) {
    $item.elapsed_ms = $ElapsedMs
  }
  return [pscustomobject]$item
}

function Split-Sections([string]$Content) {
  $sections = @{}
  $matches = [regex]::Matches($Content, "(?ms)^\s*\d+\.\s*(.+?)[：:；;](.*?)(?=^\s*\d+\.\s*|\z)")
  foreach ($match in $matches) {
    $title = $match.Groups[1].Value.Trim()
    $body = $match.Groups[2].Value.Trim()
    $sections[$title] = $body
  }
  return $sections
}

function Invoke-Json($Method, $Url, $Body = $null) {
  $started = Get-Date
  if ($null -eq $Body) {
    $data = Invoke-RestMethod -Method $Method -Uri $Url -TimeoutSec $TimeoutSec
  } else {
    $jsonBody = $Body | ConvertTo-Json -Depth 10
    $data = Invoke-RestMethod -Method $Method -Uri $Url -Body $jsonBody -ContentType "application/json; charset=utf-8" -TimeoutSec $TimeoutSec
  }
  $elapsed = [math]::Round(((Get-Date) - $started).TotalMilliseconds, 2)
  return @($data, $elapsed)
}

function Run-OntologyTests($Data) {
  $results = @()
  if (!(Test-Path $OntologyFile)) {
    return @(New-TestResult "ONT000" "知识图谱体系文件存在" $false "缺少文件: $OntologyFile")
  }

  $content = Get-Content $OntologyFile -Raw -Encoding UTF8
  foreach ($label in $Data.ontology.expected_entity_labels) {
    $results += New-TestResult "ONT_ENTITY_$label" "实体标签 $label 已定义" ($content.Contains($label)) "在知识图谱体系.txt 中查找实体标签"
  }
  foreach ($rel in $Data.ontology.expected_relation_types) {
    $results += New-TestResult "ONT_REL_$rel" "关系类型 $rel 已定义" ($content.Contains($rel)) "在知识图谱体系.txt 中查找关系类型"
  }
  return $results
}

function Run-KnowledgeFileTests($Data) {
  $results = @()
  foreach ($case in $Data.knowledge_detail_tests) {
    $sourceName = if ($case.PSObject.Properties.Name -contains "source_file") { $case.source_file } else { $case.name }
    $filePath = Join-Path $TextDir "$sourceName.txt"
    if (!(Test-Path $filePath)) {
      $results += New-TestResult $case.id "$($case.name) 文本存在" $false "缺少文件: $filePath"
      continue
    }

    $content = Get-Content $filePath -Raw -Encoding UTF8
    $sections = Split-Sections $content
    $missingSections = @()
    foreach ($title in $case.required_sections) {
      if (!$sections.ContainsKey([string]$title)) {
        $missingSections += [string]$title
      }
    }

    $hits = Get-KeywordHits $content $case.expected_keywords
    $missingKeywords = @()
    foreach ($keyword in $case.expected_keywords) {
      if ($hits -notcontains [string]$keyword) {
        $missingKeywords += [string]$keyword
      }
    }

    $passed = ($missingSections.Count -eq 0 -and $missingKeywords.Count -eq 0)
    $detail = [ordered]@{
      missing_sections = $missingSections
      keyword_hits = $hits
      missing_keywords = $missingKeywords
    }
    $results += New-TestResult $case.id "$($case.name) 本地知识文本完整性" $passed $detail
  }
  return $results
}

function Run-OfflineQaSourceTests($Data) {
  $results = @()
  foreach ($case in $Data.qa_tests) {
    if ($null -eq $case.expected_entity -or [string]::IsNullOrWhiteSpace([string]$case.expected_entity)) {
      $results += New-TestResult $case.id "未知问题保护用例仅在 api 模式评测" $true "offline 模式跳过"
      continue
    }

    $sourceName = if ($case.PSObject.Properties.Name -contains "source_file") { $case.source_file } else { $case.expected_entity }
    $filePath = Join-Path $TextDir "$sourceName.txt"
    if (!(Test-Path $filePath)) {
      $results += New-TestResult $case.id "$($case.expected_entity) 来源文本存在" $false "缺少文件: $filePath"
      continue
    }

    $content = Get-Content $filePath -Raw -Encoding UTF8
    $hits = Get-KeywordHits $content $case.expected_keywords
    $passed = ($hits.Count -ge [int]$case.min_keyword_hits)
    $detail = [ordered]@{
      question = $case.question
      expected_entity = $case.expected_entity
      keyword_hits = $hits
      min_keyword_hits = $case.min_keyword_hits
    }
    $results += New-TestResult $case.id "$($case.type) 来源知识覆盖" $passed $detail
  }
  return $results
}

function Run-ApiKnowledgeTests($Data) {
  $results = @()
  try {
    $healthResp = Invoke-Json "GET" "$BaseUrl/api/health"
    $health = $healthResp[0]
    $results += New-TestResult "API_HEALTH" "后端健康检查" ($health.status -eq "ok") $health $healthResp[1]
  } catch {
    return @(New-TestResult "API_HEALTH" "后端健康检查" $false $_.Exception.Message)
  }

  try {
    $listResp = Invoke-Json "GET" "$BaseUrl/api/knowledge/list"
    $list = @($listResp[0])
    $names = @($list | ForEach-Object { $_.name })
    $missing = @()
    foreach ($case in $Data.knowledge_detail_tests) {
      $listName = if ($case.PSObject.Properties.Name -contains "source_file") { $case.source_file } else { $case.name }
      if ($names -notcontains $listName) {
        $missing += $listName
      }
    }
    $results += New-TestResult "API_KNOWLEDGE_LIST" "知识列表包含核心测试实体" ($missing.Count -eq 0) ([ordered]@{ missing = $missing; count = $list.Count }) $listResp[1]
  } catch {
    $results += New-TestResult "API_KNOWLEDGE_LIST" "知识列表包含核心测试实体" $false $_.Exception.Message
  }

  foreach ($case in $Data.knowledge_detail_tests) {
    try {
      $queryName = if ($case.PSObject.Properties.Name -contains "source_file") { $case.source_file } else { $case.name }
      $encoded = [uri]::EscapeDataString($queryName)
      $detailResp = Invoke-Json "GET" "$BaseUrl/api/knowledge/$encoded"
      $body = $detailResp[0]
      $text = $body | ConvertTo-Json -Depth 20 -Compress
      $hits = Get-KeywordHits $text $case.expected_keywords
      $sectionTitles = @($body.sections | ForEach-Object { $_.title })
      $missingSections = @()
      foreach ($title in $case.required_sections) {
        if ($sectionTitles -notcontains $title) {
          $missingSections += $title
        }
      }
      $passed = ($missingSections.Count -eq 0 -and $hits.Count -ge $case.expected_keywords.Count)
      $detail = [ordered]@{ missing_sections = $missingSections; keyword_hits = $hits }
      $results += New-TestResult "API_$($case.id)" "$($case.name) 详情接口" $passed $detail $detailResp[1]
    } catch {
      $results += New-TestResult "API_$($case.id)" "$($case.name) 详情接口" $false $_.Exception.Message
    }
  }
  return $results
}

function Run-ApiChatTests($Data) {
  $results = @()
  foreach ($case in $Data.qa_tests) {
    try {
      $payload = @{ question = $case.question; history = @() }
      $chatResp = Invoke-Json "POST" "$BaseUrl/api/chat" $payload
      $body = $chatResp[0]
      $answer = [string]$body.answer
      $hits = Get-KeywordHits $answer $case.expected_keywords
      $passed = ($hits.Count -ge [int]$case.min_keyword_hits)
      $detail = [ordered]@{
        question = $case.question
        answer = $answer
        sources = $body.sources
        keyword_hits = $hits
        min_keyword_hits = $case.min_keyword_hits
      }
      $results += New-TestResult $case.id "$($case.type) 问答接口" $passed $detail $chatResp[1]
    } catch {
      $results += New-TestResult $case.id "$($case.type) 问答接口" $false $_.Exception.Message
    }
  }
  return $results
}

$testsetPath = Resolve-Path $Testset
$data = Import-Testset $testsetPath
$results = @()

if ($Mode -eq "offline" -or $Mode -eq "all") {
  $results += Run-OntologyTests $data
  $results += Run-KnowledgeFileTests $data
  $results += Run-OfflineQaSourceTests $data
}

if ($Mode -eq "api" -or $Mode -eq "all") {
  $results += Run-ApiKnowledgeTests $data
  if (!$SkipChat) {
    $results += Run-ApiChatTests $data
  }
}

$total = $results.Count
$passed = @($results | Where-Object { $_.passed }).Count
$failed = $total - $passed
$passRate = if ($total -gt 0) { [math]::Round($passed / $total, 4) } else { 0 }

$summary = [ordered]@{
  total = $total
  passed = $passed
  failed = $failed
  pass_rate = $passRate
}

$reportData = [ordered]@{
  summary = $summary
  mode = $Mode
  base_url = $BaseUrl
  generated_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
  results = $results
}

$reportPath = Join-Path $Root $Report
$reportDir = Split-Path $reportPath -Parent
if (!(Test-Path $reportDir)) {
  New-Item -ItemType Directory -Path $reportDir | Out-Null
}
$reportData | ConvertTo-Json -Depth 20 | Set-Content $reportPath -Encoding UTF8

Write-Host ""
Write-Host "=== 葡萄病虫害知识图谱测试结果 ==="
Write-Host ("总数: {0}  通过: {1}  失败: {2}  通过率: {3:P2}" -f $total, $passed, $failed, $passRate)

if ($failed -gt 0) {
  Write-Host ""
  Write-Host "失败项:"
  foreach ($item in ($results | Where-Object { !$_.passed })) {
    Write-Host ("- {0} {1}: {2}" -f $item.id, $item.name, ($item.detail | ConvertTo-Json -Compress -Depth 8))
  }
} else {
  Write-Host "所有测试通过。"
}

Write-Host ""
Write-Host "报告已写入: $reportPath"

if ($failed -gt 0) {
  exit 1
}
