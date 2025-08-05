' Create a shell object
Set objShell = CreateObject("WScript.Shell")

' Run the command to activate the virtual environment and execute the Python script
Dim strArgs
strArgs = "cmd /c .\.venv\Scripts\activate && py .\main.py -aaa && .\.venv\Scripts\deactivate"
objShell.Run strArgs, 0, False

' Cleanup
Set objShell = Nothing