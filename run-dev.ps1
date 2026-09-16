Set-Location $PSScriptRoot
py -3 -m pip install -e ".[gui]"
py -3 -m app --dev
