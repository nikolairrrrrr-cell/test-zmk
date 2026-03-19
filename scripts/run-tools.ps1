param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("ves", "pdf-zmk", "pdf-zmk2")]
    [string]$Command,

    [Parameter(Mandatory = $false)]
    [string]$InputPath
)

switch ($Command) {
    "ves" {
        python -m app.cli ves run --positions "ves/test_positions.txt" --online --force-refresh
        break
    }
    "pdf-zmk" {
        if (-not $InputPath) {
            Write-Error "InputPath (input directory) is required for pdf-zmk"
            exit 2
        }
        python -m app.cli pdf-zmk full --input-dir $InputPath
        break
    }
    "pdf-zmk2" {
        if (-not $InputPath) {
            Write-Error "InputPath is required for pdf-zmk2"
            exit 2
        }
        python -m app.cli pdf-zmk2 run --input $InputPath
        break
    }
}

