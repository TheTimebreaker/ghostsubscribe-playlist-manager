' Create a shell object
Set objShell = CreateObject("WScript.Shell")

' Run the command to activate the virtual environment and execute the Python script
Dim strArgs
strArgs = "cmd /c .\.venv-windows\Scripts\activate && py .\main.py && .\.venv-windows\Scripts\deactivate"
objShell.Run strArgs, 0, False

' Cleanup
Set objShell = Nothing